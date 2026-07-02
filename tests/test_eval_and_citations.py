from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "researchkb"))


def load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


eval_retrieval = load_script("eval_retrieval_test", REPO_ROOT / "scripts" / "eval_retrieval.py")
check_citations = load_script("check_citations_test", REPO_ROOT / "scripts" / "check_citations.py")
seed_demo_db = load_script("seed_demo_db_eval", REPO_ROOT / "scripts" / "seed_demo_db.py")
rk_query = load_script("rk_query_eval", REPO_ROOT / "researchkb" / "rk_query.py")


@pytest.fixture()
def demo_root(tmp_path: Path) -> Path:
    root = tmp_path / "researchkb"
    seed_demo_db.seed_demo_db(root=root, examples_dir=REPO_ROOT / "examples", force=True)
    return root


def test_gold_set_scores_perfectly_on_demo_db(demo_root: Path) -> None:
    cases = eval_retrieval.load_cases(REPO_ROOT / "evals" / "retrieval_eval.jsonl")

    with rk_query.QueryEngine(demo_root) as engine:
        report = eval_retrieval.evaluate(engine, cases)

    summary = report["summary"]
    assert summary["recall_at_k"] == 1.0
    assert summary["mrr"] == 1.0
    assert summary["precision_at_1"] == 1.0
    assert summary["guard_pass_rate"] == 1.0
    assert summary["pass_rate"] == 1.0


def test_eval_scores_misses_and_false_positives(demo_root: Path) -> None:
    cases = [
        {
            "id": "expected_miss",
            "tool": "search_chunks",
            "query": "prompt template compatibility",
            "expected_source_ids": ["chunk_that_does_not_exist"],
            "k": 5,
        },
        {
            "id": "guard_violation",
            "tool": "search_chunks",
            "query": "prompt template compatibility",
            "expected_source_ids": [],
            "k": 5,
        },
    ]

    with rk_query.QueryEngine(demo_root) as engine:
        report = eval_retrieval.evaluate(engine, cases)

    by_id = {item["id"]: item for item in report["results"]}
    assert by_id["expected_miss"]["recall"] == 0.0
    assert by_id["expected_miss"]["passed"] is False
    assert by_id["guard_violation"]["passed"] is False
    assert report["summary"]["pass_rate"] == 0.0


def test_citation_check_classifies_ids(demo_root: Path) -> None:
    text = (
        "Evidence: paper_example_cache_001 and run_example_negative_001 support this. "
        "But run_fabricated_999 was never recorded."
    )

    report = check_citations.check_citations(demo_root, text)

    assert report["valid_ids"] == ["paper_example_cache_001", "run_example_negative_001"]
    assert report["unknown_ids"] == ["run_fabricated_999"]
    assert report["citation_validity"] == pytest.approx(2 / 3, abs=1e-4)


def test_citation_check_handles_missing_tables(tmp_path: Path) -> None:
    import sqlite3

    root = tmp_path / "partial"
    (root / "db").mkdir(parents=True)
    conn = sqlite3.connect(root / "db" / "literature.sqlite")
    conn.execute("create table experiment_runs(run_id text)")
    conn.execute("insert into experiment_runs values ('run_real_001')")
    conn.commit()
    conn.close()

    report = check_citations.check_citations(root, "See run_real_001 and paper_unseen_001.")

    assert report["valid_ids"] == ["run_real_001"]
    assert report["unverifiable_ids"] == ["paper_unseen_001"]
    assert report["citation_validity"] == 1.0


def test_citation_check_without_citations(demo_root: Path) -> None:
    report = check_citations.check_citations(demo_root, "No sources cited here.")

    assert report["citation_count"] == 0
    assert report["citation_validity"] is None
