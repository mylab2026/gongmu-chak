$ErrorActionPreference = 'Stop'
$appDir = Join-Path $env:LOCALAPPDATA 'Programs\GongmuChakTest'
$pythonExe = Join-Path $appDir 'runtime\python.exe'
try {
    if (-not (Test-Path -LiteralPath $pythonExe)) { throw '먼저 설치.cmd를 실행해주세요.' }
    $running = Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -eq $pythonExe }
    if ($running) { throw '공무착착의 검은 실행 창을 닫아 종료한 뒤 업데이트해주세요. 브라우저 탭만 닫으면 종료되지 않습니다.' }
    foreach ($name in @('app.py','collection_assistant.py','history_archive.py','doctext.py','olefile.py','ui.html','review-map.js','contract-input.js','workflow.js','finder.js','collection.js','revision-ui.js','templates.json','reference-builder.html','requirements.txt','runtime_check.py','README.html','THIRD_PARTY.txt','VALIDATION.txt')) {
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Destination $appDir -Force
    }
    & $pythonExe (Join-Path $appDir 'runtime_check.py')
    if ($LASTEXITCODE -ne 0) { throw '실행환경을 확인하지 못했습니다. 오류 화면을 보내주세요.' }
    Write-Host '업데이트 완료. 사업 정보·계약 현황·API 설정은 유지했습니다.' -ForegroundColor Green
    Write-Host 'AI 연결 설정에서 모델 목록을 불러오거나 모델 ID를 입력한 뒤 연결 확인·저장을 눌러주세요.'
    Start-Process -FilePath (Join-Path $appDir 'run.cmd') -WorkingDirectory $appDir
} catch {
    Write-Host ('업데이트 실패: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
