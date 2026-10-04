"""Headless RhinoDiet commands. No API key required."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rhinodiet.compress import compress
from rhinodiet.docs import DocsWriter
from rhinodiet.graph import format_cites
from rhinodiet.guide import GUIDE_PORT, serve as serve_guide, start_guide
from rhinodiet.supervisor import open_supervisor
from rhinodiet.testhistory import PAGE_PORT, serve, show_tests
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

    test = sub.add_parser("test", help="Play the registered game, or serve test history")
    test.add_argument("--focus", default="", help="Play one area, for example avoid ghosts")
    test.add_argument("--loops", type=int, default=0, help="Endurance loops. Default is 2.")
    test.add_argument("--serve", action="store_true", help="Serve the local test history page")
    test.add_argument("--show", action="store_true", help="Print local test history and the test commands")
    test.add_argument("--port", type=int, default=PAGE_PORT)

    guide = sub.add_parser("guide", help="Serve the local walkthrough page")
    guide.add_argument("--serve", action="store_true", help="Stay in the foreground")
    guide.add_argument("--port", type=int, default=GUIDE_PORT)

    tokens = sub.add_parser("tokens", help="Record reconstructed transcript totals")
    tokens_sub = tokens.add_subparsers(dest="tokens_cmd", required=True)
    record = tokens_sub.add_parser("record", help="Count a transcript and write the totals")
    record.add_argument("transcript")
    record.add_argument("--out")

    args = parser.parse_args(argv)
    if args.cmd == "test" and args.show:
        from rhinodiet.config import project_dir

        print(show_tests(project_dir(), args.port), end="")
        return 0
    if args.cmd == "test" and args.serve:
        from rhinodiet.config import project_dir

        serve(project_dir(), args.port)
        return 0
    if args.cmd == "guide":
        if args.serve:
            from rhinodiet.testhistory import port_open

            if port_open(args.port):
                print(f"Guide is already up at http://127.0.0.1:{args.port}/")
                return 0
            serve_guide(args.port)
            return 0
        print(start_guide(args.port))
        return 0
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
    if args.cmd == "test":
        phrase = args.focus.strip()
        request = f"focus on {phrase}" if phrase else "test the game"
        if args.loops:
            request = f"{request} for {args.loops} loops"
        report = supervisor.tester.run(
            request,
            supervisor.project_root,
            focus=phrase,
            loops=args.loops,
        )
        print(report.text)
        if report.cite_ids:
            print("Cited " + ", ".join(report.cite_ids) + ".")
        return 0 if report.passed else 1
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
