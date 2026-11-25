"""3차 시험 반영(합성 자료): AI 답 부분 적용·새 폴더 제안, 4단계 새 폴더 추가, 보류가 많을 때 질문·답 적용, 보류 다시 묻기."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app

UNIT = '2. 시공단계/2. 공사/11. 실외기 구조 검토'
FILES = [UNIT + '/A 검토서/구조계산.dwg', UNIT + '/B 상세/받침 상세.dwg', UNIT + '/검토 의견.pdf',
         '9. 동아리실별 마감 확인/A실/사진 1.jpg', '9. 동아리실별 마감 확인/B실/사진 2.jpg',
         '250831 공사예정공정표_가상2차.xlsx', '251008 가상2차공사 공정표 ver1.pdf', '270101 공사예정공정표 변경.xlsx']
PLAN_PARENT = '2 기획 및 기본구상/1 사업계획'


class Round3(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); base = Path(self.tmp.name)
        self.dp = patch.object(app, 'DATA', base / 'data'); self.dp.start(); app.DATA.mkdir()
        app.atomic_json(app.DATA / 'prefs.json', {'autoClassify': False})
        self.root = base / '가상 사업'
        for i, rel in enumerate(FILES):
            path = self.root / rel; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(b'SYNTHETIC %d' % i)
        app.SELECTIONS['round3'] = str(self.root); app.PLANS.clear(); app.JOBS.clear()
        tree = [{'label': app.INBOX}] + copy.deepcopy(app.TEMPLATES['planning'])
        self.project = app.save_project({'selection': 'round3', 'name': '가상 사업', 'type': 'planning', 'tree': tree}, False)
        # 공사 계약 체결일(2026-06-01) 전의 예정 공정표만 기획 단계 '내부검토' 제안 대상이다.
        self.project['contracts'] = [{'id': 'c1', 'name': 'c1.pdf', 'analysis': {'title': '가상관 건축공사', 'kind': 'construction', 'signed_date': '2026-06-01'}}]
        app.store_project(self.project)
        self.plan = app.make_plan(self.project['id'], False)
        self.rows = {r['relative']: r for r in self.plan['rows'] if r.get('kind') != 'directory'}

    def tearDown(self):
        self.dp.stop(); app.SELECTIONS.pop('round3', None); app.PLANS.clear(); app.JOBS.clear(); self.tmp.cleanup()

    def test_rule_suggests_internal_review_folder_for_pre_construction_schedules(self):
        self.assertIn(PLAN_PARENT, self.plan['paths'])
        early = self.rows['250831 공사예정공정표_가상2차.xlsx'].get('folderSuggestion')
        self.assertEqual((early['parent'], early['name'], early['source']), (PLAN_PARENT, '내부검토', 'rule'))
        self.assertIsNone(self.rows['270101 공사예정공정표 변경.xlsx'].get('folderSuggestion'))  # 착공 뒤 → 시공 자료

    def test_add_plan_folder_numbers_the_folder_keeps_cache_and_routes_files(self):
        ids = [self.rows['250831 공사예정공정표_가상2차.xlsx']['id']]
        cache = app.get_project(self.project['id']).setdefault('classificationCache', {})
        row = self.rows[UNIT + '/검토 의견.pdf']
        cache[app.cache_key(self.plan, row)] = {'destination': '', 'method': 'hold', 'aiChecked': True}
        app.store_project(app.get_project(self.project['id']) | {'classificationCache': cache})
        result = app.dispatch('/add-plan-folder', {'plan': self.plan['id'], 'parent': PLAN_PARENT, 'name': '내부검토', 'rows': ids})
        self.assertEqual(result['path'], PLAN_PARENT + '/4 내부검토')
        self.assertIn(result['path'], self.plan['paths'])
        self.assertEqual(self.rows['250831 공사예정공정표_가상2차.xlsx']['destination'], result['path'])
        self.assertNotIn('folderSuggestion', self.rows['251008 가상2차공사 공정표 ver1.pdf'])  # 만든 제안은 정리
        saved = app.get_project(self.project['id'])
        self.assertIn(result['path'], app.work_paths(saved))
        self.assertIn(app.cache_key(self.plan, row), saved['classificationCache'])  # 새 구조 키로 옮김
        self.assertFalse((self.root / result['path']).exists())  # 실제 폴더는 이동 실행 때 만든다
        again = app.dispatch('/add-plan-folder', {'plan': self.plan['id'], 'parent': PLAN_PARENT, 'name': '내부검토', 'rows': []})
        self.assertEqual(again['path'], result['path'])  # 같은 이름이면 새로 만들지 않는다

    def test_questions_pick_the_folders_with_the_most_holds(self):
        for rel in FILES[:5]:
            self.rows[rel].update(destination='', method='hold')
        with patch.object(app, 'QUESTION_HOLD_COUNT', 3):
            questions = app.bulk_questions(self.plan['id'])
        self.assertTrue(questions['many'])
        units = [q['unit'] for q in questions['questions']]
        self.assertEqual(units[0], UNIT)
        self.assertLessEqual(len(units), 3)
        self.assertTrue(all(c in self.plan['paths'] for q in questions['questions'] for c in q['choices']))

    def test_answers_route_the_folder_add_new_folder_hold_and_become_guidance(self):
        for rel in FILES[:5]:
            self.rows[rel].update(destination='', method='hold')
        unit2 = self.rows['9. 동아리실별 마감 확인/A실/사진 1.jpg']['checkUnit']
        target = '4 시공단계/1 도급공사/8 승인요청'
        result = app.dispatch('/bulk-answers', {'plan': self.plan['id'], 'answers': [
            {'unit': UNIT, 'destination': target},
            {'unit': unit2, 'newFolder': {'parent': '5 인수인계', 'name': '마감 확인'}}]})
        self.assertTrue(all(self.rows[rel]['destination'] == target and self.rows[rel]['method'] == 'manual' for rel in FILES[:3]))
        self.assertRegex(self.rows[UNIT + '/A 검토서/구조계산.dwg'].get('keepSub'), r'^(?:[A-Z] )?실외기 구조 검토/A 검토서$')  # 폴더 이름·하위 구조 유지
        new = [p for p in result['paths'] if p.startswith('5 인수인계/') and p.endswith('마감 확인')]
        self.assertEqual(len(new), 1)
        self.assertTrue(all(self.rows[rel]['destination'] == new[0] for rel in FILES[3:5]))
        self.assertEqual({UNIT, unit2}, set(result['askedUnits']))
        self.assertEqual(self.plan['guidance'][0]['destination'], target)
        held = app.dispatch('/bulk-answers', {'plan': self.plan['id'], 'answers': [{'unit': '없는 폴더', 'hold': True}]})
        self.assertEqual(held['rows'], [])
        self.assertNotIn(UNIT, [q['unit'] for q in app.bulk_questions(self.plan['id'])['questions']])  # 다시 묻지 않음

    def test_retry_resends_held_files_ai_already_saw_with_guidance(self):
        for rel in FILES[:3]:
            self.rows[rel].update(destination='', method='hold', aiChecked=True)
        self.assertEqual(app.bulk_info(self.plan['id'])['count'], sum(1 for r in self.plan['rows'] if r['method'] == 'hold' and not r.get('aiChecked') and not r['done']))
        retry = app.bulk_info(self.plan['id'], retry=True)['count']
        self.assertGreaterEqual(retry, 3)
        self.plan['guidance'] = [{'original_folder': UNIT, 'destination': self.plan['paths'][3], 'samples': []}]
        seen = {}
        def answer(messages, **kwargs):
            import json
            payload = json.loads(messages[1]['content']); seen['guidance'] = payload['user_guidance']
            parent = next(k for k, v in payload['folders'].items() if v == PLAN_PARENT)
            return {'assignments': [{'file_id': f['file_id'], 'destination_id': None, 'reason': '근거', 'confidence': .5,
                                     'new_folder': {'parent_id': parent, 'name': '3. 내부검토'}} for f in payload['files']]}
        with patch.object(app, 'gateway', side_effect=answer):
            job = app.start_bulk(self.plan['id'], retry=True)
            app.JOBS[job['id']]['status'] = 'pending'
            app.run_bulk(job['id'])
        self.assertEqual(app.JOBS[job['id']]['status'], 'done', app.JOBS[job['id']])
        self.assertEqual(seen['guidance'][0]['original_folder'], UNIT)
        suggestion = self.rows[UNIT + '/검토 의견.pdf']['folderSuggestion']
        self.assertEqual((suggestion['parent'], suggestion['name'], suggestion['source']), (PLAN_PARENT, '내부검토', 'ai'))
        status = app.bulk_status(job['id'])
        self.assertIn('remaining', status); self.assertNotIn('guidance', status)

    def test_question_choices_drop_stage_only_and_merge_subfolders(self):
        # 4차 2번: '4 시공단계'처럼 넓은 보기는 빼고, 계약 가지 아래 '1 품의서' 같은 하위 폴더는 상위 보기 하나로 합친다.
        branch = '4 시공단계/3 설계의도 구현 용역'
        got = app.tidy_choices(['4 시공단계', branch + '/1 최초 품의 및 최초 계약서/1 품의서', branch, branch + '/1 최초 품의 및 최초 계약서',
                                '2 기획 및 기본구상/2 공사 전 건물 정보/3 석면조사 보고서', '4 시공단계/1 도급공사/13 기타공문'])
        self.assertEqual(got, [branch, '2 기획 및 기본구상/2 공사 전 건물 정보/3 석면조사 보고서', '4 시공단계/1 도급공사/13 기타공문'])

    def test_ai_new_folder_suggestion_is_validated(self):
        folders = {'d1': PLAN_PARENT}
        self.assertIsNone(app.folder_suggestion({'new_folder': {'parent_id': 'd9', 'name': '내부검토'}}, folders))
        self.assertIsNone(app.folder_suggestion({'new_folder': {'parent_id': 'd1', 'name': '../밖'}}, folders))
        self.assertIsNone(app.folder_suggestion({'new_folder': {'parent_id': 'd1', 'name': '가' * 30}}, folders))
        self.assertEqual(app.folder_suggestion({'new_folder': {'parent_id': 'd1', 'name': '4 내부검토'}}, folders)['name'], '내부검토')


if __name__ == '__main__':
    unittest.main()
