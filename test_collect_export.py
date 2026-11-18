"""Photo/notice collection and handover export: local only, never moves originals."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import app


class CollectExport(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        self.root=self.base/'사업';self.root.mkdir();self.data=self.base/'settings';self.data.mkdir()
        self.patch=patch.object(app,'DATA',self.data);self.patch.start()
        app.SELECTIONS.clear();app.PLANS.clear();app.EXPORTS.clear();app.SELECTIONS['selected']=str(self.root)
        tree=[{'label':app.INBOX}]+copy.deepcopy(app.TEMPLATES['construction'])
        self.project=app.save_project({'selection':'selected','name':'시험','tree':tree},False)
        self.report='1 공통/3 주요 보고자료(내부보고 자료)/A 261001 현황 보고'

    def tearDown(self):self.patch.stop();self.temp.cleanup()
    def write(self,relative,data=b'x'):
        p=self.root/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data);return p
    def snapshot(self):
        return {p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file() and '.gongmu-chak' not in p.parts}

    def test_collection_groups_photos_and_notices_without_ai_or_changes(self):
        self.write(self.report+'/현황 보고.hwpx');self.write(self.report+'/공사전 사진.jpg',b'p1')
        self.write(self.report+'/붙임2 관련 공문.pdf',b'n1');self.write('3 시공단계/현장/IMG_0001.jpg',b'p2')
        self.write('3 시공단계/현장/보수 후/IMG_0002.jpg',b'p3');self.write('3 시공단계/현장/공사 전 후 비교.jpg',b'p4')
        before=self.snapshot()
        with patch.object(app,'gateway',side_effect=AssertionError('no AI')):data=app.collect(self.project['id'])
        phases={p['name']:p['phase'] for p in data['photos']}
        self.assertEqual(phases,{'공사전 사진.jpg':'before','IMG_0001.jpg':'check','IMG_0002.jpg':'after','공사 전 후 비교.jpg':'check'})
        notice=data['officials'][0];self.assertEqual(notice['name'],'붙임2 관련 공문.pdf');self.assertEqual(notice['bundle'],'A 261001 현황 보고')
        self.assertEqual(self.snapshot(),before)
        app.set_photo_phase(self.project['id'],'3 시공단계/현장/IMG_0001.jpg','during')
        data=app.collect(self.project['id']);self.assertEqual(next(p for p in data['photos'] if p['name']=='IMG_0001.jpg')['phase'],'during')

    def test_missing_items_are_reported_after_path_change(self):
        path=self.write('3 시공단계/현장/공사중 사진.jpg');app.collect(self.project['id'])
        path.rename(path.with_name('다른 이름.jpg'))
        self.assertEqual(app.collect(self.project['id'])['missing'],['3 시공단계/현장/공사중 사진.jpg'])

    def test_export_creates_nothing_until_approved_and_never_overwrites_user_files(self):
        self.write(self.report+'/공사전 사진.jpg',b'p1');self.write(self.report+'/관련 공문.pdf',b'n1');self.write('3 시공단계/IMG.jpg',b'?')
        before=self.snapshot()
        plan=app.export_plan(self.project['id'])
        self.assertEqual(self.snapshot(),before);self.assertEqual(list(self.root.rglob('*.lnk')),[])
        self.assertEqual(len(plan['links']),2);self.assertEqual(plan['checks']['photoCheck'],1)
        user=self.write(app.EXPORT_DIR+'/사업 안내.html',b'user note')
        report=app.export_run(self.project['id'],plan['id'])
        self.assertTrue(report['ok']);self.assertEqual(len(report['created']),2)
        self.assertEqual(user.read_bytes(),b'user note');self.assertIn(app.EXPORT_DIR+'/사업 안내 (2).html',report['outputs'])
        listing=(self.root/app.EXPORT_DIR/'자료 목록.csv').read_text(encoding='utf-8-sig')
        self.assertIn(self.report+'/공사전 사진.jpg',listing);self.assertIn('A 261001 현황 보고',listing)
        guide=(self.root/app.EXPORT_DIR/'사업 안내 (2).html').read_text(encoding='utf-8')
        self.assertIn('href="../',guide)
        for relative,data in before.items():self.assertEqual((self.root/relative).read_bytes(),data)
        again=app.export_run(self.project['id'],app.export_plan(self.project['id'])['id'])
        self.assertEqual(len(again['kept']),2);self.assertEqual(again['created'],[])
        self.assertEqual(len(list(self.root.rglob('*.lnk'))),2)

    def test_changed_app_link_is_left_alone_on_rerun(self):
        self.write(self.report+'/공사전 사진.jpg',b'p1')
        first=app.export_run(self.project['id'],app.export_plan(self.project['id'])['id'])
        link=self.root/first['created'][0];link.write_bytes(b'user edited')
        again=app.export_run(self.project['id'],app.export_plan(self.project['id'])['id'])
        self.assertEqual(link.read_bytes(),b'user edited');self.assertIn(first['created'][0],again['userChanged'])


if __name__=='__main__':unittest.main()
