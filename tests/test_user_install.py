"""The user install is one pasted command."""

import json
import os
import subprocess
import zipfile
from pathlib import Path

from support import ROOT

WIN = "irm https://raw.githubusercontent.com/brcoding/RhinoDiet/main/install.ps1 | iex"
UNIX = "curl -fsSL https://raw.githubusercontent.com/brcoding/RhinoDiet/main/install.sh | sh"
ZIP_URL = "https://github.com/brcoding/RhinoDiet/archive/refs/heads/main.zip"


def test_readme_leads_with_one_command():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    lead = readme.split("## Install", 1)[0]
    assert WIN in lead
    assert UNIX in lead
    assert "cursor.directory" not in readme
    assert "git clone" not in lead
    assert "install.py" not in lead
    for name in ("install.sh", "install.ps1"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert ZIP_URL in text
        assert "wsl.exe" not in text
        assert "wslpath" not in text
        assert "cursor.directory" not in text
        assert "Install RhinoDiet for:" in text
        assert "1  Cursor" in text
        assert "2  Claude" in text
        assert "3  ChatGPT" in text
        assert "4  All" in text
        assert "Reload Cursor." in text


def test_install_sh_unpacks_into_the_cursor_folder(tmp_path):
    zip_path = tmp_path / "rhinodiet.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("RhinoDiet-main/keep.txt", "yes")
        archive.writestr("RhinoDiet-main/hooks/mcp.py", "print('mcp')\n")
    home = tmp_path / "home"
    env = os.environ.copy()
    env["RHINODIET_HOME"] = str(home)
    env["RHINODIET_HOST"] = "cursor"
    env["RHINODIET_ZIP_URL"] = zip_path.as_uri()
    proc = subprocess.run(
        ["sh", str(ROOT / "install.sh")],
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    dest = home / ".cursor" / "plugins" / "local" / "rhinodiet"
    assert (dest / "keep.txt").read_text(encoding="utf-8") == "yes"
    assert (dest / "hooks" / "mcp.py").is_file()
    assert proc.stdout.splitlines() == ["Reload Cursor.", "Type /rhinodiet."]

    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("RhinoDiet-main/keep.txt", "next")
    again = subprocess.run(
        ["sh", str(ROOT / "install.sh")],
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert again.returncode == 0, again.stderr
    assert (dest / "keep.txt").read_text(encoding="utf-8") == "next"
    assert not (dest / "hooks").exists()


def _zip(path, hooks=False):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("RhinoDiet-main/keep.txt", "yes")
        if hooks:
            archive.writestr("RhinoDiet-main/hooks/hooks.json", "{}\n")


def _run(home, zip_path, host):
    env = os.environ.copy()
    env["RHINODIET_HOME"] = str(home)
    env["RHINODIET_HOST"] = host
    env["RHINODIET_ZIP_URL"] = zip_path.as_uri()
    return subprocess.run(
        ["sh", str(ROOT / "install.sh")],
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )


def test_install_sh_places_claude_without_cursor_hooks(tmp_path):
    zip_path = tmp_path / "rhinodiet.zip"
    _zip(zip_path, hooks=True)
    home = tmp_path / "home"
    proc = _run(home, zip_path, "claude")
    assert proc.returncode == 0, proc.stderr
    dest = home / ".claude" / "skills" / "rhinodiet"
    assert (dest / "keep.txt").is_file()
    assert (dest / "hooks" / "cursor-hooks.json").is_file()
    assert not (dest / "hooks" / "hooks.json").exists()
    assert proc.stdout.splitlines()[0] == "Restart Claude Code."


def test_install_sh_registers_a_codex_marketplace_entry(tmp_path):
    zip_path = tmp_path / "rhinodiet.zip"
    _zip(zip_path, hooks=True)
    home = tmp_path / "home"
    market = home / ".agents" / "plugins" / "marketplace.json"
    market.parent.mkdir(parents=True)
    market.write_text(
        '{"name":"personal","plugins":[{"name":"other","source":{"source":"local","path":"./other"}}]}\n',
        encoding="utf-8",
    )
    proc = _run(home, zip_path, "codex")
    assert proc.returncode == 0, proc.stderr
    dest = home / ".codex" / "plugins" / "rhinodiet"
    assert (dest / "keep.txt").is_file()
    assert not (dest / "hooks" / "hooks.json").exists()
    data = json.loads(market.read_text(encoding="utf-8"))
    names = [item["name"] for item in data["plugins"]]
    assert names == ["other", "rhinodiet"]
    rhinodiet = data["plugins"][1]
    assert rhinodiet["source"]["path"] == "./.codex/plugins/rhinodiet"
    assert proc.stdout.splitlines() == [
        "Restart ChatGPT.",
        "In ChatGPT, type @rhinodiet.",
    ]
    config = (home / ".codex" / "config.toml").read_text(encoding="utf-8")
    assert '[plugins."rhinodiet@personal"]' in config
    assert "enabled = true" in config
    cache = home / ".codex" / "plugins" / "cache" / "personal" / "rhinodiet" / "local"
    assert (cache / "keep.txt").is_file()


def test_install_sh_can_place_all_three(tmp_path):
    zip_path = tmp_path / "rhinodiet.zip"
    _zip(zip_path, hooks=True)
    home = tmp_path / "home"
    proc = _run(home, zip_path, "all")
    assert proc.returncode == 0, proc.stderr
    cursor = home / ".cursor" / "plugins" / "local" / "rhinodiet"
    claude = home / ".claude" / "skills" / "rhinodiet"
    codex = home / ".codex" / "plugins" / "rhinodiet"
    assert (cursor / "hooks" / "hooks.json").is_file()
    assert (claude / "hooks" / "cursor-hooks.json").is_file()
    assert not (claude / "hooks" / "hooks.json").exists()
    assert (codex / "keep.txt").is_file()
    market = home / ".agents" / "plugins" / "marketplace.json"
    data = json.loads(market.read_text(encoding="utf-8"))
    assert data["plugins"][0]["name"] == "rhinodiet"
    assert proc.stdout.splitlines() == [
        "Reload Cursor.",
        "Restart Claude Code.",
        "Restart ChatGPT.",
        "Type /rhinodiet.",
        "In ChatGPT, type @rhinodiet.",
    ]


def test_install_sh_update_refreshes_only_installed_hosts(tmp_path):
    zip_path = tmp_path / "rhinodiet.zip"
    _zip(zip_path, hooks=True)
    home = tmp_path / "home"
    first = _run(home, zip_path, "cursor")
    assert first.returncode == 0, first.stderr
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("RhinoDiet-main/keep.txt", "next")
        archive.writestr("RhinoDiet-main/hooks/hooks.json", "{}\n")
    env = os.environ.copy()
    env["RHINODIET_HOME"] = str(home)
    env["RHINODIET_ZIP_URL"] = zip_path.as_uri()
    env.pop("RHINODIET_HOST", None)
    proc = subprocess.run(
        ["sh", str(ROOT / "install.sh"), "update"],
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    cursor = home / ".cursor" / "plugins" / "local" / "rhinodiet"
    assert (cursor / "keep.txt").read_text(encoding="utf-8") == "next"
    assert (cursor / "hooks" / "hooks.json").is_file()
    assert not (home / ".claude" / "skills" / "rhinodiet").exists()
    assert not (home / ".codex" / "plugins" / "rhinodiet").exists()
    assert proc.stdout.splitlines() == [
        "Updated from GitHub.",
        "Reload Cursor.",
        "Type /rhinodiet.",
    ]


def test_install_sh_upgrade_installs_all_when_nothing_is_present(tmp_path):
    zip_path = tmp_path / "rhinodiet.zip"
    _zip(zip_path, hooks=True)
    home = tmp_path / "home"
    script = (ROOT / "install.sh").read_text(encoding="utf-8")
    env = os.environ.copy()
    env["RHINODIET_HOME"] = str(home)
    env["RHINODIET_ZIP_URL"] = zip_path.as_uri()
    env.pop("RHINODIET_HOST", None)
    proc = subprocess.run(
        ["sh", "-s", "upgrade"],
        input=script,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert (home / ".cursor" / "plugins" / "local" / "rhinodiet" / "hooks" / "hooks.json").is_file()
    assert (home / ".claude" / "skills" / "rhinodiet" / "hooks" / "cursor-hooks.json").is_file()
    assert (home / ".codex" / "plugins" / "rhinodiet" / "keep.txt").is_file()
    assert proc.stdout.splitlines() == [
        "Updated from GitHub.",
        "Reload Cursor.",
        "Restart Claude Code.",
        "Restart ChatGPT.",
        "Type /rhinodiet.",
        "In ChatGPT, type @rhinodiet.",
    ]


def test_cli_update_and_upgrade_call_install_sh(monkeypatch):
    from rhinodiet.cli import main

    calls = []

    def fake_run(cmd, env, check):
        calls.append((cmd, env.get("RHINODIET_HOST"), check))

        class Done:
            returncode = 0

        return Done()

    monkeypatch.setattr("rhinodiet.cli.subprocess.run", fake_run)
    assert main(["update"]) == 0
    assert main(["upgrade"]) == 0
    assert len(calls) == 2
    for cmd, host, check in calls:
        assert cmd[0] == "sh"
        assert cmd[1].endswith("install.sh")
        assert Path(cmd[1]).is_file()
        assert host == "update"
        assert check is False


def test_install_sh_copies_the_chatgpt_skill(tmp_path):
    zip_path = tmp_path / "rhinodiet.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("RhinoDiet-main/skills/rhinodiet/SKILL.md", "---\nname: rhinodiet\n---\n")
        archive.writestr("RhinoDiet-main/hooks/hooks.json", "{}\n")
    home = tmp_path / "home"
    proc = _run(home, zip_path, "chatgpt")
    assert proc.returncode == 0, proc.stderr
    skill = home / ".agents" / "skills" / "rhinodiet" / "SKILL.md"
    assert "name: rhinodiet" in skill.read_text(encoding="utf-8")
    assert not (home / ".codex" / "plugins" / "rhinodiet" / "hooks" / "hooks.json").exists()
    assert (home / ".codex" / "plugins" / "cache" / "personal" / "rhinodiet" / "local" / "skills" / "rhinodiet" / "SKILL.md").is_file()


def test_host_manifests_are_in_the_repo():
    claude = (ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    codex = (ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    assert '"name": "rhinodiet"' in claude
    assert '"./mcp.json"' in claude
    assert '"name": "rhinodiet"' in codex
    assert '"./skills/"' in codex
