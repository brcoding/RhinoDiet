"""The user install is one pasted command."""

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
        assert "Reload Cursor." in text


def test_install_sh_unpacks_into_the_cursor_folder(tmp_path):
    zip_path = tmp_path / "rhinodiet.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("RhinoDiet-main/keep.txt", "yes")
        archive.writestr("RhinoDiet-main/hooks/mcp.py", "print('mcp')\n")
    home = tmp_path / "home"
    env = os.environ.copy()
    env["RHINODIET_HOME"] = str(home)
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
