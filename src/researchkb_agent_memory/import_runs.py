"""Import standardized experiment run records into a ResearchKB SQLite database.

Writes are explicit: the command defaults to dry-run mode and only modifies the
database when `--write` is supplied.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path(".runtime") / "researchkb"
RUN_TABLE_COLUMNS = {
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
}
REQUIRED_RECORD_FIELDS = ("project", "experiment", "run_id", "status", "metrics")
STATUS_VALUES = {"running", "completed_positive", "completed_negative", "failed"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import standardized run_record.json files into experiment_runs."
    )
    parser.add_argument("paths", nargs="+", type=Path, help="run_record.json files or directories containing them.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="ResearchKB root.")
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Recursively search directories for run_record.json. Without this, only one level is scanned.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Actually write to SQLite. Omit for dry-run planning.",
    )
    args = parser.parse_args(argv)

    summary = import_run_records(
        root=args.root,
        paths=args.paths,
        write=args.write,
        recursive=args.recursive,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["invalid"] == 0 else 1


def import_run_records(
    root: Path,
    paths: list[Path],
    write: bool = False,
    recursive: bool = False,
) -> dict[str, Any]:
    root = root.resolve()
    db_path = root / "db" / "literature.sqlite"
    record_paths = discover_run_records(paths, recursive=recursive)
    rows: list[dict[str, Any]] = []
    valid_records: list[tuple[Path, dict[str, Any]]] = []

    for record_path in record_paths:
        try:
            record = read_run_record(record_path)
            validate_run_record(record)
        except Exception as exc:
            rows.append(
                {
                    "path": safe_path(record_path),
                    "run_id": None,
                    "action": "invalid",
                    "error": str(exc),
                }
            )
            continue
        valid_records.append((record_path, record))

    existing_ids: set[str] = set()
    if db_path.exists() and valid_records:
        with sqlite3.connect(db_path) as conn:
            if table_exists(conn, "experiment_runs"):
                existing_ids = existing_run_ids(conn)

    for record_path, record in valid_records:
        action = "update" if str(record["run_id"]) in existing_ids else "insert"
        rows.append(
            {
                "path": safe_path(record_path),
                "run_id": record["run_id"],
                "project": record["project"],
                "experiment": record["experiment"],
                "status": record["status"],
                "action": action if write else f"would_{action}",
            }
        )

    inserted = 0
    updated = 0
    if write and valid_records:
        if not db_path.exists():
            raise FileNotFoundError(f"ResearchKB database not found: {db_path}")
        with sqlite3.connect(db_path) as conn:
            ensure_importable_schema(conn)
            created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            existing_ids = existing_run_ids(conn)
            for _record_path, record in valid_records:
                if str(record["run_id"]) in existing_ids:
                    updated += 1
                else:
                    inserted += 1
                upsert_experiment_run(conn, record, created_at)
            conn.commit()

    invalid = sum(1 for row in rows if row["action"] == "invalid")
    would_insert = sum(1 for row in rows if row["action"] == "would_insert")
    would_update = sum(1 for row in rows if row["action"] == "would_update")
    return {
        "root": str(root),
        "db_path": str(db_path),
        "write": write,
        "discovered": len(record_paths),
        "valid": len(valid_records),
        "invalid": invalid,
        "inserted": inserted,
        "updated": updated,
        "would_insert": would_insert,
        "would_update": would_update,
        "records": rows,
    }


def discover_run_records(paths: list[Path], recursive: bool = False) -> list[Path]:
    records: list[Path] = []
    seen: set[Path] = set()
    for raw_path in paths:
        path = raw_path.expanduser()
        candidates = candidate_run_records(path, recursive=recursive)
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            records.append(candidate)
    return records


def candidate_run_records(path: Path, recursive: bool) -> list[Path]:
    if path.is_file():
        return [path]
    if not path.exists():
        return [path]
    direct = path / "run_record.json"
    if direct.exists():
        return [direct]
    if recursive:
        return sorted(item for item in path.rglob("run_record.json") if item.is_file())
    return sorted(item for item in path.glob("*/run_record.json") if item.is_file())


def read_run_record(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Run record not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("run_record.json must contain a JSON object")
    return data


def validate_run_record(record: dict[str, Any]) -> None:
    missing = [field for field in REQUIRED_RECORD_FIELDS if field not in record]
    if missing:
        raise ValueError("missing required fields: " + ", ".join(missing))
    for field in ("project", "experiment", "run_id", "status"):
        if not isinstance(record.get(field), str) or not record[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    if record["status"] not in STATUS_VALUES:
        raise ValueError(f"status must be one of: {', '.join(sorted(STATUS_VALUES))}")
    if not isinstance(record.get("metrics"), dict):
        raise ValueError("metrics must be a JSON object")
    if "config_ref" in record and is_absolute_path_string(record.get("config_ref")):
        raise ValueError("config_ref must not be a machine-local absolute path")
    seed = record.get("seed")
    if seed is not None and not isinstance(seed, (int, str)):
        raise ValueError("seed must be an integer, string, or null")
    artifacts = record.get("artifacts", [])
    if artifacts is not None and (
        not isinstance(artifacts, list) or any(not isinstance(item, str) for item in artifacts)
    ):
        raise ValueError("artifacts must be a list of strings")


def is_absolute_path_string(value: Any) -> bool:
    return isinstance(value, str) and re.match(r"^(?:[A-Za-z]:[\\/]|/)", value) is not None


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "select 1 from sqlite_master where type='table' and name=? limit 1",
        (table,),
    ).fetchone()
    return row is not None


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"pragma table_info({quote_identifier(table)})").fetchall()
    return {str(row[1]) for row in rows}


def ensure_importable_schema(conn: sqlite3.Connection) -> None:
    if not table_exists(conn, "experiment_runs"):
        raise RuntimeError("experiment_runs table does not exist; initialize or map the schema first")
    columns = table_columns(conn, "experiment_runs")
    missing = sorted(RUN_TABLE_COLUMNS - columns)
    if missing:
        raise RuntimeError("experiment_runs is missing required columns: " + ", ".join(missing))


def existing_run_ids(conn: sqlite3.Connection) -> set[str]:
    if not table_exists(conn, "experiment_runs"):
        return set()
    if "run_id" not in table_columns(conn, "experiment_runs"):
        return set()
    rows = conn.execute("select run_id from experiment_runs").fetchall()
    return {str(row[0]) for row in rows if row[0] is not None}


def upsert_experiment_run(conn: sqlite3.Connection, record: dict[str, Any], created_at: str) -> None:
    conn.execute(
        """
        insert into experiment_runs(
            run_id, project, experiment, status, dataset, model, seed, config_ref,
            metrics_json, artifacts_json, failure_type, decision, next_action, created_at
        )
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        on conflict(run_id) do update set
            project=excluded.project,
            experiment=excluded.experiment,
            status=excluded.status,
            dataset=excluded.dataset,
            model=excluded.model,
            seed=excluded.seed,
            config_ref=excluded.config_ref,
            metrics_json=excluded.metrics_json,
            artifacts_json=excluded.artifacts_json,
            failure_type=excluded.failure_type,
            decision=excluded.decision,
            next_action=excluded.next_action,
            created_at=excluded.created_at
        """,
        (
            record["run_id"],
            record["project"],
            record["experiment"],
            record["status"],
            record.get("dataset"),
            record.get("model"),
            normalize_seed(record.get("seed")),
            record.get("config_ref"),
            dumps(record.get("metrics", {})),
            dumps(record.get("artifacts", [])),
            record.get("failure_type"),
            record.get("decision"),
            record.get("next_action"),
            record.get("created_at") or created_at,
        ),
    )


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def normalize_seed(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def quote_identifier(name: str) -> str:
    escaped = name.replace('"', '""')
    return f'"{escaped}"'


def safe_path(path: Path) -> str:
    return path.as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
