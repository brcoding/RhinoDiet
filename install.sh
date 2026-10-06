#!/bin/sh
# Ask for Cursor, Claude, or Codex, then place the plugin there.
set -eu
home="${RHINODIET_HOME:-$HOME}"
url="${RHINODIET_ZIP_URL:-https://github.com/brcoding/RhinoDiet/archive/refs/heads/main.zip}"

choose_host() {
  if [ -n "${RHINODIET_HOST:-}" ]; then
    printf '%s\n' "$RHINODIET_HOST"
    return
  fi
  if [ ! -r /dev/tty ]; then
    echo "Set RHINODIET_HOST to cursor, claude, or codex." >&2
    exit 1
  fi
  printf '%s\n' "Install RhinoDiet for:" "  1  Cursor" "  2  Claude" "  3  Codex" >/dev/tty
  printf 'Choice: ' >/dev/tty
  read -r choice </dev/tty
  case "$choice" in
    1 | cursor | Cursor) printf '%s\n' cursor ;;
    2 | claude | Claude) printf '%s\n' claude ;;
    3 | codex | Codex) printf '%s\n' codex ;;
    *)
      echo "Choose 1, 2, or 3." >&2
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

host="$(choose_host)"
case "$host" in
  cursor)
    dest="$home/.cursor/plugins/local/rhinodiet"
    next_step="Reload Cursor."
    ;;
  claude)
    dest="$home/.claude/skills/rhinodiet"
    next_step="Restart Claude Code."
    ;;
  codex)
    dest="$home/.codex/plugins/rhinodiet"
    next_step="Restart Codex."
    ;;
  *)
    echo "Choose Cursor, Claude, or Codex." >&2
    exit 1
    ;;
esac

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
curl -fsSL -o "$tmp/rhinodiet.zip" "$url"
unzip -q "$tmp/rhinodiet.zip" -d "$tmp"
mkdir -p "$(dirname "$dest")"
rm -rf "$dest"
mv "$tmp/RhinoDiet-main" "$dest"
if [ "$host" != "cursor" ] && [ -f "$dest/hooks/hooks.json" ]; then
  mv "$dest/hooks/hooks.json" "$dest/hooks/cursor-hooks.json"
fi
if [ "$host" = "codex" ]; then
  write_codex_marketplace
fi
printf '%s\n' "$next_step" "Type /rhinodiet."
