"""Bounded I/O and cache invalidation on synthetic projects, without live AI."""
import copy
import json
import os
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import app
import doctext


class LargeProjectPerformance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / '사업'
        self.root.mkdir()
        self.data = patch.object(app, 'DATA', self.base / 'settings')
        self.data.start()
        self.addCleanup(self.data.stop)
        app.DATA.mkdir()
        app.SELECTIONS['performance'] = str(self.root)
        tree = [{'label': app.INBOX}, {'label': '1 공통', 'children': [
            {'label': '1 회의록'}, {'label': '2 공정표'}, {'label': '3 계약서'}]}]
        self.project = app.save_project({'selection': 'performance', 'name': '합성 사업', 'tree': tree}, False)

    def write(self, name, content=b'synthetic'):
        path = self.root / app.INBOX / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def plan(self):
        return app.make_plan(self.project['id'], True)

    def row(self, plan, name='0001.txt'):
        return next(row for row in plan['rows'] if row['name'] == name)

    def read_counter(self, target, sizes):
        original = Path.open
        class Reader:
            def __init__(self, stream): self.stream = stream
            def __enter__(self): return self
            def __exit__(self, *args): return self.stream.__exit__(*args)
            def read(self, size=-1):
                data = self.stream.read(size)
                sizes.append(len(data))
                return data
        def opening(path, *args, **kwargs):
            stream = original(path, *args, **kwargs)
            mode = args[0] if args else kwargs.get('mode', 'r')
            return Reader(stream) if path == target and mode == 'rb' else stream
        return patch.object(Path, 'open', opening)

    def test_text_extract_reads_only_the_prefix_for_each_encoding(self):
        for suffix, encoding in [('.txt', 'utf-8'), ('.csv', 'cp949'), ('.md', 'utf-8')]:
            with self.subTest(suffix=suffix):
                prefix = ('회의록 내용입니다. ' * 3000).encode(encoding)
                source = self.write('0001' + suffix, prefix + b'x' * (1024 * 1024))
                sizes = []
                with self.read_counter(source, sizes): text = doctext.extract(source)
                self.assertTrue(text.startswith('회의록 내용입니다.'))
                self.assertLessEqual(sum(sizes), 16000)

    def test_ai_text_excerpt_reads_only_the_sent_prefix(self):
        source = self.write('0001.txt', '회의록'.encode() + b'x' * (1024 * 1024))
        sizes = []
        with self.read_counter(source, sizes): parts, _ = app.excerpt(source, 1)
        self.assertTrue(parts[0]['text'].startswith('회의록'))
        self.assertLessEqual(sum(sizes), 12000)

    def test_plan_reuses_persisted_text_and_rereads_changed_file(self):
        source = self.write('0001.txt', '회의록 현장 협의 내용'.encode())
        with patch.object(app, 'local_text', wraps=app.local_text) as extract:
            self.assertIn('회의록', self.row(self.plan())['destination'])
            self.assertIn('회의록', self.row(self.plan())['destination'])
            self.assertEqual(extract.call_count, 1)
            source.write_text('공정표 검토 내용 추가', encoding='utf-8')
            self.assertIn('공정표', self.row(self.plan())['destination'])
            self.assertEqual(extract.call_count, 2)

    def test_empty_extraction_is_retried_not_persisted(self):
        self.write('0001.txt')
        with patch.object(app, 'local_text', side_effect=['', '회의록 현장 내용']) as extract:
            self.plan()
            self.assertIn('회의록', self.row(self.plan())['destination'])
            self.assertEqual(extract.call_count, 2)

    def test_extraction_during_an_edit_does_not_poison_cache(self):
        source = self.write('0001.txt', '회의록'.encode())
        def changed(_):
            source.write_text('공정표 최신 자료 추가', encoding='utf-8')
            return '회의록'
        with patch.object(app, 'local_text', side_effect=changed): self.plan()
        self.assertIn('공정표', self.row(self.plan())['destination'])

    def test_fresh_finder_index_is_used_instead_of_stale_collection_text(self):
        source = self.write('0001.txt', '회의록'.encode())
        relative = source.relative_to(self.root).as_posix()
        app.atomic_json(app.DATA / 'collection-text' / (self.project['id'] + '.json'),
                        {relative: {'fp': 'old', 'text': '공정표'}})
        app.atomic_json(app.index_file(self.project['id']),
                        {'files': {relative: {'fp': app.fingerprint(source), 'text': '회의록'}}})
        with patch.object(app, 'local_text', side_effect=AssertionError('fresh index must be reused')):
            self.assertIn('회의록', self.row(self.plan())['destination'])

    def test_recheck_caches_text_under_current_path_not_old_origin(self):
        source = self.write('0001.txt', '회의록 현장 협의'.encode())
        relative = source.relative_to(self.root).as_posix()
        virtual = [{'relative': '이전자료/0001.txt', 'current': relative, 'name': source.name,
                    'size': source.stat().st_size, 'mtime': source.stat().st_mtime_ns}]
        with patch.object(app, 'local_text', wraps=app.local_text) as extract:
            for _ in range(2):
                self.assertIn('회의록', self.row(app.make_plan(self.project['id'], False, virtual))['destination'])
            self.assertEqual(extract.call_count, 1)
        cached = app.collection_text_index(self.project['id'])
        self.assertIn(relative, cached)
        self.assertNotIn('이전자료/0001.txt', cached)

    def setup_bulk(self):
        source = self.write('계약서.jpg', b'first candidate')
        for i in range(72): self.write(f'받은 묶음/{i:04d}.dat')
        return source

    @staticmethod
    def answer(messages):
        rows = json.loads(messages[-1]['content'])['files']
        return {'assignments': [{'file_id': row['file_id'], 'destination_id': None,
                                 'reason': '합성 응답: 보류', 'confidence': 0.1} for row in rows]}

    def bulk(self, plan, recheck=False, expected_status='done'):
        info = app.bulk_info(plan['id'], recheck)
        job_id = plan['id'] + str(recheck)
        app.JOBS[job_id] = {'id': job_id, 'planId': plan['id'], 'recheck': recheck,
                            'status': 'pending', 'processed': 0, 'completedBatches': 0, **info}
        app.run_bulk(job_id)
        self.assertEqual(app.JOBS[job_id]['status'], expected_status, app.JOBS[job_id])
        return app.JOBS[job_id]

    def test_contract_candidate_is_hashed_once_per_bulk_job(self):
        source = self.setup_bulk()
        with patch.object(app, 'file_hash', wraps=app.file_hash) as digest, patch.object(app, 'gateway', side_effect=self.answer):
            plan = self.plan()
            job = self.bulk(plan)
            self.assertEqual(job['completedBatches'], 3)
            self.assertEqual(sum(Path(call.args[0]) == source for call in digest.call_args_list), 2)
            self.bulk(plan, True)
            self.assertEqual(sum(Path(call.args[0]) == source for call in digest.call_args_list), 3)

    def test_changed_contract_is_rehashed_during_the_same_job(self):
        source = self.setup_bulk()
        calls = 0
        def change(messages):
            nonlocal calls
            calls += 1
            if calls == 2: source.write_bytes(b'changed candidate with different bytes')
            return self.answer(messages)
        with patch.object(app, 'file_hash', wraps=app.file_hash) as digest, patch.object(app, 'gateway', side_effect=change):
            self.bulk(self.plan())
        self.assertEqual(sum(Path(call.args[0]) == source for call in digest.call_args_list), 3)

    def test_edit_during_hashing_stops_the_job_before_reusing_the_digest(self):
        for legacy in (False, True):
            with self.subTest(legacy_source_without_hash=legacy):
                source = self.setup_bulk()
                if legacy:
                    project = app.get_project(self.project['id'])
                    project['contracts'] = [{'id': 'legacy', 'name': source.name, 'sourcePath': str(source),
                                              'analysis': {'title': '가상 공사', 'kind': 'construction'}}]
                    app.store_project(project)
                plan = self.plan()
                original = app.file_hash
                changed = []
                def edit(path):
                    digest = original(path)
                    if Path(path) == source and not changed:
                        changed.append(True)
                        source.write_bytes(b'edited during hashing')
                    return digest
                with patch.object(app, 'file_hash', side_effect=edit), patch.object(app, 'gateway', side_effect=self.answer):
                    job = self.bulk(plan, expected_status='failed')
                self.assertIn('파일이 변경', job['error'])

    def test_same_stat_different_paths_do_not_share_contract_identity(self):
        first = self.setup_bulk()
        second = self.write('다른 계약서.jpg', b'second document')
        for source in (first, second): os.utime(source, ns=(1784000000000000000, 1784000000000000000))
        with patch.object(app, 'file_hash', wraps=app.file_hash) as digest, patch.object(app, 'gateway', side_effect=self.answer):
            self.bulk(self.plan())
        counts = Counter(Path(call.args[0]) for call in digest.call_args_list)
        self.assertEqual((counts[first], counts[second]), (2, 2))

    def test_cache_preserves_bulk_results_and_original_bytes(self):
        self.setup_bulk()
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        results = []
        uncached = lambda path, cache=None: app.file_hash(path)
        for enabled in (False, True):
            app.store_project(copy.deepcopy(self.project))
            with patch.object(app, 'gateway', side_effect=self.answer):
                plan = self.plan()
                if enabled: self.bulk(plan)
                else:
                    with patch.object(app, 'cached_file_hash', side_effect=uncached, create=True): self.bulk(plan)
            results.append([{k: v for k, v in row.items() if k != 'id'} for row in plan['rows']])
        self.assertEqual(results[0], results[1])
        self.assertEqual(before, {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})


if __name__ == '__main__':
    unittest.main()
