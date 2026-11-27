"""Build a source-complete Windows installer ZIP; never include user data."""
import hashlib
import json
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parent
output = root.parent / 'GongmuChak-Windows-Test-0.11.3.zip'
files = ['설치.cmd', 'install.ps1', '설치복구.cmd', 'repair.ps1', '업데이트.cmd', 'update.ps1', 'runtime_check.py', 'run.cmd', 'app.py', 'doctext.py', 'olefile.py', 'ui.html', 'review-map.js', 'contract-input.js', 'workflow.js', 'finder.js', 'collection.js', 'revision-ui.js', 'templates.json',
         'requirements.txt', 'requirements-dev.txt', 'requirements-browser.txt', 'tools/browser_smoke.py', 'README.html', 'THIRD_PARTY.txt', 'VALIDATION.txt',
         'REVISION.md', 'QA-0.11.1.md', 'test_app.py', 'test_revision.py', 'test_automation.py', 'test_corrections.py', 'test_meeting_policy.py', 'test_collect_export.py', 'test_v3_roles.py', 'test_v3_collect.py', 'test_user_requirements.py', 'test_windows_runtime.py', 'test_revision_ui.cjs', 'test_ui.cjs', 'reference-builder.html', 'build_package.py']
files.extend(['collection_assistant.py','test_collection_assistant.py','test_state_consistency.py','tools/browser_smoke_gateway.py','QA-0.11.2.md'])
files.extend(['test_flat_destination_bundles.py','history_archive.py','test_history_archive.py'])
files.extend(['demo_sample.py','test_demo_sample.py'])
files.extend(['chatbot_support.py','chatbot-support.js','ui-clarity.js','test_chatbot_support.py','test_ui_clarity.py','QA-CHATBOT.md'])
files.extend(['test_user_folder_scope.py','test_journal_batching.py','test_check_groups.py','test_user_made_folders.py','test_delete_project.py','test_contract_fixes.py'])
files.extend(['test_large_project_performance.py','tools/performance_probe.py','QA-PERFORMANCE.md'])
files.extend(['test_bulk_throughput.py','test_round3.py'])
files.extend(p.relative_to(root).as_posix() for p in sorted((root/'chatbot').glob('*')) if p.is_file())
manifest = {}
with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
    for name in files:
        data = (root / name).read_bytes()
        if name.endswith(('.ps1', '.cmd')):
            data = data.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
        if name.endswith('.ps1'):
            data = b'\xef\xbb\xbf' + data.removeprefix(b'\xef\xbb\xbf').removeprefix(b'\xef\xbb\xbf')  # Windows PowerShell 5.1 Korean strings.
        archive.writestr('GongmuChak-Test/' + name, data)
        manifest[name] = hashlib.sha256(data).hexdigest()
    archive.writestr('GongmuChak-Test/SHA256.json', json.dumps(manifest, ensure_ascii=False, indent=2))
with zipfile.ZipFile(output) as archive:
    assert archive.testzip() is None
    for name, checksum in manifest.items():
        assert hashlib.sha256(archive.read('GongmuChak-Test/' + name)).hexdigest() == checksum
print(output)
print('ZIP integrity and all file hashes verified; installer uses UTF-8 BOM + CRLF.')
repair_output = root.parent / 'GongmuChak-Install-Repair.zip'
with zipfile.ZipFile(repair_output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
    for name in ['설치복구.cmd', 'repair.ps1', 'runtime_check.py']:
        data = (root / name).read_bytes()
        if name.endswith(('.ps1', '.cmd')):
            data = data.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
        if name.endswith('.ps1'):
            data = b'\xef\xbb\xbf' + data.removeprefix(b'\xef\xbb\xbf').removeprefix(b'\xef\xbb\xbf')
        archive.writestr('GongmuChak-Repair/' + name, data)
with zipfile.ZipFile(repair_output) as archive:
    assert archive.testzip() is None
    assert archive.read('GongmuChak-Repair/repair.ps1').startswith(b'\xef\xbb\xbf')
print(repair_output)

# Offline package: same files plus Python runtime, pip and Windows wheels, for PCs that block downloads.
import subprocess, sys, urllib.request
if '--offline' not in sys.argv:
    sys.exit(0)
cache = root.parent / 'offline-cache'
(cache / 'wheels').mkdir(parents=True, exist_ok=True)
python_version = '3.14.10'
for url, name in [(f'https://www.python.org/ftp/python/{python_version}/python-{python_version}-embed-amd64.zip', 'python-embed.zip'),
                  ('https://bootstrap.pypa.io/pip/pip.pyz', 'pip.pyz')]:
    if not (cache / name).exists():
        urllib.request.urlretrieve(url, cache / name)
subprocess.run([sys.executable, '-m', 'pip', 'download', '--quiet', '--only-binary=:all:', '--platform', 'win_amd64',
                '--python-version', '3.14', '--implementation', 'cp', '--dest', str(cache / 'wheels'),
                '-r', str(root / 'requirements.txt')], check=True)
offline_output = root.parent / 'GongmuChak-Windows-Offline-0.11.1.zip'
with zipfile.ZipFile(offline_output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
    with zipfile.ZipFile(output) as online:
        for item in online.namelist():
            archive.writestr(item, online.read(item))
    for path in sorted(cache.rglob('*')):
        if path.is_file():
            archive.write(path, 'GongmuChak-Test/offline/' + path.relative_to(cache).as_posix())
with zipfile.ZipFile(offline_output) as archive:
    assert archive.testzip() is None
    names = archive.namelist()
    assert 'GongmuChak-Test/offline/python-embed.zip' in names
    assert any(n.startswith('GongmuChak-Test/offline/wheels/pillow') for n in names)
    assert any(n.startswith('GongmuChak-Test/offline/wheels/pypdfium2') for n in names)
print(offline_output)

