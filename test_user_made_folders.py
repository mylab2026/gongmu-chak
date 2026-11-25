"""정리 뒤 사용자가 PC에서 직접 만든 폴더를 알아보고, 등록하면 새 파일을 그 폴더로 제안한다(합성 자료).
등록 전에도 그 폴더 안의 파일은 옮기자고 하지 않는다."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app

C = '4 시공단계/1 도급공사'
USER_IN_TREE = C + '/15 실외기 구조 검토'
USER_TOP = '9 석면 대응'


class UserMadeFolders(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); base = Path(self.tmp.name)
        self.dp = patch.object(app, 'DATA', base / 'data'); self.dp.start(); app.DATA.mkdir()
        app.atomic_json(app.DATA / 'prefs.json', {'autoClassify': False})
        self.root = base / '가상 사업'
        for rel in ['2. 시공단계/2. 공사/14. 작업일보/작업일보 0105.pdf',
                    '2. 시공단계/2. 공사/6. 사진/260124/IMG_0001.jpg',
                    '2. 시공단계/2. 공사/4. 공문/2. 선금신청/선금 신청 공문.pdf']:
            self.write(rel)
        app.SELECTIONS['made'] = str(self.root); app.PLANS.clear()
        tree = [{'label': app.INBOX}] + copy.deepcopy(app.TEMPLATES['planning'])
        self.project = app.save_project({'selection': 'made', 'name': '가상 사업', 'type': 'planning', 'tree': tree}, False)

    def tearDown(self):
        self.dp.stop(); app.SELECTIONS.pop('made', None); app.PLANS.clear(); self.tmp.cleanup()

    def write(self, rel, data=None):
        path = self.root / rel; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data or ('SYNTHETIC ' + rel).encode())

    def files(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*') if p.is_file() and '.gongmu-chak' not in p.parts}

    def organize_once(self):
        plan = app.make_plan(self.project['id'], False)
        self.assertEqual(plan['userFolders'], [])  # no run yet: old folders are material, not user folders
        chosen = [{'id': r['id'], 'destination': r['destination']} for r in plan['rows'] if r['destination']]
        return app.execute_all(plan['id'], chosen, True)

    def make_user_folders(self):
        self.write(USER_IN_TREE + '/구조검토서_1차.pdf')
        self.write(USER_IN_TREE + '/현장사진/IMG_01.jpg')
        self.write(USER_TOP + '/고용노동부 제출 공문.pdf')

    def test_program_made_folders_are_not_reported_and_user_folders_stay_put(self):
        self.organize_once()
        self.make_user_folders()
        before = self.files()
        plan = app.make_plan(self.project['id'], False)
        reported = {f['path']: f['files'] for f in plan['userFolders']}
        self.assertEqual(reported, {USER_IN_TREE: 2, USER_TOP: 1})
        moved_from = {r['relative'] for r in plan['rows'] if r.get('destination')}
        self.assertFalse(any(m.startswith((USER_IN_TREE + '/', USER_TOP + '/')) for m in moved_from), moved_from)
        self.assertEqual(self.files(), before)

    def test_registered_folder_receives_new_related_files(self):
        self.organize_once()
        self.make_user_folders()
        self.write(app.INBOX + '/실외기 구조검토서_2차.pdf')
        self.write(app.INBOX + '/석면 대응 결과보고.hwp')
        held = {r['relative']: r['destination'] for r in app.make_plan(self.project['id'], True)['rows']}
        self.assertEqual(held[app.INBOX + '/실외기 구조검토서_2차.pdf'], '')
        result = app.register_user_folders(self.project['id'], [USER_IN_TREE, USER_TOP])
        self.assertEqual(sorted(result['added']), sorted([USER_IN_TREE, USER_TOP]))
        paths = app.work_paths(app.get_project(self.project['id']))
        self.assertIn(USER_IN_TREE, paths); self.assertIn(USER_TOP, paths)
        plan = app.make_plan(self.project['id'], True)
        rows = {r['relative']: r['destination'] for r in plan['rows']}
        self.assertEqual(rows[app.INBOX + '/실외기 구조검토서_2차.pdf'], USER_IN_TREE)
        self.assertEqual(rows[app.INBOX + '/석면 대응 결과보고.hwp'], USER_TOP)
        self.assertEqual(app.make_plan(self.project['id'], False)['userFolders'], [])
        # Existing contents of the registered folder are not proposed for moving.
        whole = app.make_plan(self.project['id'], False)
        self.assertFalse(any(r['relative'].startswith(USER_IN_TREE + '/') and r.get('destination') for r in whole['rows']))

    def test_unknown_folder_cannot_be_registered(self):
        self.organize_once()
        with self.assertRaises(ValueError):
            app.register_user_folders(self.project['id'], ['없는 폴더'])


if __name__ == '__main__':
    unittest.main()
