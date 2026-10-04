"""Windows Cursor launches the MCP server through the cmd polyglot."""

import json
import os
import subprocess

from support import ROOT


def test_launchers_use_wsl_without_a_hardcoded_drive():
    mcp = json.loads((ROOT / "mcp.json").read_text(encoding="utf-8"))
    hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    assert mcp["mcpServers"]["rhinodiet"]["command"] == "./hooks/mcp.cmd"
    assert hooks["hooks"]["sessionStart"][0]["command"] == "./hooks/session_start.cmd"
    for name in ("mcp.cmd", "session_start.cmd"):
        text = (ROOT / "hooks" / name).read_text(encoding="utf-8")
        assert "wsl.exe" in text
        assert "wslpath" in text
        assert "py -3" in text
        assert "python" in text
        assert "P:" not in text
        assert "/home/" not in text
        assert "/mnt/p" not in text
        assert "\r" not in text


def test_linux_mcp_cmd_execs_the_module(tmp_path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    out = tmp_path / "out"
    fake = bindir / "python3"
    fake.write_text(
        "#!/bin/sh\nprintf '%s\\n' \"$PYTHONPATH\" > \"$OUT\"\nprintf '%s\\n' \"$@\" >> \"$OUT\"\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{bindir}{os.pathsep}{env.get('PATH', '')}"
    env["OUT"] = str(out)
    proc = subprocess.run(
        [str(ROOT / "hooks" / "mcp.cmd")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[0].endswith("/src")
    assert lines[1:] == ["-m", "rhinodiet.mcp_server"]


def test_linux_session_start_cmd_prints_json(tmp_path):
    proc = subprocess.run(
        [str(ROOT / "hooks" / "session_start.cmd")],
        cwd=tmp_path,
        input="{}",
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert "additional_context" in payload
