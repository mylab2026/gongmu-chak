"""Cumulative archive regressions on temporary, synthetic documents only."""
import base64
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import app


class CumulativeHistory(unittest.TestCase):
    def test_windows_alias_and_unc_errors_hide_absolute_paths(self):
        project={'root':r'C:\Users\Runner Admin\project'}
        raw={'error':r'테스트 잠금: C:\Users\RUNNER~1\project\첨부.txt',
             'unc':r'공유 잠금: \\server\share\project\첨부.txt',
             'relative':'미분류/첨부.txt'}
        clean=app.run_history.clean(raw,project)
        self.assertEqual(clean['error'],'테스트 잠금: [절대 경로 숨김]')
        self.assertEqual(clean['unc'],'공유 잠금: [네트워크 경로 숨김]')
        self.assertEqual(clean['relative'],raw['relative'])

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        self.data=self.base/'settings';self.root=self.base/'project';self.root.mkdir()
        self.patch=patch.object(app,'DATA',self.data);self.patch.start()
        self.plans=patch.dict(app.PLANS,{},clear=True);self.plans.start()
        app.SELECTIONS['archive-test']=str(self.root)
        self.project=app.save_project({'selection':'archive-test','name':'합성 이력 사업','tree':[{'label':app.INBOX},{'label':'1 공문'}]},False)
        self.pid=self.project['id']

    def tearDown(self):
        self.plans.stop();self.patch.stop();self.temp.cleanup()

    def file(self,name,body='SYNTHETIC_DOCUMENT_BODY'):
        path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(body);return path

    def plan(self,name):
        self.file('미분류/'+name);p=app.make_plan(self.pid,False)
        row=next(r for r in p['rows'] if r['name']==name)
        app.retarget(p['id'],row['id'],'1 공문')
        return p,row

    def move(self,p,row):
        return app.execute_all(p['id'],[{'id':row['id'],'destination':row['destination']}])

    def archive(self):
        result=app.dispatch('/history-archive',{'id':self.pid})
        self.assertTrue(result['name'].endswith('.zip'))
        z=zipfile.ZipFile(io.BytesIO(base64.b64decode(result['data'])))
        self.assertIsNone(z.testzip())
        return result,z

    def snapshots(self,z):
        return [json.loads(z.read(n)) for n in z.namelist() if n.endswith('/상세 기록.json')]

    def test_same_second_multiple_runs_and_days_survive_restart_and_undo(self):
        with patch.object(app.run_history,'stamp',return_value='2026-11-19T23:59:59.000000+09:00'):
            p,r=self.plan('첫째.txt');j=self.move(p,r);app.finish_plan(p['id'])
            p2,r2=self.plan('둘째.txt');self.move(p2,r2);app.finish_plan(p2['id'])
        old={f:f.read_bytes() for f in (self.data/'run-history').rglob('*.json')}
        with patch.object(app.run_history,'stamp',return_value='2026-11-20T00:00:01.000000+09:00'):
            p3,r3=self.plan('셋째.txt');self.move(p3,r3);app.finish_plan(p3['id'])
            app.undo(j['id'])
        app.PLANS.clear()  # A later app process has no in-memory plans.
        result,z=self.archive();self.assertEqual(result['runCount'],3)
        docs=self.snapshots(z);self.assertEqual(len(docs),3)
        self.assertEqual(len([n for n in z.namelist() if n.startswith('2026-11-19/') and n.endswith('정리 이력.txt')]),2)
        self.assertEqual(len([n for n in z.namelist() if n.startswith('2026-11-20/') and n.endswith('정리 이력.txt')]),1)
        first=next(d for d in docs if d['runId']==p['id'])
        states=[e['journal']['entries'][0]['status'] for e in first['events'] if e.get('journal') and e['journal']['entries']]
        self.assertIn('moved',states);self.assertIn('restored',states)
        for path,body in old.items():self.assertEqual(path.read_bytes(),body)
        self.assertTrue((self.root/'미분류/첫째.txt').exists())

    def test_two_move_batches_are_one_run_and_include_remaining_holds(self):
        self.file('분류대기/확인필요.bin');p,r=self.plan('선택1.txt')
        self.file('추가/선택2.txt');p=app.make_plan(self.pid,False)
        targets=[r for r in p['rows'] if r['name'].startswith('선택')]
        # 고른 파일만 옮기는 이동(/execute)을 두 번. '파일 이동 실행'(execute_all)은 보류를 정리할 문서 모음으로 함께 옮긴다(2026-11-27).
        for r in targets:app.retarget(p['id'],r['id'],'1 공문');app.execute(p['id'],[{'id':r['id'],'destination':r['destination']}])
        app.finish_plan(p['id'])
        result,z=self.archive();self.assertEqual(result['runCount'],1)
        doc=self.snapshots(z)[0]
        self.assertEqual(len([e for e in doc['events'] if e['type']=='파일 이동 결과']),2)
        finish=next(e['finish'] for e in doc['events'] if e.get('finish'))
        self.assertEqual(finish['remainingCount'],1)
        self.assertIn('확인필요.bin',json.dumps(finish,ensure_ascii=False))

    def test_old_journals_are_all_imported_without_50_run_or_300_entry_limit(self):
        for i in range(51):
            entries=[{'id':str(k),'source':f'원래/{i}-{k}.txt','destination':f'1 공문/{i}-{k}.txt','status':'moved'} for k in range(301 if i==0 else 1)]
            app.atomic_json(self.data/'history'/f'old-{i:02}.json',{'id':f'old-{i:02}','projectId':self.pid,'at':f'2026-10-{i%28+1:02} 12:00:00','entries':entries})
        result,z=self.archive();self.assertEqual(result['runCount'],51)
        legacy=next(d for d in self.snapshots(z) if d['runId']=='legacy-old-00')
        self.assertEqual(len(legacy['events'][0]['journal']['entries']),301)
        text=z.read(next(n for n in z.namelist() if 'legacy-old-00/' in n and n.endswith('.txt'))).decode('utf-8-sig')
        self.assertIn('0-300.txt',text);self.assertIn('복원할 수 없습니다',text)

    def test_missing_project_folder_still_downloads_saved_runs(self):
        p,r=self.plan('기록.txt');self.move(p,r);shutil.rmtree(self.root)
        result,z=self.archive();self.assertEqual(result['runCount'],1)
        self.assertIn('연결할 수 없어',z.read('현재 상태.txt').decode('utf-8-sig'))

    def test_export_does_not_add_runs_or_include_document_contents_keys_or_roots(self):
        p,r=self.plan('자료.txt');self.move(p,r)
        app.atomic_json(self.data/'ai.json',{'model':'test','key':'PRIVATE_API_KEY'})
        paths=list((self.data/'run-history').rglob('*.json'))
        a,z=self.archive();b,z2=self.archive();self.assertEqual(a['runCount'],b['runCount'])
        self.assertEqual(paths,list((self.data/'run-history').rglob('*.json')))
        text='\n'.join(z.read(n).decode('utf-8-sig') for n in z.namelist())
        for secret in ('SYNTHETIC_DOCUMENT_BODY','PRIVATE_API_KEY',str(self.root),str(self.data)):
            self.assertNotIn(secret,text)

    def test_failed_move_has_a_durable_reason_and_original_file(self):
        p,r=self.plan('변경.txt');path=self.root/r['relative']
        with patch.object(app,'move_no_replace',side_effect=PermissionError('테스트 잠금: '+str(path))):
            j=self.move(p,r)
        self.assertEqual(j['entries'][0]['status'],'held')
        app.PLANS.clear();result,z=self.archive();self.assertEqual(result['runCount'],1)
        text='\n'.join(z.read(n).decode('utf-8-sig') for n in z.namelist())
        self.assertIn('테스트 잠금',text);self.assertNotIn(str(self.root),text);self.assertTrue(path.exists())

    def test_no_history_produces_an_honest_empty_archive(self):
        result,z=self.archive();self.assertEqual(result['runCount'],0)
        self.assertEqual(len(self.snapshots(z)),0);self.assertIn('현재 상태.txt',z.namelist())

    def test_hold_only_finish_is_saved_without_a_move(self):
        self.file('대기/분류불명.bin');p=app.make_plan(self.pid,False)
        app.finish_plan(p['id']);app.PLANS.clear()
        result,z=self.archive();self.assertEqual(result['runCount'],1)
        finish=self.snapshots(z)[0]['events'][0]['finish']
        self.assertEqual(finish['movedCount'],0);self.assertEqual(finish['remainingCount'],1)

    def test_interrupted_run_recovers_write_ahead_journal_without_claiming_success(self):
        p,r=self.plan('중단.txt');app.record_run_event('정리 실행 시작',plan=p)
        j={'id':'interrupted','projectId':self.pid,'planId':p['id'],'at':'2026-11-19 09:00:00',
           'entries':[{'id':r['id'],'source':r['relative'],'destination':'1 공문/중단.txt','status':'prepared'}]}
        app.atomic_json(self.data/'history/interrupted.json',j);app.PLANS.clear()
        result,z=self.archive();self.assertEqual(result['runCount'],1)
        doc=self.snapshots(z)[0]
        journal=next(e['journal'] for e in doc['events'] if e.get('journal'))
        self.assertEqual(journal['entries'][0]['status'],'prepared')
        self.assertTrue((self.root/r['relative']).exists())

    def test_cannot_write_history_means_no_filesystem_move(self):
        p,r=self.plan('유지.txt');before=set(self.root.rglob('*'))
        with patch.object(app,'record_run_event',side_effect=OSError('no space')):
            with self.assertRaises(OSError):self.move(p,r)
        self.assertEqual(set(self.root.rglob('*')),before)

    def test_old_journal_undo_keeps_the_original_run_date(self):
        p,r=self.plan('이전.txt');j=self.move(p,r)
        shutil.rmtree(self.data/'run-history');j.pop('planId');j.pop('atKst');j['at']='2026-10-01 11:22:33'
        app.atomic_json(self.data/'history'/(j['id']+'.json'),j)
        app.undo(j['id']);result,z=self.archive();self.assertEqual(result['runCount'],1)
        self.assertTrue(any(n.startswith('2026-10-01/') for n in z.namelist()))

    def test_reconnected_project_does_not_export_old_absolute_error_paths(self):
        old_root=str(self.root);j={'id':'old-error','projectId':self.pid,'root':old_root,'at':'2026-10-01 10:00:00',
            'entries':[{'source':'원본.txt','destination':'1 공문/원본.txt','status':'held','error':'잠김 '+old_root+'/원본.txt'}]}
        app.atomic_json(self.data/'history/old-error.json',j)
        moved=self.base/'new-project';self.root.rename(moved);project=app.get_project(self.pid);project['root']=str(moved);app.store_project(project)
        _,z=self.archive();text='\n'.join(z.read(n).decode('utf-8-sig') for n in z.namelist())
        self.assertNotIn(old_root,text);self.assertNotIn(str(moved),text)

