@echo off
setlocal

for /f "delims=" %%I in ('git rev-parse --show-toplevel') do cd /d "%%I"

set "PYTHONIOENCODING=utf-8"
set "LINTER="
if exist "scripts\sage_linter.py" set "LINTER=scripts\sage_linter.py"
if not defined LINTER if exist "skills\sage-workflow\core\scripts\sage_linter.py" set "LINTER=skills\sage-workflow\core\scripts\sage_linter.py"
if not defined LINTER (
  echo SAGE commit-msg: sage_linter.py not found 1>&2
  exit /b 2
)

set "PYTHON_BIN="
if exist ".venv\Scripts\python.exe" set "PYTHON_BIN=.venv\Scripts\python.exe"
if not defined PYTHON_BIN set "PYTHON_BIN=python"

"%PYTHON_BIN%" "%LINTER%" --check-commit-msg "%~1"
exit /b %ERRORLEVEL%