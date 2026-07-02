"""Measure retrieval effectiveness of the ResearchKB query engine.

Runs a gold query set (evals/retrieval_eval.jsonl) against a seeded database
and reports quantified metrics:

- recall_at_k: fraction of expected source IDs retrieved in the top k
- mrr: mean reciprocal rank of the first relevant result (positive cases)
- precision_at_1: how often the top result is relevant (positive cases)
- guard_pass_rate: negative-guard queries that correctly return nothing
- avg_latency_ms: mean query latency

Exit code is non-zero when --min-recall / --min-mrr thresholds are not met,
so the eval can gate CI.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from time import perf_counter
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "researchkb"))

from rk_query import QueryEngine  # noqa: E402

DEFAULT_ROOT = Path(".runtime") / "researchkb"
DEFAULT_EVAL_FILE = REPO_ROOT / "evals" / "retrieval_eval.jsonl"

# tool -> (result list key, id field)
TOOL_RESULT_KEYS = {
    "search_papers": ("papers", "paper_id"),
    "search_chunks": ("chunks", "chunk_id"),
    "search_claims": ("claims", "claim_id"),
    "find_failure_cases": ("cases", "problem_id"),
    "search_evidence": ("evidence_links", "evidence_id"),
    "find_recent_runs": ("runs", "run_id"),
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate ResearchKB retrieval quality against a gold set.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="ResearchKB root with a seeded database.")
    parser.add_argument("--eval-file", type=Path, default=DEFAULT_EVAL_FILE, help="Gold JSONL query set.")
    parser.add_argument("--min-recall", type=float, default=0.0, help="Fail when mean recall@k is below this value.")
    parser.add_argument("--min-mrr", type=float, default=0.0, help="Fail when MRR is below this value.")
    parser.add_argument("--json", action="store_true", help="Emit the full JSON report.")
    args = parser.parse_args()

    cases = load_cases(args.eval_file)
    with QueryEngine(args.root) as engine:
        report = evaluate(engine, cases)

    summary = report["summary"]
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_text_report(report)

    failed = []
    if summary["recall_at_k"] is not None and summary["recall_at_k"] < args.min_recall:
        failed.append(f"recall_at_k {summary['recall_at_k']} < {args.min_recall}")
    if summary["mrr"] is not None and summary["mrr"] < args.min_mrr:
        failed.append(f"mrr {summary['mrr']} < {args.min_mrr}")
    if failed:
        print("EVAL_FAIL " + "; ".join(failed))
        return 1
    print("EVAL_OK")
    return 0


def load_cases(eval_file: Path) -> list[dict[str, Any]]:
    cases = []
    for line in eval_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        cases.append(json.loads(line))
    if not cases:
        raise ValueError(f"No eval cases found in {eval_file}")
    return cases


def evaluate(engine: QueryEngine, cases: list[dict[str, Any]]) -> dict[str, Any]:
    results = [run_case(engine, case) for case in cases]
    positives = [item for item in results if item["kind"] == "positive"]
    negatives = [item for item in results if item["kind"] == "negative_guard"]
    summary = {
        "cases": len(results),
        "recall_at_k": round(mean([item["recall"] for item in positives]), 4) if positives else None,
        "mrr": round(mean([item["reciprocal_rank"] for item in positives]), 4) if positives else None,
        "precision_at_1": round(mean([item["precision_at_1"] for item in positives]), 4) if positives else None,
        "guard_pass_rate": round(mean([1.0 if item["passed"] else 0.0 for item in negatives]), 4)
        if negatives
        else None,
        "pass_rate": round(mean([1.0 if item["passed"] else 0.0 for item in results]), 4),
        "avg_latency_ms": round(mean([item["latency_ms"] for item in results]), 2),
        "fts_enabled": engine.fts_available,
    }
    return {"summary": summary, "results": results}


def run_case(engine: QueryEngine, case: dict[str, Any]) -> dict[str, Any]:
    tool = case["tool"]
    if tool not in TOOL_RESULT_KEYS:
        raise ValueError(f"Unknown tool in eval case {case.get('id')}: {tool}")
    k = int(case.get("k", 5))
    arguments = case.get("arguments") or {}

    start = perf_counter()
    if tool == "find_recent_runs":
        result = engine.find_recent_runs(
            project=arguments.get("project"),
            status=arguments.get("status"),
            limit=int(arguments.get("limit", k)),
        )
    elif tool == "find_failure_cases":
        result = engine.find_failure_cases(case["query"], k)
    elif tool == "search_evidence":
        result = engine.search_evidence(case["query"], k)
    else:
        result = getattr(engine, tool)(case["query"], k)
    latency_ms = (perf_counter() - start) * 1000

    list_key, id_field = TOOL_RESULT_KEYS[tool]
    retrieved = [item.get(id_field) for item in result.get(list_key, [])][:k]
    expected = list(case.get("expected_source_ids", []))

    if expected:
        kind = "positive"
        hits = [source_id for source_id in expected if source_id in retrieved]
        recall = len(hits) / len(expected)
        reciprocal_rank = 0.0
        for rank, source_id in enumerate(retrieved, start=1):
            if source_id in expected:
                reciprocal_rank = 1.0 / rank
                break
        precision_at_1 = 1.0 if retrieved and retrieved[0] in expected else 0.0
        passed = recall == 1.0
    else:
        kind = "negative_guard"
        recall = None
        reciprocal_rank = None
        precision_at_1 = None
        passed = not retrieved

    return {
        "id": case.get("id"),
        "tool": tool,
        "kind": kind,
        "expected": expected,
        "retrieved": retrieved,
        "recall": recall,
        "reciprocal_rank": reciprocal_rank,
        "precision_at_1": precision_at_1,
        "passed": passed,
        "latency_ms": round(latency_ms, 2),
    }


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def print_text_report(report: dict[str, Any]) -> None:
    summary = report["summary"]
    print("ResearchKB retrieval eval")
    print(
        f"cases={summary['cases']} recall_at_k={summary['recall_at_k']} mrr={summary['mrr']} "
        f"precision_at_1={summary['precision_at_1']} guard_pass_rate={summary['guard_pass_rate']} "
        f"pass_rate={summary['pass_rate']} avg_latency_ms={summary['avg_latency_ms']} "
        f"fts_enabled={summary['fts_enabled']}"
    )
    for item in report["results"]:
        status = "PASS" if item["passed"] else "FAIL"
        print(f"{status} {item['id']} [{item['tool']}] retrieved={item['retrieved']}")


if __name__ == "__main__":
    raise SystemExit(main())
