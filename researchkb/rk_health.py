from __future__ import annotations

import argparse
import json
import os
import platform
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REQUIRED_TABLES = ["papers", "chunks", "claims", "problem_cases", "experiment_runs"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Report ResearchKB workflow health.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("--root", type=Path, help="ResearchKB root directory. Overrides RESEARCHKB_ROOT.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Require the mature readiness level before reporting the library as usable.",
    )
    args = parser.parse_args()

    report = build_report(root=resolve_root(args.root), strict=args.strict)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_text_report(report)


def resolve_root(root: Path | None = None) -> Path:
    if root is not None:
        return root.expanduser().resolve()
    env_root = os.environ.get("RESEARCHKB_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()
    return (Path.home() / "ResearchKB").resolve()


def build_report(root: Path | None = None, strict: bool = False, check_scheduled: bool = True) -> dict[str, Any]:
    root = resolve_root(root)
    db_path = root / "db" / "literature.sqlite"
    paths_file = root / "config" / "auto_harvest_paths.txt"
    log_file = root / "logs" / "auto_harvest.log"
    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "root": str(root),
        "strict": strict,
        "scheduled_task": scheduled_task_status(check=check_scheduled),
        "watch_paths": watch_paths(paths_file),
        "auto_harvest_log": harvest_log_status(log_file),
        "database": database_status(db_path),
        "judgement": {},
    }
    report["judgement"] = judge(report, strict=strict)
    return report


def scheduled_task_status(check: bool = True) -> dict[str, Any]:
    if not check:
        return {"checked": False, "skipped": True, "reason": "disabled"}
    if platform.system().lower() != "windows":
        return {"checked": False, "skipped": True, "reason": "non_windows"}

    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        (
            "try { "
            "$t=Get-ScheduledTask -TaskName 'ResearchKB-AutoHarvest'; "
            "$i=Get-ScheduledTaskInfo -TaskName 'ResearchKB-AutoHarvest'; "
            "[pscustomobject]@{checked=$true;exists=$true;state=$t.State.ToString();"
            "last_run=$i.LastRunTime.ToString('yyyy-MM-dd HH:mm:ss');"
            "last_result=$i.LastTaskResult;"
            "next_run=$i.NextRunTime.ToString('yyyy-MM-dd HH:mm:ss');"
            "missed=$i.NumberOfMissedRuns} | ConvertTo-Json -Compress "
            "} catch { "
            "[pscustomobject]@{checked=$true;exists=$false;error=$_.Exception.Message} "
            "| ConvertTo-Json -Compress }"
        ),
    ]
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
        if proc.stdout.strip():
            return json.loads(proc.stdout)
        return {"checked": True, "exists": False, "error": proc.stderr.strip() or "No scheduled task output."}
    except Exception as exc:
        return {"checked": True, "exists": False, "error": str(exc)}


def watch_paths(paths_file: Path) -> list[dict[str, Any]]:
    if not paths_file.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw in paths_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        path = Path(line)
        rows.append({"path": line, "exists": path.exists()})
    return rows


def harvest_log_status(log_file: Path) -> dict[str, Any]:
    if not log_file.exists():
        return {"exists": False}
    lines = read_text_fallback(log_file).splitlines()
    started = _last_matching_line(lines, "ResearchKB auto harvest started")
    finished = _last_matching_line(lines, "ResearchKB auto harvest finished")
    parse_failed = _last_json_field(lines, "parse_failed")
    recorded = _last_json_field(lines, "recorded")
    return {
        "exists": True,
        "size_bytes": log_file.stat().st_size,
        "recent_started": started,
        "recent_finished": finished,
        "last_recorded": recorded,
        "last_parse_failed": parse_failed,
    }


