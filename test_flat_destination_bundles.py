"""User scenario: many scattered files/bundles entering one approved leaf category."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app

TARGET='1 회의 및 협의기록'


class FlatDestinationBundles(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();base=Path(self.temp.name).resolve()
        self.root=base/'사업';self.root.mkdir()
        self.patch=patch.object(app,'DATA',base/'settings');self.patch.start()
        self.ai=patch.object(app,'gateway',side_effect=AssertionError('No real AI in this regression'));self.ai.start()
        app.SELECTIONS['flat-regression']=str(self.root)
        self.project=app.save_project({'selection':'flat-regression','name':'하위 분류 없는 목적지',
            'tree':[{'label':app.INBOX},{'label':TARGET}]},False)

    def tearDown(self):self.ai.stop();self.patch.stop();self.temp.cleanup()

    def add(self,relative,content=b'synthetic document'):
        p=self.root/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(content)

    def snapshot(self):
        return {p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file() and '.gongmu-chak' not in p.parts}

    def move(self):
        plan=app.make_plan(self.project['id'],False)
        self.assertTrue(all(r['destination']==TARGET for r in plan['rows']))
        journal=app.execute_all(plan['id'],[{'id':r['id'],'destination':r['destination']} for r in plan['rows']])
        self.assertTrue(all(e['status']=='moved' for e in journal['entries']))
        return plan,journal

    def test_three_bundles_and_211_loose_files_use_only_abc_and_keep_bytes(self):
        a='흩어진 자료/260327 캠퍼스 관리과 메일'
        b='다른 위치/260401 설계사 협의'
        c='3107 회의 및 협의기록/현장 회신 묶음'
        for folder in (a,b,c):
            self.add(folder+'/회의록.txt',folder.encode())
            self.add(folder+'/첨부/회의록 도면.txt',(folder+' attachment').encode())
            self.add(folder+'/첨부/세부/회의록 검토.txt',(folder+' nested').encode())
            (self.root/folder/'빈 폴더').mkdir()
        for n in range(211):self.add('회의록 낱개%03d.txt'%n,('loose '+str(n)).encode())
        before=self.snapshot();plan,journal=self.move()
        self.assertEqual(plan['scanInfo']['alreadyInPlaceCount'],0)
        mapping={m['source']:m['newName'] for m in plan['folderRenames']}
        self.assertEqual(mapping,{a:'A 260327 캠퍼스 관리과 메일',b:'B 260401 설계사 협의',c:'C 현장 회신 묶음'})
        expected={}
        for relative,content in before.items():
            source=next((p for p in mapping if relative.startswith(p+'/')),None)
            destination=TARGET+'/'+mapping[source]+'/'+relative[len(source)+1:] if source else TARGET+'/'+relative
            expected[destination]=content
        self.assertEqual(self.snapshot(),expected)
        for folder,name in mapping.items():self.assertTrue((self.root/TARGET/name/'빈 폴더').is_dir())
        self.assertEqual(sorted(p.name for p in (self.root/TARGET).iterdir() if p.is_dir()),sorted(mapping.values()))
        self.assertEqual(app.get_project(self.project['id'])['tree'][1].get('children',[]),[])
        self.assertFalse(list(self.root.rglob('*.lnk')))
        self.assertFalse(app.make_plan(self.project['id'],False)['rows'])
        app.undo(journal['id']);self.assertEqual(self.snapshot(),before)
        for folder in mapping:self.assertTrue((self.root/folder/'빈 폴더').is_dir())

    def test_undated_single_file_folder_is_a_bundle(self):
        self.add('흩어진 원본/설계사 회신 묶음/회의록 하나.txt',b'one')
        before=self.snapshot();plan,journal=self.move()
        self.assertEqual(self.snapshot(),{TARGET+'/A 설계사 회신 묶음/회의록 하나.txt':b'one'})
        app.undo(journal['id']);self.assertEqual(self.snapshot(),before)

    def test_undated_bundle_keeps_nested_attachments(self):
        source='여러 원본/설계사 회신 묶음'
        for name in ('회의록.txt','회의록 검토.txt','첨부/회의록 도면.txt','첨부/세부/회의록 세부.txt'):
            self.add(source+'/'+name,name.encode())
        before=self.snapshot();plan,journal=self.move()
        self.assertEqual(self.snapshot(),{TARGET+'/A 설계사 회신 묶음/'+k[len(source)+1:]:v for k,v in before.items()})
        app.undo(journal['id']);self.assertEqual(self.snapshot(),before)

    def test_bundle_with_only_nested_attachment_keeps_its_title(self):
        self.add('여러 원본/설계사 회신 묶음/첨부/회의록 도면.txt',b'nested only')
        before=self.snapshot();plan,journal=self.move()
        self.assertEqual(self.snapshot(),{TARGET+'/A 설계사 회신 묶음/첨부/회의록 도면.txt':b'nested only'})
        app.undo(journal['id']);self.assertEqual(self.snapshot(),before)

    def test_old_category_does_not_become_an_alphabet_bundle(self):
        self.add('3107 회의 및 협의기록/회의록 낱개.txt',b'one')
        self.add('회의록 루트.txt',b'two')
        before=self.snapshot();plan,journal=self.move()
        self.assertFalse(plan['folderRenames'])
        self.assertEqual(self.snapshot(),{TARGET+'/회의록 낱개.txt':b'one',TARGET+'/회의록 루트.txt':b'two'})
        app.undo(journal['id']);self.assertEqual(self.snapshot(),before)

    def test_legacy_order_is_removed_but_date_and_inner_numbering_remain(self):
        source='112 협의자료/1121 260327 현장 협의'
        self.add(source+'/회의록.txt',b'one');self.add(source+'/3. 첨부/회의록 도면.txt',b'two')
        before=self.snapshot();plan,journal=self.move()
        self.assertEqual(self.snapshot(),{TARGET+'/A 260327 현장 협의/회의록.txt':b'one',TARGET+'/A 260327 현장 협의/3. 첨부/회의록 도면.txt':b'two'})
        app.undo(journal['id']);self.assertEqual(self.snapshot(),before)

    def test_existing_alphabet_is_not_reused(self):
        self.add(TARGET+'/A 기존 자료/회의록 기존.txt',b'existing')
        self.add('다른 원본/260401 신규 회신/회의록 신규.txt',b'new')
        before=self.snapshot();plan=app.make_plan(self.project['id'],False)
        self.assertEqual([m['newName'] for m in plan['folderRenames']],['B 260401 신규 회신'])
        journal=app.execute_all(plan['id'],[{'id':r['id'],'destination':r['destination']} for r in plan['rows'] if r['destination']])
        self.assertEqual((self.root/TARGET/'A 기존 자료/회의록 기존.txt').read_bytes(),b'existing')
        self.assertEqual((self.root/TARGET/'B 260401 신규 회신/회의록 신규.txt').read_bytes(),b'new')
        app.undo(journal['id']);self.assertEqual(self.snapshot(),before)

    def test_conflicting_manual_destination_is_not_overwritten(self):
        rows=[{'id':'a','relative':'메일 묶음/회의록.txt','name':'회의록.txt','destination':TARGET,'method':'rule'},
              {'id':'b','relative':'메일 묶음/첨부/회의록 도면.txt','name':'회의록 도면.txt','destination':'2 도면','method':'manual'}]
        app.keep_subfolders(rows)
        self.assertEqual(rows[1]['destination'],'2 도면');self.assertEqual(rows[1]['method'],'manual')

    def test_pdf_cover_does_not_pull_nested_attachments_out_of_the_bundle(self):
        source='여러 원본/설계사 회신 묶음'
        self.add(source+'/회의록.pdf',b'synthetic cover')
        self.add(source+'/1. 붙임/회의록 도면.txt',b'synthetic drawing')
        before=self.snapshot();plan,journal=self.move()
        self.assertEqual(self.snapshot(),{TARGET+'/A 설계사 회신 묶음/회의록.pdf':b'synthetic cover',
            TARGET+'/A 설계사 회신 묶음/1. 붙임/회의록 도면.txt':b'synthetic drawing'})
        app.undo(journal['id']);self.assertEqual(self.snapshot(),before)

    def test_same_named_loose_files_never_overwrite_and_undo_restores_names(self):
        self.add('회의록.txt',b'first')
        self.add('3107 회의 및 협의기록/회의록.txt',b'second')
        before=self.snapshot();plan=app.make_plan(self.project['id'],False)
        journal=app.execute_all(plan['id'],[{'id':r['id'],'destination':r['destination']} for r in plan['rows']],True)
        self.assertEqual(sorted(self.snapshot().values()),[b'first',b'second'])
        self.assertEqual(set(self.snapshot()),{TARGET+'/회의록.txt',TARGET+'/회의록 (2).txt'})
        app.undo(journal['id']);self.assertEqual(self.snapshot(),before)


if __name__=='__main__':unittest.main()
