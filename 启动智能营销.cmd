@echo off
setlocal
set "STUDIO_ROOT=%~dp0"
set "PYTHONPATH=%STUDIO_ROOT%.runtime\python_deps;%STUDIO_ROOT%"
set "STUDIO_PYTHON=C:\Users\26840\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%STUDIO_PYTHON%" set "STUDIO_PYTHON=python"
cd /d "%STUDIO_ROOT%"
if /I "%~1"=="--check" goto check
"%STUDIO_PYTHON%" -m app.launcher
pause
exit /b
:check
"%STUDIO_PYTHON%" -c "import app.main; print('STUDIO_CHECK_OK')"
