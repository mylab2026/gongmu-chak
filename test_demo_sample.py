"""The built-in demo folder works end to end without any real folder (synthetic files only)."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app
import demo_sample


class DemoFolder(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.data=Path(self.temp.name)/'GongmuChakData';self.data.mkdir()
        self.patch=patch.object(app,'DATA',self.data);self.patch.start();app.SELECTIONS.clear();app.PLANS.clear()

    def tearDown(self):self.patch.stop();self.temp.cleanup()

    def files(self,root):return {p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file() and '.gongmu-chak' not in p.parts}

    def test_demo_folder_is_new_inside_app_data_and_selectable(self):
        first=app.dispatch('/demo-folder',{});second=app.dispatch('/demo-folder',{})
        a,b=Path(first['path']),Path(second['path'])
        self.assertNotEqual(a,b);self.assertTrue(first['demo'])
        self.assertTrue(a.resolve().is_relative_to((self.data/demo_sample.DEMO_DIR).resolve()))
        self.assertEqual(first['count'],len(demo_sample.DOCUMENTS)+len(demo_sample.PHOTOS)+len(demo_sample.SIGN_PHOTOS)+len(demo_sample.LETTERS))
        self.assertTrue((a/demo_sample.EMPTY[0]).is_dir())

    def test_demo_runs_plan_move_and_undo(self):
        selection=app.dispatch('/demo-folder',{});root=Path(selection['path'])
        tree=[{'label':app.INBOX}]+copy.deepcopy(app.TEMPLATES['design'])
        project=app.save_project({'selection':selection['selection'],'name':root.name,'type':'design','tree':tree},False)
        before=self.files(root);plan=app.make_plan(project['id'],False)
        chosen=[{'id':r['id'],'destination':r['destination']} for r in plan['rows'] if r['destination']]
        self.assertTrue(chosen);self.assertTrue(any(not r['destination'] for r in plan['rows']))  # something is held for review
        journal=app.execute_all(plan['id'],chosen,True)
        self.assertEqual(sorted(self.files(root).values()),sorted(before.values()))
        app.undo(journal['id']);self.assertEqual(self.files(root),before)
        self.assertTrue((root/demo_sample.EMPTY[0]).is_dir())

    def test_demo_shows_safety_ledgers_contractor_letters_and_a_mixed_folder(self):
        # 2026-11-28 시연 보강: 안전보건대장 3종, 시공사 공문, 섞인 폴더, 간판 사진
        selection=app.dispatch('/demo-folder',{});root=Path(selection['path'])
        tree=[{'label':app.INBOX}]+copy.deepcopy(app.TEMPLATES['design'])
        project=app.save_project({'selection':selection['selection'],'name':root.name,'type':'design','tree':tree},False)
        plan=app.make_plan(project['id'],False);rows={r['relative']:r for r in plan['rows']}
        ledger=app.safety_ledger_root(app.get_project(project['id'])['tree']);self.assertTrue(ledger)
        self.assertEqual(rows['251216 기본안전보건대장 보완/251111 기본안전보건대장.hwp']['destination'],ledger+'/1 기본안전보건대장')
        self.assertEqual(rows['2 설계단계/21 설계 용역/설계안전보건대장/설계안전보건대장(수정본).pdf']['destination'],ledger+'/2 설계안전보건대장')
        self.assertEqual(rows['3 시공단계/31 도급공사/안전보건대장/안전보건대장.hwpx']['destination'],ledger+'/3 공사안전보건대장')
        text=(root/'3 시공단계/31 도급공사/공문/260227 바닥재 자재승인 요청.txt').read_text(encoding='utf-8')
        fields=app.official_fields(text)
        self.assertEqual((fields['docNumber'],fields['sender']),('가상한빛건설-2026-016','가상한빛건설 주식회사'))
        self.assertTrue((root/demo_sample.SIGN_PHOTOS[0][0]).is_file())
        self.assertGreaterEqual(len({r['destination'] for r in plan['rows'] if r['relative'].startswith('현장 자료 모음/')}),1)


if __name__=='__main__':unittest.main()

