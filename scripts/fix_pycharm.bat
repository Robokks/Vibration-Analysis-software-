@echo off
REM Detects and cleans up per-subfolder `.venv\` directories that
REM PyCharm on Windows sometimes auto-creates alongside each
REM sub-package's `pyproject.toml`. Those sub-venvs don't have the
REM seven editable local packages, so running app.py from PyCharm
REM under qt-app/ etc. crashes with:
REM
REM   ModuleNotFoundError: No module named 'nvh_design_tokens'
REM
REM After running this script, in PyCharm:
REM   File -> Settings -> Project -> Python Interpreter
REM   -> gear icon -> Add Interpreter -> Add Local Interpreter -> Existing
REM   -> browse to  ...\Vibration-Analysis-software-\.venv\Scripts\python.exe

setlocal enabledelayedexpansion
cd /d "%~dp0\.."

set FOUND=0
for %%D in (libs\nvh_contract libs\nvh_api_schemas design-tokens analysis-engine simulator web-backend qt-app) do (
    if exist "%%D\.venv\" (
        echo Found stray venv:  %%D\.venv\
        set FOUND=1
    )
)

if !FOUND! == 0 (
    echo No stray per-subfolder venvs found. Nothing to do.
    echo.
    echo Make sure PyCharm's Project Interpreter points at the ROOT venv:
    echo   %CD%\.venv\Scripts\python.exe
    exit /b 0
)

echo.
set /p ANSWER=Delete the venvs listed above [y/N]?
if /i not "!ANSWER!" == "y" (
    echo Aborted -- nothing deleted.
    exit /b 0
)

for %%D in (libs\nvh_contract libs\nvh_api_schemas design-tokens analysis-engine simulator web-backend qt-app) do (
    if exist "%%D\.venv\" (
        echo Removing %%D\.venv\ ...
        rmdir /s /q "%%D\.venv"
    )
)

echo.
echo Done. Now in PyCharm:
echo   File -^> Settings -^> Project -^> Python Interpreter
echo   -^> gear -^> Add Interpreter -^> Add Local Interpreter -^> Existing
echo   -^> browse to  %CD%\.venv\Scripts\python.exe
