"""Token comparison for the Pac-Man task, plus a maze sanity check."""

import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))

import token_compare


def test_comparison_cuts_tokens_and_keeps_facts():
    result = token_compare.compare()
    assert result["live_model"] is False
    assert result["tokenizer"] == "o200k_base"
    assert result["inter_agent_mode"] == "caveman"
    assert result["plugins_invoked"] == ["prepare", "compress", "cite", "supervisor", "docs"]
    assert result["agents"] == [["godot", "reviewer"], ["dev", "reviewer"], ["docs"]]
    assert result["caveman_modes"] == ["caveman", "caveman"]
    assert result["calls3"] == 0
    assert result["prepare"]["turn1_after"] < result["prepare"]["turn1_before"]
    assert result["prepare"]["turn1_agents"] == ["godot"]
    assert result["prepare"]["turn2_agents"] == ["dev"]
    assert result["prepare"]["turn3_agents"] == ["docs"]
    assert result["prepare"]["turn3_cites"] == 5
    assert result["with"]["total"] < result["without"]["total"]
    assert result["saved"]["total"] == result["without"]["total"] - result["with"]["total"]
    assert result["reduction_pct"] > 20
    later = result["later_turn"]
    assert later["with_input"] < later["without_input"]
    assert later["input_reduction_pct"] > 40
    assert token_compare.BLOB_IMPORT not in later["plugin_input"]
    assert token_compare.BLOB_REVIEW not in later["plugin_input"]
    assert token_compare.BLOB_IMPORT in later["baseline_input"]
    assert token_compare.BLOB_REVIEW in later["baseline_input"]
    assert result["fidelity"]["missing"] == []
    for fact in token_compare.FACTS:
        assert fact in result["fidelity"]["turn1_worker"]
        assert fact in result["fidelity"]["later_cites"]
    worker = result["fidelity"]["turn1_worker"].lower()
    assert "in order to" not in worker
    assert "it is important to note that" not in worker
    assert result["memory"]["bodies_in_cites"] is False
    assert result["memory"]["max_summary_len"] <= 160
    assert result["docs"]["after_tokens_tiktoken"] < result["docs"]["before_tokens_tiktoken"]
    assert "gpt-4o" == result["price_illustration"]["model"]
    assert result["price_illustration"]["as_of"] == "2 Oct 2026"


def test_readme_matches_the_measured_table():
    block = token_compare.readme_section(token_compare.compare())
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert block in readme
    assert "\u2014" not in block
    assert "\u2013" not in block
    assert ";" not in block
    assert "o200k_base" in block
    assert "python benchmarks/token_compare.py" in block


def test_maze_is_19_by_21_and_reachable():
    rows = token_compare.maze_rows()
    assert len(rows) == 21
    assert all(len(row) == 19 for row in rows)
    walls = set()
    start = None
    ghosts = []
    pellets = []
    for y, row in enumerate(rows):
        assert row[0] == "#" and row[-1] == "#"
        for x, ch in enumerate(row):
            if ch == "#":
                walls.add((x, y))
            elif ch == "P":
                start = (x, y)
            elif ch == "G":
                ghosts.append((x, y))
            elif ch == ".":
                pellets.append((x, y))
            else:
                raise AssertionError(ch)
    assert rows[0] == "#" * 19
    assert rows[-1] == "#" * 19
    assert start is not None
    assert len(ghosts) == 2
    assert len(pellets) > 20
    seen = {start}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for nxt in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if nxt in seen or nxt in walls:
                continue
            if 0 <= nxt[0] < 19 and 0 <= nxt[1] < 21:
                seen.add(nxt)
                queue.append(nxt)
    assert all(pellet in seen for pellet in pellets)
    assert all(ghost in seen for ghost in ghosts)
    root = ROOT / "benchmarks/godot-pacman"
    project = (root / "project.godot").read_text(encoding="utf-8")
    assert "config_version=5" in project
    assert 'run/main_scene="res://scenes/main.tscn"' in project
    assert (root / "scenes/main.tscn").is_file()
    for name in ("main.gd", "player.gd", "ghost.gd", "maze.gd", "hud.gd"):
        assert (root / "scripts" / name).is_file()
