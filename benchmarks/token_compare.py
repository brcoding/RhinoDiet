"""Token comparison for the Godot 4 Pac-Man task.

Same task, two conditions, three turns. Headline counts use tiktoken o200k_base.
The plugin counter is estimate_tokens. No live model call.

Without the plugin, each turn resends the spec, the file tree, and prior replies.
With RhinoDiet, the supervisor prepares the turn, caveman-compresses inter-agent
text, and later turns cite memory ids plus short labels.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import rhinodiet.graph as graph_mod
from rhinodiet.compress import compress
from rhinodiet.config import load_config
from rhinodiet.creative import CreativeService, LocalCreativeProvider
from rhinodiet.graph import GraphStore, format_cites
from rhinodiet.supervisor import Supervisor
from rhinodiet.tokens import estimate_tokens

# OpenAI GPT-4o standard list price, published 2 Oct 2026.
# https://developers.openai.com/api/docs/pricing
GPT4O_INPUT_PER_M = 2.50
GPT4O_OUTPUT_PER_M = 10.00
PRICE_AS_OF = "2 Oct 2026"

GODOT_NOTE = (
    "Godot 4.3 ran headless on benchmarks/godot-pacman. "
    "The main scene loaded, reported 201 pellets and 2 ghosts, and exited cleanly."
)

FACTS = (
    "19 columns by 21 rows",
    "arrow keys and WASD",
    "win when every pellet is eaten",
    "lose when a ghost touches the player",
    "scripts/player.gd",
    "scripts/ghost.gd",
    "scripts/maze.gd",
    "scripts/hud.gd",
    "scripts/main.gd",
)

RULES = (
    ("maze", "The maze must be 19 columns by 21 rows.", 0.95),
    ("controls", "The player must move with arrow keys and WASD.", 0.94),
    ("win", "The player must win when every pellet is eaten.", 0.93),
    ("lose", "The player must lose when a ghost touches the player.", 0.92),
    (
        "files",
        "Files must be scripts/player.gd, scripts/ghost.gd, scripts/maze.gd, scripts/hud.gd, and scripts/main.gd.",
        0.91,
    ),
)

BASE_SYSTEM = (
    "You are a Godot 4 game developer. Follow the spec. "
    "Keep the maze size, the controls, the win and lose rules, and the file names."
)

USER_1 = (
    "Please could you kindly just really build the playable clone in order to match the spec. "
    "It is important to note that this is a very simple scene at this point in time. "
    "The rules below must stay exact."
)

USER_2 = "Please fix the ghost step described in the notes below. Keep the cited rules."

USER_3 = "Rewrite this paragraph."

SPEC_BODY = """
Draw the maze with ColorRect walls and ColorRect pellets. Draw the player and the ghosts with Polygon2D. Use no downloaded art.

The player steps one cell at a time. A queued key applies on arrival at a cell. The player may reverse on an open cell. The player may not enter a wall.

Two ghosts chase on the grid. They prefer a step that shortens the distance to the player. They avoid reversing when another step is open. A hit is the same occupied cell, or a swap of cells during one step.

Each pellet scores 10 points. The hud shows the score. Press R to restart after a win or a loss.

Map legend. Hash is a wall. Dot is a pellet. P is the player start. G is a ghost start.
""".strip()

REVIEW = """
The ghost can stall on the G cell when every neighbor except the way it came is a wall. Leave that cell on the first step.

The score label sits on top of the first wall row. Place it in the top margin.

The lose check should run after the step, including a head-on swap where the player cell and the ghost cell trade places.

Restart belongs on the R key after the win state and after the lose state.

