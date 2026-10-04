"""Local walkthrough page and the /rhinodiet command."""

import re
import threading
from urllib.request import urlopen

from rhinodiet.cli import main
from rhinodiet.guide import GUIDE_PORT, bind_guide, page_html

from support import ROOT


def _visible(html: str) -> str:
    text = re.sub(r"<style>.*?</style>", "", html, flags=re.S)
    return re.sub(r"<[^>]+>", " ", text)


def test_guide_page_walks_through_in_order():
    html = page_html()
    ids = ["does", "install", "first-run", "workers", "memory", "showtests", "tests"]
    spots = [html.index(f'id="{item}"') for item in ids]
    assert spots == sorted(spots)
    visible = _visible(html)
    assert ";" not in visible
    assert "\u2014" not in html
    assert "\u2013" not in html
    assert "What RhinoDiet does" in visible
    assert "Install" in visible
    assert "First run" in visible
    assert "Supervisor and the cheaper workers" in visible
    assert "Memory cites" in visible
    assert "/showtests" in visible
    assert "Test commands" in visible
    assert "The tester tries to beat the level." in visible
    assert "A few seconds of survival is not a pass." in visible
    assert ".rhinodiet/memory.db" in visible
    assert ".rhinodiet/tests/" in visible
    order = ["/dev", "/reviewer", "/creative", "/docs", "/release", "/godot", "/tester"]
    indexes = [visible.index(item) for item in order]
    assert indexes == sorted(indexes)
    for command in (
        "rhinodiet test",
        "rhinodiet test --loops N",
        'rhinodiet test --focus "avoid ghosts"',
        'rhinodiet test --focus "restart"',
        'rhinodiet test --focus "reach the end while avoiding ghosts"',
        "rhinodiet test --serve",
    ):
        assert command in visible
    assert GUIDE_PORT not in {8741, 8797}
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "/rhinodiet" in readme
    assert f"http://127.0.0.1:{GUIDE_PORT}/" in readme
    command = (ROOT / "commands" / "rhinodiet.md").read_text(encoding="utf-8")
    assert "name: rhinodiet" in command
    assert "rhinodiet guide" in command
    assert "rhinodiet_prepare" not in command
    supervisor = (ROOT / "commands" / "supervisor.md").read_text(encoding="utf-8")
    assert "name: supervisor" in supervisor
    assert "rhinodiet_prepare" in supervisor


def test_guide_serves_html():
    server = bind_guide(0)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urlopen(f"http://127.0.0.1:{port}/", timeout=2) as response:
            body = response.read().decode("utf-8")
            status = response.status
        assert status == 200
        assert "How to use RhinoDiet" in body
        assert 'id="tests"' in body
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_guide_cli_reports_an_existing_page(monkeypatch, capsys):
    monkeypatch.setattr("rhinodiet.guide.port_open", lambda _port: True)
    assert main(["guide"]) == 0
    out = capsys.readouterr().out
    assert f"Guide is already up at http://127.0.0.1:{GUIDE_PORT}/" in out
