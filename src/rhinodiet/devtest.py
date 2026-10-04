"""Dev-test server. Export, listen on IPv4 and IPv6, print reachable URLs."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Uncommon default. Leaves 8741 free for a server that is already running.
DEFAULT_PORT = 8791

_TUNNEL_URL = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")

_PRESET = """[preset.0]

name="Web"
platform="Web"
runnable=true
advanced_options=false
dedicated_server=false
custom_features=""
export_filter="all_resources"
include_filter=""
exclude_filter=""
export_path="{export_path}"
encryption_include_filters=""
encryption_exclude_filters=""
encrypt_pck=false
encrypt_directory=false
script_export_mode=2

[preset.0.options]

custom_template/debug=""
custom_template/release=""
variant/extensions_support=false
variant/thread_support=false
vram_texture_compression/for_desktop=true
vram_texture_compression/for_mobile=false
html/export_icon=true
html/custom_html_shell=""
html/head_include=""
html/canvas_resize_policy=2
html/focus_canvas_on_start=true
html/experimental_virtual_keyboard=false
progressive_web_app/enabled=false
progressive_web_app/offline_page=""
progressive_web_app/display=1
progressive_web_app/orientation=0
progressive_web_app/icon_144x144=""
progressive_web_app/icon_180x180=""
progressive_web_app/icon_512x512=""
progressive_web_app/background_color=Color(0, 0, 0, 1)
"""


def local_urls(port: int) -> list[str]:
    return [f"http://127.0.0.1:{port}/", f"http://[::1]:{port}/"]


def preset_text(export_path: Path) -> str:
    path = export_path.resolve().as_posix()
    if '"' in path:
        raise ValueError("Export path cannot contain a quote.")
    return _PRESET.format(export_path=path)


def tunnel_url_from_log(text: str) -> str | None:
    match = _TUNNEL_URL.search(text)
    if not match:
        return None
    return match.group(0)


def find_godot() -> str:
    chosen = os.environ.get("GODOT")
    if chosen:
        return chosen
    found = shutil.which("godot")
    if found:
        return found
    raise SystemExit("Godot is not on PATH. Pass --static DIR to serve an existing export.")


def find_project(root: Path, project: str | None) -> Path:
    if project:
        path = Path(project)
        if not (path / "project.godot").is_file():
            raise SystemExit(f"No project.godot in {path}.")
        return path
    candidates = [root / "benchmarks" / "godot-pacman", root]
    for candidate in candidates:
        if (candidate / "project.godot").is_file():
            return candidate
    raise SystemExit("No Godot project found. Pass --static DIR or --project PATH.")


def write_preset(project: Path, export_path: Path) -> None:
    # Godot worker and dev-test share this preset. Serving stays in dev-test.
    dest = project / "export_presets.cfg"
    if dest.exists():
        return
    dest.write_text(preset_text(export_path), encoding="utf-8")


def export_web(project: Path, dest: Path, godot: str | None = None) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    index = dest / "index.html"
    write_preset(project, index)
    binary = godot or find_godot()
    subprocess.run(
        [binary, "--headless", "--path", str(project), "--export-release", "Web", str(index)],
        check=True,
    )
    return dest


class _Server(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def _handler(directory: Path):
    class Handler(SimpleHTTPRequestHandler):
        extensions_map = {
            **SimpleHTTPRequestHandler.extensions_map,
            ".wasm": "application/wasm",
            ".pck": "application/octet-stream",
        }

        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(directory), **kwargs)

        def end_headers(self):
            self.send_header("Cache-Control", "no-cache")
            super().end_headers()

        def log_message(self, fmt, *args):
            return

    return Handler


def _bind(family: int, host: str, port: int, directory: Path, v6only: int | None) -> _Server:
    class Bound(_Server):
        address_family = family

        def server_bind(self):
            if v6only is not None:
                self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, v6only)
            super().server_bind()

    try:
        return Bound((host, port), _handler(directory))
    except OSError as exc:
        raise SystemExit(f"Could not listen on {host} port {port}. Left other listeners alone. {exc}") from exc


def bind_servers(directory: Path, port: int) -> list[_Server]:
    servers = [_bind(socket.AF_INET, "0.0.0.0", port, directory, None)]
    try:
        servers.append(_bind(socket.AF_INET6, "::", port, directory, 1))
    except SystemExit:
        servers[0].server_close()
        raise
    return servers


def open_tunnel(port: int) -> subprocess.Popen[str] | None:
    binary = shutil.which("cloudflared")
    if not binary:
        print(
            "No cloudflared on PATH. Rerun scripts/release.sh dev-test after it is installed.",
            flush=True,
        )
        return None
    proc = subprocess.Popen(
        [binary, "tunnel", "--url", f"http://127.0.0.1:{port}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    def _watch() -> None:
        assert proc.stdout is not None
        buffer = ""
        for line in proc.stdout:
            buffer += line
            url = tunnel_url_from_log(buffer)
            if url:
                print(url, flush=True)
                return

    threading.Thread(target=_watch, daemon=True).start()
    return proc


def serve_directory(directory: Path, port: int, tunnel: bool) -> list[_Server]:
    servers = bind_servers(directory, port)
    for server in servers:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    for url in local_urls(port):
        print(url, flush=True)
    if tunnel:
        open_tunnel(port)
    return servers


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rhinodiet.devtest")
    parser.add_argument("--static", help="Serve this directory instead of exporting")
    parser.add_argument("--project", help="Godot project directory")
    parser.add_argument("--dest", default="build/dev-test")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-tunnel", action="store_true")
    args = parser.parse_args(argv)
    root = Path.cwd()
    if args.static:
        directory = Path(args.static)
        if not directory.is_dir():
            raise SystemExit(f"Static directory does not exist: {directory}")
    else:
        project = find_project(root, args.project)
        directory = export_web(project, root / args.dest)
    servers = serve_directory(directory, args.port, tunnel=not args.no_tunnel)
    try:
        threading.Event().wait()
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
