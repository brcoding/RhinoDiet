#!/usr/bin/env python3
"""Start the MCP server with the plugin src on sys.path."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("RHINODIET_ROOT", str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from rhinodiet.mcp_server import main  # noqa: E402

if __name__ == "__main__":
    main()
