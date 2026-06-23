from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

SCHEMA_BY_EXAMPLE = {
    ("smoke-run", "metrics.json"): "experiment_metrics.schema.json",
    ("standardized-run", "run_record.json"): "experiment_metrics.schema.json",
    ("failure-case", "problem_case.json"): "problem_case.schema.json",
    ("paper-memory", "paper.json"): "paper.schema.json",
    ("paper-memory", "chunk.json"): "chunk.schema.json",
    ("paper-memory", "claim.json"): "claim.schema.json",
    ("paper-memory", "evidence_link.json"): "evidence_link.schema.json",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate synthetic example JSON files against public schemas.")
    parser.add_argument("--examples", type=Path, default=Path("examples"))
    parser.add_argument("--schemas", type=Path, default=Path("schemas"))
    parser.add_argument(
        "--strict-unmatched",
        action="store_true",
        help="Fail when an example JSON file has no schema mapping.",
    )
    args = parser.parse_args()

    failures = validate_examples(args.examples, args.schemas, strict_unmatched=args.strict_unmatched)
    return 1 if failures else 0


def validate_examples(examples_dir: Path, schemas_dir: Path, strict_unmatched: bool = False) -> list[str]:
    validators = load_validators(schemas_dir)
    failures: list[str] = []
    for path in sorted(examples_dir.rglob("*.json")):
        schema_name = schema_for(path, examples_dir)
        if schema_name is None:
            message = f"SKIP {path} (no schema mapping)"
            print(message)
            if strict_unmatched:
                failures.append(message)
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        validator = validators[schema_name]
        errors = sorted(validator.iter_errors(data), key=lambda err: list(err.path))
        if errors:
            for error in errors:
                location = ".".join(str(part) for part in error.path) or "<root>"
                failures.append(f"{path}: {location}: {error.message}")
            continue
        print(f"SCHEMA_OK {path} -> {schema_name}")

    for failure in failures:
        print(f"SCHEMA_FAIL {failure}")
    return failures


def load_validators(schemas_dir: Path) -> dict[str, Draft202012Validator]:
    validators = {}
    for path in sorted(schemas_dir.glob("*.schema.json")):
        schema: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        validators[path.name] = Draft202012Validator(schema)
    return validators


def schema_for(path: Path, examples_dir: Path) -> str | None:
    rel = path.relative_to(examples_dir)
    if len(rel.parts) < 2:
        return None
    return SCHEMA_BY_EXAMPLE.get((rel.parts[0], rel.name))


if __name__ == "__main__":
    raise SystemExit(main())
