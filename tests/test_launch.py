"""Cursor launches the MCP server with a Python script, not WSL."""

import json
import os
import subprocess
import sys

from support import ROOT


def _windows_block(name: str) -> str:
    text = (ROOT / "hooks" / name).read_text(encoding="utf-8")
    start = text.index("@echo off")
    end = text.index("\nCMDBLOCK", start)
    return text[start:end]


def test_windows_blocks_call_python_without_wsl():
    mcp = _windows_block("mcp.cmd")
    session = _windows_block("session_start.cmd")
    assert 'py -3 "%HOOK_DIR%mcp.py"' in mcp
    assert 'python "%HOOK_DIR%mcp.py"' in mcp
    assert 'py -3 "%HOOK_DIR%session_start.py"' in session
    assert 'python "%HOOK_DIR%session_start.py"' in session
    for block in (mcp, session):
        assert "wsl.exe" not in block
        assert "wslpath" not in block
        assert "python3" not in block
        assert "P:" not in block
        assert "/mnt/" not in block
        assert "/home/" not in block
    for name in ("mcp.cmd", "session_start.cmd", "mcp.sh", "mcp.py"):
        text = (ROOT / "hooks" / name).read_text(encoding="utf-8")
        assert "wsl.exe" not in text
        assert "wslpath" not in text
        assert "\r" not in text
    mcp_json = (ROOT / "mcp.json").read_text(encoding="utf-8")
    hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    assert "wsl" not in mcp_json.lower()
    assert json.loads(mcp_json)["mcpServers"]["rhinodiet"]["command"] == "./hooks/mcp.cmd"
    assert hooks["hooks"]["sessionStart"][0]["command"] == "./hooks/session_start.cmd"
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    install = readme.split("## Install", 1)[1].split("## Run", 1)[0]
    assert "through WSL" not in install
    assert "hooks/mcp.py" in install
    assert "py -3" in install


def test_linux_mcp_cmd_runs_the_python_script(tmp_path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    out = tmp_path / "out"
    fake = bindir / "python3"
    fake.write_text(
        "#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$OUT\"\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{bindir}{os.pathsep}{env.get('PATH', '')}"
    env["OUT"] = str(out)
    env.pop("PYTHONPATH", None)
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
    assert out.read_text(encoding="utf-8").splitlines() == [str(ROOT / "hooks" / "mcp.py")]


def test_linux_mcp_sh_runs_the_same_script(tmp_path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    out = tmp_path / "out"
    fake = bindir / "python3"
    fake.write_text(
        "#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$OUT\"\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{bindir}{os.pathsep}{env.get('PATH', '')}"
    env["OUT"] = str(out)
    proc = subprocess.run(
        [str(ROOT / "hooks" / "mcp.sh")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert out.read_text(encoding="utf-8").splitlines() == [str(ROOT / "hooks" / "mcp.py")]


def test_mcp_py_adds_src_and_serves(tmp_path):
    text = (ROOT / "hooks" / "mcp.py").read_text(encoding="utf-8")
    assert "sys.path.insert" in text
    assert 'ROOT / "src"' in text
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("RHINODIET_ROOT", None)
    env["RHINODIET_PROJECT"] = str(tmp_path)
    proc = subprocess.run(
        [sys.executable, str(ROOT / "hooks" / "mcp.py")],
        input=(
            '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}\n'
            '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":'
            '{"name":"rhinodiet_prepare","arguments":{"request":"document the token gate"}}}\n'
        ),
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    lines = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
    assert lines[0]["result"]["serverInfo"]["name"] == "rhinodiet"
    payload = json.loads(lines[1]["result"]["content"][0]["text"])
    assert payload["assignments"][0]["agent"] == "docs"


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