def read_text_fallback(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8", "utf-16", "utf-16-le"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _last_matching_line(lines: list[str], needle: str) -> str:
    for line in reversed(lines):
        if needle in line:
            return line
    return ""


def _last_json_field(lines: list[str], field: str) -> int | None:
    needle = f'"{field}"'
    for line in reversed(lines):
        if needle not in line:
            continue
        try:
            fragment = line[line.index(needle) :]
            return int(fragment.split(":", 1)[1].split(",", 1)[0].strip().rstrip("}"))
        except Exception:
            return None
    return None


def database_status(db_path: Path) -> dict[str, Any]:
    if not db_path.exists():
        return {
            "exists": False,
            "path": str(db_path),
            "tables": [],
            "missing_tables": REQUIRED_TABLES,
            "counts": {},
            "run_stats": {},
            "case_stats": {},
            "evidence_link_count": None,
            "latest_runs": [],
        }

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        tables = list_tables(conn)
        counts = {table: count_rows(conn, table) for table in REQUIRED_TABLES if table in tables}
        missing_tables = [table for table in REQUIRED_TABLES if table not in tables]
        run_stats = experiment_run_stats(conn) if "experiment_runs" in tables else {}
        case_stats = problem_case_stats(conn) if "problem_cases" in tables else {}
        evidence_link_count = count_rows(conn, "evidence_links") if "evidence_links" in tables else None
        latest_runs = latest_experiment_runs(conn) if "experiment_runs" in tables else []
        return {
            "exists": True,
            "path": str(db_path),
            "size_mb": round(db_path.stat().st_size / 1024 / 1024, 2),
            "tables": sorted(tables),
            "missing_tables": missing_tables,
            "counts": counts,
            "run_stats": run_stats,
            "case_stats": case_stats,
            "evidence_link_count": evidence_link_count,
            "latest_runs": latest_runs,
        }
    finally:
        conn.close()


def list_tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("select name from sqlite_master where type='table'").fetchall()
    return {str(row["name"]) for row in rows}


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"pragma table_info({quote_identifier(table)})").fetchall()
    return {str(row["name"]) for row in rows}


def count_rows(conn: sqlite3.Connection, table: str) -> int:
    row = conn.execute(f"select count(*) as n from {quote_identifier(table)}").fetchone()
    return int(row["n"])


def quote_identifier(name: str) -> str:
    escaped = name.replace('"', '""')
    return f'"{escaped}"'


def experiment_run_stats(conn: sqlite3.Connection) -> dict[str, Any]:
    columns = table_columns(conn, "experiment_runs")
    rows = [dict(row) for row in conn.execute("select * from experiment_runs").fetchall()]
    total = len(rows)
    with_metrics = sum(
        1
        for row in rows
        if has_nonempty_value(row, "metrics_json", columns) or has_nonempty_value(row, "metrics", columns)
    )
    with_logs = sum(
        1
        for row in rows
        if has_nonempty_value(row, "log_path", columns) or has_nonempty_value(row, "logs", columns)
    )
    failure_labeled = sum(1 for row in rows if row_is_failure_labeled(row, columns))
    kv_runs = (
        sum(1 for row in rows if str(row.get("project", "")).lower() == "kv cache reuse")
        if "project" in columns
        else 0
    )
    created_values = (
        [str(row.get("created_at")) for row in rows if row.get("created_at")] if "created_at" in columns else []
    )
    return {
        "total": total,
        "kv_runs": kv_runs,
        "with_metrics": with_metrics,
        "with_logs": with_logs,
        "failure_labeled": failure_labeled,
        "first_seen": min(created_values) if created_values else None,
        "last_seen": max(created_values) if created_values else None,
        "columns": sorted(columns),
    }


def problem_case_stats(conn: sqlite3.Connection) -> dict[str, Any]:
    columns = table_columns(conn, "problem_cases")
    rows = [dict(row) for row in conn.execute("select * from problem_cases").fetchall()]
    total = len(rows)
    documented = sum(1 for row in rows if has_nonempty_value(row, "final_solution", columns))
    return {"total": total, "documented": documented, "open": total - documented}


def has_nonempty_value(row: dict[str, Any], key: str, columns: set[str]) -> bool:
    if key not in columns:
        return False
    value = row.get(key)
    if value is None:
        return False
    return str(value).strip() not in ("", "{}")


