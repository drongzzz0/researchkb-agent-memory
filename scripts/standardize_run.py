from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

JSON_CANDIDATES = ("metrics.json", "results.json", "eval_results.json", "summary.json")
METRIC_LINE_RE = re.compile(r"\bMETRIC\s+([A-Za-z0-9_.-]+)=([^\s,;]+)")
ERROR_RE = re.compile(r"(Traceback|OutOfMemoryError|CUDA out of memory|\bERROR\b|Exception)", re.IGNORECASE)
METADATA_KEYS = {
    "project",
    "experiment",
    "run_id",
    "status",
    "git_commit",
    "config_ref",
    "dataset",
    "model",
    "seed",
    "failure_type",
    "decision",
    "next_action",
    "artifacts",
    "safety",
    "notes",
    "summary",
    "expected_agent_use",
    "created_at",
}
CANONICAL_ALIASES = {
    "sample_count": ("sample_count", "eval_n", "num_samples", "n_samples", "n"),
    "full_large_f1": ("full_large_f1", "full_large_f1_mean", "baseline_f1"),
    "route_f1": ("route_f1", "deployable_f1", "best_deployable_f1", "best_route_f1"),
    "quality_retention": ("quality_retention", "retention", "f1_retention"),
    "latency_ms": ("latency_ms", "total_latency_ms", "mean_latency_ms"),
    "ttft_ms": ("ttft_ms", "time_to_first_token_ms"),
    "speedup": ("speedup", "ttft_speedup_vs_full", "latency_speedup_vs_full"),
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert one experiment output directory into a ResearchKB run_record.json."
    )
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--output", type=Path, help="Output path. Defaults to <run_dir>/run_record.json.")
    parser.add_argument("--project")
    parser.add_argument("--experiment")
    parser.add_argument("--run-id")
    parser.add_argument("--dataset")
    parser.add_argument("--model")
    parser.add_argument("--seed")
    parser.add_argument("--config-ref")
    parser.add_argument("--git-commit")
    parser.add_argument("--failure-type")
    parser.add_argument("--decision", choices=["continue", "stop", "redesign", "rerun", "unknown"])
    parser.add_argument("--next-action")
    parser.add_argument(
        "--status",
        choices=["running", "completed_positive", "completed_negative", "failed"],
    )
    parser.add_argument(
        "--quality-floor",
        type=float,
        default=0.98,
        help="Minimum quality_retention before a run is marked completed_negative.",
    )
    args = parser.parse_args()

    record = build_run_record(
        run_dir=args.run_dir,
        project=args.project,
        experiment=args.experiment,
        run_id=args.run_id,
        dataset=args.dataset,
        model=args.model,
        seed=args.seed,
        config_ref=args.config_ref,
        git_commit=args.git_commit,
        failure_type=args.failure_type,
        decision=args.decision,
        next_action=args.next_action,
        status=args.status,
        quality_floor=args.quality_floor,
    )
    output = args.output or args.run_dir / "run_record.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"RUN_RECORD_OK {output}")
    scaffold = write_failure_scaffold(args.run_dir, record)
    if scaffold:
        print(f"FAILURE_CASE_DRAFT {scaffold}")
    return 0


