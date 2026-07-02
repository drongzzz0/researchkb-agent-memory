from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "researchkb"))

from rk_query import QueryEngine  # noqa: E402

DEFAULT_ROOT = Path(".runtime") / "researchkb"


def main() -> int:
    parser = argparse.ArgumentParser(description="Query the synthetic ResearchKB demo database.")
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help="ResearchKB root. Defaults to .runtime/researchkb.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    latest = subparsers.add_parser("latest-runs", help="Show latest experiment runs.")
    latest.add_argument("--limit", type=int, default=5)
    latest.add_argument("--project")
    latest.add_argument("--status")

    failures = subparsers.add_parser("failure-cases", help="Search synthetic failure cases.")
    failures.add_argument("query")
    failures.add_argument("--limit", type=int, default=10)

    evidence = subparsers.add_parser("evidence", help="Search synthetic evidence links and chunks.")
    evidence.add_argument("query")
    evidence.add_argument("--limit", type=int, default=10)

    papers = subparsers.add_parser("papers", help="Search synthetic paper metadata.")
    papers.add_argument("query")
    papers.add_argument("--limit", type=int, default=10)

    claims = subparsers.add_parser("claims", help="Search synthetic claims.")
    claims.add_argument("query")
    claims.add_argument("--limit", type=int, default=10)

    compare = subparsers.add_parser("compare-runs", help="Compare metrics between two runs.")
    compare.add_argument("run_a")
    compare.add_argument("run_b")
    compare.add_argument("--metric", action="append", dest="metrics")

    args = parser.parse_args()
    db_path = args.root / "db" / "literature.sqlite"
    if not db_path.exists():
        raise FileNotFoundError(f"Demo DB not found: {db_path}. Run scripts/seed_demo_db.py first.")

    with QueryEngine(args.root) as engine:
        if args.command == "latest-runs":
            result = engine.find_recent_runs(project=args.project, status=args.status, limit=args.limit)
        elif args.command == "failure-cases":
            result = engine.find_failure_cases(args.query, args.limit)
        elif args.command == "evidence":
            result = engine.search_evidence(args.query, args.limit)
        elif args.command == "papers":
            result = engine.search_papers(args.query, args.limit)
        elif args.command == "claims":
            result = engine.search_claims(args.query, args.limit)
        elif args.command == "compare-runs":
            result = engine.compare_runs(args.run_a, args.run_b, args.metrics)
        else:
            raise ValueError(f"Unknown command: {args.command}")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
