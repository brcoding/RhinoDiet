import json
from pathlib import Path

import tiktoken

from rhinodiet.cli import main
from rhinodiet.tokens import count_messages

ROOT = Path(__file__).resolve().parents[1]


def _n(text: str) -> int:
    encoder = tiktoken.get_encoding("o200k_base")
    return len(encoder.encode(text, disallowed_special=()))


def test_unique_counts_each_string_once_and_replay_resends_context():
    messages = [
        {"role": "user", "text": "one"},
        {"role": "assistant", "text": "two"},
        {"role": "user", "text": "three"},
        {"role": "assistant", "text": "four"},
    ]
    report = count_messages(messages)
    assert report["source"] == "reconstructed-transcript"
    assert report["tokenizer"] == "o200k_base"
    assert report["billed_usage"] is None
    assert report["unique"]["input"] == _n("one") + _n("three")
    assert report["unique"]["output"] == _n("two") + _n("four")
    assert report["unique"]["total"] == report["unique"]["input"] + report["unique"]["output"]
    assert report["replay"]["output"] == report["unique"]["output"]
    assert report["replay"]["generations"] == 2
    assert report["replay"]["input"] == _n("one") + _n("\n".join(["one", "two", "three"]))
    assert report["replay"]["total"] == report["replay"]["input"] + report["replay"]["output"]
    assert [turn["turn"] for turn in report["unique_turns"]] == [1, 2]
    assert report["unique_turns"][1]["input"] == _n("three")
    assert report["replay_turns"][1]["input"] == _n("\n".join(["one", "two", "three"]))


def test_shell_output_is_input_and_missing_edit_args_are_omitted():
    messages = [
        {"role": "user", "text": "build"},
        {
            "role": "tool",
            "tool_name": "run_terminal_cmd",
            "tool_args": {"command": "echo hi"},
            "tool_result": {"resultType": "runTerminalCommandV2Result", "value": {"output": "hi\n"}},
        },
        {
            "role": "tool",
            "tool_name": "search_replace",
            "tool_result": {
                "resultType": "editFileResult",
                "value": {"diff": {"chunks": []}, "isApplied": True},
            },
        },
    ]
    report = count_messages(messages)
    assert report["categories"]["tool_args"] == _n('run_terminal_cmd\n{"command": "echo hi"}')
    assert report["categories"]["tool_result"] > 0
    assert "search_replace" in report["omitted_tool_args"]
    assert "run_terminal_cmd" not in report["omitted_tool_args"]


def test_record_writes_reconstructed_totals(tmp_path, capsys):
    transcript = tmp_path / "run.json"
    transcript.write_text(
        json.dumps({"messages": [{"role": "user", "text": "hello"}, {"role": "assistant", "text": "hi"}]}),
        encoding="utf-8",
    )
    dest = tmp_path / "out" / "totals.json"
    assert main(["tokens", "record", str(transcript), "--out", str(dest)]) == 0
    saved = json.loads(dest.read_text(encoding="utf-8"))
    assert saved["billed_usage"] is None
    assert saved["unique"]["total"] == saved["unique"]["input"] + saved["unique"]["output"]
    printed = capsys.readouterr().out
    assert "Not billed usage." in printed
    assert "Unique input" in printed
    assert str(dest) in printed


def test_readme_cites_recorded_agent_totals():
    recorded = json.loads((ROOT / "benchmarks/measured/pacman-agents.json").read_text(encoding="utf-8"))
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert recorded["billed_usage"] is None
    assert recorded["tokenizer"] == "o200k_base"
    assert ";" not in readme.split("## Measured agent runs", 1)[1].split("## License", 1)[0]
    for run in recorded["runs"]:
        assert run["id"] in readme
        assert str(run["unique"]["input"]) in readme
        assert str(run["unique"]["output"]) in readme
        assert str(run["unique"]["total"]) in readme
        assert str(run["replay"]["total"]) in readme
        for turn in run["unique_turns"]:
            assert str(turn["total"]) in readme
