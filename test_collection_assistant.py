"""Synthetic regressions for plain-language search and contract-family rules."""
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import app
import collection_assistant as assistant


class PlainLanguageCollections(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();base=Path(self.temp.name)
        self.data=base/'settings';self.root=base/'project';self.root.mkdir()
        self.patch=patch.object(app,'DATA',self.data);self.patch.start()
        app.SELECTIONS['assistant-test']=str(self.root)
        self.project=app.save_project({'selection':'assistant-test','name':'샘플','tree':[{'label':app.INBOX},{'label':'1 공문'}]},False)
        self.pid=self.project['id']

    def tearDown(self):
        self.patch.stop();self.temp.cleanup()

    def file(self,name,text):
        p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8');return p

    def item(self,query='공정 변경 관련 자료',official=False):
        c=app.parse_collection('');c.update(text=query,semanticQuery=json.dumps({'request':query,'summary':query},ensure_ascii=False),officialOnly=official)
        return app.save_collection(self.pid,{'name':query,'conditions':c})

    def ready(self,**extra):
        return {'name':'찾는 자료','summary':'사용자가 쓴 조건','question':None,**extra}

    def test_contractor_letters_are_searched_only_in_construction_letter_folders(self):
        # 2026-11-28 LIM: '시공사 공문'은 시공단계 도급공사의 기타공문·착공계·준공계·기성·설계변경 등에서 찾는다.
        p=app.get_project(self.pid)
        p['tree']=[{'label':app.INBOX},{'label':'1 공통','children':[{'label':'4 타기관 협의자료'}]},
                   {'label':'3 시공단계','children':[{'label':'1 도급공사','children':[{'label':'3 착공계'},{'label':'5 지출서류','children':[{'label':'3 기성'}]},
                    {'label':'7 설계변경'},{'label':'9 승인요청'},{'label':'12 준공계'},{'label':'14 기타공문'},{'label':'15 작업일보'}]}]}]
        app.store_project(p)
        inside=['3 시공단계/1 도급공사/3 착공계/착공계 제출.txt','3 시공단계/1 도급공사/5 지출서류/3 기성/1회 기성 청구.txt',
                '3 시공단계/1 도급공사/7 설계변경/설계변경 요청.txt','3 시공단계/1 도급공사/9 승인요청/자재승인 요청.txt',
                '3 시공단계/1 도급공사/12 준공계/준공계.txt','3 시공단계/1 도급공사/14 기타공문/A 260227 회신/공문.txt']
        outside=['3 시공단계/1 도급공사/15 작업일보/일보.txt','1 공통/4 타기관 협의자료/캠퍼스 공문.txt','기타/메모.txt']
        for name in inside+outside:self.file(name,'수신 가상대학교 시설지원과 발신 가상건설 문서번호 가상-1 제목 '+name)
        item=self.item('이 사업 시공사가 보낸 공문 모두')
        result=app.run_collection(self.pid,item['id'],group_contracts=False)
        self.assertEqual(sorted(r['relative'] for r in result['candidates']),sorted(inside))
        self.assertIn('기타공문',result['scopeNote']);self.assertIn('착공계',result['scopeNote'])
        other=self.item('공정 변경 관련 자료')  # 시공사 공문이 아니면 범위를 좁히지 않는다
        self.assertEqual(len(app.run_collection(self.pid,other['id'],group_contracts=False)['candidates']),len(inside+outside))

    def test_contractor_letters_fall_back_to_whole_project_before_organizing(self):
        self.file('옛 폴더/시공사 공문.txt','수신 가상대학교 발신 가상건설')
        item=self.item('시공사 공문 찾아줘')
        result=app.run_collection(self.pid,item['id'],group_contracts=False)
        self.assertEqual([r['relative'] for r in result['candidates']],['옛 폴더/시공사 공문.txt'])
        self.assertNotIn('scopeNote',result)

    def test_clear_request_does_not_ask_for_document_type(self):
        with patch.object(app,'gateway',return_value=self.ready()) as gateway:
            result=assistant.assist(app,{'id':self.pid,'text':'지난달 시공사가 보낸 공문 중 창호 관련만'})
        self.assertEqual(result['status'],'ready');self.assertNotIn('question',result)
        self.assertIn('semanticQuery',result['collection']['conditions'])
        self.assertEqual(gateway.call_count,1)

    def test_clarifications_stop_at_two_and_unknown_is_not_a_match(self):
        question={'name':'자료','summary':'날짜 확인','question':{'text':'최근은 어느 기간인가요?','options':['이번 달','지난 달']}}
        with patch.object(app,'gateway',return_value=question):
            first=assistant.assist(app,{'id':self.pid,'text':'최근 자료'})
            second=assistant.assist(app,{'id':self.pid,'session':first['session'],'answer':'지난 달'})
            ready=assistant.assist(app,{'id':self.pid,'session':second['session'],'answer':'설계사 자료'})
        self.assertEqual((first['round'],second['round']),(1,2));self.assertEqual(ready['status'],'ready')
        self.assertTrue(ready['collection']['conditions']['unresolved'])

    def test_failed_question_call_can_be_retried_without_losing_answer(self):
        with patch.object(app,'gateway',return_value={'question':{'text':'언제인가요?','options':[]}}):
            first=assistant.assist(app,{'id':self.pid,'text':'최근 자료'})
        with patch.object(app,'gateway',side_effect=ValueError('일시 오류')):
            with self.assertRaises(ValueError):assistant.assist(app,{'id':self.pid,'session':first['session'],'answer':'3월'})
        with patch.object(app,'gateway',return_value=self.ready()):
            result=assistant.assist(app,{'id':self.pid,'session':first['session'],'answer':'3월'})
        self.assertEqual(result['status'],'ready')

    def test_unknown_filename_is_checked_from_its_body_and_result_is_cached(self):
        self.file('002839.txt','발주처가 검토한 창호 공정 변경 일정입니다.')
        item=self.item();seen=[]
        def gateway(messages):
            seen.append(messages)
            return {'results':[{'fileId':'d0','decision':'match','evidence':{'내용':'창호 공정 변경 일정'}}]}
        with patch.object(app,'gateway',side_effect=gateway):
            job=assistant.start_search(app,self.pid,item['id'])
            for _ in range(100):
                state=assistant.search_status(app,self.pid,job['id'])
                if state['status']!='running':break
                time.sleep(.01)
            self.assertEqual(state['status'],'done');self.assertEqual(len(state['run']['verified']),1)
            job=assistant.start_search(app,self.pid,item['id'])
            for _ in range(100):
                state=assistant.search_status(app,self.pid,job['id'])
                if state['status']!='running':break
                time.sleep(.01)
        self.assertEqual(len(seen),1)
        self.assertIn('창호 공정 변경 일정',json.dumps(seen,ensure_ascii=False))

    def test_changed_file_during_ai_call_is_not_cached(self):
        p=self.file('007.txt','창호 일정');item=self.item();rows=app.run_collection(self.pid,item['id'])['candidates']
        def change(messages):
            p.write_text('바뀐 내용',encoding='utf-8')
            return {'results':[{'fileId':'d0','decision':'match','evidence':{'내용':'창호'}}]}
        with patch.object(app,'gateway',side_effect=change):done,failed=assistant.check_batch(app,self.pid,item,rows)
        self.assertFalse(done);self.assertEqual(len(failed),1)
        self.assertFalse(app.get_project(self.pid).get('collectionChecks'))

    def test_official_requires_structure_but_other_document_types_do_not(self):
        self.file('공정표.txt','공정표 본문');item=self.item(official=True)
        answer={'results':[{'fileId':'d0','decision':'match','evidence':{'본문':'공정표'}}]}
        with patch.object(app,'gateway',return_value=answer):
            assistant.check_batch(app,self.pid,item,app.run_collection(self.pid,item['id'])['candidates'])
        self.assertEqual(len(app.run_collection(self.pid,item['id'])['unclear']),1)
        item=self.item('공문은 제외하고 공정표만',official=False)
        with patch.object(app,'gateway',return_value=answer):
            assistant.check_batch(app,self.pid,item,app.run_collection(self.pid,item['id'])['candidates'])
        self.assertEqual(len(app.run_collection(self.pid,item['id'])['verified']),1)

    def test_employment_contract_is_excluded_by_name_and_body_title(self):
        self.file('근로 계약서.txt','내용')
        self.file('00003.txt','표준 근로계약서\n사용자와 근로자')
        self.file('공사계약서.txt','공사 표준계약서\n근로계약서 제출 의무를 준수한다.')
        result=app.run_collection(self.pid,self.item('계약서')['id'])
        self.assertEqual([r['name'] for r in result['candidates']],['공사계약서.txt'])
        self.assertEqual(result['excludedEmployment'],2)
        self.assertFalse(app.probable_contract_file({'name':'근로계약서.pdf','relative':'계약서/근로계약서.pdf'}))

    def test_ai_detected_employment_contract_is_not_shown_even_with_numeric_name(self):
        self.file('00004.txt','계약 당사자의 권리와 의무를 정한다.')
        item=self.item('계약서');rows=app.run_collection(self.pid,item['id'])['candidates']
        with patch.object(app,'gateway',return_value={'results':[{'fileId':'d0','decision':'match','isEmploymentContract':True,'evidence':{'제목':'근로 계약'}}]}):
            assistant.check_batch(app,self.pid,item,rows)
        result=app.run_collection(self.pid,item['id'])
        self.assertFalse(any(result[k] for k in ('verified','candidates','unclear','mismatch')))
        self.assertEqual(result['excludedEmployment'],1)

    def test_same_title_and_party_is_one_contract_even_if_numbers_differ(self):
        def record(cid,date,number,party='가건설'):
            return {'id':cid,'name':cid+'.pdf','analysis':{'title':'창호 개선 공사','party':party,'signed_date':date,'kind':'construction','contract_number':number}}
        original=record('first','2026-05-01','A-1');changed=record('change','2026-09-01','B-99')
        result=app.resolve_contract_versions([original,changed])
        self.assertEqual(len(result['current']),1);self.assertEqual(result['current'][0]['id'],'change')
        self.assertEqual(len(result['current'][0]['versions']),2)
        self.assertEqual(len(app.resolve_contract_versions([original,record('other','2026-09-01','C','나건설')])['current']),2)
        self.assertNotEqual(app.contract_identity('설계변경 검토 용역','가건설'),app.contract_identity('설계 검토 용역','가건설'))

    def test_contract_cards_group_versions_without_hiding_any_file(self):
        records=[{'relative':'최초.pdf','name':'최초.pdf','isContract':True,'contractTitle':'창호 공사','party':'가건설','signed_date':'2026-05-01'},
                 {'relative':'변경.pdf','name':'변경.pdf','isContract':True,'contractTitle':'창호 공사','party':'가건설','signed_date':'2026-09-01'}]
        result=app.group_contract_results({'verified':records,'unclear':[],'candidates':[],'mismatch':[]})
        self.assertEqual(len(result['verified']),1);self.assertEqual(result['verified'][0]['name'],'변경.pdf')
        self.assertEqual({v['relative'] for v in result['verified'][0]['versions']},{'최초.pdf','변경.pdf'})

    def test_route_confirmation_preserves_names_destinations_and_bytes(self):
        p=self.file('001.txt','자료');plan=app.make_plan(self.pid,False);row=plan['rows'][0]
        row.update(destination='1 공문',reviewRequired=True,proposedName='원래 제안.txt')
        before=p.read_bytes();result=app.confirm_route(plan['id'],row['id'])
        self.assertTrue(result['rows'][0]['reviewed']);self.assertEqual(row['destination'],'1 공문')
        self.assertEqual(row['proposedName'],'원래 제안.txt');self.assertEqual(p.read_bytes(),before)

    def test_confirming_hold_leaves_the_file_and_history_route_unchanged(self):
        p=self.file('미분류/원본.txt','변경된 협의자료')
        plan=app.make_plan(self.pid,False);row=plan['rows'][0]
        row.update(destination='',historyReview=True,coverageOrigin='1 공문',reviewRequired=True)
        before=p.read_bytes()
        result=app.confirm_route(plan['id'],row['id'])
        self.assertTrue(result['rows'][0]['holdConfirmed'])
        self.assertEqual(row['destination'],'')
        self.assertNotIn(row, [r for batch in app.bulk_batches(plan,True) for r in batch])
        self.assertEqual(p.read_bytes(),before)
        self.assertFalse((self.root/'1 공문'/p.name).exists())
        self.assertFalse(list((self.data/'journals').glob('*.json')))

    def test_confirming_bundle_hold_does_not_confirm_an_unrelated_file(self):
        for name in ('묶음/첫째.txt','묶음/둘째.txt','기타/셋째.txt'):self.file(name,'합성자료')
        plan=app.make_plan(self.pid,False)
        for row in plan['rows']:
            row.update(destination='',reviewRequired=True,folderGroup='bundle' if row['relative'].startswith('묶음/') else 'other')
        target=next(r for r in plan['rows'] if r['folderGroup']=='bundle')
        result=app.confirm_route(plan['id'],target['id'])
        self.assertEqual(len(result['rows']),2)
        self.assertTrue(all(r['holdConfirmed'] for r in result['rows']))
        self.assertFalse(next(r for r in plan['rows'] if r['folderGroup']=='other').get('holdConfirmed'))

    def test_confirm_route_rejects_invalid_or_completed_rows(self):
        self.file('자료.txt','합성자료');plan=app.make_plan(self.pid,False);row=plan['rows'][0]
        row['destination']='구조에 없는 폴더'
        with self.assertRaises(Exception):app.confirm_route(plan['id'],row['id'])
        row.update(destination='',done=True)
        with self.assertRaises(Exception):app.confirm_route(plan['id'],row['id'])

    def test_history_download_has_paths_but_no_bodies_keys_or_absolute_root(self):
        self.file('자료.txt','PRIVATE_DOCUMENT_BODY')
        app.atomic_json(self.data/'ai.json',{'model':'test-model','key':'PRIVATE_API_KEY'})
        result=app.history_summary(self.pid)
        self.assertTrue(result['name'].endswith('.txt'));self.assertIn('자료.txt',result['text'])
        for secret in ('PRIVATE_DOCUMENT_BODY','PRIVATE_API_KEY',str(self.root)):
            self.assertNotIn(secret,result['text'])

    def test_model_change_invalidates_existing_ai_verification_context(self):
        first=app.verification_context(self.project,'자료.txt')
        app.atomic_json(self.data/'ai.json',{'model':'a-more-capable-model'})
        second=app.verification_context(self.project,'자료.txt')
        self.assertNotEqual(app.verify_key('same-file',{},first),app.verify_key('same-file',{},second))


if __name__=='__main__':unittest.main()
