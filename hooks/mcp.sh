#!/usr/bin/env bash
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
export RHINODIET_ROOT="$ROOT"
exec python3 -m rhinodiet.mcp_server
