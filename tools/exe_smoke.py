"""만든 EXE를 실제로 실행해 화면이 뜨는지 확인한다(임시 데이터 폴더, 브라우저 없이). 업무 문서는 쓰지 않는다.
사용: python tools/exe_smoke.py <EXE 경로>"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path


def stop(process):
    # 한 파일 EXE는 바깥 실행기와 안쪽 앱, 프로세스가 둘이다. 둘 다 끝내야 임시 폴더를 지울 수 있다.
    if os.name == 'nt':
        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
    process.kill()
    process.wait(timeout=30)


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
    exe = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory(prefix='gongmu-exe-', ignore_cleanup_errors=True) as folder:
        env = dict(os.environ, LOCALAPPDATA=folder, HOME=folder)
        process = subprocess.Popen([str(exe), '--no-browser'], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            session = Path(folder) / 'GongmuChakData' / 'session.json'
            for _ in range(240):
                if session.is_file():
                    break
                if process.poll() is not None:
                    raise SystemExit('EXE가 바로 종료됐습니다:\n' + process.stdout.read().decode('utf-8', 'replace'))
                time.sleep(0.5)
            else:
                raise SystemExit('EXE가 120초 안에 시작되지 않았습니다.')
            url = json.loads(session.read_text(encoding='utf-8'))['url']
            for attempt in range(20):
                try:
                    with urllib.request.urlopen(url, timeout=30) as response:
                        page = response.read().decode('utf-8')
                    break
                except OSError:
                    if process.poll() is not None:
                        raise SystemExit('EXE가 시작 직후 종료됐습니다:\n' + process.stdout.read().decode('utf-8', 'replace'))
                    time.sleep(0.5)
            else:
                raise SystemExit('EXE 화면에 연결하지 못했습니다.')
            assert '공무착착' in page and '__SESSION_TOKEN__' not in page, '화면을 읽지 못했습니다.'
            token = url.split('session=', 1)[1]
            request = urllib.request.Request(url.split('/?', 1)[0] + '/status', data=b'{}', headers={'X-App-Token': token})
            with urllib.request.urlopen(request, timeout=30) as response:
                status = json.load(response)
            assert status.get('templates') and status.get('version'), status
            base = url.split('/?', 1)[0]
            def call(action, payload):
                req = urllib.request.Request(base + action, data=json.dumps(payload).encode('utf-8'),
                                             headers={'X-App-Token': token, 'Content-Type': 'application/json'})
                with urllib.request.urlopen(req, timeout=120) as reply:
                    return json.load(reply)
            # 합성 예시 폴더로 Pillow(사진·PDF 만들기)와 pypdfium2(PDF 미리보기)가 EXE 안에서 동작하는지 본다.
            demo = call('/demo-folder', {})
            tree = [{'label': '0 정리할 문서 모음'}] + status['templates']['construction']
            project = call('/save-project', {'selection': demo['selection'], 'name': '시연', 'type': 'construction', 'tree': tree})
            root = Path(demo['path'])
            pdf = next(p for p in root.rglob('*.pdf')).relative_to(root).as_posix()
            jpg = next(p for p in root.rglob('*.jpg')).relative_to(root).as_posix()
            for relative in (pdf, jpg):
                assert call('/thumb', {'id': project['id'], 'relative': relative})['data'].startswith('data:image/jpeg'), relative
            print('EXE 실행 확인:', exe.name, status['version'], '템플릿', len(status['templates']), '종 · 예시 파일', demo['count'], '개 · PDF·사진 미리보기 OK')
        finally:
            stop(process)


if __name__ == '__main__':
    main()
