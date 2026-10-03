#!/usr/bin/env python3
"""Inject cite ids at session start. Never inject node bodies."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rhinodiet.config import load_config, resolve_memory_path  # noqa: E402
from rhinodiet.graph import GraphStore  # noqa: E402


def main() -> None:
    try:
        raw = sys.stdin.read()
        if raw.strip():
            json.loads(raw)
        project = Path(os.environ.get("CURSOR_PROJECT_DIR") or os.environ.get("RHINODIET_PROJECT") or Path.cwd())
        os.environ.setdefault("RHINODIET_ROOT", str(ROOT))
        config = load_config()
        db = resolve_memory_path(config, project)
        if not db.exists():
            context = "RhinoDiet memory is empty. Cite node ids after the first run."
        else:
            graph = GraphStore(db)
            cites = graph.cite("project", limit=5)
            graph.close()
            if not cites:
                context = "RhinoDiet memory has no cites yet."
            else:
                lines = [f"{item.id} [{item.label}] {item.summary}" for item in cites]
                context = "RhinoDiet cites. Pass these ids. Do not paste history.\n" + "\n".join(lines)
        json.dump({"additional_context": context}, sys.stdout)
    except Exception:
        json.dump({"additional_context": ""}, sys.stdout)


if __name__ == "__main__":
    main()
