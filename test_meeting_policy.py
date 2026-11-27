"""Before/after coverage and a/b/c material-bundle naming, without external API calls."""
import copy
import hashlib
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import app


class MeetingFolderPolicy(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        self.root=self.base/'사업';self.root.mkdir();self.data=self.base/'settings';self.data.mkdir()
        self.patch=patch.object(app,'DATA',self.data);self.patch.start()
        app.SELECTIONS.clear();app.PLANS.clear();app.JOBS.clear();app.SELECTIONS['selected']=str(self.root)
        self.tree=[{'label':app.INBOX}]+copy.deepcopy(app.TEMPLATES['construction'])
        self.project=app.save_project({'selection':'selected','name':'힌지 공사','tree':self.tree},False)
        self.old='3 시공단계/1 도급공사 1/3107 회의 및 협의기록'
        self.new='3 시공단계/1 도급공사 1/6 회의 및 협의기록'
        self.photo='3 시공단계/1 도급공사 1/11 사진/1 공사전'
        self.report='1 공통/3 주요 보고자료(내부보고 자료)'

    def tearDown(self):self.patch.stop();self.temp.cleanup()
    def write(self,relative,data=b'document'):
        p=self.root/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data);return p
    def plan(self):return app.make_plan(self.project['id'],False)
    def choices(self,plan):return [{'id':r['id'],'destination':r['destination']} for r in plan['rows'] if r.get('destination') and not r.get('done')]
    def execute(self,plan):return app.execute_all(plan['id'],self.choices(plan))

    def test_screenshot_all_seven_folders_and_two_files_remain_in_meeting(self):
        folders=['260630 62동 프레임 교체 공사 최이사 협의','260727 일정','260729 힌지교체공사 일정',
                 '260805 힌지 WP 제외 관련 회의','260813 실정보고 1차','260827 외산힌지 교체 일정','260827 창호 추가 검토']
        for i,name in enumerate(folders):self.write(self.old+'/'+name+'/'+['공사전 사진.jpg','준공계.pdf','실정보고.docx'][i%3],str(i).encode())
        self.write(self.old+'/★ 관악캠퍼스 건물현황 및 힌지 보수 필요 범위.xlsx',b'buildings')
        self.write(self.old+'/261008 논스톱 힌지 추가 공사 정리 건.xlsx',b'additional work')
        plan=self.plan();self.assertEqual(len(plan['rows']),9)
        self.assertTrue(all(r['destination']==self.new for r in plan['rows']))
        self.assertTrue(all(not r.get('reviewRequired') for r in plan['rows']))
        summary=next(s for s in plan['contextSummary'] if s['source']==self.old)
        self.assertEqual((summary['beforeCount'],summary['includedCount']),(9,9))
        journal=self.execute(plan)
        lettered=[app.letter_label(i)+' '+name for i,name in enumerate(sorted(folders))]
        actual={p.name for p in (self.root/self.new).iterdir()}
        self.assertEqual(actual,set(lettered+['★ 관악캠퍼스 건물현황 및 힌지 보수 필요 범위.xlsx','261008 논스톱 힌지 추가 공사 정리 건.xlsx']))
        self.assertTrue(all(e['status']=='moved' for e in journal['entries']))
        self.assertEqual(list(self.root.rglob('*.lnk')),[])
        app.undo(journal['id']);self.assertEqual({p.name for p in (self.root/self.old).iterdir()},set(folders+['★ 관악캠퍼스 건물현황 및 힌지 보수 필요 범위.xlsx','261008 논스톱 힌지 추가 공사 정리 건.xlsx']))

    def test_old_cache_and_ai_cannot_split_curated_meeting(self):
        self.write(self.old+'/260813 실정보고 1차/실정보고.pdf')
        self.write(self.old+'/261008 추가 공사 정리.xlsx')
        plan=self.plan();project=app.get_project(self.project['id'])
        project['classificationCache']={app.cache_key(plan,r):{'destination':self.photo,'method':'manual','reviewed':True} for r in plan['rows']};app.store_project(project)
        plan=self.plan();self.assertTrue(all(r['destination']==self.new for r in plan['rows']))
        for r in plan['rows']:r.update(destination=self.photo,method='ai')
        app.organize_context(plan['rows'],plan['paths']);app.preserve_meeting_context(plan['rows'],plan['paths'])
        self.assertTrue(all(r['destination']==self.new for r in plan['rows']))
        first=plan['rows'][0];app.retarget_many(plan['id'],[first['id']],self.report)
        self.assertEqual(first['destination'],self.report);self.assertTrue(first['contextOverride'])

    def test_empty_meeting_folder_is_preserved_and_undo_restores_it(self):
        source=self.root/self.old/'260630 빈 협의자료';source.mkdir(parents=True)
        plan=self.plan();self.assertEqual(len(plan['rows']),1);self.assertEqual(plan['rows'][0]['kind'],'directory')
        journal=self.execute(plan);target=self.root/self.new/'A 260630 빈 협의자료'
        self.assertTrue(target.is_dir());self.assertFalse(source.exists())
        app.undo(journal['id']);self.assertTrue(source.is_dir());self.assertFalse(target.exists())

    def test_shortcut_only_meeting_folder_is_not_dropped(self):
        original=self.write(self.old+'/260630 관련 문서/다른 자료.lnk',b'original user shortcut')
        plan=self.plan();self.assertEqual(len(plan['rows']),1)
        journal=self.execute(plan);target=self.root/self.new/'A 260630 관련 문서/다른 자료.lnk'
        self.assertEqual(target.read_bytes(),b'original user shortcut')
        app.undo(journal['id']);self.assertEqual(original.read_bytes(),b'original user shortcut')

    def test_existing_date_and_hangul_title_are_kept_with_letter(self):
        self.write(self.old+'/2026-07-27 62동 힌지 교체 회의/내역.xlsx')
        plan=self.plan();row=plan['rows'][0]
        self.assertEqual(row['keepSub'],'A 2026-07-27 62동 힌지 교체 회의')
        check=app.move_check(plan['id'],self.choices(plan));self.assertEqual(check['folderRenames'][0]['newName'],'A 2026-07-27 62동 힌지 교체 회의')
        self.execute(plan);self.assertTrue((self.root/self.new/'A 2026-07-27 62동 힌지 교체 회의/내역.xlsx').exists())

    def test_confirmed_old_hierarchy_number_is_removed_but_meaningful_numbers_stay(self):
        self.write(self.old+'/3107-2 260813 실정보고 1차/보고.pdf',b'1');time.sleep(0.05)
        self.write(self.old+'/2603 62동 자료/메모.txt',b'2')
        plan=self.plan();subs={r['keepSub'] for r in plan['rows']}
        # A·B·C는 원래 폴더가 만들어진 순서(2026-11-27 LIM). 이 검사의 요점은 옛 계층 번호(3107-2)만 지우는 것.
        self.assertEqual(subs,{'A 260813 실정보고 1차','B 2603 62동 자료'})

    def test_ordinal_is_replaced_by_letter_without_inventing_a_date(self):
        self.write(self.old+'/3. 62동 창호 협의/260630 회의록.txt')
        plan=self.plan();row=plan['rows'][0]
        self.assertEqual(row['keepSub'],'A 62동 창호 협의')
        self.assertEqual(row['name'],'260630 회의록.txt')

    def test_folder_naming_never_calls_ai(self):
        self.write(self.old+'/2. 힌지 검토/회의록.txt','회의일자: 2026년 7월 27일\n힌지 검토'.encode())
        with patch.object(app,'gateway',side_effect=AssertionError('no API for folder names')):plan=self.plan()
        self.assertEqual(plan['rows'][0]['keepSub'],'A 힌지 검토')

    def test_folder_without_date_moves_without_date_confirmation(self):
        a=self.write(self.old+'/1. 협의자료/260727 기록.txt',b'a')
        self.write(self.old+'/1. 협의자료/260729 사진.jpg',b'b')
        os.utime(a,(1700000000,1700000000))
        plan=self.plan();self.assertTrue(all(r['keepSub']=='A 협의자료' for r in plan['rows']))
        self.execute(plan);self.assertEqual(len(list((self.root/self.new/'A 협의자료').iterdir())),2)

    def test_empty_inner_folder_and_original_hierarchy_remain(self):
        self.write(self.old+'/2. 보수 협의/260727 회의록.txt',b'record')
        empty=self.root/self.old/'2. 보수 협의/도면/빈 첨부';empty.mkdir(parents=True)
        plan=self.plan();self.assertEqual(len(plan['rows']),2)
        self.execute(plan)
        self.assertTrue((self.root/self.new/'A 보수 협의/도면/빈 첨부').is_dir())
        self.assertTrue((self.root/self.new/'A 보수 협의/260727 회의록.txt').is_file())

    def test_separate_numbered_folders_do_not_merge_when_titles_and_dates_match(self):
        for number in (1,2):self.write(self.old+'/'+str(number)+'. 협의/260727 회의록.txt',str(number).encode())
        plan=self.plan();targets={r['keepSub'] for r in plan['rows']}
        self.assertEqual(targets,{'A 협의','B 협의'})
        self.execute(plan)
        self.assertEqual(len(list((self.root/self.new).iterdir())),2)

    def test_letters_continue_after_existing_bundles_and_are_per_parent(self):
        self.write(self.new+'/A 260701 착수 회의/회의록.txt',b'existing')
        self.write(self.old+'/260813 실정보고 1차/보고.pdf',b'new')
        plan=self.plan();row=next(r for r in plan['rows'] if r['name']=='보고.pdf')
        self.assertEqual(row['keepSub'],'B 260813 실정보고 1차')

    def test_bundle_already_in_its_category_keeps_its_name(self):
        self.write(self.photo+'/3. 보수공사 보고/260630 공사전 사진.jpg',b'photo')
        plan=self.plan();self.assertEqual(plan['rows'],[])

    def test_managed_shortcut_path_index_moves_with_preserved_meeting(self):
        photo=self.write(self.photo+'/260630 사진.jpg',b'photo')
        link=self.root/self.old/'260630 관련자료/사진 바로가기.lnk';app.make_shortcut(photo.parent,link)
        old=link.relative_to(self.root).as_posix();before=link.read_bytes()
        app.atomic_json(self.root/'.gongmu-chak/folder-links.json',{old:{'target':self.photo,'sha256':app.file_hash(link)}})
        plan=self.plan();journal=self.execute(plan)
        new=self.new+'/A 260630 관련자료/사진 바로가기.lnk'
        index=app.read_json(self.root/'.gongmu-chak/folder-links.json');self.assertIn(new,index);self.assertNotIn(old,index)
        app.undo(journal['id']);self.assertEqual(link.read_bytes(),before)
        self.assertIn(old,app.read_json(self.root/'.gongmu-chak/folder-links.json'))

    def old_move(self,name,data=b'old report',changed=False,override=False):
        origin=self.old+'/260813 실정보고 1차/'+name
        current=self.photo+'/260813 실정보고 1차/'+name
        path=self.write(current,data)
        entry={'id':'old-row-'+name,'source':origin,'destination':current,'status':'moved','fingerprint':app.fingerprint(path),'contextOverride':override}
        journal={'id':'old-journal-'+str(len(list((self.data/'history').glob('*.json'))) if (self.data/'history').exists() else 0),'projectId':self.project['id'],'root':str(self.root),'entries':[entry]}
        app.atomic_json(self.data/'history'/(journal['id']+'.json'),journal)
        if changed:path.write_bytes(data+b' user updated')
        return origin,current,path

    def test_previous_wrong_moves_are_recovered_from_unchanged_local_history(self):
        origin,current,path=self.old_move('실정보고.pdf')
        plan=self.plan();row=next(r for r in plan['rows'] if r['relative']==current)
        self.assertEqual(row['destination'],self.new);self.assertEqual(row['keepSub'],'A 260813 실정보고 1차')
        self.assertEqual(row['meetingOrigin'],origin)
        summary=next(s for s in plan['contextSummary'] if s['source']==self.old)
        self.assertEqual(summary['children'][0]['name'],'260813 실정보고 1차')
        journal=self.execute(plan);target=self.root/self.new/'A 260813 실정보고 1차/실정보고.pdf'
        self.assertEqual(target.read_bytes(),b'old report');self.assertFalse(path.exists())
        self.assertEqual(journal['contextSummary'][0]['children'][0]['status'],'이동 완료')
        app.undo(journal['id']);self.assertTrue(path.exists())

    def test_changed_historical_file_requires_explicit_content_confirmation(self):
        origin,current,path=self.old_move('실정보고.pdf',changed=True)
        plan=self.plan();row=next(r for r in plan['rows'] if r['relative']==current)
        self.assertTrue(row['historyReview']);self.assertEqual(row['destination'],'')
        app.confirm_meeting_origin(plan['id'],row['id'])
        self.assertFalse(row['historyReview']);self.assertEqual(row['destination'],self.new)
        self.assertEqual(row['keepSub'],'A 260813 실정보고 1차')
        journal=self.execute(plan);self.assertTrue(all(e['status']=='moved' for e in journal['entries']))
        self.assertEqual((self.root/self.new/'A 260813 실정보고 1차/실정보고.pdf').read_bytes(),b'old report user updated')

    def test_explicit_manual_transfer_is_not_reversed_by_old_meeting_history(self):
        _,current,_=self.old_move('공사전 사진.jpg',override=True)
        plan=self.plan();row=next((r for r in plan['rows'] if r['relative']==current),None)
        # Absent row = already in place: the explicit move is kept, not reversed.
        self.assertTrue(row is None or ('meetingOrigin' not in row and row['destination']==self.photo))

    def test_other_project_history_is_never_used_for_recovery(self):
        _,current,_=self.old_move('공사전 사진.jpg')
        history=next((self.data/'history').glob('*.json'));record=app.read_json(history);record['projectId']='another-project';app.atomic_json(history,record)
        plan=self.plan();row=next((r for r in plan['rows'] if r['relative']==current),None)
        self.assertTrue(row is None or ('meetingOrigin' not in row and row['destination']==self.photo))

    def test_second_plan_is_idempotent_for_dates_and_meeting_locations(self):
        self.write(self.old+'/260813 실정보고 1차/보고.pdf')
        plan=self.plan();self.execute(plan)
        again=self.plan();self.assertEqual(again['rows'],[])
        summary=next(s for s in again['contextSummary'] if s['destination']==self.new)
        self.assertEqual(summary['beforeCount'],1);self.assertEqual(summary['children'][0]['status'],'이미 제자리')


if __name__=='__main__':unittest.main()
