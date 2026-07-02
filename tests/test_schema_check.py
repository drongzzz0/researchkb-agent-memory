from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from researchkb_agent_memory import demo, schema_check  # noqa: E402


def test_schema_check_demo_database_is_ready(tmp_path: Path) -> None:
    root = tmp_path / "researchkb"
    demo.seed_demo_db(root=root, examples_dir=REPO_ROOT / "examples", force=True)

    report = schema_check.check_schema(root=root)

    assert report["ok"] is True
    assert report["database_exists"] is True
    assert report["missing_tables"] == []
    assert report["missing_columns"] == {}
    assert report["import_ready"] == {
        "import-runs": True,
        "import-bibtex": True,
        "import-notes": True,
    }


def test_schema_check_reports_missing_database(tmp_path: Path) -> None:
    report = schema_check.check_schema(root=tmp_path / "missing-root")

    assert report["ok"] is False
    assert report["database_exists"] is False
    assert "papers" in report["missing_tables"]
    assert report["import_ready"]["import-runs"] is False


def test_schema_check_reports_missing_tables_and_columns(tmp_path: Path) -> None:
    root = tmp_path / "researchkb"
    db_dir = root / "db"
    db_dir.mkdir(parents=True)
    conn = sqlite3.connect(db_dir / "literature.sqlite")
    try:
        conn.execute("create table papers(paper_id text)")
        conn.execute("create table experiment_runs(run_id text, project text)")
        conn.commit()
    finally:
        conn.close()

    report = schema_check.check_schema(root=root)

    assert report["ok"] is False
    assert report["tables"]["papers"]["exists"] is True
    assert "title" in report["tables"]["papers"]["missing_columns"]
    assert "chunks" in report["missing_tables"]
    assert report["import_ready"]["import-runs"] is False
    assert report["import_ready"]["import-bibtex"] is False
    assert report["import_ready"]["import-notes"] is False


def test_schema_check_accepts_explicit_db_path(tmp_path: Path) -> None:
    db_path = tmp_path / "custom.sqlite"
    root = tmp_path / "root"
    demo.seed_demo_db(root=root, examples_dir=REPO_ROOT / "examples", force=True)
    generated = root / "db" / "literature.sqlite"
    db_path.write_bytes(generated.read_bytes())

    report = schema_check.check_schema(root=tmp_path / "unused-root", db_path=db_path)

    assert report["ok"] is True
    assert report["db_path"] == str(db_path.resolve())
