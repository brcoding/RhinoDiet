"""Model tiers and runtime settings. Workers default to the cheaper tier."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

WORKER_AGENTS = ("dev", "reviewer", "creative", "release", "docs")


@dataclass(frozen=True)
class Config:
    supervisor_model: str
    worker_model: str
    agent_tiers: dict[str, str]
    compact_after_nodes: int
    input_mode: str
    inter_agent_mode: str
    user_visible_mode: str
    max_review_rounds: int
    memory_path: str

    def model_for(self, agent: str) -> str:
        tier = self.agent_tiers.get(agent, "worker")
        if tier == "supervisor":
            return self.supervisor_model
        return self.worker_model


def plugin_root() -> Path:
    for key in ("RHINODIET_ROOT", "CURSOR_PLUGIN_ROOT"):
        value = os.environ.get(key)
        if value:
            return Path(value)
    here = Path(__file__).resolve()
    candidate = here.parents[2]
    if (candidate / "rhinodiet.config.json").exists():
        return candidate
    cwd = Path.cwd()
    for path in (cwd, *cwd.parents):
        if (path / "rhinodiet.config.json").exists():
            return path
    return cwd


def project_dir() -> Path:
    for key in ("RHINODIET_PROJECT", "CURSOR_PROJECT_DIR"):
        value = os.environ.get(key)
        if value:
            return Path(value)
    return Path.cwd()


def load_config(path: Path | None = None) -> Config:
    config_path = path or (plugin_root() / "rhinodiet.config.json")
    data = json.loads(config_path.read_text(encoding="utf-8"))
    tiers = data["tiers"]
    memory = data["memory"]
    compression = data["compression"]
    review = data["review"]
    return Config(
        supervisor_model=tiers["supervisor"]["model"],
        worker_model=tiers["worker"]["model"],
        agent_tiers=dict(data["agents"]),
        compact_after_nodes=int(memory["compact_after_nodes"]),
        input_mode=compression["input"],
        inter_agent_mode=compression["inter_agent"],
        user_visible_mode=compression["user_visible"],
        max_review_rounds=int(review["max_rounds"]),
        memory_path=memory["path"],
    )


def resolve_memory_path(config: Config, project: Path | None = None) -> Path:
    raw = Path(config.memory_path)
    if raw.is_absolute():
        return raw
    return (project or project_dir()) / raw
