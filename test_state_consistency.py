"""Production regressions distilled from the browser sample state fixes (synthetic files only)."""
import tempfile
import unittest
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import app


class StateConsistency(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / '사업'
        self.root.mkdir()
        self.patch = patch.object(app, 'DATA', self.base / 'settings')
        self.patch.start()
        app.DATA.mkdir()
        for store in (app.PLANS, app.JOBS, app.INDEX_JOBS, app.EXPORTS, app.SELECTIONS):
            store.clear()
        app.SELECTIONS['test'] = str(self.root)
        tree = [{'label': app.INBOX}, {'label': '1 자료'}, {'label': '2 공문'},
                {'label': '3 사진', 'children': [{'label': '1 공사전'}, {'label': '2 공사중'}, {'label': '3 공사후'}]}]
        self.pid = app.save_project({'selection': 'test', 'name': '시험 사업', 'tree': tree}, False)['id']

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def write(self, relative, text='공정표 검토 자료'):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path

    def photo(self):
        from PIL import Image
        relative = '보고 묶음/공사전 사진.jpg'
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new('RGB', (16, 16), 'white').save(path)
        return relative

    def index(self):
        app.INDEX_JOBS['test'] = {'projectId': self.pid, 'status': 'pending', 'processed': 0, 'count': 0, 'read': 0}
        app.run_index('test')
        return app.INDEX_JOBS['test']

    def move(self, relative, destination='1 자료'):
        plan = app.make_plan(self.pid, False)
        row = next(r for r in plan['rows'] if r['relative'] == relative)
        journal = app.execute(plan['id'], [{'id': row['id'], 'destination': destination}])
        self.assertEqual(journal['entries'][0]['status'], 'moved')
        return journal

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_index_follows_two_move_batches_and_undo_without_rereading_text(self):
        sources = [app.INBOX + '/공정자료1.txt', app.INBOX + '/공정자료2.txt']
        for source in sources:
            self.write(source)
        self.assertEqual(self.index()['status'], 'done')
        with patch.object(app, 'local_text', side_effect=AssertionError('unchanged text must be reused')):
            journals = [self.move(source) for source in sources]
            expected = {j['entries'][0]['destination'] for j in journals}
            self.assertEqual({r['relative'] for r in app.search_files(self.pid, '공정표')['results']}, expected)
            self.assertEqual({r['relative'] for r in app.browse_folder(self.pid, '1 자료')['results']}, expected)
            app.undo(journals[0]['id'])
            expected.remove(journals[0]['entries'][0]['destination'])
            expected.add(sources[0])
            self.assertEqual({r['relative'] for r in app.search_files(self.pid, '공정표')['results']}, expected)
        self.assertEqual(self.index()['read'], 0)

    def test_inflight_index_cannot_overwrite_migrated_paths(self):
        relative = app.INBOX + '/공정자료.txt'
        self.write(relative)
        self.index()
        self.write(relative, '공정표 내용 수정')
        plan = app.make_plan(self.pid, False)
        row = next(r for r in plan['rows'] if r['relative'] == relative)
        original = app.local_text
        moved = []
        def move_while_reading(path):
            text = original(path)
            if not moved:
                moved.append('pending')
                journal = app.execute(plan['id'], [{'id': row['id'], 'destination': '1 자료'}])
                moved[0] = journal['entries'][0]['destination']
            return text
        with patch.object(app, 'local_text', side_effect=move_while_reading):
            job = self.index()
        self.assertEqual(job['status'], 'failed')
        self.assertNotIn(relative, app.read_json(app.index_file(self.pid))['files'])
        self.assertEqual(self.index()['status'], 'done')
        self.assertEqual(app.search_files(self.pid, '공정표')['results'][0]['relative'], moved[0])

    def test_partial_finish_counts_and_photo_counts_already_follow_state(self):
        for i in range(2):
            self.write(app.INBOX + '/자료' + str(i) + '.txt')
        plan = app.make_plan(self.pid, True)
        app.execute(plan['id'], [{'id': plan['rows'][0]['id'], 'destination': '1 자료'}])
        self.assertEqual(app.finish_plan(plan['id'])['movedCount'], 1)
        relative = self.photo()
        app.set_photo_phase(self.pid, relative, 'after')
        data = app.collect(self.pid)
        self.assertEqual(data['counts']['after'], 1)
        self.assertEqual(data['counts']['before'], 0)

    def assert_stale_export(self, change):
        self.photo()
        initial = app.export_plan(self.pid)
        app.export_run(self.pid, initial['id'])
        plan = app.export_plan(self.pid)
        change()
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, '다시 확인'):
            app.export_run(self.pid, plan['id'])
        self.assertEqual(self.snapshot(), before, 'stale approval must not create, remove or rewrite outputs')

    def test_export_rejects_changed_photo_phase_before_writing(self):
        self.assert_stale_export(lambda: app.set_photo_phase(self.pid, '보고 묶음/공사전 사진.jpg', 'after'))

    def test_export_rejects_moved_file_before_removing_existing_links(self):
        self.assert_stale_export(lambda: self.move('보고 묶음/공사전 사진.jpg', '3 사진/1 공사전'))

    def test_export_rejects_added_photo(self):
        self.assert_stale_export(lambda: self.write('보고 묶음/새 공사전 사진.jpg', 'new photo'))

    def test_export_rejects_changed_original(self):
        self.assert_stale_export(lambda: self.write('보고 묶음/공사전 사진.jpg', 'changed original'))

    def test_export_rejects_changed_official_confirmation(self):
        from PIL import Image
        relative = '보고 묶음/공문.pdf'
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new('RGB', (64, 64), 'white').save(path, 'PDF')
        self.assert_stale_export(lambda: app.set_official(self.pid, relative, True))

    def test_export_rejects_changed_tree(self):
        def change():
            project = app.get_project(self.pid)
            project['tree'][-1]['label'] = '3 현장 사진'
            app.store_project(project)
        self.assert_stale_export(change)

    def test_export_unchanged_repeat_keeps_links(self):
        self.photo()
        plan = app.export_plan(self.pid)
        first = app.export_run(self.pid, plan['id'])
        second = app.export_run(self.pid, plan['id'])
        self.assertEqual(first['created'], second['kept'])
        self.assertEqual(second['created'], [])

    def test_legacy_official_collection_does_not_trust_match_without_structure(self):
        relative = '참고/공문 작성 요령.txt'
        self.write(relative, '공문을 작성하는 방법에 대한 안내입니다.')
        item = app.save_collection(self.pid, {'name': '공문', 'text': '공문'})
        with patch.object(app, 'gateway', return_value={'decision': 'match', 'evidence': {'내용': '공문 안내'}}):
            app.verify_collection(self.pid, item['id'], [relative])
        result = app.run_collection(self.pid, item['id'])
        self.assertEqual(result['verified'], [])
        self.assertEqual(len(result['unclear']), 1)

    def test_legacy_official_can_use_fields_extracted_from_real_text(self):
        relative = '참고/공문.txt'
        self.write(relative, '문서번호: 예시-2026-001\n제목: 공정 협의 요청\n발신: 예시건설\n수신: 시설지원과')
        item = app.save_collection(self.pid, {'name': '공문', 'text': '공문'})
        with patch.object(app, 'gateway', return_value={'decision': 'match', 'evidence': {'내용': '공정 협의'}}):
            app.verify_collection(self.pid, item['id'], [relative])
        self.assertEqual(len(app.run_collection(self.pid, item['id'])['verified']), 1)

    def test_nonofficial_collections_do_not_require_official_fields(self):
        relative = '참고/공정표.txt'
        self.write(relative)
        item = app.save_collection(self.pid, {'name': '공정표', 'text': '공정표'})
        with patch.object(app, 'gateway', return_value={'decision': 'match', 'evidence': {'내용': '공정표'}}):
            app.verify_collection(self.pid, item['id'], [relative])
        self.assertEqual(len(app.run_collection(self.pid, item['id'])['verified']), 1)

    def test_only_official_collections_invalidate_pre_structure_cache(self):
        relative = '참고/공문 작성 요령.txt'
        path = self.write(relative, '공문 안내')
        for text in ('공문', '보고서'):
            conditions = app.parse_collection(text)
            context = app.verification_context(app.get_project(self.pid), relative)
            old_raw = json.dumps({'sha256': app.file_hash(path), 'context': context,
                                  'c': {k: v for k, v in conditions.items() if k != 'text'},
                                  'v': app.VERIFY_VERSION}, ensure_ascii=False, sort_keys=True)
            old_key = hashlib.sha256(old_raw.encode()).hexdigest()[:32]
            new_key = app.verify_key(app.file_hash(path), conditions, context)
            if text == '보고서':
                self.assertEqual(new_key, old_key)
                continue
            item = app.save_collection(self.pid, {'name': text, 'conditions': conditions})
            project = app.get_project(self.pid)
            project['collectionChecks'] = {old_key: {'relative': relative, 'decision': 'match',
                                                    'fields': {}, 'evidence': {'내용': '공문'}}}
            app.store_project(project)
            result = app.run_collection(self.pid, item['id'])
            self.assertEqual(result['verified'], [])
            self.assertEqual(len(result['candidates']), 1)

    def test_unknown_undo_id_does_not_change_files(self):
        before = self.snapshot()
        with self.assertRaises(ValueError):
            app.undo('unknown')
        self.assertEqual(self.snapshot(), before)
