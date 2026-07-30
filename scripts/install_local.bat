@echo off
REM One-shot install: third-party deps (from requirements.txt) then all
REM seven local packages in editable mode.
REM
REM Kept as a plain command list rather than baked into requirements.txt
REM because older pip releases (e.g. the 23.2.x that ships with many
REM Windows PyCharm bundles) reject `-e ./path` inside a requirements
REM file with "is not a valid editable requirement".
REM
REM Run from the repository root inside your activated venv:
REM   .venv\Scripts\activate
REM   scripts\install_local.bat
REM
REM Pass --dev to also install pytest via requirements-dev.txt.

setlocal
cd /d "%~dp0\.."

python -m pip install --upgrade pip
if errorlevel 1 goto :fail

if "%~1"=="--dev" (
    python -m pip install -r requirements-dev.txt
) else (
    python -m pip install -r requirements.txt
)
if errorlevel 1 goto :fail

python -m pip install ^
    -e libs/nvh_contract ^
    -e libs/nvh_api_schemas ^
    -e design-tokens ^
    -e analysis-engine ^
    -e simulator ^
    -e web-backend ^
    -e qt-app
if errorlevel 1 goto :fail

echo.
echo Local packages installed. Try:  nvh-sim --trials 5
exit /b 0

:fail
echo.
echo Install failed.
exit /b 1
