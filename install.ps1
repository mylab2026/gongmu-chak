$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$appDir = Join-Path $env:LOCALAPPDATA 'Programs\GongmuChakTest'
$runtimeDir = Join-Path $appDir 'runtime'
$packageDir = Join-Path $appDir 'packages'
$pythonVersion = '3.14.10'
$offlineDir = Join-Path $PSScriptRoot 'offline'
$offline = Test-Path -LiteralPath (Join-Path $offlineDir 'python-embed.zip')
$downloadDir = Join-Path ([IO.Path]::GetTempPath()) ('GongmuChak-' + [Guid]::NewGuid().ToString('N'))
Write-Host '공무착착 Windows 개인 시험판 설치' -ForegroundColor Cyan
Write-Host '개인 PC에만 설치합니다. 사업 문서나 API 키를 서버로 업로드하지 않습니다.'
if ($offline) { Write-Host '오프라인 설치 파일을 사용합니다. 인터넷 연결이 필요하지 않습니다.' }
else { Write-Host 'Python.org와 PyPI에서 실행 구성요소를 내려받으므로 인터넷 연결이 필요합니다.' }
try {
    if (-not [Environment]::Is64BitOperatingSystem) { throw '64비트 Windows 10/11에서 실행해주세요.' }
    $running = Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -eq (Join-Path $runtimeDir 'python.exe') }
    if ($running) { throw '실행 중인 공무착착 콘솔 창을 종료한 후 설치해주세요.' }
    New-Item -ItemType Directory -Force -Path $appDir,$runtimeDir,$packageDir,$downloadDir | Out-Null
    foreach ($name in @('app.py','doctext.py','olefile.py','ui.html','review-map.js','contract-input.js','workflow.js','finder.js','collection.js','revision-ui.js','templates.json','requirements.txt','run.cmd','runtime_check.py','reference-builder.html','README.html','THIRD_PARTY.txt')) {
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Destination $appDir -Force
    }
    $pythonExe = Join-Path $runtimeDir 'python.exe'
    if (-not (Test-Path $pythonExe)) {
        $runtimeZip = Join-Path $downloadDir 'python.zip'
        if ($offline) {
            Write-Host '[1/3] Python 실행환경 준비 중(포함된 파일)...'
            Copy-Item -LiteralPath (Join-Path $offlineDir 'python-embed.zip') -Destination $runtimeZip
        } else {
            Write-Host '[1/3] Python 실행환경 다운로드 중...'
            Invoke-WebRequest -UseBasicParsing -Uri "https://www.python.org/ftp/python/$pythonVersion/python-$pythonVersion-embed-amd64.zip" -OutFile $runtimeZip
        }
        Expand-Archive -LiteralPath $runtimeZip -DestinationPath $runtimeDir -Force
    }
    $pthFile = Join-Path $runtimeDir 'python314._pth'
    "python314.zip`r`n.`r`n../packages`r`nimport site`r`n" | Set-Content -LiteralPath $pthFile -Encoding ASCII
    Write-Host '[2/3] PDF 및 이미지 구성요소 설치 중...'
    if ($offline) {
        $pipFile = Join-Path $offlineDir 'pip.pyz'
        & $pythonExe $pipFile --isolated install --disable-pip-version-check --no-warn-script-location --only-binary=:all: --upgrade --no-index --find-links (Join-Path $offlineDir 'wheels') --target $packageDir --requirement (Join-Path $appDir 'requirements.txt')
    } else {
        $pipFile = Join-Path $downloadDir 'pip.pyz'
        Invoke-WebRequest -UseBasicParsing -Uri 'https://bootstrap.pypa.io/pip/pip.pyz' -OutFile $pipFile
        & $pythonExe $pipFile --isolated install --disable-pip-version-check --no-warn-script-location --only-binary=:all: --upgrade --target $packageDir --requirement (Join-Path $appDir 'requirements.txt')
    }
    if ($LASTEXITCODE -ne 0) { throw '구성요소 설치에 실패했습니다. 인터넷 연결 또는 학교의 다운로드 제한을 확인해주세요.' }
    & $pythonExe (Join-Path $appDir 'runtime_check.py')
    if ($LASTEXITCODE -ne 0) { throw '실행환경 확인에 실패했습니다.' }
    Write-Host '[3/3] 바탕화면 바로가기 만드는 중...'
    $shell = New-Object -ComObject WScript.Shell
    $shortcutPath = Join-Path ([Environment]::GetFolderPath('Desktop')) '공무착착 시험판.lnk'
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = Join-Path $appDir 'run.cmd'
    $shortcut.WorkingDirectory = $appDir
    $shortcut.Description = '공무착착 Windows 개인 시험판'
    $shortcut.Save()
    Write-Host '설치 완료. 바탕화면의 공무착착 시험판을 실행해주세요.' -ForegroundColor Green
    Write-Host ('설치 위치: ' + $appDir)
    Start-Process -FilePath (Join-Path $appDir 'README.html')
} catch {
    Write-Host ('설치 실패: ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host '학교 보안 정책으로 차단되면 정책을 우회하지 말고 전산 담당자에게 확인해주세요.'
    exit 1
} finally {
    if (Test-Path $downloadDir) { Remove-Item -LiteralPath $downloadDir -Recurse -Force }
}
