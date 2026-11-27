"""2026-11-28 LIM: 사업에 안전보건대장이 보이면 대분류에 'N 안전보건대장'을 넣고 기본·설계·시공 안전보건대장을 각각 모은다.
합성 자료만 쓴다."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app

FILES = {
    '251216 기본안전보건대장 보완/본문.hwp': b'BASIC',
    '251216 기본안전보건대장 보완/붙임/현장사진.jpg': b'PHOTO',
    '2. 설계/설계안전보건대장_최종.pdf': b'DESIGN',
    '3. 시공/공사안전보건대장/1차/대장.hwp': b'WORK1',
    '안전보건대장/2. 설계/검토의견.hwp': b'DESIGN-REVIEW',
    '2. 시공단계/3. 용역/1. 재해예방기술지도/2. 계약/원인행위(가상관 재해예방 기술지도 안전보건대장 관련 용역).pdf': b'CONTRACT',
}


class SafetyLedger(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); base = Path(self.tmp.name)
        self.dp = patch.object(app, 'DATA', base / 'data'); self.dp.start(); app.DATA.mkdir()
        app.atomic_json(app.DATA / 'prefs.json', {'autoClassify': False})
        self.root = base / '가상 사업'
        for rel, body in FILES.items():
            path = self.root / rel; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(body)
        (self.root / '251216 기본안전보건대장 보완/빈 폴더').mkdir()
        app.SELECTIONS['safety'] = str(self.root); app.PLANS.clear()
        tree = [{'label': app.INBOX}] + copy.deepcopy(app.TEMPLATES['construction'])
        self.project = app.save_project({'selection': 'safety', 'name': '가상 사업', 'type': 'construction', 'tree': tree}, False)

    def tearDown(self):
        self.dp.stop(); app.SELECTIONS.pop('safety', None); app.PLANS.clear(); self.tmp.cleanup()

    def files(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_ledger_folder_is_added_and_each_kind_is_collected_then_undone(self):
        before = self.files()
        plan = app.make_plan(self.project['id'], False)
        top = [n['label'] for n in app.get_project(self.project['id'])['tree']]
        root = next(label for label in top if label.endswith('안전보건대장'))
        self.assertRegex(root, r'^\d+ 안전보건대장$')
        self.assertEqual(int(root.split()[0]), max(int(t.split()[0]) for t in top if t[0].isdigit() and t != root) + 1)
        for kid in ('1 기본안전보건대장', '2 설계안전보건대장', '3 공사안전보건대장'):
            self.assertIn(root + '/' + kid, plan['paths'])
        rows = {r['relative']: r for r in plan['rows']}
        basic = rows['251216 기본안전보건대장 보완/본문.hwp']
        self.assertEqual(basic['destination'], root + '/1 기본안전보건대장')
        self.assertEqual(rows['251216 기본안전보건대장 보완/붙임/현장사진.jpg']['destination'], basic['destination'])  # 안쪽 사진도 묶음째
        self.assertEqual(rows['2. 설계/설계안전보건대장_최종.pdf']['destination'], root + '/2 설계안전보건대장')
        self.assertEqual(rows['3. 시공/공사안전보건대장/1차/대장.hwp']['destination'], root + '/3 공사안전보건대장')
        self.assertEqual(rows['안전보건대장/2. 설계/검토의견.hwp']['destination'], root + '/2 설계안전보건대장')
        contract = rows.get('2. 시공단계/3. 용역/1. 재해예방기술지도/2. 계약/원인행위(가상관 재해예방 기술지도 안전보건대장 관련 용역).pdf')
        self.assertFalse(contract and contract['destination'].startswith(root), contract)  # 용역 계약 이름은 대장이 아니다
        journal = app.execute_all(plan['id'], [{'id': r['id'], 'destination': r['destination']} for r in plan['rows'] if r.get('destination')])
        after = self.files()
        moved = {k: v for k, v in after.items() if k.startswith(root + '/1 기본안전보건대장/')}
        self.assertEqual(sorted(moved.values()), [b'BASIC', b'PHOTO'])
        self.assertTrue(any(k.endswith('기본안전보건대장 보완/붙임/현장사진.jpg') for k in moved), moved)  # 폴더 이름·하위 구조 유지
        self.assertTrue(any(p.name == '빈 폴더' for p in (self.root / root / '1 기본안전보건대장').rglob('*') if p.is_dir()))
        self.assertTrue(any(k.startswith(root + '/3 공사안전보건대장/') and k.endswith('공사안전보건대장/1차/대장.hwp') for k in after), after.keys())
        self.assertEqual(sorted(after.values()), sorted(before.values()))
        app.undo(journal['id'])
        self.assertEqual(self.files(), before)

    def test_ledger_inside_a_mapped_deliverable_stays_and_held_bundle_moves_whole(self):
        # 63동 수동 정리와 같게: 설계 '최종 성과품' 속 '9 설계안전보건대장'은 성과품 묶음에 남고,
        # 이름에 오타가 있는 '251216 기본안전보거대장 보완' 묶음은 폴더째 기본안전보건대장으로 간다.
        for rel in list(FILES):
            (self.root / rel).unlink()
        extra = {'1. 설계단계/8. 설계성과품/251211 최종 성과품/9 설계안전보건대장/날인.pdf': b'D1',
                 '1. 설계단계/8. 설계성과품/251211 최종 성과품/1 도면/평면도.dwg': b'D2',
                 '251216 기본안전보거대장 보완/251111 기본안전보건대장.hwp': b'B1',
                 '251216 기본안전보거대장 보완/보완_날인본.pdf': b'B2'}
        for rel, body in extra.items():
            path = self.root / rel; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(body)
        plan = app.make_plan(self.project['id'], False)
        rows = {r['relative']: r for r in plan['rows']}
        root = app.safety_ledger_root(app.get_project(self.project['id'])['tree'])
        design = rows['1. 설계단계/8. 설계성과품/251211 최종 성과품/9 설계안전보건대장/날인.pdf']
        self.assertFalse(design['destination'].startswith(root), design)
        self.assertEqual(design['destination'], rows['1. 설계단계/8. 설계성과품/251211 최종 성과품/1 도면/평면도.dwg']['destination'])
        for rel in ('251216 기본안전보거대장 보완/251111 기본안전보건대장.hwp', '251216 기본안전보거대장 보완/보완_날인본.pdf'):
            self.assertEqual(rows[rel]['destination'], root + '/1 기본안전보건대장', rows[rel])
            self.assertEqual(rows[rel]['keepSub'], 'A 251216 기본안전보거대장 보완')  # 폴더 이름 유지 + A·B·C 묶음 이름
        journal = app.execute_all(plan['id'], [{'id': r['id'], 'destination': r['destination']} for r in plan['rows'] if r.get('destination')])
        self.assertEqual(sorted(p.name for p in (self.root / root / '1 기본안전보건대장').rglob('*') if p.is_file()),
                         ['251111 기본안전보건대장.hwp', '보완_날인본.pdf'])
        app.undo(journal['id'])
        self.assertEqual({k: v for k, v in self.files().items()}, extra)

    def test_existing_ledger_folder_gets_the_three_kind_folders(self):
        # 2026-11-28 LIM 화면: '7 안전보건대장'만 생기고 안이 나뉘지 않았다 → 이미 있는 대분류에도 종류 폴더를 채운다.
        p = app.get_project(self.project['id']); p['tree'].append({'label': '7 안전보건대장', 'children': [{'label': '1 시공안전보건대장'}]}); app.store_project(p)
        plan = app.make_plan(self.project['id'], False)
        kids = [c['label'] for c in app.safety_ledger_node(app.get_project(self.project['id'])['tree'])['children']]
        self.assertEqual(kids, ['1 시공안전보건대장', '1 기본안전보건대장', '2 설계안전보건대장'])  # 사용자가 붙인 '시공' 이름은 공사 대장 칸으로 인정
        rows = {r['relative']: r for r in plan['rows']}
        self.assertEqual(rows['3. 시공/공사안전보건대장/1차/대장.hwp']['destination'], '7 안전보건대장/1 시공안전보건대장')
        self.assertEqual(rows['2. 설계/설계안전보건대장_최종.pdf']['destination'], '7 안전보건대장/2 설계안전보건대장')

    def test_ledger_without_kind_word_uses_the_folder_it_sits_in(self):
        # 2026-11-28 LIM 화면: '63동 …(시연)/2. 시공단계/2. 공사/안전보건대장/안전보건대장.hwpx'가 보류됐다.
        for rel in list(FILES):
            (self.root / rel).unlink()
        extra = {'63동 학생회관 환경개선사업 (시연)/2. 시공단계/2. 공사/안전보건대장/안전보건대장.hwpx': b'W',
                 '63동 학생회관 환경개선사업 (시연)/1. 설계단계/안전보건대장/대장 초안.hwp': b'D',
                 '63동 학생회관 환경개선사업 (시연)/0. 기획/안전보건대장.pdf': b'B',
                 '자료/안전보건대장/공사계획/모름.hwp': b'?'}
        for rel, body in extra.items():
            path = self.root / rel; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(body)
        plan = app.make_plan(self.project['id'], False)
        root = app.safety_ledger_root(app.get_project(self.project['id'])['tree'])
        self.assertTrue(root)
        rows = {r['relative']: r for r in plan['rows']}
        work = rows['63동 학생회관 환경개선사업 (시연)/2. 시공단계/2. 공사/안전보건대장/안전보건대장.hwpx']
        self.assertEqual(work['destination'], root + '/3 공사안전보건대장')
        self.assertTrue(work['keepSub'].endswith('안전보건대장'))  # 폴더째(이름 유지)
        self.assertEqual(rows['63동 학생회관 환경개선사업 (시연)/1. 설계단계/안전보건대장/대장 초안.hwp']['destination'], root + '/2 설계안전보건대장')
        self.assertEqual(rows['63동 학생회관 환경개선사업 (시연)/0. 기획/안전보건대장.pdf']['destination'], root + '/1 기본안전보건대장')
        self.assertFalse(rows['자료/안전보건대장/공사계획/모름.hwp']['destination'].startswith(root))  # 위치로도 모르면 넣지 않음

    def test_no_ledger_no_folder(self):
        for rel in list(FILES):
            (self.root / rel).unlink()
        (self.root / '착공계.hwp').write_bytes(b'X')
        app.make_plan(self.project['id'], False)
        self.assertFalse(app.safety_ledger_root(app.get_project(self.project['id'])['tree']))

    def test_kind_reading(self):
        self.assertEqual(app.safety_ledger_route('a/251216 기본안전보건대장 보완/x.hwp'), ('기본', 1))
        self.assertEqual(app.safety_ledger_route('안전보건대장/3. 시공/x.hwp'), ('시공', 1))
        self.assertEqual(app.safety_ledger_route('안전 보건 대장/설계/x.hwp'), ('설계', 1))
        self.assertIsNone(app.safety_ledger_route('안전보건대장/공사계획/x.hwp'))  # '공사계획'을 '공사'로 읽지 않는다
        self.assertIsNone(app.safety_ledger_route('계약/재해예방기술지도, 안전보건대장 관련 용역 계약서.pdf'))
        self.assertIsNone(app.safety_ledger_route('3 시공단계/착공계.hwp'))


if __name__ == '__main__':
    unittest.main()
