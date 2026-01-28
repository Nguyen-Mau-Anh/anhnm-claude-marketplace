@echo off
REM Auto-detect Python executable and run orchestrate-auto-dev
REM This script ensures compatibility whether 'python' or 'python3' is available

setlocal

REM Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"

REM Detect available Python executable
where python3 >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "PYTHON_CMD=python3"
    goto :run
)

where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "PYTHON_CMD=python"
    goto :run
)

echo Error: Neither 'python' nor 'python3' found in PATH
echo Please install Python 3.8 or later
exit /b 127

:run
cd /d "%SCRIPT_DIR%"
%PYTHON_CMD% -m executor %*
