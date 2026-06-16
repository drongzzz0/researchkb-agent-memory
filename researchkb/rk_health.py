from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(os.environ.get("RESEARCHKB_ROOT", str(Path.home() / "ResearchKB")))
DB_PATH = ROOT / "db" / "literature.sqlite"
PATHS_FILE = ROOT / "config" / "auto_harvest_paths.txt"
LOG_FILE = ROOT / "logs" / "auto_harvest.log"


def main() -> None:
    parser = argparse.ArgumentParser(description="Report ResearchKB workflow health.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args()

    report = build_report()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_text_report(report)


def build_report() -> dict[str, Any]:
    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "root": str(ROOT),
        "scheduled_task": scheduled_task_status(),
        "watch_paths": watch_paths(),
        "auto_harvest_log": harvest_log_status(),
        "database": database_status(),
        "judgement": {},
    }
    report["judgement"] = judge(report)
    return report


def scheduled_task_status() -> dict[str, Any]:
    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        (
            "try { "
            "$t=Get-ScheduledTask -TaskName 'ResearchKB-AutoHarvest'; "
            "$i=Get-ScheduledTaskInfo -TaskName 'ResearchKB-AutoHarvest'; "
            "[pscustomobject]@{exists=$true;state=$t.State.ToString();"
            "last_run=$i.LastRunTime.ToString('yyyy-MM-dd HH:mm:ss');"
            "last_result=$i.LastTaskResult;"
            "next_run=$i.NextRunTime.ToString('yyyy-MM-dd HH:mm:ss');"
            "missed=$i.NumberOfMissedRuns} | ConvertTo-Json -Compress "
            "} catch { [pscustomobject]@{exists=$false;error=$_.Exception.Message} | ConvertTo-Json -Compress }"
        ),
    ]
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
        if proc.stdout.strip():
            return json.loads(proc.stdout)
        return {"exists": False, "error": proc.stderr.strip() or "No scheduled task output."}
    except Exception as exc:
        return {"exists": False, "error": str(exc)}


def watch_paths() -> list[dict[str, Any]]:
    if not PATHS_FILE.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw in PATHS_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        path = Path(line)
        rows.append({"path": line, "exists": path.exists()})
    return rows


def harvest_log_status() -> dict[str, Any]:
    if not LOG_FILE.exists():
        return {"exists": False}
    lines = read_text_fallback(LOG_FILE).splitlines()
    started = _last_matching_line(lines, "ResearchKB auto harvest started")
    finished = _last_matching_line(lines, "ResearchKB auto harvest finished")
    parse_failed = _last_json_field(lines, "parse_failed")
    recorded = _last_json_field(lines, "recorded")
    return {
        "exists": True,
        "size_bytes": LOG_FILE.stat().st_size,
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
            return int(line.split(":", 1)[1].strip().rstrip(","))
        except Exception:
            return None
    return None


def database_status() -> dict[str, Any]:
    if not DB_PATH.exists():
        return {"exists": False}
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        counts = {}
        for table in ["papers", "chunks", "claims", "problem_cases", "experiment_runs"]:
            counts[table] = conn.execute(f"select count(*) as n from {table}").fetchone()["n"]
        run_stats = dict(
            conn.execute(
                """
                select
                  count(*) as total,
                  sum(case when project='KV Cache Reuse' then 1 else 0 end) as kv_runs,
                  sum(case when metrics_json is not null and trim(metrics_json) not in ('','{}') then 1 else 0 end) as with_metrics,
                  sum(case when log_path is not null and trim(log_path)!='' then 1 else 0 end) as with_logs,
                  sum(case when status like '%fail%' or failure_type is not null and trim(failure_type)!='' then 1 else 0 end) as failure_labeled,
                  min(created_at) as first_seen,
                  max(created_at) as last_seen
                from experiment_runs
                """
            ).fetchone()
        )
        latest_runs = [
            dict(row)
            for row in conn.execute(
                """
                select run_id, project, status, failure_type, created_at, log_path
                from experiment_runs
                order by created_at desc
                limit 5
                """
            )
        ]
        return {
            "exists": True,
            "size_mb": round(DB_PATH.stat().st_size / 1024 / 1024, 2),
            "counts": counts,
            "run_stats": run_stats,
            "latest_runs": latest_runs,
        }
    finally:
        conn.close()


def judge(report: dict[str, Any]) -> dict[str, Any]:
    task_ok = bool(report["scheduled_task"].get("exists")) and report["scheduled_task"].get("last_result") == 0
    log_ok = bool(report["auto_harvest_log"].get("exists")) and report["auto_harvest_log"].get("last_parse_failed") in (0, None)
    db = report["database"]
    counts = db.get("counts", {})
    run_stats = db.get("run_stats", {})
    metrics_total = int(run_stats.get("total") or 0)
    with_metrics = int(run_stats.get("with_metrics") or 0)
    metrics_coverage = (with_metrics / metrics_total) if metrics_total else 0.0
    watch_valid = sum(1 for item in report["watch_paths"] if item.get("exists"))
    usable = task_ok and log_ok and counts.get("claims", 0) >= 3000 and counts.get("problem_cases", 0) >= 40
    bottlenecks = []
    if watch_valid < 3:
        bottlenecks.append("watch_paths_too_narrow")
    if metrics_coverage < 0.7:
        bottlenecks.append("low_metrics_coverage")
    return {
        "usable": usable,
        "task_ok": task_ok,
        "log_ok": log_ok,
        "watch_path_count": watch_valid,
        "metrics_coverage": round(metrics_coverage, 4),
        "bottlenecks": bottlenecks,
    }


def print_text_report(report: dict[str, Any]) -> None:
    db = report["database"]
    print(f"ResearchKB health @ {report['generated_at']}")
    print(f"Root: {report['root']}")
    print("")
    print("[scheduled task]")
    task = report["scheduled_task"]
    print(
        "exists={exists} state={state} last_result={last_result} last_run={last_run} next_run={next_run} missed={missed}".format(
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
    for item in report["watch_paths"]:
        print(f"{'OK' if item['exists'] else 'MISS'} {item['path']}")
    print("")
    print("[auto harvest log]")
    log = report["auto_harvest_log"]
    print(f"exists={log.get('exists')} last_recorded={log.get('last_recorded')} last_parse_failed={log.get('last_parse_failed')}")
    print(f"recent_started={log.get('recent_started')}")
    print(f"recent_finished={log.get('recent_finished')}")
    print("")
    print("[database]")
    print(f"exists={db.get('exists')} size_mb={db.get('size_mb')}")
    print(json.dumps(db.get("counts", {}), ensure_ascii=False))
    print(json.dumps(db.get("run_stats", {}), ensure_ascii=False))
    print("")
    print("[judgement]")
    print(json.dumps(report["judgement"], ensure_ascii=False))


if __name__ == "__main__":
    main()
