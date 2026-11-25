"""등록된 사업 삭제는 목록에서만 빼고 실제 폴더·파일과 정리 이력 파일은 건드리지 않는다(합성 자료)."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class DeleteProject(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); base = Path(self.tmp.name)
        self.dp = patch.object(app, 'DATA', base / 'data'); self.dp.start(); app.DATA.mkdir()
        self.root = base / '합성 사업'; self.root.mkdir()
        (self.root / '설계변경').mkdir(); (self.root / '설계변경' / '검토의견서.hwp').write_bytes(b'SYNTHETIC')
        app.SELECTIONS['del'] = str(self.root); app.PLANS.clear()
        tree = [{'label': app.INBOX}, {'label': '시공단계'}]
        self.a = app.save_project({'selection': 'del', 'name': '삭제할 사업', 'type': 'construction', 'tree': tree}, False)
        self.b = app.save_project({'selection': 'del', 'name': '남길 사업', 'type': 'construction', 'tree': tree}, False)

    def tearDown(self):
        self.dp.stop(); app.SELECTIONS.pop('del', None); app.PLANS.clear(); self.tmp.cleanup()

    def files(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_removes_only_that_registration_and_keeps_folder(self):
        history = app.DATA / 'history'; history.mkdir(); (history / 'j1.json').write_text('{"projectId": "%s"}' % self.a['id'])
        app.make_plan(self.a['id'], False)
        before = self.files()
        result = app.dispatch('/delete-project', {'id': self.a['id']})
        self.assertTrue(result['ok'])
        self.assertEqual([p['id'] for p in app.projects()], [self.b['id']])
        self.assertEqual(self.files(), before)  # 사용자 폴더 그대로
        self.assertTrue((history / 'j1.json').exists())  # 정리 이력 그대로
        self.assertFalse(any(p['projectId'] == self.a['id'] for p in app.PLANS.values()))
        archived = app.read_json(app.DATA / 'deleted-projects.json')
        self.assertEqual(archived[0]['id'], self.a['id']); self.assertIn('deletedAt', archived[0])
        self.assertNotIn(self.a['id'], [p['id'] for p in app.dispatch('/status', {})['projects']])

    def test_unknown_project_fails_without_changes(self):
        before = app.read_json(app.DATA / 'projects.json')
        for payload in [{'id': 'unknown'}, {}]:
            with self.assertRaises(ValueError): app.dispatch('/delete-project', payload)
        self.assertEqual(app.read_json(app.DATA / 'projects.json'), before)

    def test_same_folder_can_be_registered_again(self):
        app.dispatch('/delete-project', {'id': self.a['id']})
        again = app.save_project({'selection': 'del', 'name': '다시 연결한 사업', 'type': 'construction', 'tree': [{'label': app.INBOX}]}, False)
        self.assertIn(again['id'], [p['id'] for p in app.projects()])


if __name__ == '__main__':
    unittest.main()
