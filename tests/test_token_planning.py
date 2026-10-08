"""Token-cheap ownership routing for prepare assignments."""

from pathlib import Path

from rhinodiet.config import WORKER_AGENTS, load_config
from rhinodiet.supervisor import plan, wants_project_manager, wants_specialist


def test_worker_agents_include_ownership_roster():
    for name in (
        "project-manager",
        "ability",
        "assembly",
        "enemy",
        "environment",
        "player",
        "qa",
    ):
        assert name in WORKER_AGENTS
        assert load_config().agent_tiers[name] == "worker"


def test_plan_routes_project_manager_for_multi_domain():
    assert wants_project_manager("plan this multi-domain ownership change")
    assert plan("who owns scripts/combat and route a handoff") == ["project-manager"]


def test_plan_routes_single_domain_specialist():
    assert wants_specialist("fix the enemy pack chase radius") == "enemy"
    assert plan("fix the enemy pack chase radius") == ["enemy"]
    assert plan("update ability loadout cooldowns") == ["ability"]


def test_plan_sends_overlapping_domains_to_project_manager():
    assert wants_specialist("wire player progression into the ability loadout") == "project-manager"
    assert plan("wire player progression into the ability loadout") == ["project-manager"]


def test_plan_keeps_engine_work_on_godot():
    assert plan("add a GDScript player") == ["godot"]
    assert plan("write the Godot export preset and input map") == ["godot"]


def test_token_planning_rule_exists():
    root = Path(__file__).resolve().parents[1]
    text = (root / "rules" / "token-planning.mdc").read_text(encoding="utf-8")
    assert "Allowed paths" in text
    assert "full-repo scan" in text
    assert "\u2014" not in text
    for name in ("ability", "assembly", "enemy", "environment", "player", "qa", "project-manager"):
        assert (root / "agents" / f"{name}.md").is_file()
