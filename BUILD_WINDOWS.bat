@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
%PY% -m pip install --upgrade pip
%PY% -m pip install -r requirements.txt pyinstaller
%PY% -m PyInstaller --noconfirm --clean --onefile --windowed --name "THAN Quiz Assistant" --icon "than_quiz.ico" --add-data "brand_logo.png;." --collect-all pyautogui --collect-all pytesseract app.py
if errorlevel 1 (echo BUILD FAILED & pause & exit /b 1)
echo.
echo EXE READY: dist\THAN Quiz Assistant.exe
pause