def row_is_failure_labeled(row: dict[str, Any], columns: set[str]) -> bool:
    if has_nonempty_value(row, "failure_type", columns):
        return True
    if "status" in columns:
        return "fail" in str(row.get("status", "")).lower()
    return False


def latest_experiment_runs(conn: sqlite3.Connection, limit: int = 5) -> list[dict[str, Any]]:
    columns = table_columns(conn, "experiment_runs")
    selected = [
        col
        for col in ["run_id", "project", "experiment", "status", "failure_type", "created_at", "log_path"]
        if col in columns
    ]
    if not selected:
        return []
    order_clause = " order by created_at desc" if "created_at" in columns else ""
    sql = f"select {', '.join(quote_identifier(col) for col in selected)} from experiment_runs{order_clause} limit ?"
    return [dict(row) for row in conn.execute(sql, (limit,)).fetchall()]


def judge(report: dict[str, Any], strict: bool = False) -> dict[str, Any]:
    db = report["database"]
    counts = db.get("counts", {})
    run_stats = db.get("run_stats", {})
    total_runs = int(run_stats.get("total") or 0)
    with_metrics = int(run_stats.get("with_metrics") or 0)
    metrics_coverage = (with_metrics / total_runs) if total_runs else 0.0
    existing_watch_paths = sum(1 for item in report["watch_paths"] if item.get("exists"))
    level = readiness_level(counts, total_runs, with_metrics, metrics_coverage, db.get("exists", False))
    usable_levels = ("mature",) if strict else ("usable", "mature")
    can_query_runs = total_runs > 0
    can_query_papers = int(counts.get("papers", 0)) > 0 and int(counts.get("chunks", 0)) > 0
    can_query_failure_cases = int(counts.get("problem_cases", 0)) > 0
    effectiveness = effectiveness_metrics(db, metrics_coverage)
    next_actions = next_actions_for(
        level,
        db,
        counts,
        total_runs,
        with_metrics,
        existing_watch_paths,
        metrics_coverage,
        effectiveness,
    )
    return {
        "level": level,
        "usable": level in usable_levels,
        "can_query_runs": can_query_runs,
        "can_query_papers": can_query_papers,
        "can_query_failure_cases": can_query_failure_cases,
        "watch_path_count": existing_watch_paths,
        "metrics_coverage": round(metrics_coverage, 4),
        "effectiveness": effectiveness,
        "missing_tables": db.get("missing_tables", []),
        "next_actions": next_actions,
    }


def effectiveness_metrics(db: dict[str, Any], metrics_coverage: float) -> dict[str, Any]:
    """Quantified effectiveness signals for the experiment- and failure-memory loop.

    - metrics_coverage: fraction of runs that recorded parseable metrics.
    - failure_documentation_rate: fraction of problem cases with a final_solution.
    - evidence_density: evidence links per claim (provenance strength).
    - run_freshness_days: days since the newest recorded run (staleness).
    """
    case_stats = db.get("case_stats", {}) or {}
    case_total = int(case_stats.get("total") or 0)
    documented = int(case_stats.get("documented") or 0)
    failure_documentation_rate = round(documented / case_total, 4) if case_total else None

    counts = db.get("counts", {}) or {}
    claims = int(counts.get("claims", 0))
    evidence_links = db.get("evidence_link_count")
    evidence_density = round(int(evidence_links) / claims, 4) if evidence_links is not None and claims else None

    run_stats = db.get("run_stats", {}) or {}
    return {
        "metrics_coverage": round(metrics_coverage, 4),
        "failure_documentation_rate": failure_documentation_rate,
        "open_failure_cases": int(case_stats.get("open") or 0) if case_total else None,
        "evidence_density": evidence_density,
        "run_freshness_days": days_since(run_stats.get("last_seen")),
    }


def days_since(timestamp: Any) -> float | None:
    if not timestamp:
        return None
    try:
        parsed = datetime.fromisoformat(str(timestamp))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - parsed
    return round(delta.total_seconds() / 86400, 2)


