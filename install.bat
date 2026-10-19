@echo off
cd /d "%~dp0"
py -m pip install -r requirements.txt
if errorlevel 1 (echo Cai dat that bai. Hay cai Python 3 va chon Add Python to PATH. & pause & exit /b 1)
echo Da cai thu vien. Can cai them Tesseract OCR voi goi tieng Viet (vie).
pause
