import copy
import io
import tempfile
import unittest
import json
import os
import threading
import urllib.request
import urllib.error
from pathlib import Path
from unittest.mock import patch

import app


class FileOperations(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()  # Windows TEMP can use an 8.3 alias.
        self.data_patch = patch.object(app, 'DATA', self.base / 'settings')
        self.data_patch.start()
        app.DATA.mkdir()
        app.SELECTIONS.clear()
        app.PLANS.clear()
        app.JOBS.clear()
        self.root = self.base / '사업'
        self.root.mkdir()
        app.SELECTIONS['picked'] = str(self.root)
        self.tree = [{'label': app.INBOX}, {'label': '01 공통', 'children': [{'label': '계약서'}]}]
        self.project = app.save_project({'selection': 'picked', 'name': '시험 사업', 'tree': self.tree})

    def tearDown(self):
        self.data_patch.stop()
        self.temp.cleanup()

    def write_file(self, name='계약서.pdf', data=b'contract'):
        path = self.root / app.INBOX / name
        path.write_bytes(data)
        return path

    def plan(self):
        return app.make_plan(self.project['id'], True)

    def execute_first(self, plan):
        return app.execute(plan['id'], [{'id': plan['rows'][0]['id'], 'destination': '01 공통/계약서'}])

    def test_no_change_until_approval_then_move_and_undo(self):
        source = self.write_file()
        plan = self.plan()
        self.assertTrue(source.exists())
        self.assertEqual(plan['rows'][0]['destination'], '01 공통/계약서')
        journal = self.execute_first(plan)
        self.assertFalse(source.exists())
        dest = self.root / '01 공통/계약서/계약서.pdf'
        self.assertEqual(dest.read_bytes(), b'contract')
        self.assertEqual(journal['entries'][0]['status'], 'moved')
        result = app.undo(journal['id'])
        self.assertEqual(result['entries'][0]['status'], 'restored')
        self.assertTrue(source.exists())
        self.assertFalse(dest.exists())

    def test_collision_does_not_overwrite(self):
        source = self.write_file()
        dest = self.root / '01 공통/계약서/계약서.pdf'
        dest.write_bytes(b'original target')
        journal = self.execute_first(self.plan())
        self.assertEqual(journal['entries'][0]['status'], 'held')
        self.assertTrue(source.exists())
        self.assertEqual(dest.read_bytes(), b'original target')

    def test_modified_after_review_held(self):
        source = self.write_file()
        plan = self.plan()
        source.write_bytes(b'changed')
        self.assertEqual(self.execute_first(plan)['entries'][0]['status'], 'held')
        self.assertEqual(source.read_bytes(), b'changed')

    def test_modified_after_move_not_undone(self):
        self.write_file()
        journal = self.execute_first(self.plan())
        (self.root / '01 공통/계약서/계약서.pdf').write_bytes(b'edited')
        self.assertEqual(app.undo(journal['id'])['entries'][0]['status'], 'undo-blocked')

    def test_original_collision_during_undo(self):
        source = self.write_file()
        journal = self.execute_first(self.plan())
        source.write_bytes(b'new file')
        self.assertEqual(app.undo(journal['id'])['entries'][0]['status'], 'undo-blocked')
        self.assertEqual(source.read_bytes(), b'new file')

    def test_inbox_only_and_empty_project(self):
        self.assertEqual(self.plan()['rows'], [])
        (self.root / '이미 정리.pdf').write_bytes(b'existing')
        self.write_file('새 문서.pdf')
        self.assertEqual(len(self.plan()['rows']), 1)
        self.assertEqual(len(app.make_plan(self.project['id'], False)['rows']), 2)

    def test_destination_and_tree_path_traversal_rejected(self):
        self.write_file()
        plan = self.plan()
        with self.assertRaises(ValueError):
            app.execute(plan['id'], [{'id': plan['rows'][0]['id'], 'destination': '../outside'}])
        for name in ('../x', 'C:\\temp', 'CON', '한글.', 'a/b'):
            with self.assertRaises(ValueError):
                app.tree_paths([{'label': name}])

    def test_symlink_escape_rejected(self):
        external = self.base / 'outside'
        external.mkdir()
        try:
            (self.root / 'link').symlink_to(external, target_is_directory=True)
        except OSError as error:  # Windows without Developer Mode/admin: WinError 1314.
            if os.name == 'nt' and getattr(error, 'winerror', None) == 1314:
                self.skipTest('이 Windows 계정은 심볼릭 링크를 만들 권한이 없습니다.')
            raise
        with self.assertRaises(ValueError):
            app.safe_path(self.root, 'link/out.pdf')

    def test_reconnect_keeps_identity_and_invalidates_plan(self):
        self.write_file()
        plan = self.plan()
        moved_root = self.base / '옮긴 사업'
        self.root.rename(moved_root)
        app.SELECTIONS['new'] = str(moved_root)
        project = app.reconnect(self.project['id'], 'new')
        self.assertEqual(project['id'], self.project['id'])
        self.assertEqual(project['tree'], self.project['tree'])
        self.assertEqual(len(app.make_plan(project['id'], True)['rows']), 1)
        self.assertNotIn(plan['id'], app.PLANS)

    def test_undo_after_reconnect(self):
        self.write_file()
        journal = self.execute_first(self.plan())
        moved_root = self.base / '옮긴 사업'
        self.root.rename(moved_root)
        app.SELECTIONS['new'] = str(moved_root)
        app.reconnect(self.project['id'], 'new')
        self.assertEqual(app.undo(journal['id'])['entries'][0]['status'], 'restored')
        self.assertTrue((moved_root / app.INBOX / '계약서.pdf').exists())

    def test_no_contract_project_persists(self):
        self.assertEqual(app.get_project(self.project['id'])['contracts'], [])

    def test_rule_conflict_is_held(self):
        tree = copy.deepcopy(self.tree)
        tree.append({'label': '02 설계', 'children': [{'label': '계약서'}]})
        app.save_project({'id': self.project['id'], 'name': '시험', 'tree': tree})
        self.write_file()
        self.assertEqual(self.plan()['rows'][0]['destination'], '')

    def test_image_excerpt_is_bounded(self):
        from PIL import Image
        path = self.root / 'image.png'
        Image.new('RGB', (2400, 1200), 'white').save(path)
        parts, _ = app.excerpt(path)
        import base64
        image = Image.open(io.BytesIO(base64.b64decode(parts[0]['image_url']['url'].split(',')[1])))
        self.assertLessEqual(max(image.size), 1800)

    def test_large_contract_stages_only_first_page_without_reading_full_bytes(self):
        import base64
        import os
        source = self.root / '큰 계약서.pdf'
        source.write_bytes(b'ORIGINAL LARGE CONTRACT')
        old_stat = Path.stat
        def fake_stat(path, *args, **kwargs):
            result = old_stat(path, *args, **kwargs)
            if path == source:
                fields = list(result)
                fields[6] = 500 * 1024 * 1024
                return os.stat_result(fields)
            return result
        preview = 'data:image/jpeg;base64,' + base64.b64encode(b'FIRST PAGE JPEG').decode()
        with (patch.object(Path, 'stat', fake_stat), patch.object(app, 'contract_page_indexes', return_value=([0], 200)),
                patch.object(app, 'render_pdf_pages', return_value=[{'type': 'image_url', 'image_url': {'url': preview}}]) as call,
                patch.object(Path, 'read_bytes', side_effect=AssertionError('full-file read forbidden'))):
            record = app.stage_contract_file(source)
            call.assert_called_once_with(source, [0])
        self.assertEqual(record['originalSize'], 500 * 1024 * 1024)
        self.assertEqual(Path(record['path']).read_bytes(), b'FIRST PAGE JPEG')
        self.assertEqual(source.read_bytes(), b'ORIGINAL LARGE CONTRACT')

    def test_contract_analysis_uses_one_page_and_confirmation_is_saved(self):
        cid = 'contract-test'
        (self.root / 'original.pdf').write_bytes(b'local contract snapshot')
        app.atomic_json(app.DATA / 'staging' / (cid + '.json'), {
            'id': cid, 'name': '계약서.pdf', 'path': str(self.root / 'original.pdf'), 'registeredAt': app.now()})
        answer = {'title': 'AI 계약명', 'party': '상대자', 'period': None, 'kind': 'construction'}
        with (patch.object(app, 'excerpt', return_value=([{'type': 'text', 'text': 'first page'}], '처음 1쪽')) as call,
                patch.object(app, 'gateway', return_value=answer)):
            app.analyze_contract(cid)
            call.assert_called_once_with(str(self.root / 'original.pdf'), 1)
        updated = app.update_contract(cid, {'title': '사용자 확인 계약명', 'kind': 'service'})
        self.assertEqual(updated['analysis']['title'], '사용자 확인 계약명')
        project = app.save_project({'id': self.project['id'], 'name': '사업', 'tree': self.tree, 'contracts': [cid]})
        self.assertEqual(project['name'], '사업')
        self.assertEqual(project['contracts'][0]['analysis']['title'], '사용자 확인 계약명')
        self.assertEqual(app.read_json(app.DATA / 'staging' / (cid + '.json'))['analysis']['kind'], 'service')

    def test_pdf_only_requested_page_sent(self):
        from pypdf import PdfWriter
        path = self.root / 'contract.pdf'
        writer = PdfWriter()
        for _ in range(4):
            writer.add_blank_page(595, 842)
        with path.open('wb') as stream:
            writer.write(stream)
        parts, sent = app.excerpt(path, 2)
        self.assertEqual(len(parts), 2)
        self.assertIn('전체 4쪽 중 처음 2쪽', sent)

    def test_untrusted_ai_destination_held(self):
        self.write_file('불명확.txt', b'content')
        plan = self.plan()
        with patch.object(app, 'gateway', return_value={'destination': '../../outside', 'confidence': .99, 'reason': 'test'}):
            row = app.ai_review(plan['id'], plan['rows'][0]['id'])
            self.assertEqual(row['destination'], '')

    def test_http_auth_and_bootstrap(self):
        server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(base + '/?session=wrong')
            self.assertEqual(caught.exception.code, 403)
            with urllib.request.urlopen(base + '/?session=' + app.TOKEN) as response:
                content = response.read().decode('utf-8')
                self.assertNotIn('__SESSION_TOKEN__', content)
                self.assertIn('모델 ID 직접 입력', content)
            for headers in ({}, {'X-App-Token': app.TOKEN, 'Origin': 'https://external.example'}):
                request = urllib.request.Request(base + '/status', data=b'{}', headers=headers)
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(request)
                self.assertEqual(caught.exception.code, 403)
            request = urllib.request.Request(base + '/status', data=b'{}', headers={'X-App-Token': app.TOKEN})
            with urllib.request.urlopen(request) as response:
                self.assertEqual(json.load(response)['model'], '')
        finally:
            server.shutdown()
            server.server_close()

    def test_selected_model_is_used_and_saved(self):
        with patch.object(app, 'gateway') as call, patch.object(app, 'protect', return_value=b'encrypted'):
            result = app.configure('test-secret', 'gemini-3.1-flash-lite')
            self.assertEqual(call.call_args.args[2], 'gemini-3.1-flash-lite')
            self.assertEqual(result['model'], 'gemini-3.1-flash-lite')
            self.assertEqual(app.read_json(app.DATA / 'ai.json')['model'], result['model'])
            self.assertEqual((app.DATA / 'api-key.dpapi').read_bytes(), b'encrypted')

    def test_any_model_with_saved_key_and_optional_image(self):
        with patch.object(app, 'load_key', return_value='saved-secret'), patch.object(app, 'gateway') as call, patch.object(app, 'protect', return_value=b'encrypted'):
            result = app.configure('', 'another-provider/text-model-v1')
            self.assertEqual(result['model'], 'another-provider/text-model-v1')
            self.assertEqual(call.call_args.args[1], 'saved-secret')
            self.assertEqual(len(call.call_args.args[0][0]['content']), 1)
            app.configure('', 'another-provider/vision-model', check_image=True)
            self.assertEqual(len(call.call_args.args[0][0]['content']), 2)
            self.assertTrue(app.read_json(app.DATA / 'ai.json')['imageVerified'])

    def test_missing_model_blocks_without_network(self):
        with patch.object(app, 'gateway') as call:
            with self.assertRaises(ValueError):
                app.configure('secret', '')
            call.assert_not_called()

    def test_gateway_uses_saved_model(self):
        app.atomic_json(app.DATA / 'ai.json', {'model': 'gemini-3.1-flash-lite'})
        reply = io.BytesIO(json.dumps({'choices': [{'message': {'content': 'OK'}}]}).encode())
        with patch.object(app.urllib.request, 'urlopen', return_value=reply) as call:
            self.assertEqual(app.gateway([{'role': 'user', 'content': 'hello'}], key='test', json_mode=False), 'OK')
            self.assertEqual(json.loads(call.call_args.args[0].data)['model'], 'gemini-3.1-flash-lite')

    def test_model_list_preserves_gateway_ids(self):
        reply = io.BytesIO(json.dumps({'data': [{'id': 'gemini-3.1-flash-lite'}, {'id': 'google/custom-model'}]}).encode())
        with patch.object(app.urllib.request, 'urlopen', return_value=reply):
            self.assertEqual(app.model_list('test')['models'], ['gemini-3.1-flash-lite', 'google/custom-model'])

    def run_bulk_sync(self, plan, recheck=False, cancel=False):
        job = {'id': 'job-test', 'planId': plan['id'], 'recheck': recheck, 'status': 'pending',
               'processed': 0, 'completedBatches': 0, 'cancel': cancel, **app.bulk_info(plan['id'], recheck)}
        app.JOBS[job['id']] = job
        app.run_bulk(job['id'])
        return job

    def test_bulk_all_files_batched_metadata_only_and_cache_reused(self):
        for i in range(52):
            self.write_file(f'문서 {i:02d}.txt', b'PRIVATE DOCUMENT CONTENT NEVER SENT')
        plan = self.plan()
        captured = []
        def respond(messages, **kwargs):
            data = json.loads(messages[1]['content'])
            captured.extend(data['files'])
            self.assertNotIn('PRIVATE DOCUMENT CONTENT', json.dumps(messages))
            self.assertTrue(all('original_folder' in file for file in data['files']))
            self.assertLessEqual(len(data['files']), app.BULK_MAX_FILES)
            return {'assignments': [{'file_id': file['file_id'], 'destination_id': 'd2',
                                      'reason': '파일명과 기존 폴더 문맥', 'confidence': .9} for file in data['files']]}
        with patch.object(app, 'gateway', side_effect=respond) as call:
            job = self.run_bulk_sync(plan)
            self.assertEqual(job['status'], 'done')
            self.assertEqual(job['processed'], 52)
            self.assertEqual(call.call_count, 1)
        self.assertEqual(len({file['file_id'] for file in captured}), 52)
        self.assertTrue(all(row['destination'] == '01 공통/계약서' for row in plan['rows']))
        self.assertEqual(len(list((self.root / app.INBOX).glob('*.txt'))), 52)
        restored = self.plan()
        self.assertEqual(app.bulk_info(restored['id'])['count'], 0)
        self.assertEqual(app.bulk_info(restored['id'], True)['count'], 52)

    def test_bulk_holds_only_the_file_answered_outside_the_tree(self):
        self.write_file('문서A.txt')
        self.write_file('문서B.txt')
        plan = self.plan()
        rows = plan['rows']
        answer = {'assignments': [
            {'file_id': rows[0]['id'], 'destination_id': 'd2', 'reason': '근거', 'confidence': .9},
            {'file_id': rows[1]['id'], 'destination_id': '../outside', 'reason': '근거', 'confidence': .9}]}
        with patch.object(app, 'gateway', return_value=answer):
            job = self.run_bulk_sync(plan)
        # 3차 5번: 구조 밖 폴더를 답한 파일만 보류, 같은 묶음의 다른 파일 답은 적용한다.
        self.assertEqual(job['status'], 'done')
        self.assertEqual(rows[0]['destination'], plan['paths'][1])
        self.assertEqual((rows[1]['destination'], rows[1]['method']), ('', 'hold'))
        self.assertIn('구조에 없는', rows[1]['reason'])

    def test_bulk_low_confidence_held(self):
        self.write_file('문서A.txt')
        self.write_file('문서B.txt')
        plan = self.plan()
        with patch.object(app, 'gateway', return_value={'assignments': [
                {'file_id': row['id'], 'destination_id': 'd2', 'reason': '불확실', 'confidence': .4} for row in plan['rows']]}):
            job = self.run_bulk_sync(plan)
        self.assertEqual(job['status'], 'done')
        self.assertTrue(all(not row['destination'] and row['aiChecked'] for row in plan['rows']))

    def test_bulk_rule_default_skipped_and_recheck_optional(self):
        self.write_file('계약서.pdf')
        plan = self.plan()
        self.assertEqual(app.bulk_info(plan['id'])['count'], 0)
        self.assertEqual(app.bulk_info(plan['id'], True)['count'], 1)

    def test_bulk_cancel_before_request_makes_no_ai_call(self):
        self.write_file('문서.txt')
        with patch.object(app, 'gateway') as call:
            job = self.run_bulk_sync(self.plan(), cancel=True)
            self.assertEqual(job['status'], 'cancelled')
            call.assert_not_called()

    def test_bulk_more_than_150_has_no_silent_limit(self):
        for i in range(161):
            self.write_file(f'자료 {i:03d}.txt')
        plan = self.plan()
        def respond(messages, **kwargs):
            files = json.loads(messages[1]['content'])['files']
            return {'assignments': [{'file_id': f['file_id'], 'destination_id': None,
                                     'reason': '추가 확인 필요', 'confidence': 0} for f in files]}
        with patch.object(app, 'gateway', side_effect=respond) as call:
            job = self.run_bulk_sync(plan)
        self.assertEqual(job['status'], 'done')
        self.assertEqual(job['processed'], 161)
        self.assertEqual(call.call_count, 2)

    def test_empty_inbox_diagnosis_and_explicit_whole_scan(self):
        (self.root / '사업 전체 문서.txt').write_bytes(b'test')
        inbox_plan = app.make_plan(self.project['id'], True)
        self.assertEqual(inbox_plan['rows'], [])
        self.assertEqual(inbox_plan['scanInfo']['sourcePath'], str(self.root / app.INBOX))
        self.assertTrue(inbox_plan['scanInfo']['sourceExists'])
        self.assertEqual(inbox_plan['scanInfo']['scannedCount'], 0)
        whole_plan = app.make_plan(self.project['id'], False)
        self.assertEqual(len(whole_plan['rows']), 1)
        self.assertEqual(whole_plan['scanInfo']['scope'], 'whole')
        self.assertTrue((self.root / '사업 전체 문서.txt').exists())

    def test_missing_inbox_differs_from_empty_and_refresh_finds_new_files(self):
        (self.root / app.INBOX).rmdir()
        self.assertFalse(self.plan()['scanInfo']['sourceExists'])
        (self.root / app.INBOX).mkdir()
        self.assertTrue(self.plan()['scanInfo']['sourceExists'])
        self.write_file('새 문서.txt')
        self.assertEqual(len(self.plan()['rows']), 1)

    def test_finish_with_remaining_keeps_original_and_undo(self):
        source = self.write_file('계약서.pdf')
        left = self.write_file('보류 문서.txt', b'unchanged')
        plan = self.plan()
        chosen = next(r for r in plan['rows'] if r['name'] == '계약서.pdf')
        journal = app.execute(plan['id'], [{'id': chosen['id'], 'destination': '01 공통/계약서'}])
        summary = app.finish_plan(plan['id'])
        self.assertEqual(summary['movedCount'], 1)
        self.assertEqual(summary['remainingCount'], 1)
        self.assertEqual(left.read_bytes(), b'unchanged')
        with self.assertRaises(ValueError):
            self.execute_first(plan)
        app.undo(journal['id'])
        self.assertTrue(source.exists())

    def test_failed_move_has_explicit_row_error(self):
        self.write_file()
        (self.root / '01 공통/계약서/계약서.pdf').write_bytes(b'collision')
        plan = self.plan()
        self.execute_first(plan)
        self.assertIn('동일한 이름', plan['rows'][0]['executionError'])

    def all_choices(self, plan, destination='01 공통/계약서'):
        return [{'id': r['id'], 'destination': destination} for r in plan['rows'] if not r['done']]

    def test_execute_all_moves_only_chosen_files_and_keeps_holds(self):
        a = self.write_file('자료A.txt')
        b = self.write_file('자료B.txt')
        plan = self.plan()
        first = self.all_choices(plan)[:1]
        journal = app.execute_all(plan['id'], first)
        self.assertEqual([e['status'] for e in journal['entries']], ['moved'])
        moved = next(r for r in plan['rows'] if r['id'] == first[0]['id'])
        kept = next(r for r in plan['rows'] if r['id'] != first[0]['id'])
        self.assertTrue((self.root / '01 공통/계약서' / moved['name']).exists())
        self.assertTrue((self.root / kept['relative']).exists())
        self.assertTrue((self.root / app.INBOX).is_dir())

    def test_execute_all_invalid_destination_blocks_every_move(self):
        a = self.write_file('자료A.txt')
        b = self.write_file('자료B.txt')
        plan = self.plan()
        with self.assertRaises(ValueError):
            app.execute_all(plan['id'], [])
        choices = self.all_choices(plan)
        choices[-1]['destination'] = ''
        with self.assertRaises(ValueError):
            app.execute_all(plan['id'], choices)
        self.assertTrue(a.exists() and b.exists())

    def test_execute_all_collision_preflight_preserves_every_source(self):
        a = self.write_file('자료A.txt')
        b = self.write_file('자료B.txt')
        (self.root / '01 공통/계약서/자료B.txt').write_bytes(b'existing')
        plan = self.plan()
        with self.assertRaises(ValueError):
            app.execute_all(plan['id'], self.all_choices(plan))
        self.assertTrue(a.exists() and b.exists())

    def test_execute_all_changed_file_preflight_preserves_every_source(self):
        a = self.write_file('자료A.txt')
        b = self.write_file('자료B.txt')
        plan = self.plan()
        b.write_bytes(b'changed')
        with self.assertRaises(ValueError):
            app.execute_all(plan['id'], self.all_choices(plan))
        self.assertTrue(a.exists() and b.exists())

    def test_full_move_cleans_only_empty_old_folders_and_undo_restores(self):
        old = self.root / '기존 자료/하위/빈 폴더'
        old.mkdir(parents=True)
        source = old.parent / '문서.txt'
        source.write_bytes(b'original')
        plan = app.make_plan(self.project['id'], False)
        journal = app.execute_all(plan['id'], self.all_choices(plan))
        self.assertFalse((self.root / '기존 자료').exists())
        self.assertTrue((self.root / app.INBOX).exists())
        self.assertTrue((self.root / '01 공통/계약서').exists())
        self.assertIn('기존 자료/하위/빈 폴더', journal['removedFolders'])
        app.undo(journal['id'])
        self.assertEqual(source.read_bytes(), b'original')
        self.assertTrue(old.is_dir())

    def test_temp_file_only_folder_is_gathered_not_deleted(self):
        old = self.root / '이전'
        old.mkdir()
        (old / '문서.txt').write_bytes(b'document')
        ignored = old / '~$잠긴문서.docx'
        ignored.write_bytes(b'NEVER DELETE')
        plan = app.make_plan(self.project['id'], False)
        journal = app.execute_all(plan['id'], self.all_choices(plan))
        # 2026-11-25 사용자 결정: 임시(잠금) 파일만 남은 기존 폴더는 그 파일을 지우지 않고 '정리 후 남은 파일'로 모은 뒤 폴더를 정리한다.
        kept = self.root / app.INBOX / app.LEFTOVER_FOLDER / '이전' / '~$잠긴문서.docx'
        self.assertEqual(kept.read_bytes(), b'NEVER DELETE')
        self.assertFalse(old.exists())
        self.assertIn('이전', journal['removedFolders'])
        app.undo(journal['id'])
        self.assertEqual(ignored.read_bytes(), b'NEVER DELETE')  # 되돌리면 제자리

    def test_retarget_is_persisted_but_does_not_move_file(self):
        source = self.write_file('문서.txt')
        plan = self.plan()
        row = app.retarget(plan['id'], plan['rows'][0]['id'], '01 공통/계약서')
        self.assertEqual(row['method'], 'manual')
        self.assertTrue(source.exists())
        self.assertEqual(self.plan()['rows'][0]['destination'], '01 공통/계약서')
        with self.assertRaises(ValueError):
            app.retarget(plan['id'], row['id'], '../outside')

    def test_already_in_place_kept_without_rename_or_delete(self):
        matched = self.root / '01 공통/계약서/계약 참고.txt'
        matched.write_bytes(b'matched')
        source = self.root / '01 공통/참고.txt'
        source.write_bytes(b'keep')
        plan = app.make_plan(self.project['id'], False)
        self.assertEqual([r['name'] for r in plan['rows']], ['참고.txt'])  # Folder name already matches the tree.
        self.assertEqual(plan['scanInfo']['alreadyInPlaceCount'], 1)
        journal = app.execute_all(plan['id'], [{'id': plan['rows'][0]['id'], 'destination': '01 공통'}])
        self.assertEqual(journal['entries'][0]['status'], 'already-in-place')
        self.assertEqual(source.read_bytes(), b'keep')
        app.undo(journal['id'])
        self.assertEqual(source.read_bytes(), b'keep')

    def test_authentication_error_distinct_from_model_error_and_key_redacted(self):
        secret = 'sk-private-key'
        for code, expected in ((401, '인증 거절'), (404, '선택한 모델')):
            body = io.BytesIO(json.dumps({'error': {'message': 'bad ' + secret}}).encode())
            error = urllib.error.HTTPError('https://example.invalid', code, 'error', {}, body)
            with self.assertRaises(ValueError) as caught:
                app.api_error(error, secret)
            self.assertIn(expected, str(caught.exception))
            self.assertIn('HTTP ' + str(code), str(caught.exception))
            self.assertNotIn(secret, str(caught.exception))

    def test_retarget_30_files_once_without_moving_and_reuses_cache(self):
        for i in range(30):
            self.write_file(f'사진 {i}.jpg')
        plan = self.plan()
        result = app.retarget_many(plan['id'], [r['id'] for r in plan['rows']], '01 공통/계약서')
        self.assertEqual(len(result['rows']), 30)
        self.assertTrue(all(r['destination'] == '01 공통/계약서' for r in result['rows']))
        self.assertEqual(len(list((self.root / app.INBOX).glob('*.jpg'))), 30)
        self.assertTrue(all(r['method'] == 'manual' for r in self.plan()['rows']))

    def test_retarget_many_validates_all_before_changes(self):
        self.write_file('사진.jpg')
        plan = self.plan()
        original = copy.deepcopy(plan['rows'])
        with self.assertRaises(ValueError):
            app.retarget_many(plan['id'], [plan['rows'][0]['id'], 'unknown'], '01 공통/계약서')
        self.assertEqual(plan['rows'], original)
        with self.assertRaises(ValueError):
            app.retarget_many(plan['id'], [plan['rows'][0]['id']], '../outside')

    def test_structure_reset_clears_proposals_without_touching_files_or_history(self):
        source = self.write_file('계약서.pdf')
        plan = self.plan()
        app.retarget_many(plan['id'], [plan['rows'][0]['id']], '01 공통/계약서')
        app.atomic_json(app.DATA / 'history' / 'history.json', {'id': 'keep'})
        tree = copy.deepcopy(self.tree)
        tree[1]['label'] = '01 수정 공통'
        project = app.save_project({'id': self.project['id'], 'name': '사업', 'tree': tree, 'resetClassification': True})
        self.assertEqual(project['classificationCache'], {})
        self.assertTrue(source.exists())
        self.assertEqual(app.read_json(app.DATA / 'history' / 'history.json')['id'], 'keep')

    def test_same_name_collision_offers_numbered_name(self):
        (self.root / app.INBOX / 'a').mkdir()
        (self.root / app.INBOX / 'b').mkdir()
        (self.root / app.INBOX / 'a/견적서.pdf').write_bytes(b'first')
        (self.root / app.INBOX / 'b/견적서.pdf').write_bytes(b'second!')
        (self.root / '01 공통/계약서/견적서.pdf').write_bytes(b'existing')
        plan = self.plan()
        choices = self.all_choices(plan)
        check = app.move_check(plan['id'], choices)
        self.assertEqual(sorted(r['newName'] for r in check['renamed']), ['견적서 (2).pdf', '견적서 (3).pdf'])
        with self.assertRaises(ValueError):
            app.execute_all(plan['id'], choices)
        self.assertTrue((self.root / app.INBOX / 'a/견적서.pdf').exists())
        journal = app.execute_all(plan['id'], choices, True)
        self.assertEqual({e['status'] for e in journal['entries']}, {'moved'})
        folder = self.root / '01 공통/계약서'
        self.assertEqual((folder / '견적서.pdf').read_bytes(), b'existing')
        self.assertEqual(sorted(p.read_bytes() for p in folder.glob('견적서 (*).pdf')), [b'first', b'second!'])
        app.undo(journal['id'])
        self.assertEqual((self.root / app.INBOX / 'b/견적서.pdf').read_bytes(), b'second!')
        self.assertEqual(sorted(p.name for p in folder.iterdir()), ['견적서.pdf'])

    def test_plan_does_not_hash_files(self):
        self.write_file('큰 자료.txt', b'x' * 1000)
        with patch.object(app, 'file_hash', side_effect=AssertionError('hash called')):
            plan = self.plan()
            journal = app.execute_all(plan['id'], self.all_choices(plan))
            self.assertEqual(journal['entries'][0]['status'], 'moved')
            self.assertEqual(app.undo(journal['id'])['entries'][0]['status'], 'restored')

    def test_folder_label_rules_and_learning_without_ai(self):
        tree = [{'label': app.INBOX}, {'label': '01 공통', 'children': [{'label': '계약서'}, {'label': '03 착공계'}]},
                {'label': '02 시공', 'children': [{'label': '공정회의'}]}]
        self.project = app.save_project({'id': self.project['id'], 'name': '시험 사업', 'tree': tree})
        self.write_file('착공계 제출본.pdf')
        self.write_file('11월 공정회의 결과.txt')
        self.write_file('주간보고 2026-11-01.txt')
        plan = self.plan()
        rows = {r['name']: r for r in plan['rows']}
        self.assertEqual(rows['착공계 제출본.pdf']['destination'], '01 공통/03 착공계')
        self.assertEqual(rows['11월 공정회의 결과.txt']['destination'], '02 시공/공정회의')
        self.assertEqual(rows['주간보고 2026-11-01.txt']['method'], 'hold')
        report = rows['주간보고 2026-11-01.txt']
        app.execute(plan['id'], [{'id': report['id'], 'destination': '02 시공/공정회의'}])
        self.write_file('주간보고 2026-11-08 (최종).txt')
        row = self.plan()['rows']
        latest = next(r for r in row if r['name'].startswith('주간보고'))
        self.assertEqual(latest['destination'], '02 시공/공정회의')
        self.assertIn('이전 정리 기록', latest['reason'])

    def test_content_rule_reads_title_locally(self):
        self.write_file('스캔0012.txt', '계약서\n계약 건명: 배수로 보수'.encode('utf-8'))
        with patch.object(app, 'gateway', side_effect=AssertionError('AI called')):
            row = self.plan()['rows'][0]
        self.assertEqual(row['destination'], '01 공통/계약서')
        self.assertIn('AI 미사용', row['reason'])

    def index(self):
        job = app.start_index(self.project['id'])
        for _ in range(200):
            if app.INDEX_JOBS[job['id']]['status'] in ('done', 'failed'):
                break
            import time
            time.sleep(.02)
        self.assertEqual(app.INDEX_JOBS[job['id']]['status'], 'done', app.INDEX_JOBS[job['id']].get('error'))

    def test_document_search_uses_name_folder_and_content(self):
        (self.root / '01 공통/계약서/도급계약서.txt').write_bytes('계약상대자 한빛건설 계약기간 2026'.encode('utf-8'))
        (self.root / '01 공통/회의록.txt').write_bytes('안전점검 결과 보고 배수로 균열'.encode('cp949'))
        docx = self.root / '01 공통/점검.docx'
        import zipfile
        with zipfile.ZipFile(docx, 'w') as archive:
            archive.writestr('word/document.xml', '<w:document xmlns:w="w"><w:body><w:p><w:r><w:t>하자보수 보증 내용</w:t></w:r></w:p></w:body></w:document>')
        self.index()
        info = app.index_info(self.project['id'])
        self.assertEqual(info['count'], 3)
        self.assertEqual(info['withText'], 3)
        result = app.search_files(self.project['id'], '한빛건설 계약서는 어디 있지?')
        self.assertEqual(result['results'][0]['name'], '도급계약서.txt')
        self.assertTrue(any('본문' in r for r in result['results'][0]['reasons']))
        self.assertEqual(app.search_files(self.project['id'], '균열')['results'][0]['name'], '회의록.txt')
        self.assertEqual(app.search_files(self.project['id'], '하자보수')['results'][0]['name'], '점검.docx')
        (self.root / '01 공통/회의록.txt').unlink()
        self.index()
        self.assertEqual(app.index_info(self.project['id'])['count'], 2)

    def test_search_ai_only_returns_known_candidates(self):
        (self.root / '01 공통/계약서/도급계약서.txt').write_bytes('계약 건명 배수로'.encode('utf-8'))
        self.index()
        answers = [{'keywords': ['계약서', '도급']},
                   {'picks': [{'id': 'c1', 'reason': '계약서 원본', 'confidence': .9}, {'id': 'c99', 'reason': 'x', 'confidence': 1}]}]
        with patch.object(app, 'gateway', side_effect=answers) as gateway:
            result = app.search_ai(self.project['id'], '공사 계약한 서류')
        self.assertEqual(gateway.call_count, 2)
        self.assertEqual([p['name'] for p in result['ai']['picks']], ['도급계약서.txt'])
        sent = json.dumps(gateway.call_args_list[1][0][0], ensure_ascii=False)
        self.assertNotIn(str(self.root), sent)

    def test_keyword_search_photo_word_finds_photo_files_and_ignores_one_letter_noise(self):
        # 2026-11-28 LIM: '사진'을 찾았는데 '현장대리인 선임계', '안전관리계획서'가 나오고 사진 파일은 안 나옴.
        for relative in ('3 시공단계/착공계/붙임1_현장대리인 선임계.txt','3 시공단계/착공계/붙임3_안전관리계획서.txt',
                         '3 시공단계/현장/KakaoTalk_0101.jpg','3 시공단계/현장/IMG_0002.png'):
            path=self.root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'synthetic')
        self.index()
        result=app.search_files(self.project['id'],'사진')
        self.assertEqual({r['name'] for r in result['results']},{'KakaoTalk_0101.jpg','IMG_0002.png'})
        self.assertTrue(all(r['kind']=='사진' for r in result['results']))
        self.assertEqual(app.query_terms('착공 전 사진'),['착공','사진'])  # 한 글자 '전'은 검색어가 아니다
        # AI가 넓힌 '공사 사진대지'는 낱말로 쪼개지 않고, 흔한 말은 결과를 흐리지 않는다.
        noisy=app.search_files(self.project['id'],'선임계',['공사 사진대지','시공'])
        self.assertEqual([r['name'] for r in noisy['results']],['붙임1_현장대리인 선임계.txt'])

    def test_keyword_search_hides_files_that_match_only_an_upper_folder_name(self):
        # 2026-11-28 LIM: '계약서'를 찾았는데 '…최초 계약서/1 품의서/A 구매품의/붙임1_자재목록.xlsx'까지 나옴.
        base='3 시공단계/1 도급공사/1 최초 품의 및 최초 계약서'
        for relative,body in ((base+'/2 계약서/260201 공사 계약서.txt',b'contract'),(base+'/2 계약서/scan001.pdf',b''),
                              (base+'/1 품의서/A 구매품의/붙임1_자재목록.txt',b'list'),(base+'/1 품의서/B 시행품의/붙임1_설계내역서.txt',b'bill')):
            path=self.root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)
        self.index()
        result=app.search_files(self.project['id'],'계약서')
        self.assertEqual({r['name'] for r in result['results']},{'260201 공사 계약서.txt','scan001.pdf'})
        self.assertEqual(result['hiddenFolderOnly'],2)
        # 파일명·본문이 맞는 파일이 하나도 없으면 상위 폴더만 맞는 파일이라도 보여 준다.
        only=app.search_files(self.project['id'],'구매품의')
        self.assertEqual([r['name'] for r in only['results']],['붙임1_자재목록.txt'])

    def test_ai_search_suggests_one_narrowing_question_with_options(self):
        for relative in ('3 시공단계/계약/최초 계약서.txt','3 시공단계/계약/1차 변경계약서.txt'):
            path=self.root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes('계약서'.encode())
        self.index()
        answers=[{'keywords':['계약서']},{'picks':[{'id':'c1','reason':'계약서','confidence':.6}],
                  'narrow':{'question':'어느 계약서인가요?','options':['최초 계약서','1차 변경계약서','최초 계약서',3]}}]
        with patch.object(app,'gateway',side_effect=answers):
            result=app.search_ai(self.project['id'],'도급공사 계약서 찾아줘')
        self.assertEqual(result['ai']['narrow'],{'question':'어느 계약서인가요?','options':['최초 계약서','1차 변경계약서']})
        self.assertIsNone(app.narrow_question({'question':'어느?','options':['하나']}))
        self.assertIsNone(app.narrow_question('질문'))

    def test_keyword_search_drops_candidates_far_weaker_than_the_best_match(self):
        for relative,body in (('3 시공단계/착공/착공계 제출.txt',b'x'),('3 시공단계/일보/작업일보.txt','착공 이후 작업'.encode())):
            path=self.root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)
        self.index()
        result=app.search_files(self.project['id'],'착공계 제출')
        self.assertEqual([r['name'] for r in result['results']],['착공계 제출.txt'])

    def test_ai_search_looks_at_photo_previews_and_keeps_captions_for_keyword_search(self):
        # 2026-11-28 LIM: 'AI로 찾기'에서 "교보문고 사진"을 못 찾음 — 사진엔 글자가 없고 파일명은 KakaoTalk_….
        from PIL import Image
        for n, (name, color) in enumerate((('KakaoTalk_20251014_08.jpg', 'green'), ('KakaoTalk_20251014_09.jpg', 'gray'))):
            path = self.root / '3 시공단계/현장' / name; path.parent.mkdir(parents=True, exist_ok=True)
            Image.new('RGB', (900, 600), color).save(path, 'JPEG'); os.utime(path, ns=(10**18 + n * 10**9, 10**18 + n * 10**9))  # Windows 수정 시각은 100ns 단위
        (self.root / '3 시공단계/공문/착공계.txt').parent.mkdir(parents=True, exist_ok=True)
        (self.root / '3 시공단계/공문/착공계.txt').write_bytes('착공계'.encode())
        self.index()
        answers = [{'keywords': ['교보문고'], 'kinds': ['image']},
                   {'picks': [{'id': 'p2', 'reason': '교보문고 간판이 보임', 'confidence': .9}],
                    'captions': {'p1': '공사 현장 회색 벽', 'p2': '교보문고 입구, 신한은행 간판', 'p9': '없는 사진'}}]
        with patch.object(app, 'gateway', side_effect=answers) as gateway:
            result = app.search_ai(self.project['id'], '교보문고 사진 찾아줘')
        sent = gateway.call_args_list[1][0][0][1]['content']
        images = [part for part in sent if isinstance(part, dict) and part.get('type') == 'image_url']
        self.assertEqual(len(images), 2)
        self.assertNotIn(str(self.root), json.dumps([p for p in sent if p.get('type') == 'text'], ensure_ascii=False))
        self.assertEqual(result['ai']['photosSeen'], 2)
        self.assertEqual([p['name'] for p in result['ai']['picks']], ['KakaoTalk_20251014_08.jpg'])  # 최근 사진이 p1… 순서
        # 다음부터는 AI 없이 키워드 찾기로도 나온다.
        found = app.search_files(self.project['id'], '교보문고')
        self.assertEqual([r['name'] for r in found['results']], ['KakaoTalk_20251014_08.jpg'])
        self.assertIn('교보문고', found['results'][0]['snippet'])
        # 이미 설명이 있는 사진은 다시 보내지 않는다.
        with patch.object(app, 'gateway', side_effect=[{'keywords': ['현장'], 'kinds': ['image']}, {'picks': []}]) as gateway:
            app.search_ai(self.project['id'], '현장 사진')
        self.assertFalse(any(isinstance(p, dict) and p.get('type') == 'image_url'
                             for p in (gateway.call_args_list[1][0][0][1]['content'] if len(gateway.call_args_list) > 1 and isinstance(gateway.call_args_list[1][0][0][1]['content'], list) else [])))

    def test_found_file_can_be_downloaded_as_a_copy(self):
        path = self.root / '3 시공단계/공문/착공계 제출.hwp'; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(b'SYNTHETIC HWP')
        server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            body = json.dumps({'id': self.project['id'], 'relative': '3 시공단계/공문/착공계 제출.hwp'}).encode()
            with urllib.request.urlopen(urllib.request.Request(base + '/download', data=body, headers={'X-App-Token': app.TOKEN})) as response:
                self.assertEqual(response.read(), b'SYNTHETIC HWP')
                self.assertIn("filename*=UTF-8''", response.headers['Content-Disposition'])
            self.assertEqual(path.read_bytes(), b'SYNTHETIC HWP')  # 원본은 그대로
            for relative in ('../밖.txt', '3 시공단계/없음.hwp'):
                bad = json.dumps({'id': self.project['id'], 'relative': relative}).encode()
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(urllib.request.Request(base + '/download', data=bad, headers={'X-App-Token': app.TOKEN}))
                self.assertEqual(caught.exception.code, 400)
            with self.assertRaises(urllib.error.HTTPError) as caught:  # 토큰 없으면 거부
                urllib.request.urlopen(urllib.request.Request(base + '/download', data=body))
            self.assertEqual(caught.exception.code, 403)
        finally:
            server.shutdown(); server.server_close()

    def test_ai_search_turns_a_detailed_question_into_keywords_kinds_and_dates(self):
        for relative,body in (('3 시공단계/현장/누수 현장.jpg',b'x'),('3 시공단계/공문/누수 보수 요청.txt','누수 보수 요청 공문'.encode()),
                              ('3 시공단계/공문/착공계.txt','착공계'.encode())):
            path=self.root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)
        self.index()
        answers=[{'keywords':['누수','보수 요청'],'kinds':['image','pdf','nope'],'date_from':'2026-11-01','date_to':'bad'},
                 {'picks':[{'id':'c1','reason':'누수 현장 사진','confidence':.8}]}]
        with patch.object(app,'gateway',side_effect=answers) as gateway:
            result=app.search_ai(self.project['id'],'11월에 받은 누수 관련 현장 사진이랑 보수 요청 공문 찾아줘')
        self.assertEqual(gateway.call_count,2)
        self.assertEqual(result['ai']['plan'],{'keywords':['누수','보수 요청'],'kinds':['사진','PDF'],'dateFrom':'2026-11-01','dateTo':''})
        self.assertEqual({r['name'] for r in result['results']},{'누수 현장.jpg','누수 보수 요청.txt'})
        self.assertEqual(result['ai']['picks'][0]['name'],result['results'][0]['name'])  # c1 = PC 검색 1순위 후보
        self.assertIn('사진 파일',next(r for r in result['results'] if r['name']=='누수 현장.jpg')['reasons'])
        self.assertNotIn('착공계.txt',[r['name'] for r in result['results']])
        first=json.dumps(gateway.call_args_list[0][0][0],ensure_ascii=False)
        self.assertIn('11월에 받은 누수',first);self.assertNotIn(str(self.root),first)

    def test_hwp_and_hwpx_text_extraction(self):
        import doctext, zipfile
        hwpx = self.base / '문서.hwpx'
        with zipfile.ZipFile(hwpx, 'w') as archive:
            archive.writestr('Contents/section0.xml', '<hs:sec xmlns:hs="h" xmlns:hp="p"><hp:p><hp:run><hp:t>준공검사 조서</hp:t></hp:run></hp:p></hs:sec>')
        self.assertEqual(doctext.extract(hwpx), '준공검사 조서')
        record = b'\x0b\x00' + b'\x00' * 14 + '작업일보'.encode('utf-16-le') + b'\r\x00'
        self.assertEqual(doctext.hwp_para_text(record).strip(), '작업일보')

    def test_slow_actions_are_not_serialized_by_global_lock(self):
        for action in ('/configure', '/analyze-contract', '/review-ai', '/pick-folder', '/search-ai'):
            self.assertIn(action, app.UNLOCKED)
        self.assertNotIn('/execute-all', app.UNLOCKED)

    def test_usage_summary_and_prefs(self):
        import time
        (app.DATA / 'usage.jsonl').write_text(json.dumps({'at': time.strftime('%Y-%m-%d'), 'model': 'm', 'usage': {'total_tokens': 12}}) + '\n', encoding='utf-8')
        self.assertEqual(app.usage_summary()['calls'], 1)
        self.assertEqual(app.usage_summary()['tokens'], 12)
        self.assertTrue(app.prefs()['autoClassify'])
        app.set_prefs({'autoClassify': False})
        self.assertFalse(app.prefs()['autoClassify'])


    def test_templates_use_short_numbers_without_inbox(self):
        for name, tree in app.TEMPLATES.items():
            self.assertNotIn(app.INBOX, [n['label'] for n in tree])
            self.assertEqual(tree[0]['label'][:2], '1 ', name)
            for path in app.tree_paths(tree):
                self.assertRegex(path.split('/')[-1], r'^\d{1,2} \S')

    def test_label_word_keeps_numbers_that_are_part_of_the_name(self):
        self.assertEqual(app.label_word('1 1차 설계변경'), '1차 설계변경')
        self.assertEqual(app.label_word('3106-1 1차 설계변경'), '1차 설계변경')
        self.assertEqual(app.label_word('01_공통'), '공통')
        self.assertEqual(app.label_word('1차 설계변경'), '1차 설계변경')

    def test_legacy_inbox_project_keeps_working(self):
        root = self.base / '예전 사업'
        (root / app.LEGACY_INBOX).mkdir(parents=True)
        app.SELECTIONS['legacy'] = str(root)
        project = app.save_project({'selection': 'legacy', 'name': '예전', 'tree': [{'label': app.LEGACY_INBOX}, {'label': '01 공통', 'children': [{'label': '계약서'}]}]})
        (root / app.LEGACY_INBOX / '계약서.pdf').write_bytes(b'x')
        plan = app.make_plan(project['id'], True)
        self.assertEqual([r['destination'] for r in plan['rows']], ['01 공통/계약서'])
        self.assertEqual(plan['scanInfo']['inbox'], app.LEGACY_INBOX)
        self.assertFalse((root / app.INBOX).exists())

    def test_learned_rule_survives_folder_renumbering(self):
        tree = [{'label': app.INBOX}, {'label': '1 시공단계', 'children': [{'label': '3 작업일보'}, {'label': '4 주간보고'}]}]
        self.project = app.save_project({'id': self.project['id'], 'name': '시험 사업', 'tree': tree})
        self.write_file('공정표 v1.txt')
        plan = self.plan()
        app.execute(plan['id'], [{'id': plan['rows'][0]['id'], 'destination': '1 시공단계/4 주간보고'}])
        tree = [{'label': app.INBOX}, {'label': '1 시공단계', 'children': [{'label': '1 작업일보'}, {'label': '2 주간보고'}]}]
        self.project = app.save_project({'id': self.project['id'], 'name': '시험 사업', 'tree': tree})
        self.write_file('공정표 v2.txt')
        row = self.plan()['rows'][0]
        self.assertEqual(row['destination'], '1 시공단계/2 주간보고')

    def test_browse_folder_lists_indexed_files(self):
        (self.root / '01 공통/계약서/도급계약서.txt').write_bytes('계약'.encode('utf-8'))
        (self.root / '01 공통/메모.txt').write_bytes(b'memo')
        self.index()
        result = app.browse_folder(self.project['id'], '01 공통/계약서')
        self.assertEqual([r['name'] for r in result['results']], ['도급계약서.txt'])
        self.assertEqual(app.browse_folder(self.project['id'], '01 공통')['total'], 2)


    def test_folders_created_only_when_move_runs_and_undo_removes_them(self):
        root = self.base / '새 사업'
        root.mkdir()
        (root / '기존').mkdir()
        (root / '기존/260305 착공계.pdf').write_bytes(b'x')
        app.SELECTIONS['n'] = str(root)
        tree = [{'label': app.INBOX}, {'label': '1 시공', 'children': [{'label': '1 착공계'}, {'label': '2 사진'}]}]
        project = app.dispatch('/save-project', {'selection': 'n', 'name': '새', 'tree': tree})
        self.assertFalse((root / '1 시공').exists())
        plan = app.make_plan(project['id'], False)
        self.assertEqual(plan['rows'][0]['destination'], '1 시공/1 착공계')
        journal = app.execute_all(plan['id'], [{'id': plan['rows'][0]['id'], 'destination': '1 시공/1 착공계'}])
        self.assertTrue((root / '1 시공/2 사진').is_dir())
        self.assertIn('1 시공/2 사진', journal['createdFolders'])
        app.undo(journal['id'])
        self.assertTrue((root / '기존/260305 착공계.pdf').exists())
        self.assertFalse((root / '1 시공').exists())

    def test_attachment_stays_with_main_document_without_shortcut(self):
        tree = [{'label': app.INBOX}, {'label': '1 공통', 'children': [{'label': '1 보고자료'}, {'label': '2 공문'}]}]
        self.project = app.save_project({'id': self.project['id'], 'name': '시험 사업', 'tree': tree})
        folder = self.root / app.INBOX / '260410 현황 보고'
        folder.mkdir()
        (folder / '260410 현황 보고자료.docx').write_bytes(b'report')
        (folder / '붙임 공문.pdf').write_bytes(b'letter')
        plan = self.plan()
        rows = {r['name']: r for r in plan['rows']}
        main, letter = rows['260410 현황 보고자료.docx'], rows['붙임 공문.pdf']
        self.assertEqual(main['destination'], '1 공통/1 보고자료')
        self.assertEqual(letter['attachTo'], main['id'])
        self.assertNotIn('canonicalAttachment', letter)
        self.assertEqual(letter['destination'], main['destination'])
        journal = app.execute_all(plan['id'], [{'id': r['id'], 'destination': r['destination']} for r in plan['rows']])
        self.assertEqual((self.root / '1 공통/1 보고자료/A 260410 현황 보고/붙임 공문.pdf').read_bytes(), b'letter')
        self.assertEqual(journal['folderShortcuts'], [])
        self.assertEqual(list(self.root.rglob('*.lnk')), [])
        self.assertEqual([r['name'] for r in self.plan()['rows']], [])
        app.undo(journal['id'])
        self.assertEqual((folder / '붙임 공문.pdf').read_bytes(), b'letter')

    def test_attached_rows_follow_main_and_can_be_detached(self):
        tree = [{'label': app.INBOX}, {'label': '1 공통', 'children': [{'label': '1 보고자료'}, {'label': '2 공문'}, {'label': '3 기타'}]}]
        self.project = app.save_project({'id': self.project['id'], 'name': '시험 사업', 'tree': tree})
        self.write_file('보고자료.docx')
        self.write_file('공문.pdf')
        plan = self.plan()
        rows = {r['name']: r for r in plan['rows']}
        app.attach_rows(plan['id'], rows['보고자료.docx']['id'], [rows['공문.pdf']['id']])
        app.retarget(plan['id'], rows['보고자료.docx']['id'], '1 공통/3 기타')
        self.assertEqual(rows['공문.pdf']['destination'], '1 공통/3 기타')
        self.assertEqual(rows['공문.pdf']['secondaryFolders'], [])
        app.attach_rows(plan['id'], rows['보고자료.docx']['id'], [rows['공문.pdf']['id']], False)
        self.assertNotIn('attachTo', rows['공문.pdf'])


    def test_numbered_report_folder_moves_together(self):
        tree = [{'label': app.INBOX}, {'label': '1 공통', 'children': [{'label': '1 주요 보고자료'}, {'label': '2 공문 및 협의기록'}]}]
        self.project = app.save_project({'id': self.project['id'], 'name': '시험 사업', 'tree': tree})
        folder = self.root / app.INBOX / '주요 보고자료/2. 힌지교체 사업 시행계획안 보고'
        folder.mkdir(parents=True)
        for name in ('1. 대상 건물 현황.pdf', '2. 공사비 산출 내역서.xlsx', '3. 관련공문.pdf', '힌지교체사업 시행계획(안).pdf'):
            (folder / name).write_bytes(name.encode())
        rows = {r['name']: r for r in self.plan()['rows']}
        main = rows['힌지교체사업 시행계획(안).pdf']
        for name in ('1. 대상 건물 현황.pdf', '2. 공사비 산출 내역서.xlsx', '3. 관련공문.pdf'):
            self.assertEqual(rows[name]['attachTo'], main['id'])
            self.assertEqual(rows[name]['destination'], main['destination'])
            self.assertEqual(app.effective_folder(rows[name], rows[name]['destination']), app.effective_folder(main, main['destination']))


    def test_original_subfolders_kept_below_matching_folder(self):
        tree = [{'label': app.INBOX}, {'label': '2 설계단계', 'children': [{'label': '1 설계 용역', 'children': [{'label': '1 착수계'}, {'label': '2 용역사에 제공 한 자료'}]}]}]
        self.project = app.save_project({'id': self.project['id'], 'name': '시험 사업', 'tree': tree})
        deep = self.root / app.INBOX / '21 설계 용역/2102 용역사에 제공 한 자료/0.도면/KD파워'
        deep.mkdir(parents=True)
        (deep / '101 단선도.dwg').write_bytes(b'a')
        (deep / '201 결선도.dwg').write_bytes(b'b')
        plan = self.plan()
        for r in plan['rows']:
            r['destination'] = '2 설계단계/1 설계 용역/2 용역사에 제공 한 자료'
        app.keep_subfolders(plan['rows'], app.INBOX)
        row = next(r for r in plan['rows'] if r['name'] == '101 단선도.dwg')
        self.assertEqual(row['keepSub'], '0.도면/KD파워')
        app.apply_folder_names(app.get_project(self.project['id']), plan)
        self.assertEqual(row['keepSub'], 'A 도면/KD파워')
        journal = app.execute_all(plan['id'], [{'id': r['id'], 'destination': r['destination']} for r in plan['rows']])
        self.assertTrue((self.root / '2 설계단계/1 설계 용역/2 용역사에 제공 한 자료/A 도면/KD파워/101 단선도.dwg').exists())
        app.undo(journal['id'])
        self.assertTrue((deep / '101 단선도.dwg').exists())
        self.assertFalse((self.root / '2 설계단계/1 설계 용역/2 용역사에 제공 한 자료/A 도면').exists())

    def test_multi_select_retarget_keeps_structure_below_common_folder(self):
        tree = [{'label': app.INBOX}, {'label': '1 공통', 'children': [{'label': '1 품의서'}, {'label': '2 기타'}]}]
        self.project = app.save_project({'id': self.project['id'], 'name': '시험 사업', 'tree': tree})
        base = self.root / app.INBOX / '최초 품의'
        (base / '첨부').mkdir(parents=True)
        (base / 'a.pdf').write_bytes(b'a')
        (base / '첨부/b.pdf').write_bytes(b'b')
        plan = self.plan()
        rows = {r['name']: r for r in plan['rows']}
        app.retarget_many(plan['id'], [rows['a.pdf']['id'], rows['b.pdf']['id']], '1 공통/1 품의서')
        self.assertNotIn('keepSub', rows['a.pdf'])
        self.assertEqual(rows['b.pdf']['keepSub'], 'A 첨부')


if __name__ == '__main__':
    unittest.main()
