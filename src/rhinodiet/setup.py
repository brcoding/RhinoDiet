"""Create the venv, install the package, and copy the plugin into Cursor."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

DONE = "Reload Cursor.\nRun /rhinodiet.\n"
_SKIP = {".venv", ".git", "__pycache__", ".pytest_cache"}


def on_windows_drive(path: Path) -> bool:
    absolute = path if path.is_absolute() else Path.cwd() / path
    parts = absolute.parts
    return (
        len(parts) >= 3
        and parts[0] == "/"
        and parts[1] == "mnt"
        and len(parts[2]) == 1
        and parts[2].isalpha()
    )


def venv_path(project: Path, home: Path | None = None) -> Path:
    root = home or Path.home()
    if on_windows_drive(project):
        return root / ".venv" / "rhinodiet"
    return project / ".venv"


def on_wsl() -> bool:
    if os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSL_INTEROP"):
        return True
    try:
        text = Path("/proc/version").read_text(encoding="utf-8", errors="replace").lower()
    except OSError:
        return False
    return "microsoft" in text or "wsl" in text


def windows_profile(run=None) -> Path | None:
    run = run or subprocess.run
    try:
        echoed = run(
            ["cmd.exe", "/c", "echo %USERPROFILE%"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    raw = (echoed.stdout or "").strip().strip('"')
    if echoed.returncode != 0 or not raw or "%" in raw:
        return None
    try:
        converted = run(
            ["wslpath", "-u", raw],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    folder = (converted.stdout or "").strip()
    if converted.returncode != 0 or not folder.startswith("/"):
        return None
    return Path(folder)


def plugin_dest(profile: Path) -> Path:
    return profile / ".cursor" / "plugins" / "local" / "rhinodiet"


def _ignore(_directory: str, names: list[str]) -> list[str]:
    return [name for name in names if name in _SKIP]


def copy_plugin(project: Path, dest: Path) -> None:
    if dest.is_symlink():
        dest.unlink()
    elif dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(project, dest, symlinks=False, ignore=_ignore)
    if dest.is_symlink():
        raise RuntimeError("Plugin copy is still a symlink.")


def create_venv(project: Path, venv: Path, run=None) -> None:
    run = run or subprocess.run
    run(
        [sys.executable, "-m", "venv", str(venv)],
        check=True,
        capture_output=True,
        text=True,
    )
    pip = venv / "bin" / "pip"
    if not pip.is_file():
        pip = venv / "Scripts" / "pip.exe"
    run(
        [str(pip), "install", "-e", ".[dev]"],
        cwd=str(project),
        check=True,
        capture_output=True,
        text=True,
    )


def cursor_user_dir(
    *,
    home: Path | None = None,
    wsl: bool | None = None,
    profile: Path | None = None,
    host: str | None = None,
    run=None,
) -> Path:
    use_wsl = on_wsl() if wsl is None else wsl
    if use_wsl:
        found = profile if profile is not None else windows_profile(run)
        if found is None:
            raise RuntimeError("Could not find the Windows user profile.")
        return found
    if (host or sys.platform) == "win32":
        raw = os.environ.get("USERPROFILE", "").strip().strip('"')
        if not raw or "%" in raw:
            raise RuntimeError("Could not find the Windows user profile.")
        return Path(raw)
    return home or Path.home()


def setup(
    project: Path,
    *,
    home: Path | None = None,
    wsl: bool | None = None,
    profile: Path | None = None,
    host: str | None = None,
    run=None,
) -> str:
    project = project.resolve()
    dest = plugin_dest(
        cursor_user_dir(home=home, wsl=wsl, profile=profile, host=host, run=run)
    )
    copy_plugin(project, dest)
    create_venv(project, venv_path(project, home), run=run)
    return f"Copied the plugin to {dest}.\n{DONE}"
