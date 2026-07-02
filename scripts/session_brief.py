"""Print a compact ResearchKB brief for injecting at agent session start.

Combines readiness level, effectiveness metrics, the latest runs, and open
failure cases (no final_solution yet) into a short text or JSON block that
fits comfortably inside a system prompt or session hook.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "researchkb"))

import rk_health  # noqa: E402
from rk_query import QueryEngine  # noqa: E402

DEFAULT_ROOT = Path(".runtime") / "researchkb"


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit a compact session-start brief from ResearchKB.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="ResearchKB root.")
    parser.add_argument("--project", help="Optional project filter for recent runs.")
    parser.add_argument("--limit", type=int, default=5, help="Number of recent runs to include.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args()

    brief = build_brief(args.root, project=args.project, limit=args.limit)
    if args.json:
        print(json.dumps(brief, ensure_ascii=False, indent=2))
    else:
        print_text_brief(brief)
    return 0


def build_brief(root: Path, project: str | None = None, limit: int = 5) -> dict[str, Any]:
    report = rk_health.build_report(root=root, check_scheduled=False)
    judgement = report["judgement"]
    brief: dict[str, Any] = {
        "root": report["root"],
        "level": judgement.get("level"),
        "effectiveness": judgement.get("effectiveness", {}),
        "next_actions": judgement.get("next_actions", []),
        "recent_runs": [],
        "open_failure_cases": [],
    }
    if not report["database"].get("exists"):
        return brief

    with QueryEngine(root) as engine:
        runs = engine.find_recent_runs(project=project, limit=limit)["runs"]
        brief["recent_runs"] = [
            {
                "run_id": run.get("run_id"),
                "project": run.get("project"),
                "status": run.get("status"),
                "decision": run.get("decision"),
                "next_action": run.get("next_action"),
                "created_at": run.get("created_at"),
            }
            for run in runs
        ]
        brief["open_failure_cases"] = open_failure_cases(engine)
    return brief


def open_failure_cases(engine: QueryEngine, limit: int = 10) -> list[dict[str, Any]]:
    if "problem_cases" not in engine.tables:
        return []
    columns = engine.columns["problem_cases"]
    if "final_solution" not in columns or "problem_id" not in columns:
        return []
    rows = engine.conn.execute(
        "select * from src.problem_cases where final_solution is null or trim(final_solution) = '' limit ?",
        (limit,),
    ).fetchall()
    return [
        {
            "problem_id": row["problem_id"],
            "symptom": dict(row).get("symptom"),
            "linked_runs": dict(row).get("linked_runs_json"),
        }
        for row in rows
    ]


def print_text_brief(brief: dict[str, Any]) -> None:
    effectiveness = brief.get("effectiveness", {})
    print(f"ResearchKB session brief (root: {brief['root']})")
    print(
        f"level={brief.get('level')} "
        f"metrics_coverage={effectiveness.get('metrics_coverage')} "
        f"failure_documentation_rate={effectiveness.get('failure_documentation_rate')} "
        f"evidence_density={effectiveness.get('evidence_density')} "
        f"run_freshness_days={effectiveness.get('run_freshness_days')}"
    )
    print("")
    print("[recent runs]")
    if brief["recent_runs"]:
        for run in brief["recent_runs"]:
            print(
                f"- {run.get('run_id')} | {run.get('project')} | {run.get('status')}"
                f" | decision={run.get('decision')} | next={run.get('next_action')}"
            )
    else:
        print("- none recorded")
    print("")
    print("[open failure cases]")
    if brief["open_failure_cases"]:
        for case in brief["open_failure_cases"]:
            print(f"- {case.get('problem_id')} | {case.get('symptom')}")
    else:
        print("- none open")
    print("")
    print("[suggested next actions]")
    for action in brief.get("next_actions", []):
        print(f"- {action}")


if __name__ == "__main__":
    raise SystemExit(main())
