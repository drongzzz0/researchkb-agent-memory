from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "public_repo_scan.py"
SPEC = importlib.util.spec_from_file_location("public_repo_scan", MODULE_PATH)
assert SPEC is not None
public_repo_scan = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = public_repo_scan
assert SPEC.loader is not None
SPEC.loader.exec_module(public_repo_scan)


def test_public_repo_scan_reports_sensitive_patterns(tmp_path: Path) -> None:
    token_value = "sk-" + "example123"
    (tmp_path / "README.md").write_text(f"token = '{token_value}'\n", encoding="utf-8")

    matches = public_repo_scan.scan(tmp_path)

    assert matches
    assert matches[0][0] == "concrete secret"


def test_public_repo_scan_skips_runtime_dirs(tmp_path: Path) -> None:
    runtime = tmp_path / ".runtime"
    runtime.mkdir()
    local_path = "C:" + "\\" + "Users" + "\\" + "mq" + "l16" + "\\" + "secret"
    (runtime / "private.txt").write_text(local_path + "\n", encoding="utf-8")

    assert public_repo_scan.scan(tmp_path) == []
