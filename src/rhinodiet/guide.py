"""Local walkthrough for the RhinoDiet plugin."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

from rhinodiet.testhistory import port_open

GUIDE_PORT = 8813


def page_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>How to use RhinoDiet</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin: 0; font: 17px/1.5 "Segoe UI", system-ui, sans-serif; background: #10140e; color: #f4f0e6; }
  a { color: #ffd56a; }
  .shell { display: grid; grid-template-columns: 210px minmax(0, 720px); gap: 12px; max-width: 980px; margin: 0 auto; }
  nav { position: sticky; top: 0; align-self: start; padding: 28px 8px 28px 20px; }
  nav p { margin: 0 0 10px; color: #b7b29f; font-size: 13px; letter-spacing: 0.04em; text-transform: uppercase; }
  nav a { display: block; margin: 0 0 8px; color: #f4f0e6; text-decoration: none; }
  nav a:hover, nav a:focus { color: #ffd56a; }
  main { padding: 28px 20px 64px; }
  h1 { font: 40px/1.15 Georgia, "Iowan Old Style", Palatino, serif; margin: 0 0 8px; }
  h2 { font: 26px/1.2 Georgia, "Iowan Old Style", Palatino, serif; margin: 0 0 8px; }
  p { margin: 0 0 12px; }
  .kicker { color: #ffd56a; font-size: 13px; letter-spacing: 0.08em; text-transform: uppercase; margin: 0 0 8px; }
  section { padding: 22px 0; border-top: 1px solid #343b2c; }
  ol.steps, ul { margin: 0 0 12px; padding-left: 20px; }
  li { margin: 0 0 8px; }
  code, pre { font-family: ui-monospace, "Cascadia Code", monospace; }
  pre { margin: 0 0 12px; padding: 12px 14px; background: #171d14; border: 1px solid #343b2c; border-radius: 10px; overflow-x: auto; }
  .rule { margin: 12px 0; padding: 12px 14px; border-left: 3px solid #ffd56a; background: #1b2116; }
  .rule p { margin: 0; }
  .muted { color: #b7b29f; }
  .cmdlist { list-style: none; margin: 0 0 12px; padding: 0; }
  .cmdlist li { margin: 0 0 8px; padding: 10px 12px; background: #171d14; border: 1px solid #343b2c; border-radius: 10px; }
  .cmdlist code { color: #ffd56a; }
  @media (max-width: 800px) {
    .shell { display: block; }
    nav { position: static; display: flex; gap: 12px; overflow-x: auto; padding: 16px; }
    nav p { display: none; }
    nav a { white-space: nowrap; }
    h1 { font-size: 32px; }
  }
</style>
</head>
<body>
<div class="shell">
  <nav aria-label="Tour steps">
    <p>Tour</p>
    <a href="#commands">Commands</a>
    <a href="#does">1. What it does</a>
    <a href="#install">2. Install</a>
    <a href="#first-run">3. First run</a>
    <a href="#workers">4. Workers</a>
    <a href="#memory">5. Memory</a>
    <a href="#showtests">6. /showtests</a>
    <a href="#tests">7. Test commands</a>
  </nav>
  <main>
    <header id="commands">
      <p class="kicker">Commands</p>
      <h1>How to use RhinoDiet</h1>
      <p>Type <code>/rhinodiet</code>. These four commands show up together.</p>
      <ul class="cmdlist">
        <li><code>/rhinodiet</code> opens this page. <code>rhinodiet guide</code></li>
        <li><code>/rhinodiet-init</code> installs the plugin. <code>rhinodiet init</code></li>
        <li><code>/rhinodiet-showtests</code> prints saved test runs. <code>rhinodiet test --show</code></li>
        <li><code>/rhinodiet-supervisor</code> plans and delegates. <code>rhinodiet run "your request"</code></li>
      </ul>
      <p class="muted"><code>/showtests</code> is the same as <code>/rhinodiet-showtests</code>. <code>/supervisor</code> is the same as <code>/rhinodiet-supervisor</code>.</p>
    </header>

    <section id="does">
      <h2>What RhinoDiet does</h2>
      <p>RhinoDiet cuts token use in Cursor. It compresses the prompt, hands the work to a cheaper model, and stores project memory in a local graph. The next prompt cites a node id instead of pasting the same history again.</p>
    </section>

    <section id="install">
      <h2>Install</h2>
      <p>Paste one command. On Windows, in PowerShell:</p>
      <pre><code>irm https://raw.githubusercontent.com/brcoding/RhinoDiet/main/install.ps1 | iex</code></pre>
      <p>On Linux and macOS:</p>
      <pre><code>curl -fsSL https://raw.githubusercontent.com/brcoding/RhinoDiet/main/install.sh | sh</code></pre>
      <p>That downloads the plugin into <code>~/.cursor/plugins/local/rhinodiet</code>. On Windows the folder is <code>%USERPROFILE%/.cursor/plugins/local/rhinodiet</code>. The copy is a real directory, not a symlink. Then reload Cursor and open a new chat. Type <code>/rhinodiet</code>. In Cursor, <code>/rhinodiet-init</code> runs that same command.</p>
      <p><code>rhinodiet init</code> installs the console script inside a checkout. You do not need it to load the plugin. A normal venv lives at <code>.venv</code> in the project, and the script is <code>.venv/bin/rhinodiet</code>. On Windows the script is <code>.venv/Scripts/rhinodiet.exe</code>. <code>rhinodiet</code> is that console script. It is not a separate app. If the project is on a Windows drive under WSL, the venv cannot sit on that drive, so init puts it at <code>~/.venv/rhinodiet</code>. The script is then <code>~/.venv/rhinodiet/bin/rhinodiet</code>. <code>source ~/.venv/rhinodiet/bin/activate</code> makes the short name work.</p>
      <p>On Windows, Cursor starts the MCP server by running <code>hooks/mcp.py</code> with <code>py -3</code>. If <code>py</code> is not on PATH, it uses <code>python</code>. That script adds the plugin <code>src</code> directory and starts the server. It does not use WSL, and it does not use the init venv. Linux runs the same script with <code>python3</code>. Windows needs Python 3.11 or newer.</p>
      <p>Local plugin imports must be allowed. On Enterprise that stays off until an admin turns it on.</p>
    </section>

    <section id="first-run">
      <h2>First run</h2>
      <p>After the reload, use <code>/rhinodiet-supervisor</code> on a real request. <code>/supervisor</code> is the same command. The supervisor plans and delegates. It does not write the product code.</p>
      <p class="muted"><code>/rhinodiet</code> opens this page. It does not run the supervisor.</p>
    </section>

    <section id="workers">
      <h2>Supervisor and the cheaper workers</h2>
      <p>The supervisor stays on the parent model, <code>inherit</code>. Dev, reviewer, creative, docs, release, Godot, and tester use the cheaper worker tier, <code>composer-2.5[fast=true]</code>, from <code>rhinodiet.config.json</code>.</p>
      <ul>
        <li><code>/rhinodiet-supervisor</code> plans, delegates, reviews, and sends work back. <code>/supervisor</code> is the same command.</li>
        <li><code>/dev</code> writes simple code and straightforward unit tests. Prefer a library that already exists.</li>
        <li><code>/reviewer</code> reviews the change. Findings go back to the worker that wrote it. Godot reviews use a short checklist.</li>
        <li><code>/creative</code> makes images, textures, or video. Read style from memory first.</li>
        <li><code>/docs</code> rewrites technical text so it is shorter, in active voice, with the same facts.</li>
        <li><code>/release</code> packages, releases, or runs a dev test. The only path is <code>scripts/release.sh</code>.</li>
        <li><code>/godot</code> owns Godot 4 scenes, scripts, signals, the input map, and the export pipeline. Read the engine version from memory first.</li>
        <li><code>/tester</code> plays a registered game.</li>
      </ul>
      <div class="rule">
        <p>The tester tries to beat the level. A few seconds of survival is not a pass.</p>
      </div>
    </section>

    <section id="memory">
      <h2>Memory cites</h2>
      <p>The graph file is <code>.rhinodiet/memory.db</code> in the project directory. It is gitignored.</p>
      <pre><code>rhinodiet cite "token expiry"</code></pre>
      <p>That command returns ids, labels, and short summaries. It does not return stored bodies. Pass those ids on the next prompt.</p>
      <p>Compaction runs after 48 nodes. It folds old short-term notes into a smaller long-term model and drops the detail.</p>
    </section>

    <section id="showtests">
      <h2>/rhinodiet-showtests</h2>
      <p><code>/rhinodiet-showtests</code> reads <code>.rhinodiet/tests/history.json</code> and prints each saved run. <code>/showtests</code> is the same command. Time, mode, area, pass or fail, pellets, time survived, ghosts hit, board cleared, and the still paths are in that read.</p>
      <pre><code>rhinodiet test --show</code></pre>
      <p>History and stills live in <code>.rhinodiet/tests/</code>. The command does not start a new game.</p>
      <p>If the history page is already up, open <a href="http://127.0.0.1:8797/">http://127.0.0.1:8797/</a>. If it is not, start it with <code>rhinodiet test --serve</code>.</p>
    </section>

    <section id="tests">
      <h2>Test commands</h2>
      <p>These commands play the registered game. For the built-in Pac-Man project, the tester tries to beat the level. A few seconds of survival is not a pass.</p>
      <pre><code>rhinodiet test
rhinodiet test --loops N
rhinodiet test --focus "avoid ghosts"
rhinodiet test --focus "restart"
rhinodiet test --focus "reach the end while avoiding ghosts"
rhinodiet test --serve</code></pre>
      <ul>
        <li><code>rhinodiet test</code> clears the board, twice by default.</li>
        <li><code>rhinodiet test --loops N</code> raises that cap.</li>
        <li><code>rhinodiet test --focus "avoid ghosts"</code> plays that area and still tries to clear the board.</li>
        <li><code>rhinodiet test --focus "restart"</code> only checks that restart restores the board.</li>
        <li><code>rhinodiet test --focus "reach the end while avoiding ghosts"</code> is the clear goal.</li>
        <li><code>rhinodiet test --serve</code> opens the history page on port 8797.</li>
      </ul>
      <p>Godot still owns the scenes and the export. The tester only plays.</p>
    </section>
  </main>
</div>
</body>
</html>
"""


class GuideHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        return

    def do_GET(self) -> None:
        path = unquote(self.path.split("?", 1)[0])
        if path in {"/", "/index.html"}:
            body = page_html().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        body = b"Not found."
        self.send_response(404)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def bind_guide(port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer(("0.0.0.0", port), GuideHandler)


def serve(port: int = GUIDE_PORT) -> None:
    server = bind_guide(port)
    actual = server.server_address[1]
    print(f"Guide at http://127.0.0.1:{actual}/")
    server.serve_forever()


def start_guide(port: int = GUIDE_PORT) -> str:
    url = f"http://127.0.0.1:{port}/"
    if port_open(port):
        return f"Guide is already up at {url}"
    root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    src = str(root / "src")
    env["PYTHONPATH"] = src + os.pathsep + env.get("PYTHONPATH", "")
    subprocess.Popen(
        [sys.executable, "-m", "rhinodiet.guide", "--serve", "--port", str(port)],
        cwd=str(root),
        env=env,
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(40):
        if port_open(port):
            return f"Guide at {url}"
        time.sleep(0.05)
    return f"Guide did not start at {url}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rhinodiet.guide")
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--port", type=int, default=GUIDE_PORT)
    args = parser.parse_args(argv)
    if port_open(args.port):
        print(f"Guide is already up at http://127.0.0.1:{args.port}/")
        return 0
    serve(args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
