from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from researchkb_agent_memory import __version__, cli  # noqa: E402


def run_cli(capsys: pytest.CaptureFixture[str], *args: str) -> tuple[int, str]:
    code = cli.main(list(args))
    captured = capsys.readouterr()
    return code, captured.out


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run_cli(capsys, "--version")

    assert code == 0
    assert __version__ in out


def test_help_lists_all_commands(capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run_cli(capsys)

    assert code == 0
    for command in cli.COMMANDS:
        assert command in out


def test_unknown_command_fails(capsys: pytest.CaptureFixture[str]) -> None:
    code = cli.main(["not-a-command"])
    capsys.readouterr()

    assert code == 2


def test_end_to_end_workflow(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = tmp_path / "researchkb"
    project_root = tmp_path / "example-project"
    run_dir = project_root / "runs" / "smoke-test"

    code, _ = run_cli(capsys, "init", "--root", str(root), "--project-root", str(project_root))
    assert code == 0

    code, out = run_cli(capsys, "standardize-run", str(run_dir))
    assert code == 0
    assert "RUN_RECORD_OK" in out

    code, out = run_cli(
        capsys,
        "seed-demo",
        "--root",
        str(root),
        "--examples",
        str(REPO_ROOT / "examples"),
        "--include-run",
        str(run_dir / "run_record.json"),
    )
    assert code == 0
    assert "DEMO_DB_OK" in out

    code, out = run_cli(capsys, "health", "--root", str(root), "--json")
    assert code == 0
    report = json.loads(out)
    assert report["judgement"]["level"] == "smoke"

    code, out = run_cli(capsys, "schema-check", "--root", str(root))
    assert code == 0
    assert json.loads(out)["ok"] is True

    code, out = run_cli(capsys, "latest-runs", "--root", str(root), "--limit", "3")
    assert code == 0
    runs = json.loads(out)["runs"]
    assert runs[0]["run_id"] == "run_smoke_001"

    code, out = run_cli(capsys, "search-evidence", "validate compatibility cached state", "--root", str(root))
    assert code == 0
    evidence = json.loads(out)["evidence_links"]
    assert evidence[0]["evidence_id"] == "evidence_example_cache_001"

    code, out = run_cli(
        capsys,
        "compare-runs",
        "run_example_smoke_001",
        "run_example_negative_001",
        "--root",
        str(root),
        "--metric",
        "latency_ms",
    )
    assert code == 0
    assert json.loads(out)["comparison"]["deltas"]["latency_ms"] == -32.5

    code, out = run_cli(
        capsys,
        "eval",
        "--root",
        str(root),
        "--eval-file",
        str(REPO_ROOT / "evals" / "retrieval_eval.jsonl"),
        "--min-recall",
        "0.9",
    )
    assert code == 0
    assert "EVAL_OK" in out

    code, out = run_cli(
        capsys,
        "check-citations",
        str(REPO_ROOT / "examples" / "agent-answers" / "good_troubleshooting_answer.md"),
        "--root",
        str(root),
        "--min-validity",
        "1.0",
    )
    assert code == 0
    assert "CITATIONS_OK" in out

    code, out = run_cli(capsys, "session-brief", "--root", str(root), "--json")
    assert code == 0
    assert json.loads(out)["level"] == "smoke"

    code, out = run_cli(capsys, "import-runs", str(run_dir / "run_record.json"), "--root", str(root))
    assert code == 0
    assert json.loads(out)["would_update"] == 1

    code, out = run_cli(
        capsys,
        "import-bibtex",
        str(REPO_ROOT / "examples" / "paper-memory" / "demo.bib"),
        "--root",
        str(root),
    )
    assert code == 0
    assert json.loads(out)["would_insert"] == 2

    code, out = run_cli(
        capsys,
        "import-notes",
        str(REPO_ROOT / "examples" / "note-memory" / "synthetic-cache-note.md"),
        "--root",
        str(root),
    )
    assert code == 0
    assert json.loads(out)["would_insert"]["chunks"] == 1


def test_find_failure_cases_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = tmp_path / "researchkb"
    code, _ = run_cli(capsys, "seed-demo", "--root", str(root), "--examples", str(REPO_ROOT / "examples"))
    assert code == 0

    code, out = run_cli(capsys, "find-failure-cases", "quality drops cache reuse", "--root", str(root))

    assert code == 0
    cases = json.loads(out)["cases"]
    assert cases[0]["problem_id"] == "problem_example_cache_template_mismatch"
