"""v3: standard roles and rounds are mapped before A/B/C bundle names (synthetic reproduction, no user data)."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import app

D='2 설계단계/21 설계 용역/2101 최초품의 및 최초 계약서/'
C='3 시공단계/31 도급공사/3109 설계변경/'
T='3 시공단계/32 기술지도 용역/'
M='1 공통/14 타기관 협의자료/260327 캠퍼스 관리과 메일/'
FILES=[D+'0. 결재참조.hwp',D+'1. 설계용역 대가 산출서.xls',D+'2. 과업요구서.pdf',D+'3. 견적서/견적서 A업체.pdf',D+'3. 견적서.zip',D+'설계용역 계약서.pdf',
       C+'3109-1 설계변경1차(설계변경 검토의견서)/설계변경 검토의견서.hwp',C+'3109-1 설계변경1차(설계변경 검토의견서)/사진/현장 사진.jpg',
       C+'3109-2 설계변경2차(설계변경 검토의견서)/설계변경 검토의견서.hwp',C+'3109-2 설계변경2차(설계변경 검토의견서)/2. 변경내역서.xlsx',
       C+'260901 설계변경 서류/변경 요청 공문.pdf',
       T+'재해예방 기술지도 계약서.pdf',T+'기술지도 회의/260410 착수 협의.hwp',T+'작업지시서 1차/작업지시서 1차.hwp',T+'작업지시서 1차/1차 계약서.pdf',
       M+'현장 사진1.jpg',M+'설명 자료.pptx',M+'회신 메일.pdf',M+'첨부/도면.pdf']
CHANGE='3 시공단계/1 도급공사/7 설계변경'
TECH='3 시공단계/2 기술지도계약서'
FIRST='2 설계단계/1 설계 용역/1 최초 품의 및 최초 계약서'
MAIL='1 공통/4 타기관 협의자료(공문, 공지, 민원 등)/1 공문 및 협의기록'


class RolesBeforeLetters(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();base=Path(self.temp.name)
        self.root=base/'사업';self.root.mkdir();data=base/'settings';data.mkdir()
        self.patch=patch.object(app,'DATA',data);self.patch.start()
        app.SELECTIONS.clear();app.PLANS.clear();app.SELECTIONS['p']=str(self.root)
        tree=[{'label':app.INBOX}]+copy.deepcopy(app.TEMPLATES['design'])
        stage=next(s for s in tree if '시공단계' in s['label'])
        stage['children'][0].update(label='1 도급공사',contractId='cons',contractKind='construction')
        stage['children'][1].update(label='2 기술지도계약서',contractId='tech',contractKind='service',serviceRole=True,serviceManagement='workOnly',
                                    children=[{'label':'1 계약서','children':[]},{'label':'2 회의 및 협의기록','children':[]},{'label':'3 작업지시서','children':[]}])
        stage['children']=stage['children'][:2]
        self.project=app.save_project({'selection':'p','name':'재현','type':'design','tree':tree},False)
        for i,f in enumerate(FILES):
            p=self.root/f;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(('doc %d'%i).encode())
        (self.root/M/'빈 폴더').mkdir()

    def tearDown(self):self.patch.stop();self.temp.cleanup()
    def target(self,row):return app.effective_folder(row,row['destination'])+'/'+(row.get('proposedName') or row['name']) if row['destination'] else ''
    def files(self):return {p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_rounds_service_and_approval_folders_map_to_numbered_destinations(self):
        plan=app.make_plan(self.project['id'],False);rows={r['relative']:r for r in plan['rows']}
        self.assertEqual(self.target(rows[C+'3109-1 설계변경1차(설계변경 검토의견서)/사진/현장 사진.jpg']),CHANGE+'/1 1차 설계변경/사진/현장 사진.jpg')
        self.assertEqual(self.target(rows[C+'3109-2 설계변경2차(설계변경 검토의견서)/2. 변경내역서.xlsx']),CHANGE+'/2 2차 설계변경/2. 변경내역서.xlsx')
        self.assertEqual(rows[C+'260901 설계변경 서류/변경 요청 공문.pdf']['keepSub'],'A 260901 설계변경 서류')
        self.assertFalse(any('설계변경1차' in m['newName'] or '기술지도' in m['newName'] for m in plan['folderRenames']))
        self.assertEqual(self.target(rows[T+'작업지시서 1차/1차 계약서.pdf']),TECH+'/2 작업지시서/1 작업지시서 1차 및 계약서/1차 계약서.pdf')
        self.assertEqual(rows[T+'기술지도 회의/260410 착수 협의.hwp']['destination'],TECH+'/1 회의 및 협의기록')
        self.assertEqual(rows[T+'재해예방 기술지도 계약서.pdf']['destination'],'')
        self.assertFalse(any(r['destination'].startswith('3 시공단계/') and not r['destination'].startswith(('3 시공단계/1 도급공사','3 시공단계/2 기술지도계약서')) for r in plan['rows']))
        self.assertEqual(self.target(rows[D+'3. 견적서/견적서 A업체.pdf']),FIRST+'/1 품의서/3. 견적서/견적서 A업체.pdf')
        self.assertEqual(self.target(rows[D+'0. 결재참조.hwp']),FIRST+'/1 품의서/0. 결재참조.hwp')
        self.assertEqual(rows[D+'설계용역 계약서.pdf']['destination'],FIRST+'/2 계약서')
        self.assertTrue(all(self.target(rows[M+n]).startswith(MAIL+'/A 260327 캠퍼스 관리과 메일/') for n in ('현장 사진1.jpg','첨부/도면.pdf')))

    def test_execution_preserves_contents_undo_restores_and_rerun_is_stable(self):
        before=self.files();plan=app.make_plan(self.project['id'],False)
        journal=app.execute_all(plan['id'],[{'id':r['id'],'destination':r['destination']} for r in plan['rows'] if r['destination']])
        after=self.files();self.assertEqual(sorted(after.values()),sorted(before.values()))
        self.assertTrue((self.root/MAIL/'A 260327 캠퍼스 관리과 메일/빈 폴더').is_dir())
        self.assertFalse((self.root/CHANGE/'B 설계변경1차(설계변경 검토의견서)').exists())
        self.assertEqual(list(self.root.rglob('*.lnk')),[])
        again=app.make_plan(self.project['id'],False)
        self.assertFalse(any(r['destination'] for r in again['rows'] if not r['relative'].startswith(T)))
        self.assertFalse(any(m['newName'].startswith(('A A','B A')) for m in again.get('folderRenames',[])))
        app.undo(journal['id']);self.assertEqual(self.files(),before)

    def test_recheck_repairs_old_result_from_history_and_undo_restores(self):
        entries=[]  # A 0.10.0-style result: round folders were wrapped as lettered bundles.
        contract=D+'설계용역 계약서.pdf';moved=FIRST+'/설계용역 계약서.pdf';(self.root/moved).parent.mkdir(parents=True,exist_ok=True);(self.root/contract).rename(self.root/moved)
        entries.append({'id':'c','source':contract,'destination':moved,'fingerprint':app.fingerprint(self.root/moved),'status':'moved','kind':'file'})
        for f in FILES:
            if '3109-1' not in f and '3109-2' not in f:continue
            old=f.split('/')[3];new=('b ' if '3109-1' in f else 'c ')+old.split(' ',1)[1]
            dest=CHANGE+'/'+new+'/'+f.split('/',4)[4];target=self.root/dest;target.parent.mkdir(parents=True,exist_ok=True)
            (self.root/f).rename(target);entries.append({'id':f,'source':f,'destination':dest,'fingerprint':app.fingerprint(target),'status':'moved','kind':'file'})
        (app.DATA/'history').mkdir(exist_ok=True)
        app.atomic_json(app.DATA/'history'/'old.json',{'id':'old','projectId':self.project['id'],'at':'2026-11-18T00:00:00','root':str(self.root),'entries':entries,'createdFolders':[]})
        wrong=[p for p in (self.root/CHANGE).iterdir() if '설계변경1차' in p.name]
        self.assertEqual(len(wrong),1);self.assertNotEqual(wrong[0].name[:2],'1 ')
        user=self.root/'1 공통/사용자 빈 폴더';user.mkdir()
        before=self.files();check=app.recheck(self.project['id']);self.assertEqual(before,self.files())
        rows={r['recheck']['original']:r for r in check['rows']}
        self.assertEqual(rows[D+'설계용역 계약서.pdf']['recheck']['proposed'],FIRST+'/2 계약서/설계용역 계약서.pdf')
        row=rows[C+'3109-1 설계변경1차(설계변경 검토의견서)/사진/현장 사진.jpg']
        self.assertEqual(row['recheck']['proposed'],CHANGE+'/1 1차 설계변경/사진/현장 사진.jpg')
        self.assertEqual(row['relative'],row['recheck']['current'])
        journal=app.execute_all(check['id'],[{'id':r['id'],'destination':r['destination']} for r in check['rows'] if r['destination']])
        self.assertTrue((self.root/CHANGE/'1 1차 설계변경/사진/현장 사진.jpg').is_file())
        self.assertFalse(wrong[0].exists());self.assertTrue(user.is_dir())
        self.assertEqual(sorted(self.files().values()),sorted(before.values()))
        again=app.recheck(self.project['id']);self.assertFalse(any(r['destination'] and r['relative'].startswith(CHANGE) for r in again['rows']))
        app.undo(journal['id']);self.assertEqual(self.files(),before);self.assertTrue(wrong[0].is_dir())


    def test_round_never_crosses_into_another_service(self):
        paths=['3 시공단계/2 감리용역/2 작업지시서/1 작업지시서 1차 및 계약서']
        self.assertEqual(app.round_target(paths,['3 시공단계','32 기술지도 용역','작업지시서 1차']),(2,''))
        paths.append('3 시공단계/3 재해예방 기술지도 용역/2 작업지시서/1 작업지시서 1차 및 계약서')
        self.assertEqual(app.round_target(paths,['3 시공단계','32 기술지도 용역','작업지시서 1차'])[1],paths[1])


if __name__=='__main__':unittest.main()