Editor cache id REVIEW_BLOB_7ab91 stays in the notes body.
""".strip()

PASSAGE = (
    "It is important to note that the pellet grid is stored by the maze module at this point in time. "
    "The score is updated by the hud. "
    "The pellet is removed by the player. "
    "Please note that the win check is really just performed by the main scene in order to stop play when every pellet is eaten. "
    "It should be noted that the overlap check is basically repeated by the main scene again when a ghost touches the player. "
    "The maze must stay 19 columns by 21 rows. "
    "The player must move with arrow keys and WASD. "
    "The player must lose when a ghost touches the player. "
    "The files must stay scripts/maze.gd, scripts/hud.gd, scripts/player.gd, scripts/ghost.gd, and scripts/main.gd."
)

FIXTURE_1 = (
    "It is important to note that the playable scene is in place at this point in time. "
    "Please note that the maze must be 19 columns by 21 rows. "
    "The player must move with arrow keys and WASD. "
    "The player must win when every pellet is eaten. "
    "The player must lose when a ghost touches the player. "
    "Files must be scripts/player.gd, scripts/ghost.gd, scripts/maze.gd, scripts/hud.gd, and scripts/main.gd. "
    "In order to keep movement simple, the actor steps one cell at a time."
)

FIXTURE_2 = (
    "Please note that the ghost now steps onto an open neighbor at this point in time. "
    "It is important to note that the score label sits in the top margin. "
    "The lose check covers a head-on swap. "
    "The maze must be 19 columns by 21 rows. "
    "The player must move with arrow keys and WASD. "
    "The player must win when every pellet is eaten. "
    "The player must lose when a ghost touches the player."
)

BLOB_IMPORT = "IMPORT_DUMP_9f3c2a"
BLOB_REVIEW = "REVIEW_BLOB_7ab91"


class _SeqId:
    def __init__(self, n: int):
        self.hex = f"{n:08d}" + ("0" * 24)


class RecordingModel:
    """Scripted worker. Records prompts. Does not call a live model."""

    def __init__(self):
        self.calls = []

    def complete(self, agent: str, model: str, system: str, user: str) -> str:
        self.calls.append(
            {"agent": agent, "model": model, "system": system, "user": user}
        )
        if agent == "reviewer":
            return json.dumps({"accept": True, "findings": []})
        if agent == "dev":
            return json.dumps(
                {
                    "summary": "Added the maze, the player, two ghosts, the score, and win and lose states.",
                    "code_changed": True,
                    "files": [
                        "scripts/player.gd",
                        "scripts/ghost.gd",
                        "scripts/maze.gd",
                        "scripts/hud.gd",
                        "scripts/main.gd",
                    ],
                    "tests": ["Checked 19 columns by 21 rows in scripts/maze.gd."],
                }
            )
        raise RuntimeError(f"unexpected agent {agent}")


def maze_rows() -> list[str]:
    text = (ROOT / "benchmarks/godot-pacman/scripts/maze.gd").read_text(encoding="utf-8")
    return [row for row in re.findall(r'"([#.PG]+)"', text) if len(row) == 19]


def build_spec(rows: list[str]) -> str:
    rules = "\n".join(rule for _label, rule, _salience in RULES)
    maze = "\n".join(rows)
    return f"{rules}\n\n{SPEC_BODY}\n\n{maze}"


def build_file_tree() -> str:
    lines = [
        "benchmarks/godot-pacman/project.godot",
        "benchmarks/godot-pacman/scenes/main.tscn",
        "benchmarks/godot-pacman/scripts/main.gd",
        "benchmarks/godot-pacman/scripts/player.gd",
        "benchmarks/godot-pacman/scripts/ghost.gd",
        "benchmarks/godot-pacman/scripts/maze.gd",
        "benchmarks/godot-pacman/scripts/hud.gd",
    ]
    for index in range(1, 25):
        lines.append(f"benchmarks/godot-pacman/.godot/imported/res{index:02d}.gd.remap")
    lines.append(f"editor-cache {BLOB_IMPORT}")
    return "\n".join(lines)


def _encoder():
    import tiktoken

    return tiktoken.get_encoding("o200k_base")


def _tally(enc, parts: list[str]) -> dict[str, int]:
    tik = 0
    plugin = 0
    for part in parts:
        tik += len(enc.encode(part, disallowed_special=()))
        plugin += estimate_tokens(part)
    return {"tiktoken": tik, "plugin": plugin}


def _dollars(inp: int, out: int) -> float:
    return (inp / 1_000_000) * GPT4O_INPUT_PER_M + (out / 1_000_000) * GPT4O_OUTPUT_PER_M


def _article_for_percent(pct: float) -> str:
    whole = int(pct)
    if whole in {8, 11, 18} or 80 <= whole <= 89:
        return "an"
    return "a"


def _pct(saved: int, base: int) -> float:
    if base <= 0:
        return 0.0
    return 100.0 * saved / base


def _boot(tmp: Path, model: RecordingModel):
    cfg = load_config(ROOT / "rhinodiet.config.json")
    graph = GraphStore(tmp / "memory.db", clock=lambda: 1_700_000_000.0)
    creative = CreativeService(graph, LocalCreativeProvider(), tmp / "art")
    supervisor = Supervisor(graph, cfg, model, tmp, creative=creative)
    return supervisor, graph


def _store_rules(graph: GraphStore, spec: str, tree: str) -> None:
    bodies = {
        "maze": spec,
        "controls": spec,
        "win": spec,
        "lose": spec,
        "files": tree,
    }
    for label, summary, salience in RULES:
        graph.add_node(
            label=label,
            name=label,
            horizon="long",
            salience=salience,
            summary=summary,
            body=bodies[label],
        )


def compare() -> dict:
    """Measure one deterministic run. Restores the id generator before returning."""
    enc = _encoder()
    saved = graph_mod.uuid.uuid4
    seq = {"n": 0}

    def uuid4():
        seq["n"] += 1
        return _SeqId(seq["n"])

    graph_mod.uuid.uuid4 = uuid4
    try:
        return _compare(enc)
    finally:
        graph_mod.uuid.uuid4 = saved


def _compare(enc) -> dict:
    rows = maze_rows()
    spec = build_spec(rows)
    tree = build_file_tree()
    docs_request = USER_3 + "\n\n" + PASSAGE
    with tempfile.TemporaryDirectory() as tmp_name:
        model = RecordingModel()
        supervisor, graph = _boot(Path(tmp_name), model)

        request1 = "\n\n".join([USER_1, spec, tree])
        prepared1 = supervisor.prepare(request1)
        report1 = supervisor.run(request1)
        calls1 = list(model.calls)
        _store_rules(graph, spec, tree)

        request2 = USER_2 + "\n\n" + REVIEW
        prepared2 = supervisor.prepare(request2)
        report2 = supervisor.run(request2)
        calls2 = list(model.calls[len(calls1) :])
        graph.add_node(
            label="review",
            name="ghost-step",
            horizon="short",
            salience=0.2,
            summary="Ghost speed note.",
            body=REVIEW,
        )

        prepared3 = supervisor.prepare(docs_request)
        report3 = supervisor.run(docs_request)
        calls3 = list(model.calls[len(calls1) + len(calls2) :])
        cite_text = format_cites(report3.cites)

        out1 = compress(FIXTURE_1, "caveman")
        out2 = compress(FIXTURE_2, "caveman")

        base1 = [BASE_SYSTEM, USER_1, spec, tree]
        base2 = base1 + [FIXTURE_1, USER_2, REVIEW]
        base3 = base2 + [FIXTURE_2, docs_request]
        plug1 = [piece for call in calls1 for piece in (call["system"], call["user"])]
        plug2 = [piece for call in calls2 for piece in (call["system"], call["user"])]
        plug3 = [cite_text, docs_request]

        b1 = _tally(enc, base1)
        b2 = _tally(enc, base2)
        b3 = _tally(enc, base3)
        p1 = _tally(enc, plug1)
        p2 = _tally(enc, plug2)
        p3 = _tally(enc, plug3)
        bo1 = _tally(enc, [FIXTURE_1])
        bo2 = _tally(enc, [FIXTURE_2])
        bo3 = _tally(enc, [docs_request])
        po1 = _tally(enc, [out1.text])
        po2 = _tally(enc, [out2.text])
        po3 = _tally(enc, [report3.rewrite])

        turns = [
            {
                "name": "implement",
                "without_input": b1["tiktoken"],
                "without_output": bo1["tiktoken"],
                "with_input": p1["tiktoken"],
                "with_output": po1["tiktoken"],
            },
            {
                "name": "review",
                "without_input": b2["tiktoken"],
                "without_output": bo2["tiktoken"],
                "with_input": p2["tiktoken"],
                "with_output": po2["tiktoken"],
            },
            {
                "name": "later",
                "without_input": b3["tiktoken"],
                "without_output": bo3["tiktoken"],
                "with_input": p3["tiktoken"],
                "with_output": po3["tiktoken"],
            },
        ]

        without_in = sum(turn["without_input"] for turn in turns)
        without_out = sum(turn["without_output"] for turn in turns)
        with_in = sum(turn["with_input"] for turn in turns)
        with_out = sum(turn["with_output"] for turn in turns)
        without_plugin = b1["plugin"] + b2["plugin"] + b3["plugin"] + bo1["plugin"] + bo2["plugin"] + bo3["plugin"]
        with_plugin = p1["plugin"] + p2["plugin"] + p3["plugin"] + po1["plugin"] + po2["plugin"] + po3["plugin"]

        worker = calls1[0]["user"]
        missing = [fact for fact in FACTS if fact not in worker or fact not in cite_text]
        survived = [fact for fact in FACTS if fact not in missing]
        bodies = [node.body for node in graph.all_nodes() if node.body]
        bodies_in_cites = any(body in cite_text for body in bodies)
        max_summary = max(len(node.summary) for node in graph.all_nodes())

        without_total = without_in + without_out
        with_total = with_in + with_out
        saved_in = without_in - with_in
        saved_out = without_out - with_out
        saved_total = without_total - with_total
        later_saved = b3["tiktoken"] - p3["tiktoken"]

        return {
            "tokenizer": enc.name,
            "live_model": False,
            "inter_agent_mode": supervisor.config.inter_agent_mode,
            "worker_model": supervisor.config.worker_model,
            "plugins_invoked": ["prepare", "compress", "cite", "supervisor", "docs"],
            "agents": [report1.agents, report2.agents, report3.agents],
            "caveman_modes": [out1.mode, out2.mode],
            "prepare": {
                "turn1_before": len(enc.encode(request1, disallowed_special=())),
                "turn1_after": len(enc.encode(prepared1["compressed"], disallowed_special=())),
                "turn1_agents": [item["agent"] for item in prepared1["assignments"]],
                "turn2_agents": [item["agent"] for item in prepared2["assignments"]],
                "turn3_agents": [item["agent"] for item in prepared3["assignments"]],
                "turn3_cites": len(prepared3["cites"]),
            },
            "model_calls": len(model.calls),
            "calls3": len(calls3),
            "turns": turns,
            "without": {"input": without_in, "output": without_out, "total": without_total},
            "with": {"input": with_in, "output": with_out, "total": with_total},
            "saved": {"input": saved_in, "output": saved_out, "total": saved_total},
            "reduction_pct": _pct(saved_total, without_total),
            "plugin_counter": {"without": without_plugin, "with": with_plugin},
            "later_turn": {
                "without_input": b3["tiktoken"],
                "with_input": p3["tiktoken"],
                "without_output": bo3["tiktoken"],
                "with_output": po3["tiktoken"],
                "input_reduction_pct": _pct(later_saved, b3["tiktoken"]),
                "baseline_input": "\n".join(base3),
                "plugin_input": "\n".join(plug3),
            },
            "fidelity": {
                "survived": survived,
                "missing": missing,
                "turn1_worker": worker,
                "later_cites": cite_text,
            },
            "memory": {
                "max_summary_len": max_summary,
                "bodies_in_cites": bodies_in_cites,
            },
            "docs": {
                "before_tokens_tiktoken": bo3["tiktoken"],
                "after_tokens_tiktoken": po3["tiktoken"],
                "before_tokens_plugin": report3.rewrite and estimate_tokens(docs_request),
                "after_tokens_plugin": estimate_tokens(report3.rewrite),
            },
            "price_illustration": {
                "model": "gpt-4o",
                "as_of": PRICE_AS_OF,
                "input_per_m": GPT4O_INPUT_PER_M,
                "output_per_m": GPT4O_OUTPUT_PER_M,
                "without": _dollars(without_in, without_out),
                "with": _dollars(with_in, with_out),
            },
            "rewrite": report3.rewrite,
        }


def readme_section(result: dict) -> str:
    """User-facing section. Numbers come from compare()."""
    w = result["without"]
    p = result["with"]
    saved = result["saved"]
    later = result["later_turn"]
    first = result["turns"][0]
    price = result["price_illustration"]
    pc = result["plugin_counter"]
    if first["with_input"] > first["without_input"]:
        first_line = (
            f"The first turn still sends the spec. "
            f"Caveman compression and the reviewer pass put that turn's input at {first['with_input']} tokens with the plugin "
            f"and {first['without_input']} without it."
        )
    else:
        first_line = (
            f"The first turn input is {first['with_input']} tokens with the plugin "
            f"and {first['without_input']} without it."
        )
    out_delta = w["output"] - p["output"]
    if out_delta >= 0:
        out_line = (
            f"Output is {out_delta} tokens lower with the plugin on these harness fixtures and the docs rewrite."
        )
    else:
        out_line = (
            f"Output is {-out_delta} tokens higher with the plugin on these harness fixtures and the docs rewrite."
        )
    survived = (
        "Compression kept the maze size (19 columns by 21 rows), the controls (arrow keys and WASD), "
        "the win rule (win when every pellet is eaten), the lose rule (lose when a ghost touches the player), "
        "and the file names (scripts/player.gd, scripts/ghost.gd, scripts/maze.gd, scripts/hud.gd, scripts/main.gd)."
    )
    if result["fidelity"]["missing"]:
        missed = ", ".join(result["fidelity"]["missing"])
        survived = f"Compression dropped {missed}."
    shown_without = round(price["without"], 4)
    shown_with = round(price["with"], 4)
    per_k_without = shown_without * 1000
    per_k_with = shown_with * 1000
    lines = [
        "## Token comparison",
        "",
        (
            "This comparison uses the Godot 4 Pac-Man clone in `benchmarks/godot-pacman`. "
            "The task stays the same across three turns. "
            "Without the plugin, each turn sends the prompt again with the spec and the file tree. "
            "With RhinoDiet, each turn calls prepare, compress, cite, and the supervisor. "
            "Inter-agent text uses caveman compression. "
            "Memory passes ids and short labels. Stored bodies stay in the graph. "
            "From the second turn the baseline also sends the review notes and earlier replies. "
            "The last turn also runs the docs rewriter on one technical passage."
        ),
        "",
        (
            "Headline counts use tiktoken `o200k_base`. "
            "Output tokens are harness fixtures, counted raw on the baseline and after caveman compression on the plugin path. "
            "The last turn counts the original technical passage on the baseline and the docs rewriter output on the plugin path. "
            "No live model call was made."
        ),
        "",
        "| Condition | Input | Output | Total |",
        "| --- | --- | --- | --- |",
        f"| Without plugin | {w['input']} | {w['output']} | {w['total']} |",
        f"| With RhinoDiet | {p['input']} | {p['output']} | {p['total']} |",
        f"| Saved | {saved['input']} | {saved['output']} | {saved['total']} ({result['reduction_pct']:.1f}%) |",
        "",
        (
            f"The later turn is the long-context case. "
            f"Input on that turn is {later['without_input']} tokens without the plugin and {later['with_input']} tokens with RhinoDiet, "
            f"{_article_for_percent(later['input_reduction_pct'])} {later['input_reduction_pct']:.1f} percent reduction. "
            f"Without the plugin that turn resends the spec, the file tree, the review notes, and earlier replies. "
            f"With RhinoDiet that turn cites stored node ids and short labels."
        ),
        "",
        first_line + " " + out_line,
        "",
        survived,
        "",
        (
            f"The plugin counter, a local whitespace split, totals {pc['without']} without the plugin and {pc['with']} with it. "
            f"The table uses tiktoken {result['tokenizer']}. That count is the headline."
        ),
        "",
        (
            f"Illustration only, from public list prices. "
            f"At the OpenAI GPT-4o standard list price of $2.50 per 1M input tokens and $10 per 1M output tokens, "
            f"published {price['as_of']}, these counts come to ${shown_without:.4f} without the plugin and ${shown_with:.4f} with it. "
            f"Per 1,000 runs the illustration is ${per_k_without:.2f} versus ${per_k_with:.2f}. "
            f"The configured worker model is composer-2.5 fast. This sketch uses the GPT-4o list, which is a different price."
        ),
        "",
        GODOT_NOTE,
        "",
        "Install the dev extra so tiktoken is available. Then rerun the count.",
        "",
        "```bash",
        'python -m pip install -e ".[dev]"',
        "python benchmarks/token_compare.py",
        "```",
    ]
    return "\n".join(lines)


def main() -> int:
    result = compare()
    print(readme_section(result))
    print()
    print("Per turn (tiktoken input / output)")
    for turn in result["turns"]:
        print(
            f"{turn['name']}: without {turn['without_input']} / {turn['without_output']}, "
            f"with {turn['with_input']} / {turn['with_output']}"
        )
    if result["fidelity"]["missing"]:
        print("Missing facts:", ", ".join(result["fidelity"]["missing"]))
        return 1
    if result["with"]["total"] >= result["without"]["total"]:
        print("Plugin total was not lower.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
