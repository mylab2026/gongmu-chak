"""Reproduce misfiled contracts and legacy duplicate folders from PC screenshots."""
import copy
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import app


class ScreenshotCorrections(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        self.root=self.base/'사업';self.root.mkdir();self.data=self.base/'settings';self.data.mkdir()
        self.data_patch=patch.object(app,'DATA',self.data);self.data_patch.start()
        app.SELECTIONS.clear();app.PLANS.clear();app.JOBS.clear();app.SELECTIONS['picked']=str(self.root)
        self.tree=[{'label':app.INBOX}]+copy.deepcopy(app.TEMPLATES['design'])
        construction=next(s for s in self.tree if '시공단계' in s['label'])
        self.cons=next(n for n in construction['children'] if '도급공사' in n['label']);self.cons.update(contractId='cons',contractKind='construction')
        self.tech=next(n for n in construction['children'] if '용역' in n['label']);self.tech.update(label='2 재해예방 기술지도 용역',contractId='tech',contractKind='service',serviceRole=True,serviceManagement='workOnly')
        self.tech['children']=[{'label':'1 회의 및 협의기록','children':[]},{'label':'2 작업지시서','children':[{'label':'1 현장1','children':[]},{'label':'2 현장2','children':[]}]}]
        self.project=app.save_project({'selection':'picked','name':'2026 보수 공사','type':'design','tree':self.tree},False)
        self.tech_root='3 시공단계/2 재해예방 기술지도 용역'
        self.cons_folder='3 시공단계/1 도급공사 1/1 최초 품의 및 최초 계약서/2 계약서'

    def tearDown(self):self.data_patch.stop();self.temp.cleanup()

    def write(self,path,content=b'document'):
        source=self.root/path;source.parent.mkdir(parents=True,exist_ok=True);source.write_bytes(content);return source

    def register(self,ident,source,kind,title,date,**extra):
        record={'id':ident,'name':source.name,'sourceHash':app.file_hash(source),'sourcePath':str(source),
                'analysis':{'kind':kind,'title':title,'party':ident+' 업체','signed_date':date,**extra}}
        project=app.get_project(self.project['id']);project['contracts'].append(record);app.store_project(project)
        return record

    def plan(self):return app.make_plan(self.project['id'],False)
    def execute(self,plan):return app.execute_all(plan['id'],[{'id':r['id'],'destination':r['destination']} for r in plan['rows'] if r['destination']])

    def test_work_only_service_upgrade_is_idempotent_and_keeps_custom_children(self):
        raw=app.read_json(self.data/'projects.json')[0]
        stage=next(n for n in raw['tree'] if '시공단계' in n['label'])
        tech=next(n for n in stage['children'] if '기술지도' in n['label'])
        tech['children'].append({'label':'3 사용자 보관함','children':[{'label':'메모','children':[]}]})
        app.store_project(raw)
        upgraded=app.get_project(raw['id'])
        node=next(n for n in next(s for s in upgraded['tree'] if '시공단계' in s['label'])['children'] if '기술지도' in n['label'])
        self.assertEqual([n['label'] for n in node['children']],['1 회의 및 협의기록','2 작업지시서','3 사용자 보관함'])
        self.assertEqual([n['label'] for n in node['children'][1]['children']],['1 작업지시서 1차 및 계약서','2 작업지시서 2차 및 계약서'])
        self.assertEqual(node['children'][2]['children'][0]['label'],'메모')
        self.assertEqual(app.upgrade_project_tree(copy.deepcopy(upgraded)),upgraded)
        self.assertFalse((self.root/self.tech_root/'1 계약서').exists())

    def test_direct_service_structure_is_not_treated_as_work_only(self):
        project=app.get_project(self.project['id'])
        tech=next(n for n in next(s for s in project['tree'] if '시공단계' in s['label'])['children'] if '기술지도' in n['label'])
        tech['serviceManagement']='direct';before=copy.deepcopy(tech['children'])
        app.upgrade_project_tree(project);self.assertEqual(tech['children'],before)

    @patch.object(app, 'CONTRACT_RENAME', True)  # 이름 바꾸기 보류 중: 켜졌을 때의 동작을 계속 검사한다
    def test_construction_contract_in_technical_service_routes_by_content_identity(self):
        original=self.write(self.tech_root+'/1. 계약서.pdf',b'construction original')
        self.register('cons',original,'construction','13동 및 힌지 보수공사','2026-07-09')
        plan=self.plan();row=next(r for r in plan['rows'] if r['relative'].endswith('1. 계약서.pdf'))
        self.assertEqual(row['destination'],self.cons_folder)
        self.assertFalse(row.get('keepSub'));self.assertTrue(row['proposedName'].startswith('260709 공사 계약서'))
        check=app.move_check(plan['id'],[{'id':row['id'],'destination':row['destination']}])
        self.assertEqual(check['contractRenames'][0]['signedDate'],'2026-07-09');self.assertTrue(original.exists())
        journal=self.execute(plan);target=self.root/self.cons_folder/row['proposedName']
        self.assertEqual(target.read_bytes(),b'construction original');self.assertFalse(original.exists())
        self.assertTrue((self.root/self.tech_root/'2 작업지시서').is_dir())
        app.undo(journal['id']);self.assertEqual(original.read_bytes(),b'construction original');self.assertFalse(target.exists())

    def test_stale_service_branch_contract_id_does_not_override_verified_kind(self):
        original=self.write(self.tech_root+'/1. 계약서.pdf',b'construction misbound id')
        self.register('cons',original,'construction','힌지 보수공사','2026-07-09')
        project=app.get_project(self.project['id'])
        stage=next(n for n in project['tree'] if '시공단계' in n['label'])
        cons=next(n for n in stage['children'] if '도급공사' in n['label'])
        tech=next(n for n in stage['children'] if '기술지도' in n['label'])
        cons.update(label='1 본공사',contractId='older-id');tech['contractId']='cons';app.store_project(project)
        row=self.plan()['rows'][0]
        self.assertTrue(row['destination'].startswith('3 시공단계/1 본공사/'))
        self.assertNotIn('기술지도',row['destination'])

    def test_technical_contract_numeric_name_goes_into_its_contract_folder(self):
        source=self.write(self.tech_root+'/20260710105218.pdf',b'technical contract')
        self.register('tech',source,'service','재해예방 기술지도 용역','2026-07-10')
        row=self.plan()['rows'][0]
        self.assertEqual(row['destination'],'')  # work-order service: no master contract folder, never guessed
        order=self.write(self.tech_root+'/계약 1차/20260801.pdf',b'order one contract')
        self.register('tech1',order,'service','재해예방 기술지도 용역 1차','2026-08-01')
        project=app.get_project(self.project['id']);project['contracts'][-1]['id']='tech';project['contracts']=project['contracts'][-1:];app.store_project(project)
        row=next(r for r in self.plan()['rows'] if r['name']=='20260801.pdf')
        self.assertEqual(row['destination'],self.tech_root+'/2 작업지시서/1 작업지시서 1차 및 계약서')

    @patch.object(app, 'CONTRACT_RENAME', True)  # 이름 바꾸기 보류 중: 켜졌을 때의 동작을 계속 검사한다
    def test_each_revision_uses_its_own_signed_date_and_rename_can_be_undone(self):
        old=self.write(self.tech_root+'/1. 계약서.pdf',b'original cons')
        new=self.write(self.tech_root+'/1. 변경 계약서.pdf',b'changed cons')
        a=self.register('old',old,'construction','힌지 보수공사','2026-07-09')
        b={'id':'cons','name':new.name,'sourceHash':app.file_hash(new),'analysis':{'kind':'construction','title':'힌지 보수공사','party':'업체','signed_date':'2026-09-28','amendment':True},'versions':[{'id':'old','name':old.name,'sourceHash':a['sourceHash'],'signed_date':'2026-07-09','analysis':a['analysis']}]}
        project=app.get_project(self.project['id']);project['contracts']=[b];app.store_project(project)
        rows={r['name']:r for r in self.plan()['rows']}
        self.assertTrue(rows[old.name]['proposedName'].startswith('260709 공사 계약서'))
        self.assertTrue(rows[new.name]['proposedName'].startswith('260928 공사 변경계약서'))
        self.assertEqual(rows[old.name]['destination'],rows[new.name]['destination'])

    def test_unknown_contract_is_not_sent_to_service_by_project_wide_preference(self):
        self.write(self.tech_root+'/1. 계약서.pdf',b'unknown contract')
        plan=self.plan();row=plan['rows'][0]
        self.assertEqual(row['destination'],'');self.assertTrue(row['contractReview'])
        row.update(destination=self.tech_root,method='ai',reviewed=True)
        app.apply_contract_routes(app.get_project(self.project['id']),plan['rows'],plan['paths'])
        self.assertEqual(row['destination'],'');self.assertFalse(row['reviewed'])

    @patch.object(app, 'CONTRACT_RENAME', True)  # 이름 바꾸기 보류 중: 켜졌을 때의 동작을 계속 검사한다
    def test_missing_signing_date_does_not_use_filesystem_date(self):
        source=self.write(self.tech_root+'/1. 계약서.pdf',b'dateless')
        self.register('cons',source,'construction','힌지 보수공사','')
        row=self.plan()['rows'][0]
        self.assertEqual(row['destination'],self.cons_folder);self.assertEqual(row['proposedName'],'')
        self.assertTrue(row['nameReviewRequired'])

    @patch.object(app, 'CONTRACT_RENAME', True)  # 이름 바꾸기 보류 중: 켜졌을 때의 동작을 계속 검사한다
    def test_contract_already_in_right_folder_still_gets_name_proposal(self):
        source=self.write(self.cons_folder+'/1. 계약서.pdf',b'correct folder')
        self.register('cons',source,'construction','힌지 보수공사','2026-07-09')
        plan=self.plan();self.assertEqual(len(plan['rows']),1)
        row=plan['rows'][0];self.execute(plan)
        self.assertTrue((self.root/self.cons_folder/row['proposedName']).exists())
        self.assertEqual(self.plan()['rows'],[])

    def test_old_numbered_standard_folders_merge_without_duplicate_nesting(self):
        sources=[
          ('2 설계단계/1 설계 용역/2101 최초 품의 및 최초 계약서/품의서.docx','2 설계단계/1 설계 용역/1 최초 품의 및 최초 계약서/1 품의서'),
          ('2 설계단계/1 설계 용역/8 완수계/2107-1 완수계 공문 및 검사 조서/공문.txt','2 설계단계/1 설계 용역/9 완수계/1 완수계 공문 및 검사 조서'),  # 4 공사전 사진 추가(2026-11-27)로 9번
          ('3 시공단계/1 도급공사 1/3113 작업일보/일지.docx','3 시공단계/1 도급공사 1/15 작업일보'),
          ('2 설계단계/1 설계 용역/1 최초 품의 및 최초 계약서/1 공통/14 주요 보고자료(결재선 없는 중간 보고자료)/3. 보수공사 보고/보고자료.pptx','1 공통/3 주요 보고자료(내부보고 자료)')]
        for relative,_ in sources:self.write(relative,relative.encode())
        plan=self.plan();rows={r['relative']:r for r in plan['rows']}
        for relative,destination in sources:
            row=rows[relative];self.assertEqual(row['destination'],destination,relative)
            self.assertNotIn('2101',row.get('keepSub',''));self.assertNotIn('2107-1',row.get('keepSub',''));self.assertNotIn('3113',row.get('keepSub',''))
            self.assertNotIn('1 공통',row.get('keepSub',''))
        journal=self.execute(plan)
        self.assertTrue(all(e['status']=='moved' for e in journal['entries']))
        self.assertFalse(any('2101' in e['destination'] or '2107-1' in e['destination'] or '3113' in e['destination'] for e in journal['entries']))
        self.assertEqual(rows[sources[-1][0]].get('keepSub'),'A 보수공사 보고')

    def test_custom_photo_site_and_numbered_folders_are_preserved(self):
        for folder in ('현장1','사진1'):
            self.write('3 시공단계/1 도급공사 1/3110 사진/'+folder+'/a.jpg',folder.encode());time.sleep(0.05)
        rows=self.plan()['rows']
        # 2026-11-27 LIM: 한 칸에 새 묶음이 여럿이면 원래 폴더가 만들어진 순서로 A·B·C(현장1을 먼저 만들었다)
        self.assertEqual({r['keepSub'] for r in rows},{'A 현장1','B 사진1'})
        self.assertTrue(all(r['destination'].endswith('/11 사진') for r in rows))

    def test_legacy_work_order_site_maps_to_round_without_extra_site_folder(self):
        self.write(self.tech_root+'/2 작업지시서/1 현장1/작업지시.pdf',b'order')
        row=self.plan()['rows'][0]
        self.assertEqual(row['destination'],self.tech_root+'/2 작업지시서/1 작업지시서 1차 및 계약서')
        self.assertFalse(row.get('keepSub'));self.assertEqual(row.get('secondaryFolders'),[])

    @patch.object(app, 'CONTRACT_RENAME', True)  # 이름 바꾸기 보류 중: 켜졌을 때의 동작을 계속 검사한다
    def test_contract_rename_collision_never_overwrites(self):
        original=self.write(self.tech_root+'/1. 계약서.pdf',b'new original')
        self.register('cons',original,'construction','힌지 보수공사','2026-07-09')
        plan=self.plan();row=plan['rows'][0]
        existing=self.write(self.cons_folder+'/'+row['proposedName'],b'other document')
        check=app.move_check(plan['id'],[{'id':row['id'],'destination':row['destination']}])
        self.assertEqual(len(check['renamed']),1);self.assertIn('(2)',check['contractRenames'][0]['newName'])
        self.assertEqual(existing.read_bytes(),b'other document')


if __name__=='__main__':unittest.main()
