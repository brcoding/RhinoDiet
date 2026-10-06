#!/bin/sh
# Place RhinoDiet where Cursor loads local plugins.
set -eu
root="${RHINODIET_HOME:-$HOME}/.cursor/plugins/local"
dest="$root/rhinodiet"
url="${RHINODIET_ZIP_URL:-https://github.com/brcoding/RhinoDiet/archive/refs/heads/main.zip}"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
curl -fsSL -o "$tmp/rhinodiet.zip" "$url"
unzip -q "$tmp/rhinodiet.zip" -d "$tmp"
mkdir -p "$root"
rm -rf "$dest"
mv "$tmp/RhinoDiet-main" "$dest"
printf '%s\n' "Reload Cursor." "Type /rhinodiet."
