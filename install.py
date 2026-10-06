#!/usr/bin/env python3
"""Copy RhinoDiet into Cursor and install the local CLI."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from rhinodiet.setup import setup  # noqa: E402


def main() -> int:
    sys.stdout.write(setup(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
