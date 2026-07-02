"""`rk-memory` console entry point.

One command surface over the ResearchKB Agent Memory toolkit. Each subcommand
delegates to the module that also backs the legacy `scripts/*.py` wrappers, so
both call paths stay behavior-identical.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path

from . import __version__, autostandardize, brief, citations, demo, health, import_runs, mcp, standardize, workspace
from . import eval as retrieval_eval
from .query import QueryEngine

DEFAULT_ROOT = Path(".runtime") / "researchkb"

QUERY_TOOLS = {
    "search-papers": "search_papers",
    "search-chunks": "search_chunks",
    "search-claims": "search_claims",
    "search-evidence": "search_evidence",
    "find-failure-cases": "find_failure_cases",
}


def _query_command(command: str) -> Callable[[list[str]], int]:
    def run(argv: list[str]) -> int:
        parser = argparse.ArgumentParser(
            prog=f"rk-memory {command}",
            description=f"Run {QUERY_TOOLS[command]} against a ResearchKB database (read-only).",
        )
        parser.add_argument("query", help="Keyword query.")
        parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="ResearchKB root.")
        parser.add_argument("--limit", type=int, default=10)
        args = parser.parse_args(argv)
        with QueryEngine(args.root) as engine:
            result = getattr(engine, QUERY_TOOLS[command])(args.query, args.limit)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    return run


def _latest_runs(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="rk-memory latest-runs",
        description="Show recent experiment runs (read-only).",
    )
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="ResearchKB root.")
    parser.add_argument("--project", help="Optional project filter.")
    parser.add_argument("--status", help="Optional status filter.")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args(argv)
    with QueryEngine(args.root) as engine:
        result = engine.find_recent_runs(project=args.project, status=args.status, limit=args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _compare_runs(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="rk-memory compare-runs",
        description="Compare metrics between two runs (read-only).",
    )
    parser.add_argument("run_a")
    parser.add_argument("run_b")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="ResearchKB root.")
    parser.add_argument("--metric", action="append", dest="metrics", help="Metric name. Repeatable.")
    args = parser.parse_args(argv)
    with QueryEngine(args.root) as engine:
        result = engine.compare_runs(args.run_a, args.run_b, args.metrics)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


COMMANDS: dict[str, tuple[Callable[[list[str]], int], str]] = {
    "init": (workspace.main, "Initialize a local smoke workspace and watch list."),
    "seed-demo": (demo.main, "Create the synthetic demo database from examples/."),
    "standardize-run": (standardize.main, "Normalize one run directory into run_record.json."),
    "auto-standardize": (autostandardize.main, "Batch-standardize watched experiment folders."),
    "import-runs": (import_runs.main, "Import run_record.json files into experiment_runs."),
    "health": (health.main, "Report readiness level and effectiveness metrics."),
    "session-brief": (brief.main, "Emit a compact session-start brief."),
    "search-papers": (_query_command("search-papers"), "Search paper metadata."),
    "search-chunks": (_query_command("search-chunks"), "Search source text chunks."),
    "search-claims": (_query_command("search-claims"), "Search structured claims."),
    "search-evidence": (_query_command("search-evidence"), "Search evidence links plus matching chunks."),
    "find-failure-cases": (_query_command("find-failure-cases"), "Search historical failure cases."),
    "latest-runs": (_latest_runs, "Show recent experiment runs."),
    "compare-runs": (_compare_runs, "Compare metrics between two runs."),
    "eval": (retrieval_eval.main, "Run the retrieval-quality eval against a gold set."),
    "check-citations": (citations.main, "Verify source IDs cited in an answer file."),
    "mcp": (mcp.main, "Start the read-only MCP stdio server."),
}


def usage() -> str:
    lines = [
        f"rk-memory {__version__} - local-first research agent memory toolkit",
        "",
        "usage: rk-memory <command> [options]",
        "",
        "commands:",
    ]
    lines.extend(f"  {name:<20} {description}" for name, (_, description) in COMMANDS.items())
    lines.append("")
    lines.append("Run 'rk-memory <command> --help' for command options.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help", "help"):
        print(usage())
        return 0
    if args[0] in ("-V", "--version", "version"):
        print(f"rk-memory {__version__}")
        return 0
    command = args.pop(0)
    entry = COMMANDS.get(command)
    if entry is None:
        print(f"Unknown command: {command}", file=sys.stderr)
        print(usage(), file=sys.stderr)
        return 2
    handler, _description = entry
    return int(handler(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
