"""Godot worker. Short graph refs, shared export preset, no second server."""

from __future__ import annotations

import re
from pathlib import Path

from rhinodiet.devtest import write_preset
from rhinodiet.graph import GraphStore

ENGINE_FALLBACK = "Godot 4"
CONVENTIONS = "GDScript, scenes, signals, input map, one main scene."
PIPELINE = "Web preset and headless export stay on scripts/release.sh dev-test."

CHECKLIST = (
    ("scene-ownership", "Each scene has one owner script."),
    ("signals", "Scenes connect through signals."),
    ("input-map", "Player input uses the input map."),
    ("main-scene", "project.godot lists one main scene."),
    ("export-preset", "Web export preset is present."),
)

_VERSION = re.compile(r'PackedStringArray\("(\d+\.\d+)')


def read_engine(root: Path) -> str:
    for path in (root / "benchmarks" / "godot-pacman" / "project.godot", root / "project.godot"):
        if not path.is_file():
            continue
        match = _VERSION.search(path.read_text(encoding="utf-8"))
        if match:
            return f"Godot {match.group(1)}"
        return ENGINE_FALLBACK
    return ENGINE_FALLBACK


def find_godot_project(root: Path) -> Path | None:
    for path in (root / "benchmarks" / "godot-pacman", root):
        if (path / "project.godot").is_file():
            return path
    return None


class GodotService:
    def __init__(self, graph: GraphStore):
        self.graph = graph

    def ensure_refs(self, root: Path) -> None:
        self._upsert("godot", "engine", read_engine(root), salience=0.8)
        self._upsert("godot", "conventions", CONVENTIONS, salience=0.75)
        for name, summary in CHECKLIST:
            self._upsert("godot-check", name, summary, salience=0.6)

    def checklist_lines(self) -> list[str]:
        lines = []
        for name, summary in CHECKLIST:
            node = self._find("godot-check", name)
            lines.append(node.summary if node is not None else summary)
        return lines

    def prepare_pipeline(self, root: Path) -> str:
        project = find_godot_project(root)
        if project is not None:
            write_preset(project, root / "build" / "dev-test" / "index.html")
        self._upsert("godot", "pipeline", PIPELINE, salience=0.7)
        return "Prepared the Web export preset. Serve stays on scripts/release.sh dev-test."

    def place_art(self, path: str) -> str:
        summary = f"Place art at {Path(path).name}."
        self._upsert("godot", "art", summary, salience=0.6)
        return summary

    def _find(self, label: str, name: str):
        for node in self.graph.by_label(label):
            if node.name == name:
                return node
        return None

    def _upsert(self, label: str, name: str, summary: str, salience: float) -> None:
        node = self._find(label, name)
        if node is None:
            self.graph.add_node(
                label=label,
                name=name,
                horizon="long",
                salience=salience,
                summary=summary,
                body="",
            )
            return
        if node.summary != summary:
            self.graph.update_summary(node.id, summary, salience=salience)
