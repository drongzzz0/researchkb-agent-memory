from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "init_researchkb_workspace.py"
SPEC = importlib.util.spec_from_file_location("init_researchkb_workspace", MODULE_PATH)
assert SPEC is not None
init_researchkb_workspace = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = init_researchkb_workspace
assert SPEC.loader is not None
SPEC.loader.exec_module(init_researchkb_workspace)


def test_init_workspace_creates_smoke_run(tmp_path: Path) -> None:
    root = tmp_path / "researchkb"
    project_root = tmp_path / "project"

    result = init_researchkb_workspace.init_workspace(
        root=root,
        project_root=project_root,
        project_name="Example Project",
    )

    assert result.watch_file.exists()
    assert (result.run_dir / "metrics.json").exists()
    assert (result.run_dir / "summary.json").exists()
    metrics = json.loads((result.run_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["project"] == "Example Project"
    assert metrics["status"] == "completed_positive"
    assert metrics["metrics"]["accuracy"] == 0.842
    assert str(project_root / "runs") in result.watch_file.read_text(encoding="utf-8")


def test_init_workspace_does_not_overwrite_without_force(tmp_path: Path) -> None:
    root = tmp_path / "researchkb"
    project_root = tmp_path / "project"
    run_dir = project_root / "runs" / "smoke-test"
    run_dir.mkdir(parents=True)
    metrics_path = run_dir / "metrics.json"
    metrics_path.write_text('{"custom": true}\n', encoding="utf-8")

    init_researchkb_workspace.init_workspace(
        root=root,
        project_root=project_root,
        project_name="Example Project",
        force=False,
    )

    assert json.loads(metrics_path.read_text(encoding="utf-8")) == {"custom": True}


def test_init_workspace_force_overwrites_generated_files(tmp_path: Path) -> None:
    root = tmp_path / "researchkb"
    project_root = tmp_path / "project"
    run_dir = project_root / "runs" / "smoke-test"
    run_dir.mkdir(parents=True)
    metrics_path = run_dir / "metrics.json"
    metrics_path.write_text('{"custom": true}\n', encoding="utf-8")

    init_researchkb_workspace.init_workspace(
        root=root,
        project_root=project_root,
        project_name="Example Project",
        force=True,
    )

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert metrics["experiment"] == "smoke-test"
    assert "metrics" in metrics
