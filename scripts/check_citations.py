"""Audit an agent answer for citation validity against a ResearchKB database.

Extracts source IDs (paper_/chunk_/claim_/run_/problem_/evidence_ prefixes)
from a text file and verifies each against the database. Reports:

- citation_validity: valid citations / verifiable citations
- unknown_ids: cited IDs that do not exist in the database
- unverifiable_ids: IDs whose backing table is missing

Use --min-validity to enforce a threshold (exit code 1 when below), which
makes agent-answer grounding a measurable, scriptable quantity.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "researchkb"))

from rk_query import QueryEngine, quote_identifier  # noqa: E402

DEFAULT_ROOT = Path(".runtime") / "researchkb"
CITATION_RE = re.compile(r"\b(?:paper|chunk|claim|run|problem|evidence)_[A-Za-z0-9][A-Za-z0-9_-]*\b")

# citation prefix -> (table, id column)
PREFIX_TABLES = {
    "paper": ("papers", "paper_id"),
    "chunk": ("chunks", "chunk_id"),
    "claim": ("claims", "claim_id"),
    "run": ("experiment_runs", "run_id"),
    "problem": ("problem_cases", "problem_id"),
    "evidence": ("evidence_links", "evidence_id"),
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Check agent answer citations against ResearchKB.")
    parser.add_argument("answer_file", type=Path, help="Text or markdown file containing the agent answer.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="ResearchKB root.")
    parser.add_argument(
        "--min-validity",
        type=float,
        default=0.0,
        help="Fail when citation_validity is below this value.",
    )
    args = parser.parse_args()

    text = args.answer_file.read_text(encoding="utf-8")
    report = check_citations(args.root, text)
    print(json.dumps(report, ensure_ascii=False, indent=2))

    validity = report["citation_validity"]
    if validity is not None and validity < args.min_validity:
        print(f"CITATIONS_FAIL validity {validity} < {args.min_validity}")
        return 1
    print("CITATIONS_OK")
    return 0


def check_citations(root: Path, text: str) -> dict[str, Any]:
    cited = sorted(set(CITATION_RE.findall(text)))
    valid: list[str] = []
    unknown: list[str] = []
    unverifiable: list[str] = []
    with QueryEngine(root) as engine:
        for citation in cited:
            prefix = citation.split("_", 1)[0]
            table, id_column = PREFIX_TABLES[prefix]
            if table not in engine.tables or id_column not in engine.columns.get(table, set()):
                unverifiable.append(citation)
                continue
            row = engine.conn.execute(
                f"select 1 from src.{quote_identifier(table)} where {quote_identifier(id_column)} = ? limit 1",
                (citation,),
            ).fetchone()
            (valid if row else unknown).append(citation)

    verifiable = len(valid) + len(unknown)
    return {
        "cited": cited,
        "valid_ids": valid,
        "unknown_ids": unknown,
        "unverifiable_ids": unverifiable,
        "citation_count": len(cited),
        "citation_validity": round(len(valid) / verifiable, 4) if verifiable else None,
    }


if __name__ == "__main__":
    raise SystemExit(main())
