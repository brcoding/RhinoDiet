import inspect
import json

import rhinodiet.godot as godot_mod
from rhinodiet.godot import CHECKLIST, read_engine
from rhinodiet.supervisor import wants_dev, wants_godot

from support import boot


def test_godot_code_skips_the_generic_dev_worker(tmp_path):
    calls = []

    class Model:
        def complete(self, agent, model, system, user):
            calls.append({"agent": agent, "model": model, "user": user})
            if agent == "reviewer":
                return json.dumps({"accept": True, "findings": []})
            return json.dumps(
                {
                    "summary": "Added scripts/player.gd.",
                    "code_changed": True,
                    "files": ["scripts/player.gd"],
                    "tests": ["Checked the input map."],
                }
            )

    supervisor, graph = boot(tmp_path, Model())
    report = supervisor.run("add a GDScript player in scripts/player.gd")
    assert report.agents == ["godot", "reviewer"]
    assert calls[0]["agent"] == "godot"
    assert calls[0]["model"] == "composer-2.5[fast=true]"
    assert calls[1]["agent"] == "reviewer"
    checklist = calls[1]["user"]
    for _name, summary in CHECKLIST:
        assert summary in checklist
    assert "dev" not in report.agents
    for node in graph.by_label("godot") + graph.by_label("godot-check"):
        assert node.body == ""
        assert len(node.summary) <= 160
    assert read_engine(tmp_path) == "Godot 4"
    engine = next(node for node in graph.by_label("godot") if node.name == "engine")
    assert engine.summary == "Godot 4"


def test_project_version_is_a_short_ref_and_preset_is_shared(tmp_path):
    project = tmp_path / "project.godot"
    project.write_text('config/features=PackedStringArray("4.3", "GL Compatibility")\n', encoding="utf-8")
    supervisor, graph = boot(tmp_path)
    report = supervisor.run("prepare the Godot export preset and the headless boot")
    assert report.agents == ["godot"]
    assert "dev" not in report.agents
    assert "release" not in report.agents
    engine = next(node for node in graph.by_label("godot") if node.name == "engine")
    assert engine.summary == "Godot 4.3"
    assert engine.body == ""
    preset = (tmp_path / "export_presets.cfg").read_text(encoding="utf-8")
    assert 'name="Web"' in preset
    assert "trycloudflare" not in report.reply
    source = inspect.getsource(godot_mod)
    assert "serve_directory" not in source
    assert "open_tunnel" not in source
    assert "cloudflared" not in source


def test_parser_stays_on_dev_and_docs_keep_script_names(tmp_path):
    supervisor, _graph = boot(tmp_path)
    code = supervisor.run("add a parser in src/app.py")
    assert code.agents == ["dev"]
    assert not wants_godot("add a parser in src/app.py")
    docs = supervisor.run("rewrite this paragraph about scripts/player.gd")
    assert docs.agents == ["docs"]
    assert wants_dev("add a GDScript player")
    assert wants_godot("add a GDScript player")


def test_godot_places_creative_art_and_release_still_serves(tmp_path):
    supervisor, graph = boot(tmp_path)
    report = supervisor.run("draw a logo for the Godot project and serve the html export")
    assert report.agents == ["creative", "godot", "release"]
    art = next(node for node in graph.by_label("godot") if node.name == "art")
    assert art.summary == "Place art at mark.svg."
    assert art.body == ""
    assert "<svg" not in art.body
    script = (tmp_path / "scripts" / "release.sh").read_text(encoding="utf-8")
    assert "python -u -m rhinodiet.devtest" in script
    assert "cloudflared tunnel" not in script
