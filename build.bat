@echo off
setlocal

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

set ICON_ARGS=
if exist assets\icon.ico (
    set ICON_ARGS=--icon assets\icon.ico
)

pyinstaller ^
 --clean ^
 --noconsole ^
 --onefile ^
 %ICON_ARGS% ^
 --name PDFImageExtractor ^
 --additional-hooks-dir hooks ^
 src\main.py

pause
