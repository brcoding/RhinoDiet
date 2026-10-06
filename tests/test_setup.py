"""rhinodiet init copies the plugin into Cursor and creates the venv."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

from rhinodiet.cli import main
from rhinodiet.setup import DONE, on_windows_drive, plugin_dest, setup, venv_path, windows_profile

from support import ROOT


class _Done:
    def __init__(self, stdout="", code=0):
        self.returncode = code
        self.stdout = stdout
        self.stderr = ""


def _run_ok(calls):
    def run(cmd, **_kwargs):
        calls.append(list(cmd))
        return _Done()

    return run


def test_windows_drive_venv_lives_in_the_home_directory(tmp_path):
    home = tmp_path / "home"
    assert on_windows_drive(Path("/mnt/p/RhinoDiet"))
    assert on_windows_drive(Path("/mnt/C/work"))
    assert not on_windows_drive(tmp_path / "proj")
    assert not on_windows_drive(Path("/mnt/windows/proj"))
    assert venv_path(Path("/mnt/p/RhinoDiet"), home) == home / ".venv" / "rhinodiet"
    assert venv_path(tmp_path / "proj", home) == tmp_path / "proj" / ".venv"


def test_setup_installs_dev_extra_and_copies_a_real_directory(tmp_path):
    project = tmp_path / "proj"
    (project / "src").mkdir(parents=True)
    (project / "keep.txt").write_text("yes", encoding="utf-8")
    (project / ".venv").mkdir()
    (project / ".venv" / "skip.txt").write_text("no", encoding="utf-8")
    (project / "link.txt").symlink_to(project / "keep.txt")
    home = tmp_path / "home"
    profile = tmp_path / "winhome"
    dest = plugin_dest(profile)
    dest.parent.mkdir(parents=True)
    dest.symlink_to(project)
    calls = []

    text = setup(project, home=home, wsl=True, profile=profile, run=_run_ok(calls))

    assert text == f"Copied the plugin to {dest}.\n{DONE}"
    assert calls[0][:3] == [sys.executable, "-m", "venv"]
    assert calls[0][-1] == str(project.resolve() / ".venv")
    assert calls[1][-3:] == ["install", "-e", ".[dev]"]
    assert dest.is_dir()
    assert not dest.is_symlink()
    assert (dest / "keep.txt").read_text(encoding="utf-8") == "yes"
    assert (dest / "link.txt").is_file()
    assert not (dest / "link.txt").is_symlink()
    assert not (dest / ".venv").exists()


def test_windows_profile_comes_from_cmd_and_wslpath():
    calls = []

    def run(cmd, **_kwargs):
        calls.append(list(cmd))
        if cmd[0] == "cmd.exe":
            return _Done(stdout=r"C:\Users\someone")
        return _Done(stdout="/mnt/c/Users/someone")

    assert windows_profile(run) == Path("/mnt/c/Users/someone")
    assert calls == [
        ["cmd.exe", "/c", "echo %USERPROFILE%"],
        ["wslpath", "-u", r"C:\Users\someone"],
    ]


def test_unexpanded_profile_is_rejected():
    def run(cmd, **_kwargs):
        return _Done(stdout="%USERPROFILE%")

    assert windows_profile(run) is None


def test_wsl_without_a_profile_fails(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    with pytest.raises(RuntimeError, match="Windows user profile"):
        setup(project, wsl=True, run=_run_ok([]))


def test_linux_copies_into_the_home_cursor_folder(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "keep.txt").write_text("yes", encoding="utf-8")
    home = tmp_path / "home"
    calls = []

    text = setup(project, home=home, wsl=False, host="linux", run=_run_ok(calls))

    dest = plugin_dest(home)
    assert text == f"Copied the plugin to {dest}.\n{DONE}"
    assert (dest / "keep.txt").read_text(encoding="utf-8") == "yes"
    assert calls[0][-1] == str(project.resolve() / ".venv")
    assert all("wslpath" not in " ".join(cmd) for cmd in calls)


def test_native_windows_copies_into_the_user_profile(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "keep.txt").write_text("yes", encoding="utf-8")
    profile = tmp_path / "Users" / "ada"
    monkeypatch.setenv("USERPROFILE", str(profile))
    calls = []

    setup(project, home=tmp_path / "ignored", wsl=False, host="win32", run=_run_ok(calls))

    dest = plugin_dest(profile)
    assert (dest / "keep.txt").read_text(encoding="utf-8") == "yes"
    assert all("wslpath" not in " ".join(cmd) for cmd in calls)


def test_plugin_copy_survives_a_venv_failure(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "keep.txt").write_text("yes", encoding="utf-8")
    home = tmp_path / "home"

    def run(cmd, **_kwargs):
        raise subprocess.CalledProcessError(1, cmd, stderr="pip failed")

    with pytest.raises(subprocess.CalledProcessError):
        setup(project, home=home, wsl=False, host="linux", run=run)

    assert (plugin_dest(home) / "keep.txt").read_text(encoding="utf-8") == "yes"


def test_install_script_calls_setup(monkeypatch, capsys):
    spec = importlib.util.spec_from_file_location("rhinodiet_install", ROOT / "install.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "setup", lambda project: DONE)
    assert module.main() == 0
    assert capsys.readouterr().out == DONE


def test_init_prints_the_reload_lines(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr("rhinodiet.config.project_dir", lambda: tmp_path)
    monkeypatch.setattr("rhinodiet.setup.setup", lambda _project: DONE)
    assert main(["init"]) == 0
    assert capsys.readouterr().out == DONE
