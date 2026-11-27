"""Independent user requirement regressions. Synthetic fixtures; no real API."""
import io
import json
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
        body='문서번호: 예시-001\n제목: 공정 협의\n발신: 예시건설\n수신: 시설지원과\n내용: '
        a=self.write('3 시공단계/1 공문/a 공문.txt',body+'AAAA');b=self.write('3 시공단계/1 공문/b 공문.txt',body+'BBBB')
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


class HeldFilesGoToInbox(unittest.TestCase):
    """2026-11-27 LIM: 정리를 마치면 정리 전 폴더가 남지 않아야 한다. 보류는 원래 폴더 이름째 정리할 문서 모음으로."""
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        self.root=self.base/'사업';self.root.mkdir();data=self.base/'data';data.mkdir()
        self.patcher=patch.object(app,'DATA',data);self.patcher.start()
        self.gateway=patch.object(app,'gateway',side_effect=AssertionError('no AI in tests'));self.gateway.start()
        app.SELECTIONS.clear();app.PLANS.clear();app.SELECTIONS['held']=str(self.root)
        self.tree=[{'label':app.INBOX},{'label':'1 공통','children':[{'label':'1 사업계획서'}]},{'label':'3 시공단계','children':[{'label':'1 공문'}]}]
        self.project=app.save_project({'selection':'held','name':'보류 정리','tree':self.tree},False)
        self.inbox=self.root/app.INBOX

    def tearDown(self):self.gateway.stop();self.patcher.stop();self.temp.cleanup()

    def write(self,relative,data=b'SYNTHETIC'):
        p=self.root/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data);return p

    def files(self):
        return {p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file() and '.gongmu-chak' not in p.parts}

    def dirs(self):
        return {p.relative_to(self.root).as_posix() for p in self.root.rglob('*') if p.is_dir() and '.gongmu-chak' not in p.parts}

    def run_all(self,assign,ongoing=False):
        plan=app.make_plan(self.project['id'],ongoing)
        for r in plan['rows']:
            r['destination']=assign.get(r['relative'],'')
        return plan,app.execute_all(plan['id'],[{'id':r['id'],'destination':r['destination']} for r in plan['rows'] if r['destination']])

    def test_held_files_keep_folder_path_in_inbox_and_old_folders_disappear(self):
        self.write('옛자료/설계/과업지시서.pdf',b'A');self.write('옛자료/설계/메모.txt',b'B')
        self.write('옛자료/기타/하위/참고.hwp',b'C');self.write('옛자료/기타/하위/~$참고.hwp',b'lock')
        self.write('옛자료/기타/Thumbs.db',b'thumb');self.write('현장 사진.jpg',b'D')
        self.write('1 공통/1 사업계획서/표준폴더 보류.pdf',b'E')
        (self.root/'옛자료/빈 폴더').mkdir()
        before=self.files()
        plan,journal=self.run_all({'옛자료/설계/과업지시서.pdf':'3 시공단계/1 공문'})
        self.assertNotIn('Thumbs.db',[r['name'] for r in plan['rows']])  # 찌꺼기는 문서 행이 아니다
        self.assertEqual((self.root/'3 시공단계/1 공문/과업지시서.pdf').read_bytes(),b'A')
        self.assertEqual((self.inbox/'옛자료/설계/메모.txt').read_bytes(),b'B')  # 일부만 보류: 같은 폴더 이름으로
        self.assertEqual((self.inbox/'옛자료/기타/하위/참고.hwp').read_bytes(),b'C')  # 폴더 덩어리 경로 유지
        self.assertEqual((self.inbox/'현장 사진.jpg').read_bytes(),b'D')  # 사업 폴더 바로 아래 낱개 파일은 모음 바로 아래
        self.assertEqual((self.root/'1 공통/1 사업계획서/표준폴더 보류.pdf').read_bytes(),b'E')  # 표준 폴더에 있던 파일은 그 자리
        left=self.inbox/app.LEFTOVER_FOLDER
        self.assertTrue((left/'옛자료/기타/Thumbs.db').is_file() and (left/'옛자료/기타/하위/~$참고.hwp').is_file())
        self.assertFalse((self.root/'옛자료').exists())  # 정리 전 폴더는 하나도 남지 않는다
        self.assertEqual({p.name for p in self.root.iterdir()}-{'.gongmu-chak'},{app.INBOX,'1 공통','3 시공단계'})
        self.assertEqual(sorted(b for b in self.files().values()),sorted(before.values()))  # 바이트 그대로, 잃은 파일 없음
        self.assertTrue(all(r['done'] for r in plan['rows'] if r['relative']!='1 공통/1 사업계획서/표준폴더 보류.pdf'))
        app.undo(journal['id'])
        self.assertEqual(self.files(),before)
        self.assertIn('옛자료/빈 폴더',self.dirs())
        self.assertFalse(self.inbox.exists() and any(self.inbox.iterdir()))

    def test_name_clash_in_inbox_gets_number_and_undo_restores_name(self):
        self.write(app.INBOX+'/현장 사진.jpg',b'OLD');self.write('현장 사진.jpg',b'NEW');self.write('옛/보고.pdf',b'R')
        before=self.files()
        plan,journal=self.run_all({'옛/보고.pdf':'1 공통/1 사업계획서'})
        self.assertEqual((self.inbox/'현장 사진.jpg').read_bytes(),b'OLD')  # 덮어쓰지 않는다
        self.assertEqual((self.inbox/'현장 사진 (2).jpg').read_bytes(),b'NEW')
        app.undo(journal['id']);self.assertEqual(self.files(),before)

    def test_one_failed_move_does_not_keep_other_empty_old_folders(self):
        self.write('가/문서.pdf',b'1');self.write('나/잠긴 문서.pdf',b'2');(self.root/'다 빈 폴더').mkdir()
        real=app.move_no_replace
        def locked(source,destination):
            if source.name=='잠긴 문서.pdf':raise PermissionError('다른 프로그램이 사용 중')
            return real(source,destination)
        with patch.object(app,'move_no_replace',side_effect=locked):
            plan,journal=self.run_all({'가/문서.pdf':'1 공통/1 사업계획서','나/잠긴 문서.pdf':'3 시공단계/1 공문'})
        self.assertNotIn('cleanupSkipped',journal);self.assertIn('cleanupPartial',journal)
        self.assertFalse((self.root/'가').exists());self.assertFalse((self.root/'다 빈 폴더').exists())
        self.assertTrue((self.root/'나/잠긴 문서.pdf').is_file())  # 실패한 파일과 그 폴더만 남는다

    def test_continue_organizing_removes_old_folders_left_empty_by_the_first_run(self):
        # 2026-11-28 LIM 연간단가 시연: 처음 정리 뒤 빈 '계약' 폴더가 남았는데 계속 문서 정리로는 지워지지 않았다.
        self.write('계약/계약서.pdf',b'K');self.write('기성/청구.hwp',b'G')
        plan,first=self.run_all({'계약/계약서.pdf':'1 공통/1 사업계획서','기성/청구.hwp':'3 시공단계/1 공문'})
        (self.root/'계약').mkdir();(self.root/'기성'/'빈 하위').mkdir(parents=True)  # 남은 빈 옛 폴더(지우지 못했던 상황 재현)
        (self.root/'사용자 폴더').mkdir();(self.root/'사용자 폴더'/'메모.txt').write_bytes(b'U')  # 파일이 있는 폴더는 그대로
        self.write(app.INBOX+'/새 공문.pdf',b'N')
        plan,second=self.run_all({app.INBOX+'/새 공문.pdf':'3 시공단계/1 공문'},ongoing=True)
        self.assertFalse((self.root/'계약').exists());self.assertFalse((self.root/'기성').exists())
        self.assertTrue((self.root/'사용자 폴더'/'메모.txt').is_file())
        app.undo(second['id']);self.assertTrue((self.root/'계약').is_dir() and (self.root/'기성'/'빈 하위').is_dir())

    def test_continue_organizing_leaves_held_files_in_inbox(self):
        self.write(app.INBOX+'/낱개 메모.txt',b'M');self.write(app.INBOX+'/받은 폴더/회의록.hwp',b'H');self.write(app.INBOX+'/공문.pdf',b'P')
        plan,journal=self.run_all({app.INBOX+'/공문.pdf':'3 시공단계/1 공문'},ongoing=True)
        self.assertEqual(journal['inboxMoves'],[])
        self.assertEqual((self.inbox/'낱개 메모.txt').read_bytes(),b'M')
        self.assertEqual((self.inbox/'받은 폴더/회의록.hwp').read_bytes(),b'H')

    def test_file_placed_by_earlier_run_is_not_pulled_back_into_inbox(self):
        self.write('옛/결재.pdf',b'K')
        plan,first=self.run_all({'옛/결재.pdf':'1 공통/1 사업계획서'})
        (self.root/'1 공통/1 사업계획서/하위').mkdir()
        app.move_no_replace(self.root/'1 공통/1 사업계획서/결재.pdf',self.root/'1 공통/1 사업계획서/하위/결재.pdf')
        app.store_project(app.get_project(self.project['id']))
        hist=app.DATA/'history'/(first['id']+'.json');j=app.read_json(hist)
        j['entries'][0]['destination']='1 공통/1 사업계획서/하위/결재.pdf';app.atomic_json(hist,j)
        self.write(app.INBOX+'/새 공문.pdf',b'Z')
        plan,second=self.run_all({app.INBOX+'/새 공문.pdf':'3 시공단계/1 공문'})
        self.assertTrue((self.root/'1 공통/1 사업계획서/하위/결재.pdf').is_file())
        self.assertEqual([m['source'] for m in second['inboxMoves']],[])


