"""v3 collections: scans are not photos, dated photo phases, saved collections with cached AI verification (synthetic)."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import app


class V3Collections(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();base=Path(self.temp.name)
        self.root=base/'사업';self.root.mkdir();data=base/'settings';data.mkdir()
        self.patch=patch.object(app,'DATA',data);self.patch.start()
        app.SELECTIONS.clear();app.SELECTIONS['p']=str(self.root)
        self.project=app.save_project({'selection':'p','name':'모아보기','type':'construction','tree':[{'label':app.INBOX},{'label':'1 공통','children':[{'label':'1 공문','children':[]}]},{'label':'3 시공단계','children':[{'label':'1 사진','children':[]}]}]},False)
        project=app.get_project(self.project['id'])
        project['contracts']=[{'id':'c','analysis':{'kind':'construction','title':'보수공사','period':'2026.03.01 ~ 2026.06.30'}}];app.store_project(project)

    def tearDown(self):self.patch.stop();self.temp.cleanup()

    def photo(self,relative,taken=None):
        from PIL import Image
        path=self.root/relative;path.parent.mkdir(parents=True,exist_ok=True);image=Image.new('RGB',(8,8),'white');exif=image.getexif()
        if taken:exif[36867]=taken
        image.save(path,'JPEG',exif=exif);return path

    def write(self,relative,text):
        path=self.root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8');return path

    def test_scans_are_not_photos_and_dates_decide_phase(self):
        self.photo('3 시공단계/1 사진/IMG_01.jpg','2026:02:10 09:00:00')
        self.photo('3 시공단계/1 사진/IMG_02.jpg','2026:04:10 09:00:00')
        self.photo('3 시공단계/1 사진/IMG_03.jpg','2026:07:10 09:00:00')
        self.photo('3 시공단계/1 사진/IMG_04.jpg')
        self.photo('1 공통/1 공문/스캔_0012.jpg');self.photo('3 시공단계/1 사진/협조 공문.png')
        before={p:p.stat().st_mtime_ns for p in self.root.rglob('*')}
        data=app.collect(self.project['id'])
        phases={p['name']:p['phase'] for p in data['photos']}
        self.assertEqual(phases,{'IMG_01.jpg':'before','IMG_02.jpg':'during','IMG_03.jpg':'check','IMG_04.jpg':'check'})
        self.assertIn('촬영일(EXIF)',next(p for p in data['photos'] if p['name']=='IMG_02.jpg')['evidence'])
        self.assertEqual({o['name'] for o in data['officials'] if o.get('scan')},{'스캔_0012.jpg','협조 공문.png'})
        self.assertEqual(before,{p:p.stat().st_mtime_ns for p in self.root.rglob('*')});self.assertEqual(list(self.root.rglob('*.lnk')),[])

    def test_sender_means_who_sent_it(self):
        c=app.parse_collection('시공사 공문')
        self.assertEqual((c['types'],c['sender']),(['공문'],'시공사'))
        sent=self.write('1 공통/1 공문/260401 협조 공문.txt','수신 시설지원과장\n제목 자재 승인 요청\n발신 ○○종합건설 대표이사')
        mention=self.write('1 공통/1 공문/260402 통보 공문.txt','수신 ○○종합건설 대표이사\n제목 공정 회의 통보\n발신 시설지원과장')
        self.assertTrue(app.local_match('1 공통/1 공문/260401 협조 공문.txt',sent.read_text(encoding='utf-8'),c)[0])
        self.assertFalse(app.local_match('1 공통/1 공문/260402 통보 공문.txt',mention.read_text(encoding='utf-8'),c)[0])
        r=app.parse_collection('캠퍼스 관리과에 보낸 공문');self.assertEqual((r['recipient'],r['sender']),('캠퍼스 관리과',''))

    def test_saved_collection_verification_is_cached_and_failure_is_not_verified(self):
        self.write('1 공통/1 공문/260401 협조 공문.txt','문서번호: 예시-001\n수신 시설지원과장\n제목 자재 승인 요청\n발신 ○○종합건설 대표이사')
        self.write('1 공통/1 공문/260405 회신 공문.txt','문서번호: 예시-002\n수신 시설지원과장\n제목 공정 회신\n발신 ○○종합건설 대표이사')
        item=app.save_collection(self.project['id'],{'name':'시공사 공문','text':'시공사 공문'})
        run=app.run_collection(self.project['id'],item['id']);self.assertEqual(run['estimate']['aiCalls'],2)
        calls=[]
        def fake(messages,**k):
            calls.append(1)
            if len(calls)==2:app.fail('학내 API에 연결하지 못했습니다.')
            return {'decision':'match','evidence':{'발신':'○○종합건설'},'sender':'○○종합건설'}
        with patch.object(app,'gateway',fake):
            result=app.verify_collection(self.project['id'],item['id'],[c['relative'] for c in run['candidates']])
        self.assertEqual((len(result['done']),len(result['failed'])),(1,1))
        again=app.run_collection(self.project['id'],item['id'])
        self.assertEqual((len(again['verified']),len(again['candidates']),again['estimate']['aiCalls']),(1,1,1))
        with patch.object(app,'gateway',lambda *a,**k:self.fail('cached result must not call AI')):
            app.run_collection(self.project['id'],item['id'])

    def test_old_official_marks_become_a_saved_collection(self):
        project=app.get_project(self.project['id']);project['officialMarks']={'1 공통/1 공문/a.pdf':True};app.store_project(project)
        self.assertEqual([c['name'] for c in app.saved_collections(self.project['id'])],['공문'])
        self.assertEqual(app.get_project(self.project['id'])['officialMarks'],{'1 공통/1 공문/a.pdf':True})


if __name__=='__main__':unittest.main()
