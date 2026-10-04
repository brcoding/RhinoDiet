"""Release worker. The script is the path. One-off commands are not."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

_PR = re.compile(r"\bpull request\b|\bopen a pr\b|\bpr\b", re.I)

_HEADER = """#!/usr/bin/env bash
# One release path. check, dev-test, publish, and tokens.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="$(pwd)/src${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUNBUFFERED=1

run_check() {
  python -m pytest
  python -m build
  echo "Release build finished."
}

run_dev_test() {
  # Export, serve on IPv4 and IPv6, and start cloudflared when it is on PATH.
  python -u -m rhinodiet.devtest "$@"
}

run_tokens() {
  python -u -m rhinodiet.tokens record "$@"
}
"""

_PUBLISH = """
run_publish() {
  git add -A
  git commit -m "Release"
  git push -u origin HEAD
  if command -v gh >/dev/null 2>&1; then
    url=$(gh pr list --head "$(git branch --show-current)" --state open --json url --jq '.[0].url // empty' || true)
    if [ -n "$url" ]; then
      printf '%s\\n' "$url"
    else
      gh pr create --draft --title "Release" --body "Release."
    fi
  else
    echo "Open a draft pull request for this branch."
  fi
}
"""

_DISPATCH_PUBLISH = """
cmd="${1:-check}"
case "$cmd" in
  check) run_check ;;
  dev-test) shift; run_dev_test "$@" ;;
  publish) run_publish ;;
  tokens) shift; run_tokens "$@" ;;
  *)
    echo "Use check, dev-test, publish, or tokens." >&2
    exit 2
    ;;
esac
"""

_DISPATCH = """
cmd="${1:-check}"
case "$cmd" in
  check) run_check ;;
  dev-test) shift; run_dev_test "$@" ;;
  tokens) shift; run_tokens "$@" ;;
  *)
    echo "Use check, dev-test, or tokens." >&2
    exit 2
    ;;
esac
"""


@dataclass(frozen=True)
class ReleaseResult:
    script: Path
    summary: str


class ReleaseWriter:
    def run(self, request: str, root: Path, apply: bool = False) -> ReleaseResult:
        script = root / "scripts" / "release.sh"
        script.parent.mkdir(parents=True, exist_ok=True)
        body = _HEADER
        if _PR.search(request):
            body += _PUBLISH + _DISPATCH_PUBLISH
        else:
            body += _DISPATCH
        script.write_text(body, encoding="utf-8")
        script.chmod(0o755)
        if apply:
            subprocess.run(["bash", str(script)], check=False, cwd=root)
        return ReleaseResult(script, "Wrote scripts/release.sh.")
