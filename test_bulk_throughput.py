"""Adaptive metadata batches, bounded concurrency, retries and late-result handling."""
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class BulkThroughput(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / '사업'
        self.root.mkdir()
        data = patch.object(app, 'DATA', self.base / 'settings')
        data.start(); self.addCleanup(data.stop)
        app.DATA.mkdir()
        app.SELECTIONS['bulk-test'] = str(self.root)
        tree = [{'label': app.INBOX}, {'label': '1 자료', 'children': [
            {'label': '1 회의록'}, {'label': '2 도면'}]}]
        self.project = app.save_project({'selection': 'bulk-test', 'name': '합성 사업', 'tree': tree}, False)

    def plan(self, count):
        inbox = self.root / app.INBOX
        inbox.mkdir(exist_ok=True)
        for i in range(count): (inbox / f'{i:04d}.dat').write_bytes(b'PRIVATE ORIGINAL NEVER SENT')
        return app.make_plan(self.project['id'], True)

    def job(self, plan):
        job_id = plan['id']
        job = {'id': job_id, 'planId': plan['id'], 'status': 'pending', 'recheck': False,
               'processed': 0, 'completedBatches': 0, **app.bulk_info(plan['id'])}
        app.JOBS[job_id] = job
        return job

    @staticmethod
    def payload(messages): return json.loads(messages[-1]['content'])

    def answer(self, messages, **kwargs):
        payload = self.payload(messages)
        self.assertNotIn('PRIVATE ORIGINAL', json.dumps(messages))
        target = next(k for k, v in payload['folders'].items() if v.endswith('회의록'))
        return {'assignments': [{'file_id': row['file_id'], 'destination_id': target,
                                 'confidence': .9, 'reason': '합성 근거'} for row in payload['files']]}

    def run_job(self, plan, gateway):
        job = self.job(plan)
        with patch.object(app, 'gateway', side_effect=gateway): app.run_bulk(job['id'])
        return job

    def test_2100_files_need_22_batches_with_no_silent_limit(self):
        plan = {'rows': [{'id': f'{i:024x}', 'relative': f'받은자료/{i}.dat', 'name': f'{i}.dat',
                          'size': 1, 'method': 'hold', 'done': False} for i in range(2100)]}
        batches = app.bulk_batches(plan)
        self.assertEqual(len(batches), 22)
        self.assertEqual(sum(map(len, batches)), 2100)
        self.assertLessEqual(max(map(len, batches)), 96)

    def test_long_korean_paths_are_bounded_by_utf8_metadata_size(self):
        plan = {'rows': [{'id': str(i), 'relative': '가나다/' * 300 + f'{i}.dat', 'name': f'{i}.dat',
                          'size': 1, 'method': 'hold', 'done': False} for i in range(96)]}
        batches = app.bulk_batches(plan)
        self.assertGreater(len(batches), 1)
        self.assertEqual(sum(map(len, batches)), 96)
        self.assertLess(max(map(len, batches)), 96)

    def test_two_requests_overlap_but_results_apply_in_original_order(self):
        with patch.object(app, 'BULK_MAX_FILES', 16): plan = self.plan(48); job = self.job(plan)
        first_started, second_done, release = threading.Event(), threading.Event(), threading.Event()
        lock = threading.Lock(); active = 0; peak = 0; passes = []
        # Keep this test's request shape stable while exercising the production worker count.
        first_ids = {r['id'] for r in sorted(plan['rows'], key=lambda r: r['relative'])[:16]}
        original_routes = app.apply_contract_routes
        def routes(*args, **kwargs):
            passes.append({r['id'] for r in plan['rows'] if r.get('aiChecked')})
            return original_routes(*args, **kwargs)
        def respond(messages, **kwargs):
            nonlocal active, peak
            with lock: active += 1; peak = max(peak, active)
            try:
                first = self.payload(messages)['files'][0]['name'] == '0000.dat'
                if first:
                    first_started.set()
                    self.assertTrue(release.wait(5))
                else: second_done.set()
                return self.answer(messages, **kwargs)
            finally:
                with lock: active -= 1
        with patch.object(app, 'BULK_MAX_FILES', 16), patch.object(app, 'gateway', side_effect=respond), \
                patch.object(app, 'apply_contract_routes', side_effect=routes):
            thread = threading.Thread(target=app.run_bulk, args=(job['id'],)); thread.start()
            try:
                self.assertTrue(first_started.wait(5)); self.assertTrue(second_done.wait(5))
                self.assertEqual(job['processed'], 0)
            finally: release.set(); thread.join(5)
        self.assertFalse(thread.is_alive()); self.assertEqual(job['status'], 'done', job)
        self.assertEqual(peak, 2); self.assertEqual(passes[0], first_ids)
        self.assertEqual(job['processed'], 48)

    def test_truncation_splits_until_the_response_fits(self):
        plan = self.plan(96); calls = []
        def respond(messages, **kwargs):
            count = len(self.payload(messages)['files']); calls.append((count, kwargs['max_tokens']))
            if count > 24: raise app.AIResponseError('AI 응답이 길이 한도로 잘렸습니다.')
            return self.answer(messages, **kwargs)
        job = self.run_job(plan, respond)
        self.assertEqual(job['status'], 'done', job)
        self.assertEqual([n for n, _ in calls], [96, 48, 24, 24, 24, 24])
        self.assertGreater(calls[0][1], 4096)
        self.assertEqual((job['processed'], job['completedBatches']), (96, 1))

    def test_learned_smaller_size_is_reused_for_later_batches(self):
        plan = self.plan(288); calls = []
        def limited(messages, **kwargs):
            count = len(self.payload(messages)['files']); calls.append(count)
            if count > 24: raise app.AIResponseError('AI 응답이 길이 한도로 잘렸습니다.')
            return self.answer(messages, **kwargs)
        with patch.object(app, 'BULK_WORKERS', 1): job = self.run_job(plan, limited)
        self.assertEqual(job['status'], 'done', job)
        self.assertEqual((calls.count(96), calls.count(48), calls.count(24)), (1, 1, 12))
        self.assertEqual(job['effectiveBatchSize'], 24)

    def test_missing_assignments_are_retried_not_marked_checked(self):
        plan = self.plan(48); calls = []
        def respond(messages, **kwargs):
            result = self.answer(messages, **kwargs)
            count = len(self.payload(messages)['files']); calls.append(count)
            if count > 24: result['assignments'].pop()
            return result
        job = self.run_job(plan, respond)
        self.assertEqual(job['status'], 'done', job); self.assertEqual(calls, [48, 24, 24])
        self.assertTrue(all(r.get('aiChecked') for r in plan['rows']))

    def test_invalid_ids_destinations_and_confidence_never_partially_apply(self):
        for kind in ('duplicate', 'unknown', 'array_id', 'bool_confidence'):
            with self.subTest(kind=kind):
                app.store_project(self.project)
                plan = self.plan(8)
                def invalid(messages, **kwargs):
                    result = self.answer(messages, **kwargs); rows = result['assignments']
                    if kind == 'duplicate': rows[-1]['file_id'] = rows[0]['file_id']
                    elif kind == 'unknown': rows[-1]['file_id'] = 'unknown'
                    elif kind == 'array_id': rows[-1]['file_id'] = []
                    else: rows[-1]['confidence'] = True
                    return result
                job = self.run_job(plan, invalid)
                self.assertEqual(job['status'], 'failed', job)
                self.assertFalse(any(r.get('aiChecked') or r['destination'] for r in plan['rows']))

    def test_outside_destination_holds_only_that_file(self):
        # 3차 5번: 구조 밖·형식이 틀린 목적지는 그 파일만 보류하고 나머지는 적용한다.
        for kind in ('outside', 'array_destination'):
            with self.subTest(kind=kind):
                app.store_project(self.project)
                plan = self.plan(8)
                def outside(messages, **kwargs):
                    result = self.answer(messages, **kwargs)
                    result['assignments'][-1]['destination_id'] = '../outside' if kind == 'outside' else []
                    return result
                job = self.run_job(plan, outside)
                self.assertEqual(job['status'], 'done', job)
                held = [r for r in plan['rows'] if not r['destination']]
                self.assertEqual(len(held), 1)
                self.assertTrue(all(r.get('aiChecked') for r in plan['rows']))

    def test_missing_smallest_batch_stays_unverified(self):
        plan = self.plan(8)
        job = self.run_job(plan, lambda *args, **kwargs: {'assignments': []})
        self.assertEqual(job['status'], 'failed', job); self.assertIn('누락', job['error'])
        self.assertFalse(any(r.get('aiChecked') for r in plan['rows']))

    def test_failed_split_does_not_publish_the_other_half(self):
        plan = self.plan(48)
        def partial(messages, **kwargs):
            result = self.answer(messages, **kwargs)
            rows = self.payload(messages)['files']
            if len(rows) > 24 or rows[0]['name'] >= '0024.dat': result['assignments'].pop()
            return result
        job = self.run_job(plan, partial)
        self.assertEqual(job['status'], 'failed', job)
        self.assertFalse(any(r.get('aiChecked') or r['destination'] for r in plan['rows']))
        self.assertFalse(app.get_project(self.project['id']).get('classificationCache'))

    def test_lower_model_output_limit_falls_back_to_smaller_batches(self):
        plan = self.plan(48)
        def limited(messages, **kwargs):
            if kwargs['max_tokens'] > 4096: raise app.GatewayError('max_tokens 한도', 400)
            return self.answer(messages, **kwargs)
        job = self.run_job(plan, limited)
        self.assertEqual(job['status'], 'done', job); self.assertEqual(job['requests'], 3)

    def test_rate_limit_has_bounded_retries_and_switches_to_serial(self):
        plan = self.plan(8); calls = []
        def limited(messages, **kwargs):
            calls.append(True)
            if len(calls) == 1: raise app.GatewayError('HTTP 429', 429, retry_after=0)
            return self.answer(messages, **kwargs)
        job = self.run_job(plan, limited)
        self.assertEqual((job['status'], job['parallelism'], job['requests']), ('done', 1, 2))
        app.store_project(self.project); plan = self.plan(8)
        def always(*args, **kwargs): raise app.GatewayError('HTTP 429', 429, retry_after=0)
        job = self.run_job(plan, always)
        self.assertEqual((job['status'], job['requests']), ('failed', 3))

    def test_completed_batches_survive_later_auth_failure(self):
        plan = self.plan(40)
        def respond(messages, **kwargs):
            if self.payload(messages)['files'][0]['name'] != '0000.dat': raise app.GatewayError('HTTP 401', 401)
            return self.answer(messages, **kwargs)
        with patch.object(app, 'BULK_MAX_FILES', 16), patch.object(app, 'BULK_WORKERS', 1):
            job = self.run_job(plan, respond)
        self.assertEqual((job['status'], job['processed'], job['requests']), ('failed', 16, 2))
        ordered = sorted(plan['rows'], key=lambda r: r['relative'])
        self.assertTrue(all(r.get('aiChecked') for r in ordered[:16]))
        self.assertFalse(any(r.get('aiChecked') for r in ordered[16:]))

    def test_cancelled_requests_cannot_publish_and_new_job_respects_global_gate(self):
        plan = self.plan(32)
        with patch.object(app, 'BULK_MAX_FILES', 16): job = self.job(plan)
        barrier = threading.Barrier(3); release = threading.Event(); new_started = threading.Event()
        active = 0; peak = 0; lock = threading.Lock(); old_active = 0; old_done = threading.Event()
        def blocked(messages, **kwargs):
            nonlocal active, peak, old_active
            with lock: active += 1; old_active += 1; peak = max(peak, active)
            try:
                barrier.wait(5); self.assertTrue(release.wait(5))
                return self.answer(messages, **kwargs)
            finally:
                with lock:
                    active -= 1; old_active -= 1
                    if not old_active: old_done.set()
        def fresh(messages, **kwargs):
            nonlocal active, peak
            with lock: active += 1; peak = max(peak, active)
            try: new_started.set(); return self.answer(messages, **kwargs)
            finally:
                with lock: active -= 1
        with patch.object(app, 'BULK_MAX_FILES', 16), patch.object(app, 'gateway', side_effect=blocked):
            thread = threading.Thread(target=app.run_bulk, args=(job['id'],)); thread.start()
            new_thread = None
            try:
                barrier.wait(5); app.bulk_status(job['id'], cancel=True); thread.join(2)
                self.assertFalse(thread.is_alive()); self.assertEqual(job['status'], 'cancelled')
                self.assertFalse(any(r.get('aiChecked') for r in plan['rows']))
                new_plan = self.plan(32); new_job = self.job(new_plan)
                with patch.object(app, 'gateway', side_effect=fresh):
                    new_thread = threading.Thread(target=app.run_bulk, args=(new_job['id'],)); new_thread.start()
                    self.assertFalse(new_started.wait(.1)); release.set()
                    self.assertTrue(old_done.wait(5)); new_thread.join(5)
                    self.assertEqual(new_job['status'], 'done', new_job)
            finally:
                release.set(); thread.join(5)
                if new_thread: new_thread.join(5)
        self.assertLessEqual(peak, 2)
        self.assertFalse(any(r.get('aiChecked') for r in plan['rows']))

    def test_user_destination_changed_during_request_is_preserved(self):
        plan = self.plan(8); row = plan['rows'][0]
        def manual(messages, **kwargs):
            row.update(method='manual', destination='1 자료/2 도면')
            return self.answer(messages, **kwargs)
        job = self.run_job(plan, manual)
        self.assertEqual(job['status'], 'done', job)
        self.assertEqual((row['method'], row['destination']), ('manual', '1 자료/2 도면'))

    def test_worker_timeout_is_a_failure_not_an_infinite_poll(self):
        plan = self.plan(8)
        def timeout(*args, **kwargs): raise TimeoutError('synthetic worker timeout')
        job = self.run_job(plan, timeout)
        self.assertEqual(job['status'], 'failed', job)

    def test_completion_at_poll_timeout_is_not_mistaken_for_worker_failure(self):
        plan = self.plan(8)
        class Ready:
            def __init__(self, value): self.value = value; self.polled = False
            def done(self): return True
            def result(self, timeout=None):
                if not self.polled:
                    self.polled = True
                    raise TimeoutError('poll expired just before completion')
                return self.value
        class Pool:
            def __init__(self, **kwargs): pass
            def submit(self, function, *args): return Ready(function(*args))
            def shutdown(self, **kwargs): pass
        with patch.object(app, 'ThreadPoolExecutor', Pool): job = self.run_job(plan, self.answer)
        self.assertEqual(job['status'], 'done', job)

    def test_gateway_uses_bulk_token_budget_and_rejects_truncated_valid_json(self):
        reply = io.BytesIO(json.dumps({'choices': [{'message': {'content': '{"assignments":[]}'},
                                                   'finish_reason': 'length'}],
                                     'usage': {'total_tokens': 42}}).encode())
        with patch.object(app.urllib.request, 'urlopen', return_value=reply) as call:
            with self.assertRaises(app.AIResponseError):
                app.gateway([{'role': 'user', 'content': 'synthetic'}], key='test', model='test', max_tokens=15360)
        self.assertEqual(json.loads(call.call_args.args[0].data)['max_tokens'], 15360)
        self.assertEqual(json.loads((app.DATA / 'usage.jsonl').read_text())['usage']['total_tokens'], 42)

    def test_gateway_non_text_json_response_is_retryable(self):
        reply = io.BytesIO(json.dumps({'choices': [{'message': {'content': None}, 'finish_reason': 'stop'}]}).encode())
        with patch.object(app.urllib.request, 'urlopen', return_value=reply):
            with self.assertRaises(app.AIResponseError):
                app.gateway([{'role': 'user', 'content': 'synthetic'}], key='test', model='test')


if __name__ == '__main__':
    unittest.main()