def readiness_level(
    counts: dict[str, int],
    total_runs: int,
    with_metrics: int,
    metrics_coverage: float,
    db_exists: bool,
) -> str:
    if not db_exists:
        return "empty"
    if int(counts.get("claims", 0)) >= 3000 and int(counts.get("problem_cases", 0)) >= 40 and metrics_coverage >= 0.7:
        return "mature"
    if int(counts.get("papers", 0)) >= 20 and int(counts.get("chunks", 0)) >= 500 and total_runs >= 5:
        return "usable"
    if total_runs >= 1 and with_metrics >= 1:
        return "smoke"
    return "empty"


def next_actions_for(
    level: str,
    db: dict[str, Any],
    counts: dict[str, int],
    total_runs: int,
    with_metrics: int,
    existing_watch_paths: int,
    metrics_coverage: float,
    effectiveness: dict[str, Any] | None = None,
) -> list[str]:
    actions: list[str] = []
    effectiveness = effectiveness or {}
    if not db.get("exists"):
        actions.append("Create or point --root to a ResearchKB directory containing db/literature.sqlite.")
    if db.get("missing_tables"):
        actions.append("Create or map missing tables: " + ", ".join(db["missing_tables"]))
    if total_runs == 0:
        actions.append("Run rk-harvest on one experiment output folder.")
    elif with_metrics == 0:
        actions.append("Add metrics_json or metrics data to at least one experiment run.")
    if existing_watch_paths == 0:
        actions.append("Add one narrow project output folder to config/auto_harvest_paths.txt.")
    if level == "smoke" and int(counts.get("papers", 0)) == 0:
        actions.append("Ingest at least one paper batch or Zotero export to enable literature queries.")
    if level in ("smoke", "usable") and metrics_coverage < 0.7:
        actions.append("Increase metrics coverage by emitting metrics.json or METRIC key=value for more runs.")
    if effectiveness.get("open_failure_cases"):
        actions.append("Document final_solution for open problem cases to make failure memory reusable.")
    if not actions:
        actions.append("No immediate action required.")
    return actions


def print_text_report(report: dict[str, Any]) -> None:
    db = report["database"]
    judgement = report["judgement"]
    print(f"ResearchKB health @ {report['generated_at']}")
    print(f"Root: {report['root']}")
    print(f"Level: {judgement.get('level')}")
    print("")
    print("[scheduled task]")
    task = report["scheduled_task"]
    if task.get("skipped"):
        print(f"skipped={task.get('skipped')} reason={task.get('reason')}")
    else:
        print(
            (
                "exists={exists} state={state} last_result={last_result} "
                "last_run={last_run} next_run={next_run} missed={missed}"
            ).format(
                **{
                    "exists": task.get("exists"),
                    "state": task.get("state"),
                    "last_result": task.get("last_result"),
                    "last_run": task.get("last_run"),
                    "next_run": task.get("next_run"),
                    "missed": task.get("missed"),
                }
            )
        )
    print("")
    print("[watch paths]")
    if report["watch_paths"]:
        for item in report["watch_paths"]:
            print(f"{'OK' if item['exists'] else 'MISS'} {item['path']}")
    else:
        print("none")
    print("")
    print("[auto harvest log]")
    log = report["auto_harvest_log"]
    print(
        f"exists={log.get('exists')} "
        f"last_recorded={log.get('last_recorded')} "
        f"last_parse_failed={log.get('last_parse_failed')}"
    )
    print(f"recent_started={log.get('recent_started')}")
    print(f"recent_finished={log.get('recent_finished')}")
    print("")
    print("[database]")
    print(f"exists={db.get('exists')} size_mb={db.get('size_mb')}")
    print(f"missing_tables={db.get('missing_tables')}")
    print(json.dumps(db.get("counts", {}), ensure_ascii=False))
    print(json.dumps(db.get("run_stats", {}), ensure_ascii=False))
    print("")
    print("[judgement]")
    print(json.dumps(judgement, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