class BundleFirstClassification(unittest.TestCase):
    """2026-11-27 63동 수동정리 비교 보고서 재현(합성 자료): 기존 폴더·첨부 묶음을 먼저 지키고,
    여러 표준 항목이 섞인 폴더만 나눈다. 학내 AI는 호출하지 않는다."""
    C='3 시공단계/1 도급공사 1'
    S='3 시공단계/2 설계의도 구현'
    D='2 설계단계/1 설계 용역'

    def setUp(self):
        import copy
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        self.root=self.base/'사업';self.root.mkdir();data=self.base/'data';data.mkdir()
        self.patcher=patch.object(app,'DATA',data);self.patcher.start()
        self.gateway=patch.object(app,'gateway',side_effect=AssertionError('no AI in tests'));self.gateway.start()
        app.SELECTIONS.clear();app.PLANS.clear();app.SELECTIONS['bundle']=str(self.root)
        tree=[{'label':app.INBOX}]+copy.deepcopy(app.TEMPLATES['design'])
        stage=next(n for n in tree if n['label']=='3 시공단계')
        service=next(n for n in stage['children'] if n['label']=='2 용역1')
        service.update(label='2 설계의도 구현',contractId='intent',contractKind='service')
        stage['children'][0].update(contractId='cons',contractKind='construction')
        self.tree=tree

    def tearDown(self):self.gateway.stop();self.patcher.stop();self.temp.cleanup()

    def write(self,relative,data=None):
        p=self.root/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data or ('SYNTHETIC '+relative).encode());return p

    def project(self,contracts=()):
        project=app.save_project({'selection':'bundle','name':'묶음 우선','type':'design','tree':self.tree},False)
        project['contracts']=list(contracts);app.store_project(project);return project

    def contract(self,ident,relative,kind,title,amendment=False):
        return {'id':ident,'name':Path(relative).name,'sourceRelative':relative,'sourceHash':app.file_hash(self.root/relative),
                'analysis':{'kind':kind,'kind_confirmed':True,'title':title,'party':'합성 업체','signed_date':'2026-01-10','amendment':amendment}}

    def plan(self,project):
        plan=app.make_plan(project['id'],False)
        return plan,{r['relative']:r for r in plan['rows'] if r.get('kind')!='directory'}

    def final(self,row):
        return app.effective_folder(row,row['destination'])+'/'+row['name'] if row['destination'] else ''

    def test_punch_list_bundle_is_not_split_by_inner_photo_folders(self):
        base='2. 시공단계/2. 공사/26. PUNCH LIST'
        for rel in (base+'/260512 PUNCH LIST.xlsm',base+'/260512 사진/현장1.jpg',base+'/260601 게시판 사진/현장2.png'):self.write(rel)
        plan,rows=self.plan(self.project())
        self.assertEqual({self.final(r) for r in rows.values()},{self.C+'/12 준공계/A PUNCH LIST/260512 PUNCH LIST.xlsm',
            self.C+'/12 준공계/A PUNCH LIST/260512 사진/현장1.jpg',self.C+'/12 준공계/A PUNCH LIST/260601 게시판 사진/현장2.png'})

    def test_defect_folder_keeps_its_photo_subfolder(self):
        self.write('2. 시공단계/2. 공사/27. 하자/하자 목록.xlsx');self.write('2. 시공단계/2. 공사/27. 하자/1. 관련사진/누수.jpg')
        plan,rows=self.plan(self.project())
        self.assertTrue(all(r['destination']==self.C+'/16 하자' for r in rows.values()),[r['destination'] for r in rows.values()])
        self.assertTrue(self.final(rows['2. 시공단계/2. 공사/27. 하자/1. 관련사진/누수.jpg']).endswith('/16 하자/A 관련사진/누수.jpg'))

    def test_two_approval_bundles_stay_separate_without_name_collision(self):
        self.write('2. 시공단계/2. 공사/1. 시행품의/0. 결재참조.pdf',b'A');self.write('2. 시공단계/2. 공사/2. 구매품의/0. 결재참조.pdf',b'B')
        project=self.project();plan,rows=self.plan(project)
        got={rel:self.final(r) for rel,r in rows.items()}
        approval=self.C+'/1 최초 품의 및 최초 계약서/1 품의서'
        self.assertEqual(got,{'2. 시공단계/2. 공사/1. 시행품의/0. 결재참조.pdf':approval+'/A 시행품의/0. 결재참조.pdf',
                              '2. 시공단계/2. 공사/2. 구매품의/0. 결재참조.pdf':approval+'/B 구매품의/0. 결재참조.pdf'})
        self.assertEqual(app.move_check(plan['id'],[{'id':r['id'],'destination':r['destination']} for r in rows.values()])['renamed'],[])

    def test_registered_change_contract_goes_to_its_round_not_the_first_contract_folder(self):
        first='2. 시공단계/2. 공사/3. 계약/최초/계약서.pdf';one='2. 시공단계/2. 공사/3. 계약/변경1차/원인행위변경.pdf'
        three='2. 시공단계/2. 공사/3. 계약/변경3차/계약변경.pdf';unknown='2. 시공단계/2. 공사/3. 계약/원인행위변경(재송부).pdf'
        for rel in (first,one,three,unknown):self.write(rel)
        records=[self.contract('cons',first,'construction','합성 건축공사')]
        for i,rel in enumerate((one,three,unknown)):
            records[0].setdefault('versions',[]).append({**self.contract('cons-v%d'%i,rel,'construction','합성 건축공사',True),'name':Path(rel).name})
        plan,rows=self.plan(self.project(records))
        self.assertEqual(rows[first]['destination'],self.C+'/1 최초 품의 및 최초 계약서/2 계약서')
        self.assertEqual(rows[one]['destination'],self.C+'/7 설계변경/1 1차 설계변경')
        self.assertEqual(self.final(rows[three]),self.C+'/7 설계변경/3 3차 설계변경/계약변경.pdf')
        # 차수를 알 수 없는 변경계약은 계약서 칸에 두되 차수 확인을 받는다.
        self.assertTrue(rows[unknown]['amendmentRoundReview'] and rows[unknown]['reviewRequired'])

    def test_change_round_approval_folder_goes_to_that_round(self):
        self.write('2. 시공단계/2. 공사/1. 품의/2. 변경1차 시행품의/합의서.pdf');self.write('2. 시공단계/2. 공사/1. 품의/1. 구매품의/산출서.pdf')
        plan,rows=self.plan(self.project())
        self.assertEqual(rows['2. 시공단계/2. 공사/1. 품의/2. 변경1차 시행품의/합의서.pdf']['destination'],self.C+'/7 설계변경/1 1차 설계변경')

    def test_special_top_level_work_is_held_as_one_bundle_and_moves_whole_into_inbox(self):
        files=['6. 석면관련/1. 경과보고서/붙임1. 현장사진/현장.jpg','6. 석면관련/4. 관련공문/1. 출석요구/공문.pdf',
               '6. 석면관련/2. 고용노동부 관계서류/작업일보 제출본.pdf','6. 석면관련/석면조사 보고서.pdf']
        for rel in files:self.write(rel)
        self.write('2. 시공단계/2. 공사/14. 작업일보/작업일보 0105.pdf')
        project=self.project();plan,rows=self.plan(project)
        for rel in files:
            self.assertEqual((rows[rel]['destination'],rows[rel].get('bundleHold')),('','6. 석면관련'),rel+' · '+rows[rel]['reason'])
        before={p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        ready=[{'id':r['id'],'destination':r['destination']} for r in rows.values() if r['destination']]
        journal=app.execute_all(plan['id'],ready)
        for rel in files:self.assertTrue((self.root/app.INBOX/rel).is_file(),rel)  # 원래 폴더 구조째 정리할 문서 모음으로
        self.assertFalse((self.root/'6. 석면관련').exists())
        app.undo(journal['id'])
        self.assertEqual({p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file() and '.gongmu-chak' not in p.parts},before)

    def test_custom_work_folder_with_photo_subfolder_is_held_whole(self):
        unit='2. 시공단계/2. 공사/11. 실외기 구조 검토'
        for rel in (unit+'/최종 성과품/보고서.pdf',unit+'/현황 사진/지붕.jpg',unit+'/0준공도면(2000)/구조/평면.dwg'):self.write(rel)
        plan,rows=self.plan(self.project())
        self.assertTrue(all(not r['destination'] and r.get('bundleHold')==unit for r in rows.values()),{k:r['destination'] for k,r in rows.items()})

    def test_mixed_folder_is_still_split_by_its_standard_items(self):
        # 여러 표준 항목(착공계·작업일보·사진)이 섞인 사용자 폴더는 나눈다.
        mixed='2. 시공단계/2. 공사/받은 자료'
        for rel in (mixed+'/착공계/착공계.hwp',mixed+'/작업일보/0105.pdf',mixed+'/사진/a.jpg'):self.write(rel)
        plan,rows=self.plan(self.project())
        self.assertEqual({rel:r['destination'] for rel,r in rows.items()},{mixed+'/착공계/착공계.hwp':self.C+'/3 착공계',
            mixed+'/작업일보/0105.pdf':self.C+'/15 작업일보',mixed+'/사진/a.jpg':self.C+'/11 사진'})

    def test_confirmed_contract_links_a_differently_named_service_folder(self):
        root='2. 시공단계/3. 용역/2. 디자인 감리'
        contract=root+'/2. 계약/원인행위(설계의도 구현 용역).pdf'
        for rel in (contract,root+'/1. 품의/1. 구매품의/산출서.pdf',root+'/3. 공문/3. 준공계/완료보고서.pdf'):self.write(rel)
        plan,rows=self.plan(self.project([self.contract('intent',contract,'service','설계의도 구현 용역')]))
        self.assertEqual(rows[contract]['destination'],self.S+'/1 최초 품의 및 최초 계약서/2 계약서')
        self.assertEqual(rows[root+'/1. 품의/1. 구매품의/산출서.pdf']['destination'],self.S+'/1 최초 품의 및 최초 계약서/1 품의서')
        self.assertEqual(rows[root+'/3. 공문/3. 준공계/완료보고서.pdf']['destination'],self.S+'/7 완수계/1 완수계 공문 및 검사 조서')

    def test_handover_inside_the_construction_folder_is_the_contractors_completion_bundle(self):
        self.write('2. 시공단계/2. 공사/24. 인수인계/04.열쇠 인계 확인서/열쇠인계 목록.xlsx')
        plan,rows=self.plan(self.project())
        row=rows['2. 시공단계/2. 공사/24. 인수인계/04.열쇠 인계 확인서/열쇠인계 목록.xlsx']
        self.assertEqual(self.final(row),self.C+'/12 준공계/A 인수인계/04.열쇠 인계 확인서/열쇠인계 목록.xlsx')

    def test_top_level_before_construction_photos_go_to_the_design_service(self):
        self.write('4. 공사전 사진/251209/305호/a.jpg')
        plan,rows=self.plan(self.project())
        self.assertEqual(rows['4. 공사전 사진/251209/305호/a.jpg']['destination'],self.D+'/4 공사전 사진')


class BundleLettersByCreationDate(unittest.TestCase):
    """2026-11-27 LIM: 표준 폴더 하나에 새 묶음 여러 개가 들어오면 원래 폴더가 만들어진 날짜 순으로 A·B·C(합성 자료)."""
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();base=Path(self.temp.name)
        self.root=base/'사업';self.root.mkdir();data=base/'data';data.mkdir()
        self.patcher=patch.object(app,'DATA',data);self.patcher.start()
        app.SELECTIONS.clear();app.PLANS.clear();app.SELECTIONS['letters']=str(self.root)
        self.project=app.save_project({'selection':'letters','name':'날짜 순서','tree':[{'label':app.INBOX},{'label':'1 회의 및 협의기록'}]},False)

    def tearDown(self):self.patcher.stop();self.temp.cleanup()

    def test_letters_follow_folder_creation_order_not_names_or_numbers(self):
        import time
        made=[]
        for i,folder in enumerate(('3. 나중 번호지만 먼저 만든 협의','1. 두 번째로 만든 회의','2. 가장 늦게 만든 회의')):
            path=self.root/'옛 자료'/folder/'회의록.txt';path.parent.mkdir(parents=True);path.write_bytes(('synthetic %d'%i).encode())
            stamp=1_780_000_000+i*86400;os.utime(path,(stamp,stamp));made.append(folder);time.sleep(0.05)
        plan=app.make_plan(self.project['id'],False)
        names={r['relative'].split('/')[1]:r['keepSub'].split('/')[0] for r in plan['rows']}
        self.assertEqual(names,{made[0]:'A 나중 번호지만 먼저 만든 협의',made[1]:'B 두 번째로 만든 회의',made[2]:'C 가장 늦게 만든 회의'})

    def test_without_any_date_the_old_number_order_is_kept(self):
        rows=[{'relative':'x/2. 나/a.txt','mtime':0},{'relative':'x/1. 가/b.txt','mtime':0}]
        self.assertIsNone(app.folder_created(self.root,'없는 폴더/1. 가',[rows[1]]))


class AnnualTemplates(unittest.TestCase):
    """2026-11-28 LIM: 연간단가 표준 트리(합성 자료)."""
    def labels(self,nodes):return [n['label'] for n in nodes]

    def test_annual_types_have_no_common_branch(self):
        for name in [k for k in app.TEMPLATES if k.startswith('annual-')]:
            self.assertFalse(any('공통' in n['label'] for n in app.TEMPLATES[name]),name)

    def test_direct_construction_gets_schedule_and_defects_like_other_types(self):
        branch=app.TEMPLATES['annual-construction-direct'][0]['children'][0]
        kids=self.labels(branch['children'])
        self.assertEqual(kids[kids.index('3 착공계')+1],'4 공정표')
        self.assertEqual(kids[-1],'14 하자')
        self.assertIn('2 시공사에 제공 한 자료',kids)
        self.assertNotIn('하도급 통보',' '.join(kids));self.assertNotIn('승인요청',' '.join(kids))

    def test_work_only_types_sit_directly_under_the_project_folder(self):
        for name,orders in (('annual-construction-workOnly',['1 현장1','2 현장2']),('annual-service-workOnly',['1 작업지시서 1차 및 계약서','2 작업지시서 2차 및 계약서'])):
            tree=app.TEMPLATES[name]
            self.assertEqual(self.labels(tree),['1 품의 및 계약서','2 회의 및 협의기록','3 작업지시서'],name)
            self.assertEqual(self.labels(tree[0]['children']),['1 품의서','2 계약서'],name)
            self.assertEqual(self.labels(tree[2]['children']),orders,name)

    def test_work_only_contract_goes_to_the_top_level_contract_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'연간단가 사업';data=base/'data';data.mkdir()
            source=root/'받은 자료/연간단가 계약서.pdf';source.parent.mkdir(parents=True);source.write_bytes(b'SYNTHETIC annual contract')
            with patch.object(app,'DATA',data),patch.object(app,'gateway',side_effect=AssertionError('no AI')):
                app.SELECTIONS['annual']=str(root)
                tree=[{'label':app.INBOX}]+__import__('copy').deepcopy(app.TEMPLATES['annual-construction-workOnly'])
                project=app.save_project({'selection':'annual','name':'가상 연간단가','type':'annual','tree':tree},False)
                project['contracts']=[{'id':'a','name':source.name,'sourceRelative':'받은 자료/'+source.name,'sourceHash':app.file_hash(source),
                    'analysis':{'kind':'construction','kind_confirmed':True,'title':'가상 시설물 보수공사 연간단가','party':'가상건설','signed_date':'2026-01-05','annual':True}}]
                app.store_project(project)
                row=app.make_plan(project['id'],False)['rows'][0]
                self.assertEqual(row['destination'],'1 품의 및 계약서/2 계약서',row['reason'])


class OldFolderRemovalOnBusyPC(unittest.TestCase):
    """2026-11-28 LIM 연간단가 시연(OneDrive 폴더): 파일은 다 빠졌는데 옛 폴더가 남음. 합성 자료."""
    def test_briefly_locked_empty_folder_is_retried_then_removed(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'계약';target.mkdir()
            real=Path.rmdir;calls=[]
            def busy(self):
                calls.append(1)
                if len(calls)<3:raise PermissionError(5,'다른 프로세스가 사용 중')
                return real(self)
            with patch.object(Path,'rmdir',busy),patch.object(app.time,'sleep'):
                app.remove_empty_folder(target)
            self.assertFalse(target.exists());self.assertEqual(len(calls),3)

    def test_kept_folder_reason_names_what_is_left(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'기성';target.mkdir();(target/'남은 파일.hwp').write_bytes(b'x')
            with self.assertRaises(OSError) as raised:app.remove_empty_folder(target)
            self.assertIn('남은 파일.hwp',app.kept_reason(target,raised.exception))
            empty=Path(folder)/'회의자료';empty.mkdir()
            self.assertIn('다른 프로그램',app.kept_reason(empty,PermissionError(5,'denied')))


def simple_text_pdf(path, lines):
    """글자 층이 있는 아주 작은 PDF(ASCII 글자, 합성)."""
    body='BT /F1 12 Tf 50 750 Td '+' '.join('(%s) Tj 0 -16 Td'%l for l in lines)+' ET'
    objects=['<< /Type /Catalog /Pages 2 0 R >>','<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
             '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
             '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>','<< /Length %d >>\nstream\n%s\nendstream'%(len(body),body)]
    out=b'%PDF-1.4\n';offsets=[]
    for i,o in enumerate(objects,1):offsets.append(len(out));out+=('%d 0 obj\n%s\nendobj\n'%(i,o)).encode('latin-1')
    xref=len(out);out+=('xref\n0 %d\n0000000000 65535 f \n'%(len(objects)+1)).encode()+b''.join(b'%010d 00000 n \n'%o for o in offsets)
    out+=('trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n'%(len(objects)+1,xref)).encode();Path(path).write_bytes(out)


class DemoContractReading(unittest.TestCase):
    """2026-11-28 LIM 시연: '공사연간단가_계약서.pdf'(글자 층 있는 가상 계약서)를 자동·수동 모두 못 읽음. 합성 자료, 학내 AI 없음."""
    LAYER=('공사연간단가_계약서\n문서구분: 시연용 가상 계약서\n계약번호: DEMO-A-2026-001\n사업명: 2026년 가상대학교 시설물 보수공사 연간단가\n'
           '계약명: 2026년 가상대학교 시설물 보수공사 연간단가\n계약종류: 공사 연간단가\n계약상대자: 가상보수건설 주식회사\n'
           '계약체결일: 2026-01-05\n계약기간: 2026-01-10 ~ 2026-12-31\n계약금액: 100,000,000원')

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.data=Path(self.temp.name)/'data';(self.data/'staging').mkdir(parents=True)
        self.patcher=patch.object(app,'DATA',self.data);self.patcher.start()
        image=self.data/'staging'/'c1.jpg';Image.new('RGB',(20,20),'white').save(image)
        app.atomic_json(self.data/'staging'/'c1.json',{'id':'c1','name':'공사연간단가_계약서.pdf','path':str(image),'preparedFrom':'PDF 전체 1쪽 중 1쪽 이미지','textLayer':self.LAYER})

    def tearDown(self):self.patcher.stop();self.temp.cleanup()

    def test_model_answer_wrapped_in_a_list_is_accepted(self):
        reply={'choices':[{'message':{'content':'[{"title":"가상 보수공사 연간단가","kind":"construction"}]'},'finish_reason':'stop'}]}
        class Response(io.BytesIO):
            def __enter__(self):return self
            def __exit__(self,*a):return False
        with patch.object(app,'load_key',return_value='synthetic-key'),patch.object(app,'read_json',side_effect=lambda p,d=None:{'model':'demo'} if str(p).endswith('ai.json') else d),\
             patch.object(app.urllib.request,'urlopen',return_value=Response(json.dumps(reply).encode())):
            self.assertEqual(app.gateway([{'role':'user','content':'x'}])['title'],'가상 보수공사 연간단가')

    def test_text_layer_is_sent_and_used_when_the_answer_stays_broken(self):
        sent=[]
        def broken(messages,**k):
            sent.append(messages);raise app.AIResponseError('AI가 올바른 결과를 보내지 않았습니다. 다시 검토하거나 보류해주세요.')
        with patch.object(app,'gateway',side_effect=broken):
            record=app.analyze_contract('c1')
        self.assertTrue(any('계약상대자: 가상보수건설' in part.get('text','') for part in sent[0][1]['content']))
        a=record['analysis']
        self.assertEqual((a['title'],a['party'],a['signed_date'],a['kind'],a['annual'],a['uncertain']),
                         ('2026년 가상대학교 시설물 보수공사 연간단가','가상보수건설 주식회사','2026-01-05','construction',True,True))
        self.assertIn('확인 필요',record['sent'])

    def test_scanned_contract_without_text_still_reports_the_error(self):
        app.atomic_json(self.data/'staging'/'c1.json',{**app.read_json(self.data/'staging'/'c1.json'),'textLayer':''})
        with patch.object(app,'gateway',side_effect=app.AIResponseError('AI가 올바른 결과를 보내지 않았습니다.')):
            with self.assertRaises(app.AIResponseError):app.analyze_contract('c1')

    def test_pdf_text_layer_is_read_from_the_chosen_pages(self):
        pdf=Path(self.temp.name)/'contract.pdf';simple_text_pdf(pdf,['Contract name: DEMO annual repair','Party: DEMO Construction'])
        self.assertIn('DEMO Construction',app.pdf_text_layer(pdf,[0]))


if __name__=='__main__':unittest.main()
