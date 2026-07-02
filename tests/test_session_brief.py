from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "researchkb"))

SPEC = importlib.util.spec_from_file_location("session_brief", REPO_ROOT / "scripts" / "session_brief.py")
assert SPEC is not None
session_brief = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = session_brief
assert SPEC.loader is not None
SPEC.loader.exec_module(session_brief)

SEED_SPEC = importlib.util.spec_from_file_location("seed_demo_db_brief", REPO_ROOT / "scripts" / "seed_demo_db.py")
assert SEED_SPEC is not None
seed_demo_db = importlib.util.module_from_spec(SEED_SPEC)
assert SEED_SPEC.loader is not None
SEED_SPEC.loader.exec_module(seed_demo_db)


def seeded_root(tmp_path: Path) -> Path:
    root = tmp_path / "researchkb"
    seed_demo_db.seed_demo_db(root=root, examples_dir=REPO_ROOT / "examples", force=True)
    return root


def test_brief_contains_runs_and_effectiveness(tmp_path: Path) -> None:
    root = seeded_root(tmp_path)

    brief = session_brief.build_brief(root, limit=3)

    assert brief["level"] == "smoke"
    assert len(brief["recent_runs"]) == 3
    assert brief["effectiveness"]["metrics_coverage"] == 1.0
    assert brief["effectiveness"]["failure_documentation_rate"] == 1.0
    assert brief["open_failure_cases"] == []


def test_brief_lists_open_failure_cases(tmp_path: Path) -> None:
    root = seeded_root(tmp_path)
    conn = sqlite3.connect(root / "db" / "literature.sqlite")
    conn.execute(
        "insert into problem_cases values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("problem_open_001", "OOM during long-context eval.", "{}", "[]", "[]", None, "[]", "[]", None, "2026-01-02"),
    )
    conn.commit()
    conn.close()

    brief = session_brief.build_brief(root)

    open_ids = [case["problem_id"] for case in brief["open_failure_cases"]]
    assert open_ids == ["problem_open_001"]
    assert brief["effectiveness"]["failure_documentation_rate"] == 0.5
    assert any("final_solution" in action for action in brief["next_actions"])


def test_brief_for_missing_database(tmp_path: Path) -> None:
    brief = session_brief.build_brief(tmp_path / "nowhere")

    assert brief["level"] == "empty"
    assert brief["recent_runs"] == []
    assert brief["open_failure_cases"] == []
