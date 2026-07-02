from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path(".runtime") / "researchkb"
EXAMPLES_DIR = Path("examples")
DEMO_CREATED_AT = "2026-01-01T00:00:00+00:00"

# Referenced by the failure-case example (linked_runs) and the good-answer
# example, so the demo database keeps every cited source ID resolvable.
NEGATIVE_RUN = {
    "run_id": "run_example_negative_001",
    "project": "Example Research Project",
    "experiment": "reuse-only decoding quality check",
    "status": "completed_negative",
    "dataset": "synthetic-repeated-prefix",
    "model": "example-model",
    "seed": 42,
    "config_ref": "configs/reuse-only-decoding.synthetic.json",
    "metrics": {
        "quality_retention": 0.71,
        "latency_ms": 96.0,
        "sample_count": 50,
    },
    "failure_type": "quality_below_threshold",
    "decision": "redesign",
    "next_action": "Validate prompt-template compatibility before reuse.",
    "artifacts": ["metrics.json"],
    "created_at": "2025-12-31T00:00:00+00:00",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed a synthetic ResearchKB demo SQLite database from examples/.")
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help="ResearchKB root. Defaults to .runtime/researchkb.",
    )
    parser.add_argument("--examples", type=Path, default=EXAMPLES_DIR, help="Examples directory.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing database outside .runtime.")
    parser.add_argument(
        "--include-run",
        action="append",
        type=Path,
        default=[],
        help="Additional run_record.json file to include in experiment_runs. Can be passed more than once.",
    )
    args = parser.parse_args()

    db_path = seed_demo_db(args.root, args.examples, force=args.force, include_runs=args.include_run)
    print(f"DEMO_DB_OK {db_path}")
    return 0


def seed_demo_db(
    root: Path,
    examples_dir: Path,
    force: bool = False,
    include_runs: list[Path] | None = None,
) -> Path:
    root = root.resolve()
    db_path = root / "db" / "literature.sqlite"
    if db_path.exists():
        if not force and ".runtime" not in db_path.parts:
            raise FileExistsError(f"Refusing to overwrite existing non-runtime database: {db_path}")
        db_path.unlink()

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        create_tables(conn)
        seed_records(conn, examples_dir, include_runs=include_runs or [])
        conn.commit()
    finally:
        conn.close()
    return db_path


def create_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table papers(
            paper_id text primary key,
            title text not null,
            authors_json text,
            year integer,
            venue text,
            doi text,
            arxiv_id text,
            url text,
            tags_json text,
            created_at text
        );

        create table chunks(
            chunk_id text primary key,
            paper_id text,
            source_type text not null,
            section text,
            locator text,
            text text not null,
            embedding_ref text,
            created_at text
        );

        create table claims(
            claim_id text primary key,
            claim_type text not null,
            statement text not null,
            paper_id text,
            chunk_id text,
            confidence real,
            created_by text,
            created_at text
        );

        create table evidence_links(
            evidence_id text primary key,
            source_type text not null,
            source_id text not null,
            paper_id text,
            chunk_id text,
            run_id text,
            problem_id text,
            locator text,
            quote_or_snippet text,
            confidence real,
            created_at text
        );

        create table experiment_runs(
            run_id text primary key,
            project text not null,
            experiment text not null,
            status text not null,
            dataset text,
            model text,
            seed text,
            config_ref text,
            metrics_json text,
            artifacts_json text,
            failure_type text,
            decision text,
            next_action text,
            created_at text
        );

        create table problem_cases(
            problem_id text primary key,
            symptom text not null,
            context_json text,
            suspected_causes_json text,
            tried_fixes_json text,
            final_solution text,
            linked_runs_json text,
            linked_papers_json text,
            confidence real,
            created_at text
        );
        """
    )


def seed_records(conn: sqlite3.Connection, examples_dir: Path, include_runs: list[Path]) -> None:
    created_at = DEMO_CREATED_AT
    paper = read_json(examples_dir / "paper-memory" / "paper.json")
    chunk = read_json(examples_dir / "paper-memory" / "chunk.json")
    claim = read_json(examples_dir / "paper-memory" / "claim.json")
    evidence = read_json(examples_dir / "paper-memory" / "evidence_link.json")
    runs = [read_json(examples_dir / "smoke-run" / "metrics.json"), dict(NEGATIVE_RUN)]
    standardized_run = examples_dir / "standardized-run" / "run_record.json"
    if standardized_run.exists():
        runs.append(read_json(standardized_run))
    for run_path in include_runs:
        runs.append(read_json(run_path))
    problem = read_json(examples_dir / "failure-case" / "problem_case.json")

    conn.execute(
        """
        insert into papers values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            paper["paper_id"],
            paper["title"],
            dumps(paper.get("authors", [])),
            paper.get("year"),
            paper.get("venue"),
            paper.get("doi"),
            paper.get("arxiv_id"),
            paper.get("url"),
            dumps(paper.get("tags", [])),
            created_at,
        ),
    )
    conn.execute(
        "insert into chunks values (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            chunk["chunk_id"],
            chunk.get("paper_id"),
            chunk["source_type"],
            chunk.get("section"),
            chunk.get("locator"),
            chunk["text"],
            chunk.get("embedding_ref"),
            created_at,
        ),
    )
    conn.execute(
        "insert into claims values (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            claim["claim_id"],
            claim["claim_type"],
            claim["statement"],
            claim.get("paper_id"),
            claim.get("chunk_id"),
            claim.get("confidence"),
            claim.get("created_by"),
            created_at,
        ),
    )
    conn.execute(
        "insert into evidence_links values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            evidence["evidence_id"],
            evidence["source_type"],
            evidence["source_id"],
            evidence.get("paper_id"),
            evidence.get("chunk_id"),
            evidence.get("run_id"),
            evidence.get("problem_id"),
            evidence.get("locator"),
            evidence.get("quote_or_snippet"),
            evidence.get("confidence"),
            created_at,
        ),
    )
    for run in runs:
        insert_experiment_run(conn, run, created_at)
    conn.execute(
        "insert into problem_cases values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            problem["problem_id"],
            problem["symptom"],
            dumps(problem.get("context", {})),
            dumps(problem.get("suspected_causes", [])),
            dumps(problem.get("tried_fixes", [])),
            problem.get("final_solution"),
            dumps(problem.get("linked_runs", [])),
            dumps(problem.get("linked_papers", [])),
            problem.get("confidence"),
            created_at,
        ),
    )


def insert_experiment_run(conn: sqlite3.Connection, run: dict[str, Any], created_at: str) -> None:
    conn.execute(
        "insert or replace into experiment_runs values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            run.get("run_id", "run_smoke_001"),
            run["project"],
            run["experiment"],
            run["status"],
            run.get("dataset"),
            run.get("model"),
            normalize_seed(run.get("seed")),
            run.get("config_ref"),
            dumps(run.get("metrics", {})),
            dumps(run.get("artifacts", [])),
            run.get("failure_type"),
            run.get("decision"),
            run.get("next_action"),
            run.get("created_at", created_at),
        ),
    )


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def normalize_seed(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


if __name__ == "__main__":
    raise SystemExit(main())
