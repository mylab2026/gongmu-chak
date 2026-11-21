﻿$ErrorActionPreference = 'Stop'
$appDir = Join-Path $env:LOCALAPPDATA 'Programs\GongmuChakTest'
$pythonExe = Join-Path $appDir 'runtime\python.exe'
Write-Host '공무착착 설치 마무리 복구' -ForegroundColor Cyan
Write-Host '이미 설치된 Python과 구성요소를 사용합니다. 다시 다운로드하지 않습니다.'
try {
    foreach ($path in @($pythonExe, (Join-Path $appDir 'app.py'), (Join-Path $appDir 'ui.html'), (Join-Path $appDir 'run.cmd'))) {
        if (-not (Test-Path -LiteralPath $path)) { throw '기본 설치 파일이 없습니다. 수정된 전체 패키지의 설치.cmd를 실행해주세요.' }
    }
    $checkFile = Join-Path $appDir 'runtime_check.py'
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'runtime_check.py') -Destination $checkFile -Force
    Write-Host '[1/2] 실행환경 확인 중...'
    & $pythonExe $checkFile
    if ($LASTEXITCODE -ne 0) { throw '구성요소를 불러오지 못했습니다. 이 화면 전체를 보내주세요.' }
    Write-Host '[2/2] 바탕화면 바로가기 만드는 중...'
    $shell = New-Object -ComObject WScript.Shell
    $shortcutPath = Join-Path ([Environment]::GetFolderPath('Desktop')) '공무착착 시험판.lnk'
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = Join-Path $appDir 'run.cmd'
    $shortcut.WorkingDirectory = $appDir
    $shortcut.Description = '공무착착 Windows 개인 시험판'
    $shortcut.Save()
    Write-Host '복구 완료. 공무착착을 실행합니다.' -ForegroundColor Green
    Start-Process -FilePath (Join-Path $appDir 'run.cmd') -WorkingDirectory $appDir
} catch {
    Write-Host ('복구 실패: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
