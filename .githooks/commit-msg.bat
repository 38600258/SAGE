@echo off
setlocal

cd /d "%~dp0.."

set "PYTHONIOENCODING=utf-8"
set "PYTHON_BIN="
if exist ".venv\Scripts\python.exe" set "PYTHON_BIN=.venv\Scripts\python.exe"
if not defined PYTHON_BIN set "PYTHON_BIN=python"

"%PYTHON_BIN%" scripts\sage_linter.py --check-commit-msg "%~1"
exit /b %ERRORLEVEL%
