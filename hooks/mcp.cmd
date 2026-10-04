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

wsl.exe env "PYTHONPATH=!PLUGIN_WSL!/src" "RHINODIET_ROOT=!PLUGIN_WSL!" python3 -m rhinodiet.mcp_server
exit /b !ERRORLEVEL!

:native
set "PYTHONPATH=%PLUGIN_WIN%\src"
set "RHINODIET_ROOT=%PLUGIN_WIN%"
where py >nul 2>&1
if errorlevel 1 goto pythoncmd
py -3 -m rhinodiet.mcp_server
exit /b !ERRORLEVEL!

:pythoncmd
python -m rhinodiet.mcp_server
exit /b !ERRORLEVEL!
CMDBLOCK

exec "$(cd "$(dirname "$0")" && pwd)/mcp.sh" "$@"
