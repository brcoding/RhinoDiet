"""Headless RhinoDiet commands. No API key required."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rhinodiet.compress import compress
from rhinodiet.docs import DocsWriter
from rhinodiet.graph import format_cites
from rhinodiet.supervisor import open_supervisor
from rhinodiet.tokens import format_report, record_transcript


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rhinodiet")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="Run the supervisor on a request")
    run.add_argument("request")

    comp = sub.add_parser("compress", help="Compress text")
    comp.add_argument("text")
    comp.add_argument("--mode", default="default")

    cite = sub.add_parser("cite", help="Cite memory refs for a query")
    cite.add_argument("query")

    sub.add_parser("compact", help="Compact the memory graph")

    docs = sub.add_parser("docs", help="Rewrite technical text and store a short ref")
    docs.add_argument("text")

    tokens = sub.add_parser("tokens", help="Record reconstructed transcript totals")
    tokens_sub = tokens.add_subparsers(dest="tokens_cmd", required=True)
    record = tokens_sub.add_parser("record", help="Count a transcript and write the totals")
    record.add_argument("transcript")
    record.add_argument("--out")

    args = parser.parse_args(argv)
    if args.cmd == "tokens":
        dest = Path(args.out) if args.out else None
        print(format_report(record_transcript(Path(args.transcript), dest)))
        return 0
    if args.cmd == "compress":
        result = compress(args.text, args.mode)
        print(result.text)
        print(f"{result.before_tokens} to {result.after_tokens} tokens.")
        return 0
    supervisor = open_supervisor()
    if args.cmd == "run":
        print(supervisor.run(args.request).reply)
        return 0
    if args.cmd == "cite":
        print(format_cites(supervisor.graph.cite(args.query)))
        return 0
    if args.cmd == "compact":
        report = supervisor.graph.compact(supervisor.config.compact_after_nodes)
        print(f"Compact {report.before} to {report.after}.")
        return 0
    if args.cmd == "docs":
        result = DocsWriter().run(args.text)
        node = supervisor.graph.add_node(
            label="docs",
            name="docs-pass",
            horizon="short",
            salience=0.6,
            summary=result.summary_line,
            body="",
        )
        print(result.text)
        print(f"Memory {node.id}. {result.summary_line}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
