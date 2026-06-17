from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


SKIP_DIRS = {".git", ".pytest_cache", ".ruff_cache", ".mypy_cache", "__pycache__", ".venv", "tmp", ".runtime"}
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".pyc", ".sqlite", ".sqlite3", ".db"}


@dataclass(frozen=True)
class PatternRule:
    label: str
    pattern: re.Pattern[str]


def joined(*parts: str) -> str:
    return "".join(parts)


PRIVATE_TERMS = [
    joined("C:", "\\", "Users", "\\", "mq", "l16"),
    joined("C:/", "Users", "/", "mq", "l16"),
    joined("D:", "\\", "Research", "KB"),
    joined("/", "home", "/", "student"),
    joined("/", "disk", "_n"),
    joined("student", "_t"),
    joined("ma", "qian", "li"),
    joined("mq", "l16"),
    joined("api", ".", "ma", "qian", "li"),
    joined("A", "800"),
    joined("c", "101"),
]

PRIVATE_WORD_TERMS = [
    joined("s", "er"),
]

PRIVATE_ARTIFACT_TERMS = [
    joined("draft", "kv"),
    joined("rl", "_hw2"),
    joined("\u5f3a", "\u5316", "\u5b66", "\u4e60"),
    joined("bio", "logy"),
    joined("current", "_inapp"),
    joined("\u4f5c", "\u4e1a"),
]


GENERIC_PATH_PATTERNS = [
    r"[A-Za-z]:" + re.escape("\\"),
    re.escape(joined("/", "home", "/")),
    re.escape(joined("/", "Users", "/")),
]


def any_literal_pattern(terms: list[str]) -> re.Pattern[str]:
    return re.compile("|".join(re.escape(term) for term in terms))


def any_word_pattern(terms: list[str]) -> re.Pattern[str]:
    return re.compile("|".join(rf"\b{re.escape(term)}\b" for term in terms))


RULES = [
    PatternRule(
        "personal/path/host",
        re.compile(f"{any_literal_pattern(PRIVATE_TERMS).pattern}|{any_word_pattern(PRIVATE_WORD_TERMS).pattern}"),
    ),
    PatternRule("generic absolute path", re.compile("|".join(GENERIC_PATH_PATTERNS))),
    PatternRule(
        "concrete secret",
        re.compile(
            r"sk-[A-Za-z0-9]|BEGIN [A-Z ]*PRIVATE KEY|bearer\s+[A-Za-z0-9._-]+|"
            r"(api[_-]?key|auth[_-]?token|password|secret)\s*[:=]\s*['\"][^'\"]+",
            re.IGNORECASE,
        ),
    ),
    PatternRule("personal artifact traces", any_literal_pattern(PRIVATE_ARTIFACT_TERMS)),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan public repository files for local paths, secrets, and private traces.")
    parser.add_argument("root", nargs="?", default=".", type=Path)
    args = parser.parse_args()

    matches = scan(args.root)
    for label, path, line_no, line in matches:
        print(f"{label}: {path}:{line_no}: {line}")
    if matches:
        print(f"Found {len(matches)} public hygiene issue(s).")
        return 1
    print("NO_MATCH")
    return 0


def scan(root: Path) -> list[tuple[str, Path, int, str]]:
    root = root.resolve()
    matches: list[tuple[str, Path, int, str]] = []
    for path in iter_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="replace")
        rel_path = path.relative_to(root)
        for line_no, line in enumerate(text.splitlines(), start=1):
            for rule in RULES:
                if rule.pattern.search(line):
                    matches.append((rule.label, rel_path, line_no, line.strip()))
    return matches


def iter_files(root: Path):
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        rel_parts = path.relative_to(root).parts
        if any(part in SKIP_DIRS for part in rel_parts):
            continue
        yield path


if __name__ == "__main__":
    raise SystemExit(main())
