#!/usr/bin/env bash
# Linux execs this file and skips the Windows block. Windows cmd runs the block.
: << 'CMDBLOCK'
@echo off
setlocal EnableExtensions EnableDelayedExpansion
set "HOOK_DIR=%~dp0"
for %%I in ("%HOOK_DIR%..") do set "PLUGIN_WIN=%%~fI"

where wsl.exe >nul 2>&1
if errorlevel 1 goto native

set "PLUGIN_WSL="
for /f "usebackq delims=" %%P in (`wsl.exe wslpath -a "%PLUGIN_WIN%"`) do set "PLUGIN_WSL=%%P"
if not defined PLUGIN_WSL goto native

call :wslvar CURSOR_PROJECT_DIR
call :wslvar RHINODIET_PROJECT

wsl.exe env "PYTHONPATH=!PLUGIN_WSL!/src" "RHINODIET_ROOT=!PLUGIN_WSL!" "CURSOR_PROJECT_DIR=!CURSOR_PROJECT_DIR!" "RHINODIET_PROJECT=!RHINODIET_PROJECT!" python3 "!PLUGIN_WSL!/hooks/session_start.py"
exit /b !ERRORLEVEL!

:wslvar
set "VAR_NAME=%~1"
set "VAR_VALUE=!%VAR_NAME%!"
if "!VAR_VALUE!"=="" exit /b 0
set "VAR_WSL="
for /f "usebackq delims=" %%P in (`wsl.exe wslpath -a "!VAR_VALUE!"`) do set "VAR_WSL=%%P"
if defined VAR_WSL set "%VAR_NAME%=!VAR_WSL!"
exit /b 0

:native
set "PYTHONPATH=%PLUGIN_WIN%\src"
set "RHINODIET_ROOT=%PLUGIN_WIN%"
where py >nul 2>&1
if errorlevel 1 goto pythoncmd
py -3 "%PLUGIN_WIN%\hooks\session_start.py"
exit /b !ERRORLEVEL!

:pythoncmd
python "%PLUGIN_WIN%\hooks\session_start.py"
exit /b !ERRORLEVEL!
CMDBLOCK

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
export RHINODIET_ROOT="${RHINODIET_ROOT:-$ROOT}"
exec python3 "$ROOT/hooks/session_start.py" "$@"
