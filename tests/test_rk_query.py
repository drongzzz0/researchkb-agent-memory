from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "researchkb"))

SPEC = importlib.util.spec_from_file_location("rk_query", REPO_ROOT / "researchkb" / "rk_query.py")
assert SPEC is not None
rk_query = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = rk_query
assert SPEC.loader is not None
SPEC.loader.exec_module(rk_query)

SEED_SPEC = importlib.util.spec_from_file_location("seed_demo_db_query", REPO_ROOT / "scripts" / "seed_demo_db.py")
assert SEED_SPEC is not None
seed_demo_db = importlib.util.module_from_spec(SEED_SPEC)
assert SEED_SPEC.loader is not None
SEED_SPEC.loader.exec_module(seed_demo_db)


@pytest.fixture()
def demo_root(tmp_path: Path) -> Path:
    root = tmp_path / "researchkb"
    seed_demo_db.seed_demo_db(root=root, examples_dir=REPO_ROOT / "examples", force=True)
    return root


def test_engine_requires_database(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        rk_query.QueryEngine(tmp_path)


def test_fts_search_finds_expected_records(demo_root: Path) -> None:
    with rk_query.QueryEngine(demo_root) as engine:
        assert engine.fts_available is True
        chunks = engine.search_chunks("prompt template compatibility")
        papers = engine.search_papers("cache reuse safety")
        claims = engine.search_claims("validate prompt-template compatibility")
        cases = engine.find_failure_cases("quality drops after enabling cache reuse")

    assert chunks["chunks"][0]["chunk_id"] == "chunk_example_cache_001"
    assert chunks["chunks"][0]["locator"] == "section:Safety Discussion"
    assert papers["papers"][0]["paper_id"] == "paper_example_cache_001"
    assert claims["claims"][0]["confidence"] == 0.86
    assert cases["cases"][0]["problem_id"] == "problem_example_cache_template_mismatch"
    assert cases["cases"][0]["fix"].startswith("Require a matching prompt-template hash")


def test_like_fallback_matches_fts_results(demo_root: Path) -> None:
    with rk_query.QueryEngine(demo_root) as engine:
        engine.fts_available = False
        chunks = engine.search_chunks("prompt template compatibility")
        empty = engine.search_chunks("quantum entanglement teleportation")

    assert chunks["chunks"][0]["chunk_id"] == "chunk_example_cache_001"
    assert any("substring search" in warning for warning in chunks["warnings"])
    assert empty["chunks"] == []
    assert empty["missing_context"]


def test_empty_query_returns_no_results(demo_root: Path) -> None:
    with rk_query.QueryEngine(demo_root) as engine:
        result = engine.search_chunks("   ")

    assert result["chunks"] == []


def test_find_recent_runs_orders_and_filters(demo_root: Path) -> None:
    with rk_query.QueryEngine(demo_root) as engine:
        latest = engine.find_recent_runs(limit=10)
        negative = engine.find_recent_runs(status="completed_negative", limit=10)
        filtered_project = engine.find_recent_runs(project="Example Research Project", limit=10)

    run_ids = [run["run_id"] for run in latest["runs"]]
    assert run_ids[0] == "run_example_smoke_001"
    assert "run_example_negative_001" in run_ids
    assert {run["status"] for run in negative["runs"]} == {"completed_negative"}
    assert {run["project"] for run in filtered_project["runs"]} == {"Example Research Project"}


def test_compare_runs_reports_deltas_and_missing_metrics(demo_root: Path) -> None:
    with rk_query.QueryEngine(demo_root) as engine:
        result = engine.compare_runs(
            "run_example_smoke_001",
            "run_example_negative_001",
            ["latency_ms", "quality_retention"],
        )
        missing = engine.compare_runs("run_example_smoke_001", "run_missing_999")

    assert result["comparison"]["deltas"]["latency_ms"] == -32.5
    assert any("quality_retention" in item for item in result["missing_context"])
    assert [entry["source_type"] for entry in result["evidence"]] == ["run", "run"]
    assert missing["comparison"] is None
    assert any("run_missing_999" in item for item in missing["missing_context"])


def test_missing_tables_are_tolerated(tmp_path: Path) -> None:
    root = tmp_path / "partial"
    db_dir = root / "db"
    db_dir.mkdir(parents=True)
    conn = sqlite3.connect(db_dir / "literature.sqlite")
    conn.execute("create table experiment_runs(run_id text, project text, status text, created_at text)")
    conn.execute("insert into experiment_runs values ('run_only_001', 'Solo', 'failed', '2026-01-01T00:00:00')")
    conn.commit()
    conn.close()

    with rk_query.QueryEngine(root) as engine:
        papers = engine.search_papers("anything")
        runs = engine.find_recent_runs()

    assert papers["papers"] == []
    assert any("does not exist" in warning for warning in papers["warnings"])
    assert runs["runs"][0]["run_id"] == "run_only_001"


def test_engine_is_read_only(demo_root: Path) -> None:
    with rk_query.QueryEngine(demo_root) as engine:
        with pytest.raises(sqlite3.OperationalError):
            engine.conn.execute("insert into src.papers(paper_id, title) values ('x', 'y')")
