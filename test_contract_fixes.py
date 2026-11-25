"""계약서 자동 찾기 보완(합성 자료): 계약 내용 쪽 고르기, 계약 문서 자동 제외 완화, 같은 계약 묶기(표기 차이·발주자 상대자·
문서 제목뿐인 건명·장기계속계약 총차 기준), AI 답 고정, 파일 이름 바꾸기 보류."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app

COVER = '원인행위 결재 지출 요청 기안 문서번호 시설관리국 ' * 3
TERMS = '공사 계약서 계약금액 금 원 계약상대자 계약기간 착공 준공 계약보증금 '


def record(rid, title, party, signed='', **extra):
    analysis = {'title': title, 'party': party, 'signed_date': signed, 'is_contract': True, **extra}
    return {'id': rid, 'name': rid + '.pdf', 'analysis': analysis}


class PagePick(unittest.TestCase):
    def test_contract_terms_page_is_sent_with_the_cover(self):
        texts = [COVER, '붙임 목록 ' * 10, TERMS, '일반조건 ' * 20]
        self.assertEqual(app.pick_contract_pages(texts, 46), [0, 2])

    def test_scanned_pdf_sends_first_three_pages(self):
        self.assertEqual(app.pick_contract_pages(['', '', '', ''], 26), [0, 1, 2])

    def test_single_page_and_contract_on_first_page(self):
        self.assertEqual(app.pick_contract_pages([TERMS], 1), [0])
        self.assertEqual(app.pick_contract_pages([TERMS, COVER], 3), [0])


class Exclusion(unittest.TestCase):
    def check(self, relative, is_contract=False, analysis=None):
        result = {'name': Path(relative).name, 'preparedFrom': 'PDF 전체 3쪽 중 1쪽 이미지',
                  'analysis': {'is_contract': is_contract, 'title': '가상 용역', **(analysis or {})}}
        return app.contract_exclusion(result, {'relative': relative}, Path('/가상') / relative)

    def test_contract_named_document_is_kept_for_review_not_excluded(self):
        for relative in ['3. 용역/1. 기술지도/2. 계약/계약변경서류-가상관 재해예방 기술지도 용역_260417 (1).pdf',
                         '3. 용역/2. 감리/2. 계약/원인행위변경(가상관 감리 용역).pdf',
                         '3. 용역/2. 감리/2. 계약/스캔0001.pdf']:
            result = self.check(relative)
            self.assertFalse(result['ignored'], relative)
            self.assertTrue(result['contractDoubt'], relative)

    def test_conditions_unrelated_and_employment_documents_are_excluded(self):
        self.assertTrue(self.check('참고/공사계약일반조건 송부.pdf')['ignored'])
        self.assertTrue(self.check('참고/회의 자료.pdf')['ignored'])
        employment = self.check('2. 계약/근로계약서.pdf', True, {'is_employment_contract': True})
        self.assertTrue(employment['ignored'])

    def test_real_contract_is_kept(self):
        self.assertFalse(self.check('2. 계약/아무 이름.pdf', True)['ignored'])


class Grouping(unittest.TestCase):
    RECORDS = [
        # 도급공사: 총차 및 장기1차, 원인행위/계약변경, 같은 날 두 문서
        record('c1', '서울대학교 SNU Commons 가상관(63동) 식당라인 환경개선 건축공사(총차 및 장기1차)', '(주)가상건설', '2025-12-22',
               long_term=True, total_amount='10,000,000,000', total_period='2025-12-22~2027-06-30', annual_round=1, amount='3,000,000,000'),
        record('c2', '가상관(63동) 식당라인 환경개선 건축공사(총차 및 장기1차)', '가상건설', '2025-12-22', long_term=True, annual_round=1),
        record('c3', '서울대학교 가상관(63동) 식당라인 환경개선 건축공사(총차 및 장기1차) 변경계약서', '가상건설 주식회사', '2026-05-29',
               long_term=True, total_amount='11,000,000,000', total_period='2025-12-22~2027-08-31', annual_round=1, amount='3,500,000,000'),
        record('c4', '서울대학교 가상관(63동) 식당라인 환경개선 건축공사(장기2차)', '가상건설', '2026-07-01', long_term=True, annual_round=2),
        # 기술지도: 발주자를 상대자로 읽음, 문서 제목뿐인 건명, 사본 번호
        record('t1', '서울대학교 SNU Commons 가상관(63동) 및 다른관(67동) 환경개선 건축공사 재해예방 기술지도 안전보건대장 관련 용역', '가상기술원', '2025-12-08'),
        record('t2', '서울대학교 SNU Commons 가상관(63동) 및 다른관(67동) 환경개선 건축공사 재해예방기술지도, 안전보건대장 관련 용역 (1)', '서울대학교총장', '2026-04-17'),
        record('t3', '기술지도계약서', '가상기술원', '2025-12-22'),
        record('t4', 'SNU Commons 가상관(63동) 및 다른관(67동) 환경개선 건축공사 재해예방기술지도, 안전보건대장 관련 용역', '가상기술원', '2026-05-28'),
        # 음향: 층수·용역 표기 차이, 상대자를 발주 부서로 읽음
        record('a1', '가상관 라운지 건축음향 컨설팅', '서울대학교 시설관리국 시설과', '2026-02-05'),
        record('a2', '서울대학교 SNU Commons 가상관(63동) 2층 라운지 건축음향 컨설팅 용역', '가상음향', '2026-02-09'),
        # 같은 상대자의 서로 다른 용역은 합치지 않는다
        record('d1', '서울대학교 가상관(63동) 식당라인 환경개선 건축공사 실시설계 용역', '가상건축사사무소', '2025-09-15'),
        record('d2', '서울대학교 SNU Commons 가상관(63동) 식당라인 환경개선 건축공사 설계의도 구현 용역', '가상건축사사무소', '2025-12-22'),
    ]

    def resolve(self):
        return app.resolve_contract_versions([dict(r, analysis=dict(r['analysis'])) for r in self.RECORDS])

    def test_variants_collapse_to_real_contracts(self):
        result = self.resolve()
        groups = {frozenset([c['id']] + c.get('supersededIds', [])) for c in result['current']}
        self.assertEqual(groups, {frozenset({'c1', 'c2', 'c3', 'c4'}), frozenset({'t1', 't2', 't3', 't4'}),
                                  frozenset({'a1', 'a2'}), frozenset({'d1'}), frozenset({'d2'})})

    def test_latest_contract_and_long_term_totals_are_shown(self):
        result = {c['id']: c for c in self.resolve()['current']}
        construction = result['c4']
        self.assertEqual(construction['analysis']['amount'], '11,000,000,000')  # 총차 금액(가장 나중 계약서의 총차)
        self.assertEqual(construction['analysis']['period'], '2025-12-22~2027-08-31')
        self.assertTrue(construction['analysis']['long_term'])
        self.assertEqual(result['t4']['analysis']['party'], '가상기술원')  # 발주자가 아닌 상대자
        self.assertNotEqual(result['t4']['analysis']['title'], '기술지도계약서')  # 문서 제목뿐인 건명은 쓰지 않음
        self.assertEqual(result['a2']['analysis']['party'], '가상음향')

    def test_identity_ignores_owner_and_suffix_noise(self):
        self.assertEqual(app.contract_party_key('서울대학교총장'), '')
        self.assertEqual(app.contract_title_core('가상관 공사(총차 및 장기1차)'), app.contract_title_core('서울대학교 가상관 공사 (1)'))
        self.assertTrue(app.generic_contract_title('기술지도계약서'))
        self.assertFalse(app.similar_contract_core(app.contract_title_core('가상관 건축공사 실시설계 용역'),
                                                   app.contract_title_core('가상관 건축공사 설계의도 구현 용역')))


class AnalysisAndNames(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dp = patch.object(app, 'DATA', Path(self.tmp.name)); self.dp.start()
        (app.DATA / 'staging').mkdir()
        image = app.DATA / 'staging' / 'p.txt'; image.write_text('계약서 계약금액', encoding='utf-8')
        app.atomic_json(app.DATA / 'staging' / 'cid.json', {'id': 'cid', 'name': '계약서.pdf', 'path': str(image), 'sourceHash': 'h'})

    def tearDown(self):
        self.dp.stop(); self.tmp.cleanup()

    def test_analysis_is_deterministic_and_retries_a_broken_answer_once(self):
        calls = []
        def fake(messages, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                raise ValueError('AI가 올바른 결과를 보내지 않았습니다. 다시 검토하거나 보류해주세요.')
            return {'title': '가상 공사', 'is_contract': True}
        with patch.object(app, 'gateway', side_effect=fake):
            result = app.analyze_contract('cid')
        self.assertEqual(result['analysis']['title'], '가상 공사')
        self.assertEqual([c.get('temperature') for c in calls], [0, 0])
        self.assertIn('발주자', app.CONTRACT_PROMPT); self.assertIn('total_amount', app.CONTRACT_PROMPT)

    def test_numbers_and_bundles_from_ai_do_not_block_next(self):
        # 이미 숫자로 저장된 캐시(이전 판)도 '다음'에서 통과해야 한다.
        cached = {'title': '가상 공사', 'kind': 'construction', 'amount': 1200, 'total_amount': 3500000000,
                  'annual_amount': 1200000000.5, 'total_period': {'start': '2026-01-02', 'end': '2027-12-31'},
                  'annual_period': ['2026-01-02', '2026-12-31'], 'party': True, 'short_name': 'x' * 1500}
        rec = app.read_json(app.DATA / 'staging' / 'cid.json'); rec['analysis'] = dict(cached)
        app.atomic_json(app.DATA / 'staging' / 'cid.json', rec)
        updated = app.update_contract('cid', {'stage': '시공'})['analysis']
        self.assertEqual(updated['total_amount'], '3500000000')
        self.assertEqual(updated['annual_amount'], '1200000000.5')
        self.assertEqual(updated['amount'], '1200')
        self.assertEqual(updated['total_period'], '2026-01-02 ~ 2027-12-31')
        self.assertEqual(updated['annual_period'], '2026-01-02, 2026-12-31')
        self.assertIsNone(updated['party'])
        self.assertEqual(len(updated['short_name']), 1000)
        self.assertEqual(updated['stage'], '시공')
        # AI 분석 결과도 받을 때 같은 정리를 해서 남긴다.
        with patch.object(app, 'gateway', return_value=dict(cached, kind='goods', stage='착공')):
            analysed = app.analyze_contract('cid')['analysis']
        self.assertEqual(analysed['total_amount'], '3500000000')
        self.assertEqual(analysed['kind'], 'unknown'); self.assertIsNone(analysed['stage'])
        self.assertEqual(app.read_json(app.DATA / 'contract-cache' / 'h.json')['analysis']['total_period'], '2026-01-02 ~ 2027-12-31')
        with self.assertRaises(Exception):
            app.update_contract('cid', {'stage': '착공'})

    def test_user_chosen_kind_wins_over_title_and_survives_merging(self):
        rec = app.read_json(app.DATA / 'staging' / 'cid.json')
        rec['analysis'] = {'title': '가상관 재해예방 기술지도 용역', 'kind': 'service', 'signed_date': '2026-01-02'}
        app.atomic_json(app.DATA / 'staging' / 'cid.json', rec)
        self.assertEqual(app.contract_category(rec['analysis']), 'service')
        saved = app.update_contract('cid', {'kind': 'material', 'kind_confirmed': True})['analysis']
        self.assertTrue(saved['kind_confirmed'])
        self.assertEqual(app.contract_category(saved), 'material')  # 건명의 '기술지도 용역'보다 사용자가 고른 값
        older = record('old', '가상관 재해예방 기술지도 용역', '가상기술원', '2025-12-01', kind='service')
        newer = record('new', '가상관 재해예방 기술지도 용역 변경계약서', '가상기술원', '2026-02-01', kind='service')
        older['analysis'].update(kind='material', kind_confirmed=True)
        merged = app.resolve_contract_versions([older, newer])['current'][0]['analysis']
        self.assertEqual((merged['kind'], merged.get('kind_confirmed')), ('material', True))
        unknown = app.update_contract('cid', {'kind': 'unknown', 'kind_confirmed': True})['analysis']
        self.assertNotIn('kind_confirmed', unknown)

    def test_plan_progress_estimates_remaining_time_after_ten_seconds(self):
        with patch.object(app, 'PROGRESS', {}):
            app.plan_progress('scan', started=1000.0)
            with patch.object(app.time, 'time', return_value=1005.0):
                app.plan_progress('classify', 0, 100)
            self.assertIsNone(app.PROGRESS['plan']['remaining'])  # 10초 전에는 추정하지 않는다
            with patch.object(app.time, 'time', return_value=1060.0):
                app.plan_progress('content', 50, 100)  # 35~90% 구간의 절반 = 62.5%
            state = app.PROGRESS['plan']
            self.assertEqual((state['percent'], state['elapsed'], state['remaining']), (62, 60, 36))

    def test_contract_file_names_are_left_unchanged_by_default(self):
        self.assertFalse(app.CONTRACT_RENAME)
        rec = record('x', '가상관 건축공사', '가상건설', '2026-01-02', kind='construction')
        self.assertEqual(app.proposed_contract_name(rec, '스캔0001.pdf'), '')


if __name__ == '__main__':
    unittest.main()
