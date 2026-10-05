#!/usr/bin/env bash
# Linux execs this file and skips the Windows block. Windows cmd runs the block.
: << 'CMDBLOCK'
@echo off
setlocal EnableExtensions
set "HOOK_DIR=%~dp0"
where py >nul 2>&1
if errorlevel 1 goto pythoncmd
py -3 "%HOOK_DIR%mcp.py"
exit /b %ERRORLEVEL%

:pythoncmd
python "%HOOK_DIR%mcp.py"
exit /b %ERRORLEVEL%
CMDBLOCK

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec python3 "$ROOT/hooks/mcp.py" "$@"
