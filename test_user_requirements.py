"""Independent user requirement regressions. Synthetic fixtures; no real API."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import app
from PIL import Image


class UserRequirements(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        self.root=self.base/'사업';self.root.mkdir();data=self.base/'data';data.mkdir()
        self.patcher=patch.object(app,'DATA',data);self.patcher.start()
        app.SELECTIONS.clear();app.PLANS.clear();app.SELECTIONS['review']=str(self.root)
        self.project=app.save_project({'selection':'review','name':'독립검증','type':'construction',
            'tree':[{'label':app.INBOX},{'label':'3 시공단계','children':[{'label':'1 공문'},{'label':'2 사진'}]}]},False)
        p=app.get_project(self.project['id'])
        p['contracts']=[{'id':'construction','analysis':{'kind':'construction','signed_date':'2026-07-10','period':'2026.08.01 ~ 2026.09.30'}}]
        app.store_project(p)

    def tearDown(self):self.patcher.stop();self.temp.cleanup()

    def photo(self,relative,date):
        p=self.root/relative;p.parent.mkdir(parents=True,exist_ok=True)
        image=Image.new('RGB',(30,30),'green');exif=image.getexif();exif[36867]=date+' 09:00:00'
        image.save(p,'JPEG',exif=exif);return p

    def write(self,relative,text):
        p=self.root/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8');return p

    def photos(self):return {p['name']:p for p in app.collect(self.project['id'])['photos']}

    def test_01_seven_days_after_completion_requires_review(self):
        self.photo('3 시공단계/2 사진/IMG_1007.jpg','2026:10:07')
        self.assertEqual(self.photos()['IMG_1007.jpg']['phase'],'check')

    def test_02_user_completion_boundary_propagates(self):
        a='3 시공단계/2 사진/IMG_0920.jpg'
        self.photo(a,'2026:09:20');self.photo('3 시공단계/2 사진/IMG_0921.jpg','2026:09:21')
        app.set_photo_phase(self.project['id'],a,'after')
        self.assertEqual(self.photos()['IMG_0921.jpg']['phase'],'after')

    def test_03_contract_date_does_not_require_period(self):
        p=app.get_project(self.project['id']);p['contracts'][0]['analysis'].pop('period');app.store_project(p)
        self.photo('3 시공단계/2 사진/IMG_0709.jpg','2026:07:09')
        self.assertEqual(self.photos()['IMG_0709.jpg']['phase'],'before')

    def test_04_actual_site_photo_attached_to_official_is_kept(self):
        self.photo('3 시공단계/1 공문/A 현황 보고/첨부 사진/IMG_0820.jpg','2026:08:20')
        self.assertIn('IMG_0820.jpg',self.photos())

    def test_05_filename_is_not_confirmation_of_official_document(self):
        p=self.root/'3 시공단계/검토/공문 작성 요령.pdf';p.parent.mkdir(parents=True)
        Image.new('RGB',(300,400),'white').save(p,'PDF')
        self.assertNotIn(p.name,[d['name'] for d in app.collect(self.project['id'])['officials'] if d['status']=='yes'])

    def test_06_different_content_same_stat_does_not_share_ai_verdict(self):
        a=self.write('3 시공단계/1 공문/a 공문.txt','AAAA');b=self.write('3 시공단계/1 공문/b 공문.txt','BBBB')
        stamp=1784000000000000000
        for p in (a,b):os.utime(p,ns=(stamp,stamp))
        c=app.save_collection(self.project['id'],{'name':'공문','text':'공문'})
        with patch.object(app,'gateway',return_value={'decision':'match','evidence':{'test':'only A'}}):
            app.verify_collection(self.project['id'],c['id'],[a.relative_to(self.root).as_posix()])
        self.assertEqual([d['name'] for d in app.run_collection(self.project['id'],c['id'])['verified']],[a.name])

    def test_07_numeric_filename_content_is_discovered(self):
        self.write('3 시공단계/2 사진/20260820123456.txt','문서번호: 시설-101\n수신: 시설과\n제목: 공정 회의 안내\n발신: 예시종합건설 대표이사\n시행: 시설-101 (2026.08.20)')
        c=app.save_collection(self.project['id'],{'name':'공문','text':'공문'})
        self.assertTrue(app.run_collection(self.project['id'],c['id'])['candidates'])

    def test_08_real_extraction_preserves_official_fields(self):
        p=self.write('3 시공단계/1 공문/a 공문.txt','문서번호: 시설-101\n수신: 시설과\n제목: 자재 승인 요청\n발신: 예시종합건설 대표이사\n시행: 시설-101 (2026.08.20)')
        self.assertEqual(app.official_fields(app.local_text(p))['title'],'자재 승인 요청')

    def test_09_collection_command_is_not_a_required_content_keyword(self):
        self.assertNotIn('모아보기',app.parse_collection('시공사 공문 모아보기')['keywordsAll'])

    def test_10_round_mapping_preserves_inner_contract_attachment_name(self):
        from test_v3_roles import RolesBeforeLetters,C,CHANGE
        fixture=RolesBeforeLetters();fixture.setUp()
        try:
            relative=C+'3109-1 설계변경1차(설계변경 검토의견서)/참고 계약서.pdf'
            p=fixture.root/relative;p.write_bytes(b'original attachment contract')
            project=app.get_project(fixture.project['id'])
            project['contracts']=[{'id':'cons','sourceHash':app.file_hash(p),'name':p.name,'analysis':{'kind':'construction','title':'보수 공사','party':'예시건설','signed_date':'2026-07-10'}}]
            app.store_project(project);plan=app.make_plan(project['id'],False)
            row=next(r for r in plan['rows'] if r['relative']==relative)
            self.assertEqual(row['destination'],CHANGE+'/1 1차 설계변경')
            journal=app.execute_all(plan['id'],[{'id':row['id'],'destination':row['destination']}])
            actual=journal['entries'][0]['destination'];app.undo(journal['id'])
            self.assertEqual(Path(actual).name,'참고 계약서.pdf')
        finally:fixture.tearDown()

    def test_11_thirty_days_after_completion_is_an_estimate(self):
        self.photo('3 시공단계/2 사진/IMG_1030.jpg','2026:10:30');item=self.photos()['IMG_1030.jpg']
        self.assertEqual(item['phase'],'after');self.assertIn('추정',item['evidence'])

    def test_12_unrelated_contract_dates_are_not_combined(self):
        p=app.get_project(self.project['id']);p['contracts'].append({'id':'other','analysis':{'kind':'construction','signed_date':'2027-01-01','period':'2027.02.01 ~ 2027.03.01'}});app.store_project(p)
        self.photo('3 시공단계/2 사진/IMG_0820.jpg','2026:08:20')
        self.assertEqual(self.photos()['IMG_0820.jpg']['phase'],'check')

    def test_13_manual_phase_survives_propagated_boundary(self):
        a='3 시공단계/2 사진/IMG_0920.jpg';b='3 시공단계/2 사진/IMG_0921.jpg'
        self.photo(a,'2026:09:20');self.photo(b,'2026:09:21')
        app.set_photo_phase(self.project['id'],a,'after');app.set_photo_phase(self.project['id'],b,'during')
        self.assertEqual(self.photos()['IMG_0921.jpg']['phase'],'during')

    def test_14_change_during_ai_verification_is_not_cached(self):
        p=self.write('3 시공단계/1 공문/a 공문.txt','original');c=app.save_collection(self.project['id'],{'name':'공문','text':'공문'})
        def response(*args,**kwargs):
            p.write_text('changed',encoding='utf-8');return {'decision':'match','evidence':{'test':'original'}}
        with patch.object(app,'gateway',side_effect=response):result=app.verify_collection(self.project['id'],c['id'],[p.relative_to(self.root).as_posix()])
        self.assertFalse(result['done']);self.assertEqual(len(result['failed']),1)

    def test_15_specific_department_and_month_are_preserved(self):
        c=app.parse_collection('2026년 2월 캠퍼스 관리과에 보낸 공문 모아보기')
        self.assertEqual(c['dateTo'],'2026-02-28');self.assertEqual(c['recipient'],'캠퍼스 관리과')
        self.assertNotIn('모아보기',c['keywordsAll'])

    def test_16_official_fields_without_colons(self):
        p=self.write('3 시공단계/1 공문/a 공문.txt','문서번호 시설-101\n수신 시설과장\n제목 자재 승인 요청\n발신 예시종합건설 대표이사\n시행 시설-101 (2026.08.20)')
        fields=app.official_fields(app.local_text(p))
        self.assertEqual(fields['title'],'자재 승인 요청');self.assertEqual(fields['recipient'],'시설과장')

    def test_17_bulk_ai_preserves_round_and_manual_destination(self):
        from test_v3_roles import RolesBeforeLetters,C,CHANGE
        import json
        fixture=RolesBeforeLetters();fixture.setUp()
        try:
            plan=app.make_plan(fixture.project['id'],False)
            row=next(r for r in plan['rows'] if '3109-1' in r['relative'] and r['name'].endswith('.hwp'))
            def fake(messages,**kwargs):
                payload=json.loads(messages[-1]['content'])
                return {'assignments':[{'file_id':f['file_id'],'destination_id':'d1','reason':'synthetic wrong AI','confidence':.99} for f in payload['files']]}
            job={'id':'review','planId':plan['id'],'recheck':True,'status':'pending','processed':0,'completedBatches':0};app.JOBS['review']=job
            with patch.object(app,'gateway',side_effect=fake):app.run_bulk('review')
            self.assertEqual(job['status'],'done',job.get('error'));self.assertEqual(row['destination'],CHANGE+'/1 1차 설계변경')
            row['method']='manual';self.assertNotIn(row,[item for chunk in app.bulk_batches(plan,True) for item in chunk])
        finally:fixture.tearDown()

    def test_18_parenthesized_round_keeps_its_folder_and_inner_names(self):
        from test_v3_roles import RolesBeforeLetters,C,CHANGE
        fixture=RolesBeforeLetters();fixture.setUp()
        try:
            old=C+'설계변경(1차)/'
            for relative,data in ((old+'검토 의견.hwp',b'r1 opinion'),(old+'사진/IMG_0001.jpg',b'r1 photo')):
                p=fixture.root/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
            before=fixture.files();plan=app.make_plan(fixture.project['id'],False)
            rows={r['relative']:r for r in plan['rows']}
            self.assertEqual(fixture.target(rows[old+'검토 의견.hwp']),CHANGE+'/1 1차 설계변경/검토 의견.hwp')
            self.assertEqual(fixture.target(rows[old+'사진/IMG_0001.jpg']),CHANGE+'/1 1차 설계변경/사진/IMG_0001.jpg')
            journal=app.execute_all(plan['id'],[{'id':r['id'],'destination':r['destination']} for r in plan['rows'] if r['destination']])
            self.assertEqual((fixture.root/CHANGE/'1 1차 설계변경/사진/IMG_0001.jpg').read_bytes(),b'r1 photo')
            self.assertEqual(sorted(fixture.files().values()),sorted(before.values()))
            app.undo(journal['id']);self.assertEqual(fixture.files(),before)
        finally:fixture.tearDown()

    def test_19_confirmed_marks_follow_the_apps_own_move_and_undo(self):
        from test_v3_roles import RolesBeforeLetters,M,MAIL
        fixture=RolesBeforeLetters();fixture.setUp()
        try:
            pid=fixture.project['id'];photo=M+'현장 사진1.jpg';letter=M+'회신 메일.pdf'
            image=Image.new('RGB',(30,30),'green');exif=image.getexif();exif[36867]='2026:08:20 09:00:00'
            image.save(fixture.root/photo,'JPEG',exif=exif)
            app.set_photo_phase(pid,photo,'during');app.set_official(pid,letter,True);app.collect(pid)
            plan=app.make_plan(pid,False)
            journal=app.execute_all(plan['id'],[{'id':r['id'],'destination':r['destination']} for r in plan['rows'] if r['destination']])
            bundle=MAIL+'/A 260327 캠퍼스 관리과 메일/'
            moved=app.collect(pid)
            photos={p['relative']:p for p in moved['photos']};officials={o['relative']:o for o in moved['officials']}
            self.assertEqual((photos[bundle+'현장 사진1.jpg']['phase'],photos[bundle+'현장 사진1.jpg']['confirmed']),('during',True))
            self.assertEqual((officials[bundle+'회신 메일.pdf']['status'],officials[bundle+'회신 메일.pdf']['confirmed']),('yes',True))
            self.assertEqual((moved['missing'],moved['stale']),([],[]))
            app.undo(journal['id']);back=app.collect(pid)
            self.assertEqual({p['relative']:p['phase'] for p in back['photos'] if p['confirmed']},{photo:'during'})
            self.assertEqual({o['relative'] for o in back['officials'] if o['confirmed']},{letter})
            self.assertEqual((back['missing'],back['stale']),([],[]))
        finally:fixture.tearDown()

    def test_20_bundle_keeps_nested_same_names_and_relative_paths(self):
        from test_v3_roles import RolesBeforeLetters,M,MAIL
        fixture=RolesBeforeLetters();fixture.setUp()
        try:
            for relative,data in ((M+'첨부/1차/도면.pdf',b'first drawing'),(M+'첨부/2차/도면.pdf',b'second drawing'),(M+'첨부/2차/세부/깊은 자료.xlsx',b'deep')):
                (fixture.root/relative).parent.mkdir(parents=True,exist_ok=True);(fixture.root/relative).write_bytes(data)
            before=fixture.files();plan=app.make_plan(fixture.project['id'],False)
            journal=app.execute_all(plan['id'],[{'id':r['id'],'destination':r['destination']} for r in plan['rows'] if r['destination']])
            bundle=fixture.root/MAIL/'A 260327 캠퍼스 관리과 메일'
            moved={p.relative_to(bundle).as_posix():p.read_bytes() for p in bundle.rglob('*') if p.is_file()}
            original={k[len(M):]:v for k,v in before.items() if k.startswith(M)}
            self.assertEqual(moved,original)
            self.assertTrue((bundle/'빈 폴더').is_dir())
            app.undo(journal['id']);self.assertEqual(fixture.files(),before)
        finally:fixture.tearDown()


if __name__=='__main__':unittest.main()
