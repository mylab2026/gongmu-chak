"""공무착착 실행 파일(EXE) 만들기. Windows에서 실행하면 dist/GongmuChak-<버전>.exe 하나가 생긴다.

- 화면 파일(ui.html, *.js)과 templates.json을 EXE 안에 넣는다. 설정·기록·색인은 그대로 %LOCALAPPDATA%\\GongmuChakData에 둔다.
- 실행하면 검은 창(서버)이 뜨고 브라우저가 열린다. 창을 닫으면 종료된다(기존 run.cmd와 같다).
- 디지털 서명은 하지 않는다. 서명이 없으면 Windows가 처음 실행 때 경고할 수 있다.
사용: python tools/build_exe.py [--output 폴더]
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_FILES = ['templates.json', 'ui.html', 'review-map.js', 'contract-input.js', 'workflow.js', 'finder.js',
              'collection.js', 'revision-ui.js', 'chatbot-support.js', 'ui-clarity.js']


def version():
    match = re.search(r"'version': '([0-9.]+)", (ROOT / 'app.py').read_text(encoding='utf-8'))
    return match.group(1) if match else 'test'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default=str(ROOT / 'dist'))
    args = parser.parse_args()
    output = Path(args.output).resolve()
    work = output / 'build-work'
    name = 'GongmuChak-' + version()
    missing = [f for f in DATA_FILES if not (ROOT / f).is_file()]
    if missing:
        raise SystemExit('EXE에 넣을 파일이 없습니다: ' + ', '.join(missing))
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--console',
               '--name', name, '--distpath', str(output), '--workpath', str(work), '--specpath', str(work),
               '--paths', str(ROOT), '--hidden-import', 'collection_assistant', '--collect-all', 'pypdfium2']
    for name_ in DATA_FILES:
        command += ['--add-data', str(ROOT / name_) + os.pathsep + '.']
    command.append(str(ROOT / 'app.py'))
    subprocess.run(command, check=True, cwd=ROOT)
    exe = output / (name + ('.exe' if os.name == 'nt' else ''))
    if not exe.is_file():
        raise SystemExit('EXE가 만들어지지 않았습니다.')
    print(exe)


if __name__ == '__main__':
    main()
