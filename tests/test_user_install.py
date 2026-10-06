"""The user install is one pasted command."""

import json
import os
import subprocess
import zipfile

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
        assert "3  Codex" in text
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
    assert proc.stdout.splitlines()[0] == "Restart Codex."


def test_host_manifests_are_in_the_repo():
    claude = (ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    codex = (ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    assert '"name": "rhinodiet"' in claude
    assert '"./mcp.json"' in claude
    assert '"name": "rhinodiet"' in codex
    assert '"./skills/"' in codex
