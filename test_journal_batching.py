"""큰 정리 실행에서 기록 파일을 파일마다 다시 쓰지 않으면서도, 중간에 멈춘 실행을 되돌릴 수 있어야 한다(합성 자료)."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class JournalBatching(unittest.TestCase):
    COUNT = 250

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); base = Path(self.tmp.name)
        self.dp = patch.object(app, 'DATA', base / 'data'); self.dp.start(); app.DATA.mkdir()
        app.atomic_json(app.DATA / 'prefs.json', {'autoClassify': False})
        self.root = base / '가상 사업'
        for i in range(self.COUNT):
            path = self.root / '작업일보' / f'작업일보 {i:03d}.txt'; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'SYNTHETIC %d' % i)
        app.SELECTIONS['batch'] = str(self.root); app.PLANS.clear()
        tree = [{'label': app.INBOX}, {'label': '3 시공단계', 'children': [{'label': '1 도급공사', 'children': [{'label': '14 작업일보'}]}]}]
        self.project = app.save_project({'selection': 'batch', 'name': '가상 사업', 'type': 'construction', 'tree': tree}, False)

    def tearDown(self):
        self.dp.stop(); app.SELECTIONS.pop('batch', None); app.PLANS.clear(); self.tmp.cleanup()

    def files(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*') if p.is_file() and '.gongmu-chak' not in p.parts}

    def plan(self):
        plan = app.make_plan(self.project['id'], False)
        chosen = [{'id': r['id'], 'destination': r['destination']} for r in plan['rows'] if r['destination']]
        self.assertEqual(len(chosen), self.COUNT)
        return plan, chosen

    def test_journal_is_written_in_batches_not_per_file(self):
        plan, chosen = self.plan()
        writes = []
        real = app.atomic_json
        def counting(path, value):
            if Path(path).parent.name == 'history':
                writes.append(len(value.get('entries', [])))
            return real(path, value)
        with patch.object(app, 'atomic_json', side_effect=counting):
            journal = app.execute(plan['id'], chosen)
        self.assertTrue(all(e['status'] == 'moved' for e in journal['entries']))
        self.assertLess(len(writes), 20, writes)
        # The first journal on disk already lists every planned move.
        self.assertEqual(writes[0], self.COUNT)

    def test_crash_in_the_middle_is_fully_undone(self):
        before = self.files()
        plan, chosen = self.plan()
        real_move = app.move_no_replace
        moved = []
        def crash_after(source, destination):
            if len(moved) == 137:
                raise RuntimeError('simulated power loss')
            real_move(source, destination); moved.append(destination)
        with patch.object(app, 'move_no_replace', side_effect=crash_after):
            with self.assertRaises(RuntimeError):
                app.execute(plan['id'], chosen)
        self.assertNotEqual(self.files(), before)  # some files really moved
        journal_id = next(p.stem for p in (app.DATA / 'history').glob('*.json'))
        on_disk = app.read_json(app.DATA / 'history' / (journal_id + '.json'))
        self.assertEqual(len(on_disk['entries']), self.COUNT)
        app.undo(journal_id)
        self.assertEqual(self.files(), before)

    def test_atomic_json_retries_a_briefly_locked_file(self):
        real = os.replace
        calls = []
        def flaky(src, dst):
            calls.append(dst)
            if len(calls) < 3:
                raise PermissionError(5, 'locked by scanner')
            return real(src, dst)
        target = app.DATA / 'retry.json'
        with patch.object(app.os, 'replace', side_effect=flaky):
            app.atomic_json(target, {'ok': True})
        self.assertEqual(app.read_json(target), {'ok': True})
        self.assertEqual(len(calls), 3)


    @unittest.skipUnless(os.name == 'nt', 'Windows rename path only')
    def test_briefly_locked_file_is_moved_after_retry_without_replacing(self):
        source = self.root / '작업일보' / '작업일보 000.txt'; destination = self.root / '옮긴 곳' / 'a.txt'
        real = os.rename
        calls = []
        def locked_once(src, dst):
            calls.append(dst)
            if len(calls) == 1:
                raise PermissionError(32, 'used by another process')
            return real(src, dst)
        with patch.object(app.os, 'rename', side_effect=locked_once):
            app.move_no_replace(source, destination)
        self.assertTrue(destination.is_file()); self.assertFalse(source.exists()); self.assertEqual(len(calls), 2)


if __name__ == '__main__':
    unittest.main()
