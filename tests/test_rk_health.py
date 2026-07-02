from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "researchkb" / "rk_health.py"
SPEC = importlib.util.spec_from_file_location("rk_health", MODULE_PATH)
assert SPEC is not None
rk_health = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(rk_health)


def make_db(root: Path) -> sqlite3.Connection:
    db_dir = root / "db"
    db_dir.mkdir(parents=True)
    return sqlite3.connect(db_dir / "literature.sqlite")


def test_health_empty_root(tmp_path: Path) -> None:
    report = rk_health.build_report(root=tmp_path, check_scheduled=False)

    assert report["database"]["exists"] is False
    assert report["judgement"]["level"] == "empty"
    assert "papers" in report["database"]["missing_tables"]
    assert report["judgement"]["can_query_runs"] is False


def test_health_missing_tables(tmp_path: Path) -> None:
    conn = make_db(tmp_path)
    conn.execute("create table unrelated(id text)")
    conn.commit()
    conn.close()

    report = rk_health.build_report(root=tmp_path, check_scheduled=False)

    assert report["database"]["exists"] is True
    assert report["judgement"]["level"] == "empty"
    assert set(report["database"]["missing_tables"]) == set(rk_health.REQUIRED_TABLES)


def test_health_smoke_level(tmp_path: Path) -> None:
    conn = make_db(tmp_path)
    conn.execute("create table experiment_runs(run_id text, metrics_json text, status text, created_at text)")
    conn.execute(
        "insert into experiment_runs values (?, ?, ?, ?)",
        ("run_smoke_001", '{"accuracy": 0.84}', "completed_positive", "2026-01-01T00:00:00"),
    )
    conn.commit()
    conn.close()

    report = rk_health.build_report(root=tmp_path, check_scheduled=False)

    assert report["judgement"]["level"] == "smoke"
    assert report["judgement"]["can_query_runs"] is True
    assert report["database"]["run_stats"]["with_metrics"] == 1


def test_health_usable_level(tmp_path: Path) -> None:
    conn = make_db(tmp_path)
    conn.execute("create table papers(paper_id text)")
    conn.execute("create table chunks(chunk_id text)")
    conn.execute("create table experiment_runs(run_id text, metrics_json text, created_at text)")
    conn.executemany("insert into papers values (?)", [(f"paper_{i}",) for i in range(20)])
    conn.executemany("insert into chunks values (?)", [(f"chunk_{i}",) for i in range(500)])
    conn.executemany(
        "insert into experiment_runs values (?, ?, ?)",
        [(f"run_{i}", '{"accuracy": 0.9}', f"2026-01-0{i + 1}T00:00:00") for i in range(5)],
    )
    conn.commit()
    conn.close()

    report = rk_health.build_report(root=tmp_path, check_scheduled=False)

    assert report["judgement"]["level"] == "usable"
    assert report["judgement"]["usable"] is True
    assert report["judgement"]["can_query_papers"] is True


def test_health_mature_level_in_strict_mode(tmp_path: Path) -> None:
    conn = make_db(tmp_path)
    conn.execute("create table claims(claim_id text)")
    conn.execute("create table problem_cases(problem_id text)")
    conn.execute("create table experiment_runs(run_id text, metrics_json text)")
    conn.executemany("insert into claims values (?)", [(f"claim_{i}",) for i in range(3000)])
    conn.executemany("insert into problem_cases values (?)", [(f"problem_{i}",) for i in range(40)])
    conn.executemany("insert into experiment_runs values (?, ?)", [(f"run_{i}", '{"metric": 1}') for i in range(10)])
    conn.commit()
    conn.close()

    report = rk_health.build_report(root=tmp_path, strict=True, check_scheduled=False)

    assert report["judgement"]["level"] == "mature"
    assert report["judgement"]["usable"] is True
    assert report["judgement"]["metrics_coverage"] == 1.0


