"""Measure synthetic plan/bulk I/O. Uses a temporary project and a local fake AI only."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--files', type=int, default=240)
    parser.add_argument('--candidate-mib', type=int, default=64)
    parser.add_argument('--output')
    args = parser.parse_args()
    if not 1 <= args.files <= 2000 or not 1 <= args.candidate_mib <= 256:
        parser.error('Use 1..2000 files and a 1..256 MiB synthetic candidate.')
    with tempfile.TemporaryDirectory(prefix='gongmu-performance-') as folder:
        base = Path(folder)
        root = base / 'synthetic-project'
        inbox = root / app.INBOX
        inbox.mkdir(parents=True)
        for i in range(args.files): (inbox / f'{i:05d}.dat').write_bytes(b'SYNTHETIC')
        # Candidate metadata and hash reads are measured; no JPEG decoding/OCR is tested.
        candidate = inbox / '계약서.jpg'
        with candidate.open('wb') as stream: stream.truncate(args.candidate_mib * 1024 * 1024)
        reads = []
        original_hash = app.file_hash
        def digest(path):
            reads.append(Path(path).stat().st_size)
            return original_hash(path)
        def gateway(messages):
            files = json.loads(messages[-1]['content'])['files']
            return {'assignments': [{'file_id': row['file_id'], 'destination_id': None,
                                     'reason': '합성 검사: 보류', 'confidence': 0.1} for row in files]}
        with patch.object(app, 'DATA', base / 'settings'), patch.object(app, 'file_hash', side_effect=digest), \
                patch.object(app, 'gateway', side_effect=gateway) as ai:
            app.SELECTIONS['performance-probe'] = str(root)
            project = app.save_project({'selection': 'performance-probe', 'name': '합성 사업',
                                        'type': 'construction', 'tree': [{'label': app.INBOX}] + app.TEMPLATES['construction']}, False)
            started = time.perf_counter()
            plan = app.make_plan(project['id'], True)
            planned = time.perf_counter()
            info = app.bulk_info(plan['id'])
            app.JOBS['performance-probe'] = {'id': 'performance-probe', 'planId': plan['id'], 'recheck': False,
                                             'status': 'pending', 'processed': 0, 'completedBatches': 0, **info}
            app.run_bulk('performance-probe')
            job = app.JOBS['performance-probe']
            result = {'source': str(app.APP), 'synthetic': True, 'liveAI': False,
                      'files': args.files, 'candidateMiB': args.candidate_mib, 'batches': info['batches'],
                      'hashReads': len(reads), 'bytesHashed': sum(reads), 'mockAICalls': ai.call_count,
                      'planSeconds': round(planned - started, 3), 'totalSeconds': round(time.perf_counter() - started, 3),
                      'status': job['status'], 'error': job.get('error')}
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output: Path(args.output).write_text(text + '\n', encoding='utf-8')
    print(text)
    if result['status'] != 'done': raise SystemExit(1)


if __name__ == '__main__':
    main()
