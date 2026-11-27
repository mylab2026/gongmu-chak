"""사용자가 직접 만든 사업 폴더(1. 설계단계 / 2. 시공단계/2. 공사 / 3. 용역/<용역명>)를 단계·계약 범위 안에서 대응한다.
실사용 폴더에서 확인한 누락·오분류를 합성 자료로 재현한다(실제 문서·이름 없음)."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app

C = '4 시공단계/1 도급공사'
D = '3 설계단계/1 설계 용역'
S_TECH = '4 시공단계/2 재해예방 기술지도 용역'
S_DESIGN = '4 시공단계/3 디자인 감리 용역'
S_SOUND = '4 시공단계/4 음향컨설팅 용역'
S_STRUCT = '4 시공단계/5 구조도면 현행화 및 안전진단 용역'

FILES = {
    # 계약서 찾기
    '2. 시공단계/3. 용역/2. 디자인 감리/2. 계약/원인행위(가상관 설계의도 구현 용역).pdf': None,
    '2. 시공단계/3. 용역/4. 구조도면 현행화 용역/4. 계약서/원인행위(가상관 구조도면 현행화 및 안전진단 용역).pdf': None,
    '2. 시공단계/3. 용역/1. 재해예방기술지도/2. 계약/원인행위(가상관 재해예방 기술지도 안전보건대장 관련 용역).pdf': None,
    '2. 시공단계/2. 공사/3. 계약/최초/계약서_원인행위(가상관 환경개선 건축공사).pdf': None,
    '2. 시공단계/2. 공사/3. 계약/변경1차/원인행위변경(가상관 환경개선 건축공사).pdf': None,
    '2. 시공단계/2. 공사/3. 계약/변경3차/계약변경(가상관 환경개선 건축공사).pdf': None,
    '참고/공사계약일반조건 송부.pdf': None,
    '2. 시공단계/3. 용역/1. 재해예방기술지도/5. 설계변경/4차/붙임서류_계약변경 요청 공문.pdf': None,
    '2. 시공단계/3. 용역/1. 재해예방기술지도/3. 공문/완수계/준공검사조서 -계약변경 후 작성.pdf': None,
    '2. 시공단계/2. 공사/4. 공문/3. 노무비 신청/1월/가상건설_근로계약서.pdf': None,
    # 도급공사 업무 폴더
    '2. 시공단계/2. 공사/1. 시행품의/1-2. 도면_가상관 환경개선 건축공사.pdf': C + '/1 최초 품의 및 최초 계약서/1 품의서',
    '2. 시공단계/2. 공사/4. 공문/2. 선금신청/선금 신청 공문.pdf': C + '/5 지출서류/1 선금',
    '2. 시공단계/2. 공사/4. 공문/3. 노무비 신청/1월/노무비 청구.pdf': C + '/5 지출서류/2 노무비',
    '2. 시공단계/2. 공사/4. 공문/10. 준공계 제출/09.자재승인서류/자재승인요청서.pdf': C + '/12 준공계',
    '2. 시공단계/2. 공사/4. 공문/10. 준공계 제출/준공계.pdf': C + '/12 준공계',
    '2. 시공단계/2. 공사/12. 설계변경/설계변경 1차/검토의견서.hwp': C + '/7 설계변경/1 1차 설계변경',
    '2. 시공단계/2. 공사/12. 설계변경/설계변경 3차/검토의견서.hwp': C + '/7 설계변경',
    '2. 시공단계/2. 공사/7. 추가도면/[가상2차] 라운지 설계변경도면/평면도.pdf': C + '/2 시공사에 제공 한 자료',
    '2. 시공단계/2. 공사/6. 사진/260124/IMG_0001.jpg': C + '/11 사진',  # 공사 전·중·후는 모아보기에서 촬영일로 나눈다
    '2. 시공단계/2. 공사/6. 사진/준공 후 사진/IMG_0002.jpg': C + '/11 사진',
    '2. 시공단계/2. 공사/14. 작업일보/작업일보 0105.pdf': C + '/15 작업일보',
    '2. 시공단계/2. 공사/24. 인수인계/열쇠 인계 확인서.pdf': '5 인수인계/1 인수인계 도서',
    # 용역: 용역 자료가 도급공사로 가지 않는다
    '2. 시공단계/3. 용역/3. 음향컨설팅/3. 공문/3. 준공계/준공계.pdf': S_SOUND + '/7 완수계/1 완수계 공문 및 검사 조서',
    '2. 시공단계/3. 용역/3. 음향컨설팅/1. 구매품의/비교견적서.pdf': S_SOUND + '/1 최초 품의 및 최초 계약서/1 품의서',
    '2. 시공단계/3. 용역/2. 디자인 감리/1. 품의/2. 변경 품의/1차/합의서.pdf': S_DESIGN + '/6 설계변경/1 1차 설계변경',
    '2. 시공단계/3. 용역/4. 구조도면 현행화 용역/3. 성과품/구조안전진단 보고서.pdf': S_STRUCT + '/7 완수계/2 최종 성과품',
    '2. 시공단계/2. 공사/16. 구조도면 현행화 용역/구조도면 현행화 용역/a.pdf': None,
    '2. 시공단계/3. 용역/9. 모르는 컨설팅/검토서.pdf': '',
    # 설계단계 = 설계 용역
    '1. 설계단계/3. 공문/1. 착수계/착수계.pdf': D + '/3 착수계',
    '1. 설계단계/3. 공문/2. 완수계/용역검사조서.pdf': D + '/8 완수계/1 완수계 공문 및 검사 조서',
    '1. 설계단계/5. 회의/250926 착수보고회/회의록.hwp': D + '/6 회의 및 협의기록',
    '1. 설계단계/8. 설계성과품/최종 성과품/공사용도면.pdf': D + '/8 완수계/2 최종 성과품',
    '1. 설계단계/100. 설계사 송부 자료/현황도면.pdf': D + '/2 용역사에 제공 한 자료',
    # 단계 밖 맨 위 폴더
    '4. 공사전 사진/IMG_0003.jpg': C + '/11 사진/1 공사전',
    '7. 경과보고/경과보고.hwp': '1 공통/2 주요 보고자료',
}


def tree():
    nodes = copy.deepcopy(app.TEMPLATES['planning'])
    stage = next(n for n in nodes if '시공' in n['label'])
    service = next(c for c in stage['children'] if '용역' in c['label'])
    construction, material = [c for c in stage['children'] if c is not service]
    names = ['재해예방 기술지도 용역', '디자인 감리 용역', '음향컨설팅 용역', '구조도면 현행화 및 안전진단 용역']
    services = []
    for i, name in enumerate(names):
        node = copy.deepcopy(service); node['label'] = f'{i + 2} {name}'; services.append(node)
    material['label'] = '6 관급자재 1'
    stage['children'] = [construction] + services + [material]
    return [{'label': app.INBOX}] + nodes


class UserFolderScope(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); base = Path(self.tmp.name)
        self.dp = patch.object(app, 'DATA', base / 'data'); self.dp.start(); app.DATA.mkdir()
        app.atomic_json(app.DATA / 'prefs.json', {'autoClassify': False})
        self.root = base / '가상 사업'
        for i, relative in enumerate(FILES):
            path = self.root / relative; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(('SYNTHETIC %d' % i).encode())
        app.SELECTIONS['scope'] = str(self.root); app.PLANS.clear()
        self.project = app.save_project({'selection': 'scope', 'name': '가상 사업', 'type': 'planning', 'tree': tree()}, False)

    def tearDown(self):
        self.dp.stop(); app.SELECTIONS.pop('scope', None); app.PLANS.clear(); self.tmp.cleanup()

    def files(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*') if p.is_file() and '.gongmu-chak' not in p.parts}

    def test_dot_numbered_folder_names_are_ordering_marks(self):
        self.assertEqual(app.label_word('2. 시공단계'), '시공단계')
        self.assertEqual(app.label_word('1) 품의'), '품의')
        self.assertEqual(app.label_word('03 착공계'), '착공계')
        self.assertEqual(app.semantic_label('12. 설계변경'), '설계변경')

    def test_asbestos_topic_folder_is_not_a_service(self):
        self.assertEqual(app.service_word('6. 석면관련'), '')
        self.assertEqual(app.service_word('석면 대응'), '')
        self.assertEqual(app.service_word('7 석면 해체 제거 용역'), '석면')
        self.assertEqual(app.service_word('2 기술지도 용역'), '기술지도')
        relative = '6. 석면관련/2. 고용노동부 관계서류/제출 공문.pdf'
        path = self.root / relative; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(b'SYNTHETIC asbestos')
        plan = app.make_plan(self.project['id'], False)
        row = next(r for r in plan['rows'] if r['relative'] == relative)
        self.assertNotIn('용역', row['reason'])
        self.assertFalse(row['destination'].startswith('4 시공단계/'), row['destination'])

    def test_contract_search_finds_cause_documents_and_skips_conditions_and_requests(self):
        found = {c['relative'] for c in app.contract_candidates({'selection': 'scope'})['candidates']}
        for relative in list(FILES)[:6]:
            self.assertIn(relative, found)
        for relative in list(FILES)[6:10]:
            self.assertNotIn(relative, found)

    def test_folders_map_inside_their_own_stage_and_contract(self):
        plan = app.make_plan(self.project['id'], False)
        rows = {r['relative']: r for r in plan['rows'] if r.get('kind') != 'directory'}
        for relative, expected in FILES.items():
            if expected is None:
                continue
            row = rows[relative]
            if expected == '':
                self.assertEqual(row['destination'], '', relative)
            else:
                self.assertEqual(row['destination'], expected, relative + ' · ' + row['reason'])
        third = rows['2. 시공단계/2. 공사/12. 설계변경/설계변경 3차/검토의견서.hwp']
        self.assertTrue(third['keepSub'].startswith('3 3차 설계변경'), third.get('keepSub'))
        # A service's 준공계 never goes to the construction contract's 준공계.
        self.assertFalse(any(r['destination'].startswith(C) for k, r in rows.items() if '/3. 용역/' in k and r['destination']))

    def test_move_then_undo_keeps_bytes_and_paths(self):
        before = self.files()
        plan = app.make_plan(self.project['id'], False)
        chosen = [{'id': r['id'], 'destination': r['destination']} for r in plan['rows'] if r['destination']]
        journal = app.execute_all(plan['id'], chosen, True)
        self.assertEqual(sorted(self.files().values()), sorted(before.values()))
        moved = {e.get('destination', '') for e in journal['entries']}
        self.assertTrue(any('3 3차 설계변경' in m for m in moved))
        app.undo(journal['id'])
        self.assertEqual(self.files(), before)


if __name__ == '__main__':
    unittest.main()
