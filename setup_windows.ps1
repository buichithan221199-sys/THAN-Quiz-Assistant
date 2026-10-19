$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.Encoding]::UTF8
$src=Split-Path -Parent $MyInvocation.MyCommand.Path
$dest=Join-Path $env:LOCALAPPDATA 'Programs\THAN Quiz Assistant'
Write-Host 'THAN Quiz Assistant - One-click Windows setup' -ForegroundColor Cyan
if (-not (Get-Command py -ErrorAction SilentlyContinue) -and -not (Get-Command python -ErrorAction SilentlyContinue)) {
  if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { throw 'Python is missing and winget is unavailable. Install Python 3.12 from python.org, then rerun setup.' }
  Write-Host 'Installing Python 3.12 via winget...'
  winget install --id Python.Python.3.12 --exact --source winget --accept-package-agreements --accept-source-agreements --silent
  if ($LASTEXITCODE -ne 0) { throw 'Python installation failed.' }
}
$py = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'
if (-not (Test-Path $py)) {
  $cmd=Get-Command py -ErrorAction SilentlyContinue
  if ($cmd) { $py='py'; $prefix=@('-3') }
  else {
    $cmd=Get-Command python -ErrorAction SilentlyContinue
    if (-not $cmd) { throw 'Python not found after installation. Restart Windows and rerun setup.' }
    $py=$cmd.Source; $prefix=@()
  }
} else { $prefix=@() }
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item (Join-Path $src 'app.py') $dest -Force
Copy-Item (Join-Path $src 'requirements.txt') $dest -Force
Write-Host 'Creating isolated Python environment...'
& $py @prefix -m venv (Join-Path $dest '.venv')
if ($LASTEXITCODE -ne 0) { throw 'Failed to create Python environment.' }
$venvpy=Join-Path $dest '.venv\Scripts\python.exe'
Write-Host 'Installing dependencies (Internet required)...'
& $venvpy -m pip install --disable-pip-version-check -r (Join-Path $dest 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
$tess=Join-Path $env:ProgramFiles 'Tesseract-OCR\tesseract.exe'
if (-not (Test-Path $tess)) {
  Write-Host 'Tesseract OCR is not installed. Trying winget...'
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    winget install --id UB-Mannheim.TesseractOCR --exact --source winget --accept-package-agreements --accept-source-agreements --silent
    if ($LASTEXITCODE -ne 0) { Write-Warning 'OCR installation failed; manual Tesseract installation may be needed.' }
  } else { Write-Warning 'Please install Tesseract OCR separately.' }
}
if (Test-Path $tess) {
  $settingsDir=Join-Path $env:APPDATA 'ThanQuizAssistant'
  New-Item -ItemType Directory -Force -Path $settingsDir | Out-Null
  $settingsPath=Join-Path $settingsDir 'settings.json'
  if (-not (Test-Path $settingsPath)) { @{region=@(0,0,620,760);next=@(335,575);threshold=0.84;tesseract=$tess} | ConvertTo-Json | Set-Content -Encoding UTF8 $settingsPath }
  $vie=Join-Path $env:ProgramFiles 'Tesseract-OCR\tessdata\vie.traineddata'
  if (-not (Test-Path $vie)) { Write-Warning 'Vietnamese OCR data missing. Install Vietnamese language data for Tesseract before using OCR.' }
}
$launcher=Join-Path $dest 'Launch_THAN_Quiz_Assistant.bat'
@'
@echo off
cd /d "%~dp0"
"%~dp0.venv\Scripts\pythonw.exe" "%~dp0app.py"
'@ | Set-Content -Encoding ASCII $launcher
$desktop=[Environment]::GetFolderPath('Desktop')
$shortcut=Join-Path $desktop 'THAN Quiz Assistant.lnk'
$ws=New-Object -ComObject WScript.Shell
$lnk=$ws.CreateShortcut($shortcut)
$lnk.TargetPath=$launcher
$lnk.WorkingDirectory=$dest
$lnk.Description='THAN Quiz Assistant'
$lnk.Save()
Write-Host "Installed to $dest" -ForegroundColor Green
Write-Host "Desktop shortcut: $shortcut" -ForegroundColor Green
Write-Host 'Note: Auto Mode does not click answers in this version.' -ForegroundColor Yellow
