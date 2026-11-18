"""Regression coverage for local discovery, canonical storage and folder links."""
import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import app


class AutomationRegression(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / '사업'; self.root.mkdir()
        self.data = self.base / 'settings'; self.data.mkdir()
        self.data_patch = patch.object(app, 'DATA', self.data); self.data_patch.start()
        app.SELECTIONS.clear(); app.PLANS.clear(); app.JOBS.clear(); app.CONTRACT_CANDIDATES.clear()
        app.SELECTIONS['selected'] = str(self.root)
        self.tree = [{'label': app.INBOX}, {'label':'1 공통','children':[
            {'label':'1 주요 보고자료'}, {'label':'2 타기관 협의자료','children':[
                {'label':'1 공문 및 협의기록','children':[{'label':'1 수신'},{'label':'2 발신'}]},
                {'label':'2 학내 안내'}, {'label':'3 민원'}]}]},
            {'label':'2 시공단계','children':[{'label':'1 도급공사','children':[{'label':'1 사진','children':[{'label':'1 공사전'},{'label':'2 공사후'}]}]}]}]
        self.project = app.save_project({'selection':'selected','name':'시험','tree':self.tree},False)
        self.report = '1 공통/1 주요 보고자료'
        self.photo = '2 시공단계/1 도급공사/1 사진/1 공사전'
        self.mail = '1 공통/2 타기관 협의자료/1 공문 및 협의기록'

    def tearDown(self):
        self.data_patch.stop(); self.temp.cleanup()

    def write(self, relative, data=b'document'):
        path=self.root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);return path

    def plan(self):
        return app.make_plan(self.project['id'],False)

    def execute(self, plan):
        return app.execute_all(plan['id'],[{'id':r['id'],'destination':r['destination']} for r in plan['rows'] if not r['done'] and r.get('destination')])

    def record(self, ident, date, **fields):
        analysis={'title':'창호개선 공사','party':'가건설','kind':'construction','signed_date':date,'contract_number':'A-1','period':'2026.01~12','amount':'100'}
        analysis.update(fields)
        return {'id':ident,'name':ident+' 계약서.pdf','analysis':analysis}

    def test_candidates_are_local_and_do_not_call_gateway(self):
        self.write('계약/공사 계약서.txt');self.write('계약/변경계약서 양식.txt')
        self.write('사진/현장.jpg');self.write('.gongmu-chak/contracts/계약서.pdf')
        with patch.object(app,'gateway',side_effect=AssertionError('no network during search')):
            found=app.contract_candidates({'selection':'selected'})
        self.assertEqual([r['name'] for r in found['candidates']],['공사 계약서.txt'])

    def test_discovery_hash_cache_and_user_corrections_are_reused(self):
        self.write('공사 계약서.txt','계약 내용'.encode())
        (self.data/'api-key.dpapi').write_bytes(b'test-only')
        with patch.object(app,'gateway',return_value=self.record('a','2026-10-01')['analysis']) as gateway:
            first=app.auto_contract(app.contract_candidates({'selection':'selected'})['candidates'][0]['candidate'])
            app.update_contract(first['id'],{'amount':'확인한 금액'})
            self.write('다른경로/공사 계약서 사본.txt','계약 내용'.encode())
            found=app.contract_candidates({'selection':'selected'})
            results=[app.auto_contract(c['candidate']) for c in found['candidates']]
            self.assertEqual(gateway.call_count,1)
            self.assertTrue(all(r['cached'] for r in results))
            self.assertTrue(all(r['analysis']['amount']=='확인한 금액' for r in results))
            self.assertEqual(len({r['id'] for r in results}),1)

    def test_changed_candidate_and_unknown_token_are_rejected(self):
        source=self.write('계약서.txt',b'before')
        token=app.contract_candidates({'selection':'selected'})['candidates'][0]['candidate']
        source.write_bytes(b'changed content')
        with self.assertRaises(ValueError):app.auto_contract(token)
        with self.assertRaises(ValueError):app.auto_contract('../escape')

    def test_no_ai_key_does_not_send_documents(self):
        self.write('계약서.txt',b'contract')
        token=app.contract_candidates({'selection':'selected'})['candidates'][0]['candidate']
        with patch.object(app,'gateway',side_effect=AssertionError('no key')):
            result=app.auto_contract(token)
        self.assertIn('AI 연결',result['discoveryError'])
        self.assertTrue(Path(result['path']).exists())

    def test_latest_signed_contract_merges_changes_without_losing_original_fields(self):
        old=self.record('old','2026-01-03')
        new=self.record('new','2026-10-01',title='창호개선 공사 (1차 변경)',period=None,amount='200')
        result=app.resolve_contract_versions([new,old])
        self.assertEqual(len(result['current']),1)
        current=result['current'][0]
        self.assertEqual(current['id'],'new');self.assertEqual(current['analysis']['amount'],'200')
        self.assertEqual(current['analysis']['period'],'2026.01~12')
        self.assertEqual(current['supersededIds'],['old'])
        self.assertEqual(len(result['archived']),1)
        again=app.resolve_contract_versions(result['current'])['current'][0]
        self.assertEqual(len(again['versions']),2)
        self.assertEqual(again['supersededIds'],['old'])

    def test_ambiguous_contracts_are_not_silently_merged(self):
        for change in ({'party':'나건설'},{'contract_number':'B-1'},{'signed_date':''},{'signed_date':'2026-01-03'}):
            with self.subTest(change=change):
                records=[self.record('old','2026-01-03'),self.record('new','2026-10-01',**change)] if 'signed_date' not in change else [self.record('old','2026-01-03'),self.record('new',change['signed_date'])]
                self.assertEqual(len(app.resolve_contract_versions(records)['current']),2)





    def test_date_correspondence_batch_is_red_and_retargets_as_one_folder(self):
        prefix='1 공통/15 타기관 협의자료/1501 공문 및 협의기록/260327 캠퍼스 관리과 메일'
        for n in range(8):self.write(prefix+'/'+('하위/' if n==7 else '')+str(n)+('.jpg' if n<3 else '.txt'),str(n).encode())
        plan=self.plan();self.assertEqual(len(plan['rows']),8)
        self.assertTrue(all(r.get('reviewRequired') for r in plan['rows']))
        self.assertEqual(len({r['folderGroup'] for r in plan['rows']}),1)
        with self.assertRaisesRegex(ValueError,'보관 위치를 먼저 확인'):
            self.execute(plan)
        self.assertTrue((self.root/prefix/'0.jpg').is_file())
        result=app.retarget_many(plan['id'],[plan['rows'][0]['id']],self.mail+'/1 수신')
        self.assertEqual(len(result['rows']),8)
        self.assertTrue(all(not r['reviewRequired'] for r in result['rows']))
        self.assertTrue(all(r['keepSub'].startswith('A 260327 캠퍼스 관리과 메일') for r in result['rows']))
        self.execute(plan)
        target=self.root/self.mail/'1 수신/A 260327 캠퍼스 관리과 메일'
        self.assertEqual(len(list(target.rglob('*.*'))),8)
        self.assertTrue((target/'하위/7.txt').is_file())
        self.assertFalse((self.root/prefix).exists())

    def test_same_date_in_different_source_contexts_is_not_one_group(self):
        self.write('협의자료/기관A/261001 회신/a.txt')
        self.write('협의자료/기관B/261001 회신/b.txt')
        plan=self.plan()
        self.assertEqual(len({r['folderGroup'] for r in plan['rows']}),2)

    def test_normal_move_creates_no_shortcut_or_copy(self):
        self.write('주요 보고자료/261001 보고/공사전 사진.jpg',b'photo')
        plan=self.plan();row=plan['rows'][0];app.retarget_many(plan['id'],[row['id']],self.photo)
        with patch.object(app,'make_shortcut',side_effect=AssertionError('no daily shortcuts')):journal=self.execute(plan)
        self.assertEqual(journal['folderShortcuts'],[])
        files=[p for p in self.root.rglob('*') if p.is_file() and '.gongmu-chak' not in p.parts]
        self.assertEqual([p.name for p in files],['공사전 사진.jpg'])


if __name__=='__main__':unittest.main()