def test_health_strict_mode_requires_mature_before_usable(tmp_path: Path) -> None:
    conn = make_db(tmp_path)
    conn.execute("create table papers(paper_id text)")
    conn.execute("create table chunks(chunk_id text)")
    conn.execute("create table experiment_runs(run_id text, metrics_json text, created_at text)")
    conn.executemany("insert into papers values (?)", [(f"paper_{i}",) for i in range(20)])
    conn.executemany("insert into chunks values (?)", [(f"chunk_{i}",) for i in range(500)])
    conn.executemany(
        "insert into experiment_runs values (?, ?, ?)",
        [(f"run_{i}", '{"accuracy": 0.9}', f"2026-01-0{i + 1}T00:00:00") for i in range(5)],
    )
    conn.commit()
    conn.close()

    default_report = rk_health.build_report(root=tmp_path, check_scheduled=False)
    strict_report = rk_health.build_report(root=tmp_path, strict=True, check_scheduled=False)

    assert default_report["judgement"]["level"] == "usable"
    assert default_report["judgement"]["usable"] is True
    assert strict_report["judgement"]["level"] == "usable"
    assert strict_report["judgement"]["usable"] is False


def test_health_effectiveness_metrics(tmp_path: Path) -> None:
    from datetime import datetime, timezone

    conn = make_db(tmp_path)
    conn.execute("create table claims(claim_id text)")
    conn.execute("create table evidence_links(evidence_id text)")
    conn.execute("create table problem_cases(problem_id text, final_solution text)")
    conn.execute("create table experiment_runs(run_id text, metrics_json text, created_at text)")
    conn.executemany("insert into claims values (?)", [(f"claim_{i}",) for i in range(4)])
    conn.executemany("insert into evidence_links values (?)", [(f"evidence_{i}",) for i in range(2)])
    conn.execute("insert into problem_cases values ('problem_1', 'Documented fix.')")
    conn.execute("insert into problem_cases values ('problem_2', null)")
    recent = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.execute("insert into experiment_runs values ('run_1', '{\"accuracy\": 0.9}', ?)", (recent,))
    conn.commit()
    conn.close()

    report = rk_health.build_report(root=tmp_path, check_scheduled=False)

    effectiveness = report["judgement"]["effectiveness"]
    assert effectiveness["failure_documentation_rate"] == 0.5
    assert effectiveness["evidence_density"] == 0.5
    assert effectiveness["metrics_coverage"] == 1.0
    assert effectiveness["run_freshness_days"] is not None
    assert effectiveness["run_freshness_days"] < 1
    assert any("final_solution" in action for action in report["judgement"]["next_actions"])


def test_health_effectiveness_handles_missing_tables(tmp_path: Path) -> None:
    conn = make_db(tmp_path)
    conn.execute("create table experiment_runs(run_id text, metrics_json text)")
    conn.commit()
    conn.close()

    report = rk_health.build_report(root=tmp_path, check_scheduled=False)

    effectiveness = report["judgement"]["effectiveness"]
    assert effectiveness["failure_documentation_rate"] is None
    assert effectiveness["evidence_density"] is None
    assert effectiveness["run_freshness_days"] is None


def test_watch_paths_with_comments(tmp_path: Path) -> None:
    existing = tmp_path / "runs"
    existing.mkdir()
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    paths_file = config_dir / "auto_harvest_paths.txt"
    paths_file.write_text(f"\n# ignored\n{existing}\n{tmp_path / 'missing'}\n", encoding="utf-8")

    rows = rk_health.watch_paths(paths_file)

    assert len(rows) == 2
    assert rows[0]["exists"] is True
    assert rows[1]["exists"] is False


def test_read_utf16_log(tmp_path: Path) -> None:
    log_file = tmp_path / "auto_harvest.log"
    log_file.write_text('ResearchKB auto harvest finished\n{"recorded": 3, "parse_failed": 0}', encoding="utf-16")

    status = rk_health.harvest_log_status(log_file)

    assert status["exists"] is True
    assert status["last_recorded"] == 3
    assert status["last_parse_failed"] == 0
