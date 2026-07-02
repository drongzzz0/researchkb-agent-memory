from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from researchkb_agent_memory import demo, import_runs  # noqa: E402


def write_run_record(path: Path, run_id: str = "run_imported_001", latency: float = 77.0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "project": "Import Test",
        "experiment": "import-smoke",
        "run_id": run_id,
        "status": "completed_positive",
        "config_ref": "configs/import-smoke.synthetic.json",
        "dataset": "synthetic",
        "model": "example-model",
        "seed": 3,
        "metrics": {
            "accuracy": 0.91,
            "latency_ms": latency,
        },
        "artifacts": ["metrics.json"],
        "decision": "continue",
        "next_action": "Use this imported run for query testing.",
        "created_at": "2026-01-02T00:00:00+00:00",
    }
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def fetch_run(root: Path, run_id: str) -> sqlite3.Row | None:
    conn = sqlite3.connect(root / "db" / "literature.sqlite")
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("select * from experiment_runs where run_id = ?", (run_id,)).fetchone()
    finally:
        conn.close()


@pytest.fixture()
def demo_root(tmp_path: Path) -> Path:
    root = tmp_path / "researchkb"
    demo.seed_demo_db(root=root, examples_dir=REPO_ROOT / "examples", force=True)
    return root


def test_import_runs_dry_run_does_not_write(demo_root: Path, tmp_path: Path) -> None:
    record_path = write_run_record(tmp_path / "runs" / "run-a" / "run_record.json")

    summary = import_runs.import_run_records(root=demo_root, paths=[record_path], write=False)

    assert summary["write"] is False
    assert summary["valid"] == 1
    assert summary["would_insert"] == 1
    assert fetch_run(demo_root, "run_imported_001") is None


def test_import_runs_write_inserts_and_updates(demo_root: Path, tmp_path: Path) -> None:
    record_path = write_run_record(tmp_path / "runs" / "run-a" / "run_record.json", latency=77.0)

    first = import_runs.import_run_records(root=demo_root, paths=[record_path], write=True)
    assert first["inserted"] == 1
    assert first["updated"] == 0
    row = fetch_run(demo_root, "run_imported_001")
    assert row is not None
    assert json.loads(row["metrics_json"])["latency_ms"] == 77.0

    write_run_record(record_path, latency=88.0)
    second = import_runs.import_run_records(root=demo_root, paths=[record_path], write=True)
    assert second["inserted"] == 0
    assert second["updated"] == 1
    row = fetch_run(demo_root, "run_imported_001")
    assert row is not None
    assert json.loads(row["metrics_json"])["latency_ms"] == 88.0


def test_import_runs_rejects_absolute_config_ref(tmp_path: Path) -> None:
    record_path = write_run_record(tmp_path / "runs" / "run-a" / "run_record.json")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["config_ref"] = "C:" + "\\" + "private" + "\\" + "config.json"
    record_path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    summary = import_runs.import_run_records(root=tmp_path / "researchkb", paths=[record_path])

    assert summary["valid"] == 0
    assert summary["invalid"] == 1
    assert "config_ref" in summary["records"][0]["error"]


def test_import_runs_discovers_run_records_one_level_deep(demo_root: Path, tmp_path: Path) -> None:
    runs_root = tmp_path / "runs"
    write_run_record(runs_root / "run-a" / "run_record.json", run_id="run_import_a")
    write_run_record(runs_root / "run-b" / "run_record.json", run_id="run_import_b")

    summary = import_runs.import_run_records(root=demo_root, paths=[runs_root], write=False)

    assert summary["discovered"] == 2
    assert {row["run_id"] for row in summary["records"]} == {"run_import_a", "run_import_b"}


def test_import_runs_requires_schema_for_write(tmp_path: Path) -> None:
    root = tmp_path / "researchkb"
    db_dir = root / "db"
    db_dir.mkdir(parents=True)
    sqlite3.connect(db_dir / "literature.sqlite").close()
    record_path = write_run_record(tmp_path / "runs" / "run-a" / "run_record.json")

    with pytest.raises(RuntimeError, match="experiment_runs table"):
        import_runs.import_run_records(root=root, paths=[record_path], write=True)
