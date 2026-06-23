from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "standardize_run.py"
SPEC = importlib.util.spec_from_file_location("standardize_run", MODULE_PATH)
assert SPEC is not None
standardize_run = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = standardize_run
assert SPEC.loader is not None
SPEC.loader.exec_module(standardize_run)


def test_standardize_run_extracts_json_and_metric_lines(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "quality-check"
    run_dir.mkdir(parents=True)
    (run_dir / "results.json").write_text(
        json.dumps(
            {
                "project": "Example Project",
                "experiment": "quality-check",
                "run_id": "run_example_quality_001",
                "dataset": "synthetic-eval",
                "model": "example-model",
                "seed": 7,
                "config_ref": "configs/quality-check.synthetic.json",
                "full_large_f1_mean": 0.5,
                "best_deployable_f1": 0.45,
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "run.log").write_text(
        "METRIC latency_ms=128.5\nMETRIC sample_count=50\n",
        encoding="utf-8",
    )

    record = standardize_run.build_run_record(run_dir)

    assert record["project"] == "Example Project"
    assert record["status"] == "completed_negative"
    assert record["failure_type"] == "quality_below_threshold"
    assert record["decision"] == "redesign"
    assert record["metrics"]["full_large_f1"] == 0.5
    assert record["metrics"]["route_f1"] == 0.45
    assert record["metrics"]["quality_retention"] == 0.9
    assert record["metrics"]["latency_ms"] == 128.5
    assert record["metrics"]["sample_count"] == 50
    assert record["artifacts"] == ["results.json", "run.log"]


def test_standardize_run_rejects_absolute_config_ref(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    absolute_config = "C:" + "\\" + "private" + "\\" + "config.json"

    try:
        standardize_run.build_run_record(run_dir, config_ref=absolute_config)
    except ValueError as exc:
        assert "config_ref" in str(exc)
    else:
        raise AssertionError("absolute config_ref should be rejected")
