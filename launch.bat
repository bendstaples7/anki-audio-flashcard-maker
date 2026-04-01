@echo off
title Cantonese Anki Generator - Updating...

cd /d "%~dp0"

echo ============================================================
echo   Cantonese Anki Generator - Auto-Update Launcher
echo ============================================================
echo.

:: Check if git is available
where git >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo WARNING: git not found. Skipping update, launching with current version.
    echo.
    goto :launch
)

:: Check if this is a git repo
git rev-parse --git-dir >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo WARNING: Not a git repository. Skipping update, launching with current version.
    echo.
    goto :launch
)

echo Checking for updates from GitHub...
echo.

:: Fetch latest from origin
git fetch origin main >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo WARNING: Could not reach GitHub. Launching with current version.
    echo.
    goto :launch
)

:: Switch to main if not already there
for /f "tokens=*" %%b in ('git rev-parse --abbrev-ref HEAD') do set CURRENT_BRANCH=%%b
if not "%CURRENT_BRANCH%"=="main" (
    echo Switching to main branch...
    git checkout main >nul 2>nul
)
:: Check checkout result outside the block so ERRORLEVEL is evaluated correctly
if not "%CURRENT_BRANCH%"=="main" if errorlevel 1 (
    echo WARNING: Could not switch to main. Launching with current version.
    echo.
    goto :launch
)

:: Confirm we're actually on main before pulling
for /f "tokens=*" %%b in ('git rev-parse --abbrev-ref HEAD') do set CURRENT_BRANCH=%%b
if not "%CURRENT_BRANCH%"=="main" (
    echo WARNING: Not on main branch. Launching with current version.
    echo.
    goto :launch
)

:: Check if there are updates
for /f "tokens=*" %%a in ('git rev-parse HEAD') do set LOCAL=%%a
for /f "tokens=*" %%a in ('git rev-parse origin/main') do set REMOTE=%%a

if "%LOCAL%"=="%REMOTE%" (
    echo Already up to date.
) else (
    echo Pulling latest changes...
    git pull origin main
    if errorlevel 1 (
        echo WARNING: Pull failed. Launching with current version.
        echo.
        goto :launch
    )
    echo.
    echo Updated successfully.

    :: Install any new dependencies
    echo Checking dependencies...
    python -m pip install -r requirements.txt -q >nul 2>nul
    python -m pip install -e . -q >nul 2>nul
)

echo.

:launch
echo Starting Cantonese Anki Generator...
echo ============================================================
echo.
python -m cantonese_anki_generator.web.run
