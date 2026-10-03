"""Stdio MCP server. Newline JSON-RPC. No API key required."""

from __future__ import annotations

import json
import sys

from rhinodiet.compress import compress
from rhinodiet.docs import DocsWriter
from rhinodiet.graph import format_cites
from rhinodiet.supervisor import open_supervisor

TOOLS = [
    {
        "name": "rhinodiet_prepare",
        "description": "Compress the request, cite memory ids, and assign the cheapest agents.",
        "inputSchema": {
            "type": "object",
            "properties": {"request": {"type": "string"}},
            "required": ["request"],
        },
    },
    {
        "name": "rhinodiet_run",
        "description": "Run the supervisor loop. Delegate, review, remember, and compact.",
        "inputSchema": {
            "type": "object",
            "properties": {"request": {"type": "string"}},
            "required": ["request"],
        },
    },
    {
        "name": "rhinodiet_compress",
        "description": "Compress text. Modes are default, ponytail, caveman, and tighten.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "mode": {"type": "string"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "rhinodiet_cite",
        "description": "Return memory refs for the next prompt. Ids and short labels, not bodies.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "rhinodiet_docs",
        "description": "Rewrite technical text. About 30 percent shorter, active voice, facts kept. Store a short ref.",
        "inputSchema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "name": "rhinodiet_creative",
        "description": "Read or define project style, then write a local image or storyboard.",
        "inputSchema": {
            "type": "object",
            "properties": {"request": {"type": "string"}},
            "required": ["request"],
        },
    },
    {
        "name": "rhinodiet_release",
        "description": "Write scripts/release.sh. That script is the release path.",
        "inputSchema": {
            "type": "object",
            "properties": {"request": {"type": "string"}},
            "required": ["request"],
        },
    },
    {
        "name": "rhinodiet_remember",
        "description": "Store a short memory update and compact when over the threshold.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "label": {"type": "string"},
            },
            "required": ["summary"],
        },
    },
    {
        "name": "rhinodiet_get",
        "description": "Fetch one node body. Use only when the task truly needs the blob.",
        "inputSchema": {
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "required": ["id"],
        },
    },
]


def handle(message: dict) -> dict | None:
    method = message.get("method") or ""
    if method.startswith("notifications/") or "id" not in message:
        return None
    msg_id = message["id"]
    try:
        result = _dispatch(method, message.get("params") or {})
    except Exception as exc:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32000, "message": str(exc)},
        }
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _dispatch(method: str, params: dict) -> dict:
    if method == "initialize":
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "rhinodiet", "version": "0.1.0"},
        }
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        text = _call_tool(str(name), args)
        return {"content": [{"type": "text", "text": text}], "isError": False}
    raise RuntimeError(f"unknown method: {method}")


def _call_tool(name: str, args: dict) -> str:
    if name == "rhinodiet_compress":
        result = compress(str(args.get("text") or ""), str(args.get("mode") or "default"))
        return json.dumps(
            {
                "text": result.text,
                "before_tokens": result.before_tokens,
                "after_tokens": result.after_tokens,
                "mode": result.mode,
            }
        )
    supervisor = open_supervisor()
    if name == "rhinodiet_prepare":
        return json.dumps(supervisor.prepare(str(args.get("request") or "")))
    if name == "rhinodiet_run":
        report = supervisor.run(str(args.get("request") or ""))
        return json.dumps(
            {
                "reply": report.reply,
                "agents": report.agents,
                "memory_id": report.memory_id,
                "compacted": report.compacted,
                "accepted": report.accepted,
                "rewrite": report.rewrite,
            }
        )
    if name == "rhinodiet_cite":
        limit = int(args.get("limit") or 5)
        cites = supervisor.graph.cite(str(args.get("query") or ""), limit=limit)
        return format_cites(cites)
    if name == "rhinodiet_docs":
        result = DocsWriter().run(str(args.get("text") or ""))
        node = supervisor.graph.add_node(
            label="docs",
            name="docs-pass",
            horizon="short",
            salience=0.6,
            summary=result.summary_line,
            body="",
        )
        compact = supervisor.graph.compact(supervisor.config.compact_after_nodes)
        return json.dumps(
            {
                "text": result.text,
                "memory_id": node.id,
                "summary": result.summary_line,
                "compacted": compact.ran,
            }
        )
    if name == "rhinodiet_creative":
        artifact = supervisor._creative(str(args.get("request") or ""))
        return json.dumps({"path": str(artifact.path), "summary": artifact.summary})
    if name == "rhinodiet_release":
        result = supervisor.release.run(str(args.get("request") or ""), supervisor.project_root)
        return json.dumps({"script": str(result.script), "summary": result.summary})
    if name == "rhinodiet_remember":
        summary = str(args.get("summary") or "")[:160]
        node = supervisor.graph.add_node(
            label=str(args.get("label") or "task"),
            name=summary[:60] or "note",
            horizon="short",
            salience=0.5,
            summary=summary,
            body="",
        )
        compact = supervisor.graph.compact(supervisor.config.compact_after_nodes)
        return json.dumps({"id": node.id, "summary": node.summary, "compacted": compact.ran})
    if name == "rhinodiet_get":
        node = supervisor.graph.get(str(args.get("id") or ""))
        return json.dumps({"id": node.id, "label": node.label, "body": node.body})
    raise RuntimeError(f"unknown tool: {name}")


def serve(stdin=None, stdout=None) -> None:
    incoming = stdin or sys.stdin
    outgoing = stdout or sys.stdout
    for line in incoming:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(message, dict):
            continue
        response = handle(message)
        if response is None:
            continue
        outgoing.write(json.dumps(response) + "\n")
        outgoing.flush()


def main() -> None:
    serve()


if __name__ == "__main__":
    main()
