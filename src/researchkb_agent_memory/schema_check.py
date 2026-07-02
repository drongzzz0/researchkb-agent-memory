"""Check whether a ResearchKB SQLite database can accept the public importers.

This command is read-only. It verifies table and column availability before a
user runs write-capable commands such as `import-runs --write`,
`import-bibtex --write`, or `import-notes --write`.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path(".runtime") / "researchkb"

REQUIRED_TABLES: dict[str, set[str]] = {
    "papers": {
        "paper_id",
        "title",
        "authors_json",
        "year",
        "venue",
        "doi",
        "arxiv_id",
        "url",
        "tags_json",
        "created_at",
    },
    "chunks": {
        "chunk_id",
        "paper_id",
        "source_type",
        "section",
        "locator",
        "text",
        "embedding_ref",
        "created_at",
    },
    "claims": {
        "claim_id",
        "claim_type",
        "statement",
        "paper_id",
        "chunk_id",
        "confidence",
        "created_by",
        "created_at",
    },
    "evidence_links": {
        "evidence_id",
        "source_type",
        "source_id",
        "paper_id",
        "chunk_id",
        "run_id",
        "problem_id",
        "locator",
        "quote_or_snippet",
        "confidence",
        "created_at",
    },
    "experiment_runs": {
        "run_id",
        "project",
        "experiment",
        "status",
        "dataset",
        "model",
        "seed",
        "config_ref",
        "metrics_json",
        "artifacts_json",
        "failure_type",
        "decision",
        "next_action",
        "created_at",
    },
    "problem_cases": {
        "problem_id",
        "symptom",
        "context_json",
        "suspected_causes_json",
        "tried_fixes_json",
        "final_solution",
        "linked_runs_json",
        "linked_papers_json",
        "confidence",
        "created_at",
    },
}

IMPORTER_TABLES = {
    "import-runs": {"experiment_runs"},
    "import-bibtex": {"papers"},
    "import-notes": {"chunks", "claims", "evidence_links"},
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check ResearchKB SQLite schema readiness.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="ResearchKB root.")
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="SQLite database path. Defaults to <root>/db/literature.sqlite.",
    )
    args = parser.parse_args(argv)

    summary = check_schema(root=args.root, db_path=args.db)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["ok"] else 1


def check_schema(root: Path, db_path: Path | None = None) -> dict[str, Any]:
    root = root.resolve()
    resolved_db = (db_path or root / "db" / "literature.sqlite").resolve()
    if not resolved_db.exists():
        return {
            "root": str(root),
            "db_path": str(resolved_db),
            "ok": False,
            "database_exists": False,
            "missing_tables": sorted(REQUIRED_TABLES),
            "tables": table_report_for_missing_database(),
            "import_ready": importer_readiness({table: False for table in REQUIRED_TABLES}),
        }

    with sqlite3.connect(resolved_db) as conn:
        tables = inspect_tables(conn)

    table_ok = {table: report["ok"] for table, report in tables.items()}
    missing_tables = [table for table, ok in table_ok.items() if not ok and not tables[table]["exists"]]
    missing_columns = {
        table: report["missing_columns"]
        for table, report in tables.items()
        if report["exists"] and report["missing_columns"]
    }
    ok = all(table_ok.values())
    return {
        "root": str(root),
        "db_path": str(resolved_db),
        "ok": ok,
        "database_exists": True,
        "missing_tables": missing_tables,
        "missing_columns": missing_columns,
        "tables": tables,
        "import_ready": importer_readiness(table_ok),
    }


def table_report_for_missing_database() -> dict[str, dict[str, Any]]:
    return {
        table: {
            "exists": False,
            "ok": False,
            "required_columns": sorted(required_columns),
            "present_columns": [],
            "missing_columns": sorted(required_columns),
            "extra_columns": [],
        }
        for table, required_columns in REQUIRED_TABLES.items()
    }


def inspect_tables(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    return {table: inspect_table(conn, table, required_columns) for table, required_columns in REQUIRED_TABLES.items()}


def inspect_table(conn: sqlite3.Connection, table: str, required_columns: set[str]) -> dict[str, Any]:
    if not table_exists(conn, table):
        return {
            "exists": False,
            "ok": False,
            "required_columns": sorted(required_columns),
            "present_columns": [],
            "missing_columns": sorted(required_columns),
            "extra_columns": [],
        }
    present_columns = table_columns(conn, table)
    missing_columns = sorted(required_columns - present_columns)
    return {
        "exists": True,
        "ok": not missing_columns,
        "required_columns": sorted(required_columns),
        "present_columns": sorted(present_columns),
        "missing_columns": missing_columns,
        "extra_columns": sorted(present_columns - required_columns),
    }


def importer_readiness(table_ok: dict[str, bool]) -> dict[str, bool]:
    return {
        importer: all(table_ok.get(table, False) for table in tables)
        for importer, tables in IMPORTER_TABLES.items()
    }


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "select 1 from sqlite_master where type='table' and name=? limit 1",
        (table,),
    ).fetchone()
    return row is not None


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"pragma table_info({quote_identifier(table)})").fetchall()
    return {str(row[1]) for row in rows}


def quote_identifier(name: str) -> str:
    escaped = name.replace('"', '""')
    return f'"{escaped}"'


if __name__ == "__main__":
    raise SystemExit(main())
