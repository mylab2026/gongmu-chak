"""확인(!) 묶음: 원래 폴더 단위로 묶고, 묶음 확정·묶음 목적지 변경을 한 번에 한다(합성 자료)."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app

UNIT = '2. 시공단계/2. 공사/11. 실외기 구조 검토'
TOPIC = '6. 석면관련'
FILES = [UNIT + '/A 검토서/구조계산.dwg', UNIT + '/B 상세/받침 상세.dwg', UNIT + '/검토 의견.pdf',
         TOPIC + '/2. 노동부 관계서류/제출 1.pdf', TOPIC + '/2. 노동부 관계서류/제출 2.pdf', TOPIC + '/2. 노동부 관계서류/제출 3.pdf',
         TOPIC + '/1. 경과/경과 메모.hwp', TOPIC + '/3. 법무 의견/의견.pdf', TOPIC + '/석면조사 보고서 추가.pdf',
         '2. 시공단계/2. 공사/14. 작업일보/작업일보 0105.pdf']


class CheckGroups(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); base = Path(self.tmp.name)
        self.dp = patch.object(app, 'DATA', base / 'data'); self.dp.start(); app.DATA.mkdir()
        app.atomic_json(app.DATA / 'prefs.json', {'autoClassify': False})
        self.root = base / '가상 사업'
        for i, rel in enumerate(FILES):
            path = self.root / rel; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(b'SYNTHETIC %d' % i)
        app.SELECTIONS['groups'] = str(self.root); app.PLANS.clear()
        tree = [{'label': app.INBOX}] + copy.deepcopy(app.TEMPLATES['planning'])
        self.project = app.save_project({'selection': 'groups', 'name': '가상 사업', 'type': 'planning', 'tree': tree}, False)
        self.plan = app.make_plan(self.project['id'], False)
        self.rows = {r['relative']: r for r in self.plan['rows'] if r.get('kind') != 'directory'}

    def tearDown(self):
        self.dp.stop(); app.SELECTIONS.pop('groups', None); app.PLANS.clear(); self.tmp.cleanup()

    def test_unit_is_first_unrecognized_folder_from_the_top(self):
        for rel in FILES[:3]:
            self.assertEqual(self.rows[rel]['checkUnit'], UNIT, rel)
        for rel in FILES[3:9]:
            self.assertEqual(self.rows[rel]['checkUnit'], TOPIC, rel)

    def test_lone_filename_guess_inside_a_held_folder_needs_review(self):
        guess = self.rows[TOPIC + '/석면조사 보고서 추가.pdf']
        self.assertTrue(guess['destination'], guess['reason'])
        self.assertTrue(guess.get('unitReview'), guess['reason'])
        self.assertFalse(self.rows['2. 시공단계/2. 공사/14. 작업일보/작업일보 0105.pdf'].get('unitReview'))

    def test_group_confirm_and_group_retarget_keep_the_folder_name(self):
        held = [self.rows[rel]['id'] for rel in FILES[:3]]
        self.assertTrue(all(not self.rows[rel]['destination'] for rel in FILES[:3]))
        confirmed = app.dispatch('/confirm-route', {'plan': self.plan['id'], 'rows': held})['rows']
        self.assertEqual({r['id'] for r in confirmed}, set(held))
        self.assertTrue(all(r['holdConfirmed'] for r in confirmed))
        target = '4 시공단계/1 도급공사/8 승인요청'
        changed = app.dispatch('/retarget-many', {'plan': self.plan['id'], 'rows': held, 'destination': target, 'keepFolder': UNIT})['rows']
        subs = {r['relative']: r.get('keepSub', '') for r in changed}
        self.assertRegex(subs[UNIT + '/A 검토서/구조계산.dwg'], r'^(?:[A-Z] )?실외기 구조 검토/A 검토서$')
        self.assertRegex(subs[UNIT + '/검토 의견.pdf'], r'^(?:[A-Z] )?실외기 구조 검토$')
        self.assertTrue(all(r['destination'] == target for r in changed))


if __name__ == '__main__':
    unittest.main()
