from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from standardize_run import JSON_CANDIDATES, build_run_record, write_failure_scaffold

LOG_SUFFIXES = (".log", ".metrics.txt")
IGNORE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    ".cache",
}


@dataclass(frozen=True)
class StandardizeResult:
    run_dir: str
    output: str
    status: str
    reason: str


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan watched experiment folders and write missing or stale run_record.json files."
    )
    parser.add_argument("paths", nargs="*", type=Path, help="Experiment roots or run directories to scan.")
    parser.add_argument("--paths-file", type=Path, help="One watched path per line. Lines starting with # are ignored.")
    parser.add_argument("--project", help="Project name to apply when source files do not include one.")
    parser.add_argument("--since-hours", type=float, default=24.0)
    parser.add_argument("--max-dirs", type=int, default=200)
    parser.add_argument("--quality-floor", type=float, default=0.98)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    paths = list(args.paths)
    if args.paths_file:
        paths.extend(read_paths_file(args.paths_file))
    if not paths:
        paths = [Path(".")]

    report = auto_standardize(
        paths=paths,
        project=args.project,
        since_hours=args.since_hours,
        max_dirs=args.max_dirs,
        quality_floor=args.quality_floor,
        force=args.force,
        dry_run=args.dry_run,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def auto_standardize(
    *,
    paths: list[Path],
    project: str | None = None,
    since_hours: float = 24.0,
    max_dirs: int = 200,
    quality_floor: float = 0.98,
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    cutoff = datetime.now() - timedelta(hours=max(since_hours, 0.1))
    run_dirs = discover_run_dirs(paths, cutoff=cutoff, max_dirs=max_dirs)
    results: list[StandardizeResult] = []
    written = skipped = failed = 0

    for run_dir in run_dirs:
        try:
            result = standardize_one(
                run_dir=run_dir,
                project=project,
                quality_floor=quality_floor,
                force=force,
                dry_run=dry_run,
            )
        except Exception as exc:
            failed += 1
            results.append(
                StandardizeResult(
                    run_dir=run_dir.as_posix(),
                    output=(run_dir / "run_record.json").as_posix(),
                    status="failed",
                    reason=str(exc),
                )
            )
            continue
        if result.status == "written":
            written += 1
        else:
            skipped += 1
        results.append(result)

    return {
        "scanned_dirs": len(run_dirs),
        "written": written,
        "skipped": skipped,
        "failed": failed,
        "records": [result.__dict__ for result in results[:50]],
    }


def standardize_one(
    *,
    run_dir: Path,
    project: str | None,
    quality_floor: float,
    force: bool,
    dry_run: bool,
) -> StandardizeResult:
    output = run_dir / "run_record.json"
    sources = source_files(run_dir)
    if not sources:
        return StandardizeResult(run_dir.as_posix(), output.as_posix(), "skipped", "no parseable source files")
    if output.exists() and not force:
        output_mtime = output.stat().st_mtime
        if all(source.stat().st_mtime <= output_mtime for source in sources):
            return StandardizeResult(run_dir.as_posix(), output.as_posix(), "skipped", "fresh")

    record = build_run_record(run_dir=run_dir, project=project, quality_floor=quality_floor)
    if not dry_run:
        output.write_text(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        write_failure_scaffold(run_dir, record)
    status = "written"
    reason = record.get("status", "unknown")
    if dry_run:
        status = "written"
        reason = f"dry-run:{reason}"
    return StandardizeResult(run_dir.as_posix(), output.as_posix(), status, reason)


def discover_run_dirs(paths: list[Path], *, cutoff: datetime, max_dirs: int) -> list[Path]:
    found: dict[Path, float] = {}
    for raw_path in paths:
        path = raw_path.expanduser().resolve()
        if not path.exists():
            continue
        if path.is_file():
            path = path.parent
        if looks_like_run_dir(path):
            newest = newest_source_mtime(path)
            if newest is not None and datetime.fromtimestamp(newest) >= cutoff:
                found[path] = newest
            continue
        for root, dirs, _files in os.walk(path):
            dirs[:] = [name for name in dirs if name not in IGNORE_DIRS]
            run_dir = Path(root)
            if not looks_like_run_dir(run_dir):
                continue
            newest = newest_source_mtime(run_dir)
            if newest is not None and datetime.fromtimestamp(newest) >= cutoff:
                found[run_dir] = newest
            if len(found) >= max_dirs * 2:
                break
    return [path for path, _mtime in sorted(found.items(), key=lambda item: item[1], reverse=True)[:max_dirs]]


def looks_like_run_dir(path: Path) -> bool:
    return any(source_files(path))


def source_files(path: Path) -> list[Path]:
    files: list[Path] = []
    try:
        for name in JSON_CANDIDATES:
            candidate = path / name
            if candidate.is_file():
                files.append(candidate)
        files.extend(sorted(item for item in path.iterdir() if item.is_file() and item.name.endswith(LOG_SUFFIXES)))
    except OSError:
        # Unattended scans must survive unreadable directories; treat them as
        # having no extra parseable sources instead of aborting the whole batch.
        pass
    return files


def newest_source_mtime(path: Path) -> float | None:
    mtimes: list[float] = []
    for source in source_files(path):
        try:
            mtimes.append(source.stat().st_mtime)
        except OSError:
            continue
    return max(mtimes) if mtimes else None


def read_paths_file(paths_file: Path) -> list[Path]:
    base = paths_file.expanduser().resolve().parent
    paths: list[Path] = []
    for raw_line in paths_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        path = Path(line).expanduser()
        paths.append(path if path.is_absolute() else base / path)
    return paths


if __name__ == "__main__":
    raise SystemExit(main())
