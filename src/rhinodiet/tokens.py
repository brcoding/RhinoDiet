"""Token counts. The local estimate needs no model file. Transcript totals use tiktoken."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_PARTS = re.compile(r"\w+|[^\w\s]", re.UNICODE)

NOTES = [
    "Reconstructed from transcript text with tiktoken o200k_base.",
    "Not billed usage. The export did not include a provider usage field.",
    "The system prompt and the chat template are not in the export.",
    "Tool arguments missing from the export are omitted from output.",
    "Edit diffs are counted as input because the export stored them on the tool result.",
]


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return len(_PARTS.findall(text))


def _encoder():
    try:
        import tiktoken
    except ImportError as exc:
        raise RuntimeError("Install the dev extra so tiktoken is available.") from exc
    return tiktoken.get_encoding("o200k_base")


def _ntok(encoder, text: str) -> int:
    if not text:
        return 0
    return len(encoder.encode(text, disallowed_special=()))


def _result_text(result: object) -> str:
    if not isinstance(result, dict):
        return ""
    value = result.get("value")
    kind = result.get("resultType")
    if not isinstance(value, dict):
        return "" if value is None else str(value)
    if kind == "runTerminalCommandV2Result":
        return str(value.get("output") or "")
    if kind == "readFileResult":
        path = str(value.get("relativeWorkspacePath") or "")
        body = str(value.get("contents") or "")
        return f"{path}\n{body}" if path else body
    if kind == "editFileResult":
        return json.dumps(value.get("diff") or {}, ensure_ascii=False, sort_keys=True)
    if kind == "getMcpToolsResult":
        return str(value.get("content") or "")
    if kind == "mcpResult":
        return f"{value.get('selectedTool') or ''}\n{value.get('result') or ''}"
    if kind == "webSearchResult":
        return json.dumps(value.get("references") or [], ensure_ascii=False, sort_keys=True)
    if kind == "globFileSearchResult":
        return json.dumps(value.get("directories") or [], ensure_ascii=False, sort_keys=True)
    if kind == "ripgrepSearchResult":
        return json.dumps(value.get("internal") or {}, ensure_ascii=False, sort_keys=True)
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _args_text(message: dict) -> str:
    name = str(message.get("tool_name") or "")
    payload = json.dumps(message.get("tool_args") or {}, ensure_ascii=False, sort_keys=True)
    return f"{name}\n{payload}" if name else payload


def transcript_parts(messages: list[dict]) -> list[tuple[int, str, str, str]]:
    """Ordered pieces. Each item is turn, kind, category, text."""
    parts: list[tuple[int, str, str, str]] = []
    turn = 0
    seen_user = 0
    for message in messages:
        role = message.get("role")
        if role == "user" and message.get("text"):
            seen_user += 1
            if seen_user > 1:
                turn += 1
            parts.append((turn, "input", "user", str(message["text"])))
            continue
        if role == "assistant" and message.get("thinking"):
            parts.append((turn, "output", "thinking", str(message["thinking"])))
        if role == "assistant" and message.get("text"):
            parts.append((turn, "output", "assistant", str(message["text"])))
        if role == "tool" and message.get("tool_args") is not None:
            parts.append((turn, "output", "tool_args", _args_text(message)))
        if role == "tool" and message.get("tool_result") is not None:
            text = _result_text(message.get("tool_result"))
            if text:
                parts.append((turn, "input", "tool_result", text))
    return parts


def _totals(encoder, pieces: list[tuple[str, str]]) -> dict[str, int]:
    incoming = 0
    outgoing = 0
    for kind, text in pieces:
        count = _ntok(encoder, text)
        if kind == "input":
            incoming += count
        else:
            outgoing += count
    return {"input": incoming, "output": outgoing, "total": incoming + outgoing}


def _replay(encoder, parts: list[tuple[int, str, str, str]]) -> tuple[dict[str, int], list[dict]]:
    """Each generation resends prior transcript text. Output is counted once."""
    incoming = 0
    outgoing = 0
    generations = 0
    turns: dict[int, dict[str, int]] = {}
    index = 0
    while index < len(parts):
        if parts[index][1] != "output":
            index += 1
            continue
        end = index
        while end < len(parts) and parts[end][1] == "output":
            end += 1
        turn = parts[index][0]
        context = "\n".join(text for _turn, _kind, _cat, text in parts[:index])
        out_count = sum(_ntok(encoder, text) for _turn, _kind, _cat, text in parts[index:end])
        in_count = _ntok(encoder, context)
        incoming += in_count
        outgoing += out_count
        generations += 1
        bucket = turns.setdefault(turn, {"input": 0, "output": 0, "generations": 0})
        bucket["input"] += in_count
        bucket["output"] += out_count
        bucket["generations"] += 1
        index = end
    replay = {
        "input": incoming,
        "output": outgoing,
        "total": incoming + outgoing,
        "generations": generations,
    }
    ordered = []
    for turn in sorted(turns):
        bucket = turns[turn]
        ordered.append(
            {
                "turn": turn + 1,
                "input": bucket["input"],
                "output": bucket["output"],
                "total": bucket["input"] + bucket["output"],
                "generations": bucket["generations"],
            }
        )
    return replay, ordered


def load_transcript(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("messages"), list):
        return data["messages"]
    if isinstance(data, list):
        return data
    raise ValueError("Transcript must be a message list or an object with messages.")


def count_messages(messages: list[dict]) -> dict:
    """Reconstruct input, output, and total. Does not invent billed usage."""
    encoder = _encoder()
    parts = transcript_parts(messages)
    unique = _totals(encoder, [(kind, text) for _turn, kind, _cat, text in parts])
    categories: dict[str, int] = {}
    for _turn, _kind, category, text in parts:
        categories[category] = categories.get(category, 0) + _ntok(encoder, text)
    omitted = sorted(
        {
            str(message["tool_name"])
            for message in messages
            if message.get("role") == "tool" and message.get("tool_args") is None and message.get("tool_name")
        }
    )
    replay, turns = _replay(encoder, parts)
    unique_turns = []
    seen = sorted({turn for turn, _kind, _cat, _text in parts})
    for turn in seen:
        pieces = [(kind, text) for item_turn, kind, _cat, text in parts if item_turn == turn]
        totals = _totals(encoder, pieces)
        unique_turns.append({"turn": turn + 1, **totals})
    return {
        "source": "reconstructed-transcript",
        "tokenizer": encoder.name,
        "billed_usage": None,
        "unique": unique,
        "replay": replay,
        "unique_turns": unique_turns,
        "replay_turns": turns,
        "categories": categories,
        "omitted_tool_args": omitted,
        "notes": list(NOTES),
    }


def record_transcript(path: Path, dest: Path | None = None) -> dict:
    report = count_messages(load_transcript(path))
    target = dest
    if target is None:
        target = Path(".rhinodiet") / "runs" / f"{path.stem}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    report["wrote"] = str(target)
    return report


def format_report(report: dict) -> str:
    unique = report["unique"]
    replay = report["replay"]
    lines = [
        "Reconstructed from transcript. Not billed usage.",
        f"Unique input {unique['input']} output {unique['output']} total {unique['total']}.",
        f"Replay input {replay['input']} output {replay['output']} total {replay['total']}.",
        f"Wrote {report['wrote']}.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rhinodiet.tokens")
    sub = parser.add_subparsers(dest="cmd", required=True)
    record = sub.add_parser("record", help="Record reconstructed totals for a transcript")
    record.add_argument("transcript")
    record.add_argument("--out")
    args = parser.parse_args(argv)
    if args.cmd == "record":
        dest = Path(args.out) if args.out else None
        report = record_transcript(Path(args.transcript), dest)
        print(format_report(report))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