def build_run_record(
    run_dir: Path,
    project: str | None = None,
    experiment: str | None = None,
    run_id: str | None = None,
    dataset: str | None = None,
    model: str | None = None,
    seed: str | int | None = None,
    config_ref: str | None = None,
    git_commit: str | None = None,
    failure_type: str | None = None,
    decision: str | None = None,
    next_action: str | None = None,
    status: str | None = None,
    quality_floor: float | None = 0.98,
) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    if not run_dir.exists() or not run_dir.is_dir():
        raise FileNotFoundError(f"Run directory does not exist: {run_dir}")

    metadata: dict[str, Any] = {}
    metrics: dict[str, Any] = {}
    artifacts: list[str] = []
    log_has_error = False
    log_error_text = ""

    for path in discover_json_files(run_dir):
        artifacts.append(path.name)
        data = read_json_object(path)
        metadata.update(extract_metadata(data))
        metrics.update(extract_metrics(data))

    for path in discover_log_files(run_dir):
        artifacts.append(path.name)
        text = path.read_text(encoding="utf-8", errors="replace")
        metrics.update(extract_metric_lines(text))
        if ERROR_RE.search(text):
            log_has_error = True
            log_error_text = first_error_label(text)

    metrics = add_canonical_metrics(metrics)
    config_ref = first_non_empty(config_ref, metadata.get("config_ref"))
    ensure_public_config_ref(config_ref)
    project_value = project or metadata.get("project") or infer_project(run_dir)
    experiment_value = experiment or metadata.get("experiment") or run_dir.name
    git_commit_value = git_commit or metadata.get("git_commit")
    source_created_at = first_non_empty(metadata.get("created_at"))
    failure_type = derive_failure_type(
        failure_type,
        metadata.get("failure_type"),
        metrics,
        log_has_error,
        log_error_text,
    )
    status = derive_status(status or metadata.get("status"), failure_type, metrics, quality_floor)
    decision = decision or metadata.get("decision") or derive_decision(status)
    next_action = next_action or metadata.get("next_action") or derive_next_action(status, failure_type)
    run_id_value = first_non_empty(run_id, metadata.get("run_id")) or stable_run_id(
        run_dir,
        project=project_value,
        experiment=experiment_value,
        created_at=source_created_at,
        git_commit=git_commit_value,
        metrics=metrics,
        artifacts=artifacts,
    )

    return {
        "project": project_value,
        "experiment": experiment_value,
        "run_id": run_id_value,
        "status": status,
        "git_commit": git_commit_value,
        "config_ref": config_ref,
        "dataset": dataset or metadata.get("dataset"),
        "model": model or metadata.get("model"),
        "seed": normalize_seed(seed if seed is not None else metadata.get("seed")),
        "metrics": metrics,
        "failure_type": failure_type,
        "decision": decision,
        "next_action": next_action,
        "artifacts": sorted(set(artifacts)),
        "created_at": source_created_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def discover_json_files(run_dir: Path) -> list[Path]:
    return [run_dir / name for name in JSON_CANDIDATES if (run_dir / name).exists()]


def discover_log_files(run_dir: Path) -> list[Path]:
    paths = [*run_dir.glob("*.log"), *run_dir.glob("*.metrics.txt")]
    return sorted(path for path in paths if path.is_file())


def read_json_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return data


def extract_metadata(data: dict[str, Any]) -> dict[str, Any]:
    return {key: data[key] for key in METADATA_KEYS if key in data}


def extract_metrics(data: dict[str, Any]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    nested = data.get("metrics")
    if isinstance(nested, dict):
        metrics.update({key: value for key, value in nested.items() if is_metric_value(value)})
    for key, value in data.items():
        if key in METADATA_KEYS or key == "metrics":
            continue
        if is_metric_value(value):
            metrics[key] = value
    return metrics


def extract_metric_lines(text: str) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for match in METRIC_LINE_RE.finditer(text):
        metrics[match.group(1)] = parse_scalar(match.group(2))
    return metrics


def add_canonical_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(metrics)
    for canonical, aliases in CANONICAL_ALIASES.items():
        if canonical in normalized:
            continue
        for alias in aliases:
            if alias in normalized:
                normalized[canonical] = normalized[alias]
                break

    route_f1 = to_float(normalized.get("route_f1"))
    full_large_f1 = to_float(normalized.get("full_large_f1"))
    if "quality_retention" not in normalized and route_f1 is not None and full_large_f1:
        normalized["quality_retention"] = round(route_f1 / full_large_f1, 6)
    return normalized


def derive_status(
    requested_status: str | None,
    failure_type: str | None,
    metrics: dict[str, Any],
    quality_floor: float | None,
) -> str:
    if requested_status:
        return requested_status
    if failure_type and not failure_type.startswith("quality_"):
        return "failed"
    retention = to_float(metrics.get("quality_retention"))
    if quality_floor is not None and retention is not None and retention < quality_floor:
        return "completed_negative"
    return "completed_positive"


def derive_failure_type(
    requested: str | None,
    metadata_value: Any,
    metrics: dict[str, Any],
    log_has_error: bool,
    log_error_text: str,
) -> str | None:
    if requested:
        return requested
    if isinstance(metadata_value, str) and metadata_value:
        return metadata_value
    if log_has_error:
        if "outofmemory" in log_error_text.lower() or "out of memory" in log_error_text.lower():
            return "oom"
        return "error"
    retention = to_float(metrics.get("quality_retention"))
    if retention is not None and retention < 0.98:
        return "quality_below_threshold"
    return None


def derive_decision(status: str) -> str:
    if status == "failed":
        return "rerun"
    if status == "completed_negative":
        return "redesign"
    if status == "running":
        return "unknown"
    return "continue"


def derive_next_action(status: str, failure_type: str | None) -> str:
    if status == "failed":
        return f"Inspect failure_type={failure_type or 'error'} and rerun with a smaller controlled change."
    if status == "completed_negative":
        return "Compare quality-retention drivers before launching a larger run."
    if status == "running":
        return "Wait for completion, then standardize the final metrics."
    return "Harvest this run and use it as evidence for the next experiment decision."


def write_failure_scaffold(run_dir: Path, record: dict[str, Any]) -> Path | None:
    """Scaffold a problem_case draft for runs with a failure_type, so failure
    memory gets captured while the context is still fresh. Never overwrites."""
    if not record.get("failure_type"):
        return None
    draft_path = run_dir / "problem_case.draft.json"
    if draft_path.exists():
        return None
    draft = {
        "problem_id": f"problem_{record.get('run_id', 'unknown_run')}",
        "symptom": (
            f"Experiment '{record.get('experiment')}' ended with "
            f"status={record.get('status')} failure_type={record.get('failure_type')}."
        ),
        "context": {
            "project": record.get("project"),
            "dataset": record.get("dataset"),
            "model": record.get("model"),
            "failure_type": record.get("failure_type"),
            "generated_by": "standardize_run auto-scaffold",
        },
        "suspected_causes": [],
        "tried_fixes": [],
        "final_solution": None,
        "linked_runs": [record.get("run_id")],
        "linked_papers": [],
        "confidence": None,
    }
    draft_path.write_text(json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return draft_path


def ensure_public_config_ref(config_ref: str | None) -> None:
    if not config_ref:
        return
    if re.match(r"^(?:[A-Za-z]:[\\/]|/)", config_ref):
        raise ValueError("config_ref must be a relative path, content hash, or git ref, not an absolute path.")


def first_error_label(text: str) -> str:
    for line in text.splitlines():
        if ERROR_RE.search(line):
            return line.strip()
    return ""


def first_non_empty(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def infer_project(run_dir: Path) -> str:
    parent = run_dir.parent.name
    if parent and parent not in {".", "runs"}:
        return parent
    return "Research Project"


def stable_run_id(
    run_dir: Path,
    project: str | None = None,
    experiment: str | None = None,
    created_at: str | None = None,
    git_commit: str | None = None,
    metrics: dict[str, Any] | None = None,
    artifacts: list[str] | None = None,
) -> str:
    if project and experiment and (created_at or git_commit):
        identity = {
            "project": project,
            "experiment": experiment,
            "created_at": created_at,
            "git_commit": git_commit,
        }
        return f"run_{short_hash(identity)}"

    file_digests = []
    for path in [*discover_json_files(run_dir), *discover_log_files(run_dir)]:
        file_digests.append(
            {
                "name": path.name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )

    payload: dict[str, Any] = {
        "project": project,
        "experiment": experiment,
        "metrics": metrics or {},
        "artifacts": sorted(set(artifacts or [])),
        "files": file_digests,
    }
    if not file_digests and not metrics:
        payload["run_dir_name"] = run_dir.name
    return f"run_{short_hash(payload)}"


def short_hash(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def normalize_seed(value: Any) -> int | str | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value)
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    return text


def is_metric_value(value: Any) -> bool:
    return isinstance(value, (int, float, str, bool)) and value is not None


def parse_scalar(value: str) -> Any:
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "null":
        return None
    try:
        if re.fullmatch(r"-?\d+", value):
            return int(value)
        return float(value)
    except ValueError:
        return value


def to_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


if __name__ == "__main__":
    raise SystemExit(main())
