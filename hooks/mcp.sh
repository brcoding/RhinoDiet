#!/usr/bin/env bash
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec python3 "$ROOT/hooks/mcp.py" "$@"
