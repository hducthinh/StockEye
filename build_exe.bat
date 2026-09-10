@echo off
echo ===========================================
echo       STOCKEYE - BUILD TO EXE SCRIPT
echo ===========================================

echo [1/4] Building auto_setup.exe...
pyinstaller --onefile auto_setup.py

echo [2/4] Building main.exe...
pyinstaller --onefile main.py

echo [3/4] Copying config, engine and templates to dist folder...
copy /Y config.json dist\config.json
if not exist dist\engine mkdir dist\engine
copy /Y engine\* dist\engine\
if not exist dist\templates mkdir dist\templates
xcopy /E /I /Y templates dist\templates

echo [4/4] Cleaning up temporary build files...
if exist build rmdir /S /Q build
if exist auto_setup.spec del /Q auto_setup.spec
if exist main.spec del /Q main.spec
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"

echo ===========================================
echo Build complete! Ready-to-run folder is 'dist'.
echo ===========================================
pause
