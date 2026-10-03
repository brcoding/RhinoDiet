import json
import os
import subprocess
import sys

from rhinodiet.graph import GraphStore
from rhinodiet.mcp_server import handle

from support import ROOT


def test_mcp_lists_tools_and_prepares_docs(tmp_path, monkeypatch):
    monkeypatch.setenv("RHINODIET_PROJECT", str(tmp_path))
    monkeypatch.setenv("RHINODIET_ROOT", str(ROOT))
    init = handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert init["result"]["serverInfo"]["name"] == "rhinodiet"
    listed = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = {tool["name"] for tool in listed["result"]["tools"]}
    assert "rhinodiet_run" in names
    assert "rhinodiet_cite" in names
    assert "rhinodiet_docs" in names
    assert "rhinodiet_prepare" in names
    note = handle({"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert note is None
    prepared = handle(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "rhinodiet_prepare",
                "arguments": {"request": "document the API for UserToken"},
            },
        }
    )
    payload = json.loads(prepared["result"]["content"][0]["text"])
    assert payload["assignments"][0]["agent"] == "docs"
    assert payload["assignments"][0]["model"] == "composer-2.5[fast=true]"


def test_session_hook_cites_refs_not_blobs(tmp_path):
    db = tmp_path / ".rhinodiet" / "memory.db"
    graph = GraphStore(db)
    graph.add_node(
        label="task",
        name="tokens",
        summary="keep tokens",
        body="BLOB_FULL_HISTORY_SHOULD_NOT_LEAK",
        salience=0.8,
    )
    graph.close()
    env = os.environ.copy()
    env["CURSOR_PROJECT_DIR"] = str(tmp_path)
    env["RHINODIET_ROOT"] = str(ROOT)
    proc = subprocess.run(
        [sys.executable, str(ROOT / "hooks" / "session_start.py")],
        input=b"{}",
        capture_output=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert "keep tokens" in payload["additional_context"]
    assert "BLOB_FULL_HISTORY_SHOULD_NOT_LEAK" not in payload["additional_context"]


def test_repo_prose_has_no_em_dash_or_markdown_semicolons():
    skip = {".git", "agent-tools", ".pytest_cache", ".venv", "__pycache__", ".rhinodiet"}
    bad_dash = []
    bad_semi = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in skip for part in path.parts):
            continue
        if path.suffix not in {".py", ".md", ".mdc", ".json", ".sh", ".toml"}:
            continue
        text = path.read_text(encoding="utf-8")
        if "\u2014" in text or "\u2013" in text:
            bad_dash.append(str(path.relative_to(ROOT)))
        if path.suffix in {".md", ".mdc"} and ";" in text:
            bad_semi.append(str(path.relative_to(ROOT)))
    assert bad_dash == []
    assert bad_semi == []
