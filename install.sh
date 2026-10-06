#!/bin/sh
# Ask for Cursor, Claude, or Codex, then place the plugin there.
set -eu
home="${RHINODIET_HOME:-$HOME}"
url="${RHINODIET_ZIP_URL:-https://github.com/brcoding/RhinoDiet/archive/refs/heads/main.zip}"
if [ -z "${RHINODIET_HOST:-}" ] && [ -n "${1:-}" ]; then
  RHINODIET_HOST="$1"
fi

choose_host() {
  if [ -n "${RHINODIET_HOST:-}" ]; then
    printf '%s\n' "$RHINODIET_HOST"
    return
  fi
  if [ ! -r /dev/tty ]; then
    echo "Set RHINODIET_HOST to cursor, claude, codex, or all." >&2
    exit 1
  fi
  printf '%s\n' "Install RhinoDiet for:" "  1  Cursor" "  2  Claude" "  3  Codex" "  4  All" >/dev/tty
  printf 'Choice: ' >/dev/tty
  read -r choice </dev/tty
  case "$choice" in
    1 | cursor | Cursor) printf '%s\n' cursor ;;
    2 | claude | Claude) printf '%s\n' claude ;;
    3 | codex | Codex) printf '%s\n' codex ;;
    4 | all | All) printf '%s\n' all ;;
    *)
      echo "Choose 1, 2, 3, or 4." >&2
      exit 1
      ;;
  esac
}

write_codex_marketplace() {
  python3 - "$home" <<'PY'
import json
import sys
from pathlib import Path

home = Path(sys.argv[1])
path = home / ".agents" / "plugins" / "marketplace.json"
entry = {
    "name": "rhinodiet",
    "source": {"source": "local", "path": "./.codex/plugins/rhinodiet"},
    "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
    "category": "Productivity",
}
path.parent.mkdir(parents=True, exist_ok=True)
data = {"name": "personal", "plugins": []}
if path.exists():
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(loaded, dict):
        data = loaded
plugins = data.get("plugins")
if not isinstance(plugins, list):
    plugins = []
kept = [
    item
    for item in plugins
    if not (isinstance(item, dict) and item.get("name") == "rhinodiet")
]
kept.append(entry)
data["plugins"] = kept
data.setdefault("name", "personal")
path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
}

place_copy() {
  case "$1" in
    cursor) dest="$home/.cursor/plugins/local/rhinodiet" ;;
    claude) dest="$home/.claude/skills/rhinodiet" ;;
    codex) dest="$home/.codex/plugins/rhinodiet" ;;
    *)
      echo "Choose Cursor, Claude, Codex, or all." >&2
      exit 1
      ;;
  esac
  mkdir -p "$(dirname "$dest")"
  rm -rf "$dest"
  cp -R "$tmp/RhinoDiet-main" "$dest"
  if [ "$1" != "cursor" ] && [ -f "$dest/hooks/hooks.json" ]; then
    mv "$dest/hooks/hooks.json" "$dest/hooks/cursor-hooks.json"
  fi
  if [ "$1" = "codex" ]; then
    write_codex_marketplace
  fi
}

host="$(choose_host)"
host="$(printf '%s' "$host" | tr '[:upper:]' '[:lower:]')"
case "$host" in
  cursor | claude | codex | all | update | upgrade) ;;
  *)
    echo "Choose Cursor, Claude, Codex, or all." >&2
    exit 1
    ;;
esac

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
curl -fsSL -o "$tmp/rhinodiet.zip" "$url"
unzip -q "$tmp/rhinodiet.zip" -d "$tmp"
if [ "$host" = "update" ] || [ "$host" = "upgrade" ]; then
  found=0
  for one in cursor claude codex; do
    case "$one" in
      cursor) have="$home/.cursor/plugins/local/rhinodiet" ;;
      claude) have="$home/.claude/skills/rhinodiet" ;;
      codex) have="$home/.codex/plugins/rhinodiet" ;;
    esac
    if [ -d "$have" ]; then
      place_copy "$one"
      found=1
    fi
  done
  if [ "$found" -eq 0 ]; then
    place_copy cursor
    place_copy claude
    place_copy codex
  fi
  printf '%s\n' "Updated from GitHub."
  if [ -d "$home/.cursor/plugins/local/rhinodiet" ]; then
    printf '%s\n' "Reload Cursor."
  fi
  if [ -d "$home/.claude/skills/rhinodiet" ]; then
    printf '%s\n' "Restart Claude Code."
  fi
  if [ -d "$home/.codex/plugins/rhinodiet" ]; then
    printf '%s\n' "Restart Codex."
  fi
  printf '%s\n' "Type /rhinodiet."
elif [ "$host" = "all" ]; then
  place_copy cursor
  place_copy claude
  place_copy codex
  printf '%s\n' "Reload Cursor." "Restart Claude Code." "Restart Codex." "Type /rhinodiet."
else
  place_copy "$host"
  case "$host" in
    cursor) printf '%s\n' "Reload Cursor." ;;
    claude) printf '%s\n' "Restart Claude Code." ;;
    codex) printf '%s\n' "Restart Codex." ;;
  esac
  printf '%s\n' "Type /rhinodiet."
fi
