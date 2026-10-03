"""Release worker. The script is the path. One-off commands are not."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

_PR = re.compile(r"\bpull request\b|\bopen a pr\b|\bpr\b", re.I)

_BASE = """#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m pytest
python -m build
echo "Release build finished."
"""

_PUBLISH = """git add -A
git commit -m "Release"
git push -u origin HEAD
echo "Open a draft pull request for this branch."
"""


@dataclass(frozen=True)
class ReleaseResult:
    script: Path
    summary: str


class ReleaseWriter:
    def run(self, request: str, root: Path, apply: bool = False) -> ReleaseResult:
        script = root / "scripts" / "release.sh"
        script.parent.mkdir(parents=True, exist_ok=True)
        body = _BASE
        if _PR.search(request):
            body += _PUBLISH
        script.write_text(body, encoding="utf-8")
        script.chmod(0o755)
        if apply:
            subprocess.run(["bash", str(script)], check=False, cwd=root)
        return ReleaseResult(script, "Wrote scripts/release.sh.")
