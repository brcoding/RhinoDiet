#!/usr/bin/env bash
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

run_publish() {
  git add -A
  git commit -m "Release"
  git push -u origin HEAD
  if command -v gh >/dev/null 2>&1; then
    url=$(gh pr list --head "$(git branch --show-current)" --state open --json url --jq '.[0].url // empty' || true)
    if [ -n "$url" ]; then
      printf '%s\n' "$url"
    else
      gh pr create --draft --title "Release" --body "Release."
    fi
  else
    echo "Open a draft pull request for this branch."
  fi
}

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
