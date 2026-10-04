import os
import signal
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

from rhinodiet.devtest import (
    DEFAULT_PORT,
    local_urls,
    open_tunnel,
    preset_text,
    serve_directory,
    tunnel_url_from_log,
)
from rhinodiet.release import ReleaseWriter
from rhinodiet.supervisor import wants_dev, wants_release

from support import boot


ROOT = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def test_dev_test_request_writes_one_script_and_does_not_run_it(tmp_path):
    model_calls = []

    class Recording:
        def complete(self, agent, model, system, user):
            model_calls.append(agent)
            return "{}"

    supervisor, _graph = boot(tmp_path, Recording())
    report = supervisor.run("serve the html export for a dev test")
    script = tmp_path / "scripts" / "release.sh"
    text = script.read_text(encoding="utf-8")
    assert report.agents == ["release"]
    assert model_calls == []
    assert "python -u -m rhinodiet.devtest" in text
    assert "python -u -m rhinodiet.tokens record" in text
    assert "python -m pytest" in text
    assert 'git commit -m "Release"' not in text
    assert "cloudflared tunnel" not in text
    assert not (tmp_path / "dist").exists()


def test_publish_stays_in_the_release_script(tmp_path):
    supervisor, _graph = boot(tmp_path)
    supervisor.run("package the release and open a pull request")
    text = (tmp_path / "scripts" / "release.sh").read_text(encoding="utf-8")
    committed = (ROOT / "scripts" / "release.sh").read_text(encoding="utf-8")
    assert text == committed
    assert 'git commit -m "Release"' in text
    assert "git push -u origin HEAD" in text
    assert "gh pr create --draft" in text
    assert "gh pr list --head" in text
    assert "Open a draft pull request for this branch." in text


def test_dev_test_phrase_is_release_not_dev():
    assert wants_release("run a dev-test")
    assert not wants_dev("run a dev-test")
    assert wants_dev("add a parser")
    assert not wants_release("write the release notes")


def test_preset_targets_the_export_path(tmp_path):
    index = tmp_path / "web" / "index.html"
    text = preset_text(index)
    assert 'name="Web"' in text
    assert f'export_path="{index.resolve().as_posix()}"' in text


def test_tunnel_url_is_parsed_from_the_log():
    assert tunnel_url_from_log("log https://example.trycloudflare.com/ more") == "https://example.trycloudflare.com"
    assert tunnel_url_from_log("no url") is None


def test_missing_cloudflared_does_not_print_a_hand_command(capsys, monkeypatch):
    monkeypatch.setattr("rhinodiet.devtest.shutil.which", lambda _name: None)
    assert open_tunnel(DEFAULT_PORT) is None
    printed = capsys.readouterr().out
    assert "scripts/release.sh dev-test" in printed
    assert "--url" not in printed
    assert DEFAULT_PORT not in {3000, 5173, 8080, 8741}


def test_dev_test_serves_localhost_and_ipv6(tmp_path):
    static = tmp_path / "site"
    static.mkdir()
    (static / "index.html").write_text("<title>Pac-Man</title>\n", encoding="utf-8")
    (static / "index.wasm").write_bytes(b"\0asm")
    port = _free_port()
    servers = serve_directory(static, port, tunnel=False)
    try:
        for url in local_urls(port):
            with urllib.request.urlopen(url, timeout=2) as response:
                assert response.status == 200
                if url.endswith("/") and "index.wasm" not in url:
                    assert "Pac-Man" in response.read().decode()
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/index.wasm", timeout=2) as response:
            assert response.headers.get("Content-Type", "").startswith("application/wasm")
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()


def test_release_script_serves_without_godot(tmp_path):
    writer = ReleaseWriter()
    script = writer.run("serve the html export", tmp_path).script
    static = tmp_path / "site"
    static.mkdir()
    (static / "index.html").write_text("<title>Pac-Man</title>\n", encoding="utf-8")
    port = _free_port()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    shim = bin_dir / "python"
    shim.write_text('#!/bin/sh\nexec python3 "$@"\n', encoding="utf-8")
    shim.chmod(0o755)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    proc = subprocess.Popen(
        ["bash", str(script), "dev-test", "--static", str(static), "--port", str(port), "--no-tunnel"],
        cwd=tmp_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
        env=env,
    )
    try:
        body = ""
        for _ in range(50):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=0.5) as response:
                    body = response.read().decode()
                    break
            except Exception:
                time.sleep(0.1)
        else:
            raise AssertionError(proc.stderr.read() if proc.stderr else "server did not start")
        assert "Pac-Man" in body
        with urllib.request.urlopen(f"http://[::1]:{port}/", timeout=2) as response:
            assert response.status == 200
        assert proc.poll() is None
    finally:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=5)
