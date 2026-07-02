"""Import curated Markdown notes into ResearchKB chunks, claims, and evidence links.

Writes are explicit: the command defaults to dry-run mode and only modifies the
database when `--write` is supplied. This importer stores Markdown note content
and extracted claim statements; it does not copy PDFs or store machine-local
absolute paths as locators.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path(".runtime") / "researchkb"
CHUNK_TABLE_COLUMNS = {
    "chunk_id",
    "paper_id",
    "source_type",
    "section",
    "locator",
    "text",
    "embedding_ref",
    "created_at",
}
CLAIM_TABLE_COLUMNS = {
    "claim_id",
    "claim_type",
    "statement",
    "paper_id",
    "chunk_id",
    "confidence",
    "created_by",
    "created_at",
}
EVIDENCE_TABLE_COLUMNS = {
    "evidence_id",
    "source_type",
    "source_id",
    "paper_id",
    "chunk_id",
    "run_id",
    "problem_id",
    "locator",
    "quote_or_snippet",
    "confidence",
    "created_at",
}
CHUNK_SOURCE_TYPES = {"paper_text", "abstract", "appendix", "table", "human_note", "web_page"}
CLAIM_TYPES = {"method", "experiment", "limitation", "failure", "safety", "future_work", "result"}
EVIDENCE_SOURCE_TYPES = {"paper", "chunk", "claim", "run", "problem_case", "human_note", "code_state"}
CREATED_BY_VALUES = {"human", "llm", "script", None}


@dataclass(frozen=True)
class NoteImportRecord:
    source: Path
    chunk: dict[str, Any]
    claims: list[dict[str, Any]]
    evidence_links: list[dict[str, Any]]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import curated Markdown notes into chunks, claims, and evidence.")
    parser.add_argument("paths", nargs="+", type=Path, help="Markdown files or directories containing .md notes.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="ResearchKB root.")
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Recursively search directories for .md files. Without this, only direct children are scanned.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Actually write to SQLite. Omit for dry-run planning.",
    )
    args = parser.parse_args(argv)

    summary = import_markdown_notes(
        root=args.root,
        paths=args.paths,
        recursive=args.recursive,
        write=args.write,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["invalid"] == 0 else 1


def import_markdown_notes(
    root: Path,
    paths: list[Path],
    recursive: bool = False,
    write: bool = False,
) -> dict[str, Any]:
    root = root.resolve()
    db_path = root / "db" / "literature.sqlite"
    note_paths = discover_markdown_notes(paths, recursive=recursive)
    rows: list[dict[str, Any]] = []
    valid_records: list[NoteImportRecord] = []

    for note_path in note_paths:
        try:
            record = read_markdown_note(note_path)
            validate_note_record(record)
        except Exception as exc:
            rows.append(
                {
                    "path": safe_path(note_path),
                    "chunk_id": None,
                    "action": "invalid",
                    "error": str(exc),
                }
            )
            continue
        valid_records.append(record)

    existing = {"chunks": set(), "claims": set(), "evidence_links": set()}
    if db_path.exists() and valid_records:
        with sqlite3.connect(db_path) as conn:
            existing = existing_record_ids(conn)

    planned_rows = plan_rows(valid_records, existing, write=write)
    rows.extend(planned_rows)

    inserted = {"chunks": 0, "claims": 0, "evidence_links": 0}
    updated = {"chunks": 0, "claims": 0, "evidence_links": 0}
    if write and valid_records:
        if not db_path.exists():
            raise FileNotFoundError(f"ResearchKB database not found: {db_path}")
        with sqlite3.connect(db_path) as conn:
            ensure_importable_schema(conn)
            existing = existing_record_ids(conn)
            created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            for record in valid_records:
                inserted["chunks"] += int(record.chunk["chunk_id"] not in existing["chunks"])
                updated["chunks"] += int(record.chunk["chunk_id"] in existing["chunks"])
                upsert_chunk(conn, record.chunk, created_at)
                for claim in record.claims:
                    inserted["claims"] += int(claim["claim_id"] not in existing["claims"])
                    updated["claims"] += int(claim["claim_id"] in existing["claims"])
                    upsert_claim(conn, claim, created_at)
                for evidence in record.evidence_links:
                    inserted["evidence_links"] += int(evidence["evidence_id"] not in existing["evidence_links"])
                    updated["evidence_links"] += int(evidence["evidence_id"] in existing["evidence_links"])
                    upsert_evidence_link(conn, evidence, created_at)
            conn.commit()

    invalid = sum(1 for row in rows if row["action"] == "invalid")
    would_insert = count_planned(planned_rows, "would_insert")
    would_update = count_planned(planned_rows, "would_update")
    return {
        "root": str(root),
        "db_path": str(db_path),
        "write": write,
        "discovered": len(note_paths),
        "valid": len(valid_records),
        "invalid": invalid,
        "inserted": inserted,
        "updated": updated,
        "would_insert": would_insert,
        "would_update": would_update,
        "records": rows,
    }


def discover_markdown_notes(paths: list[Path], recursive: bool = False) -> list[Path]:
    notes: list[Path] = []
    seen: set[Path] = set()
    for raw_path in paths:
        path = raw_path.expanduser()
        candidates = candidate_markdown_notes(path, recursive=recursive)
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            notes.append(candidate)
    return notes


def candidate_markdown_notes(path: Path, recursive: bool) -> list[Path]:
    if path.is_file():
        return [path]
    if not path.exists():
        return [path]
    pattern = "**/*.md" if recursive else "*.md"
    return sorted(item for item in path.glob(pattern) if item.is_file())


def read_markdown_note(path: Path) -> NoteImportRecord:
    if not path.exists():
        raise FileNotFoundError(f"Markdown note not found: {path}")
    if not path.is_file():
        raise ValueError(f"Markdown note path is not a file: {path}")
    if path.suffix.lower() not in {".md", ".markdown"}:
        raise ValueError(f"Markdown note must have .md or .markdown extension: {path}")
    text = path.read_text(encoding="utf-8")
    metadata, body = split_frontmatter(text)
    return build_note_record(path, metadata, body)


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        return {}, normalized.strip()
    end = normalized.find("\n---\n", 4)
    if end < 0:
        raise ValueError("frontmatter is missing a closing --- line")
    frontmatter = normalized[4:end]
    body = normalized[end + len("\n---\n") :]
    return parse_frontmatter(frontmatter), body.strip()


def parse_frontmatter(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    metadata: dict[str, Any] = {}
    index = 0
    while index < len(lines):
        raw_line = lines[index]
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            index += 1
            continue
        match = re.match(r"^([A-Za-z][A-Za-z0-9_-]*)\s*:\s*(.*)$", raw_line)
        if not match:
            raise ValueError(f"unsupported frontmatter line: {raw_line}")
        key = match.group(1)
        value = match.group(2).strip()
        index += 1
        if value:
            metadata[key] = parse_scalar(value)
            continue
        block_lines: list[str] = []
        while index < len(lines):
            next_line = lines[index]
            if next_line.strip() and re.match(r"^[A-Za-z][A-Za-z0-9_-]*\s*:", next_line):
                break
            block_lines.append(next_line)
            index += 1
        metadata[key] = parse_block_value(key, block_lines)
    return metadata


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if value in {"null", "None", "~"}:
        return None
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [strip_quotes(item.strip()) for item in inner.split(",") if item.strip()]
    value = strip_quotes(value)
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return value


def parse_block_value(key: str, lines: list[str]) -> Any:
    if key == "claims":
        return parse_claim_block(lines)
    values: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- "):
            values.append(strip_quotes(stripped[2:].strip()))
    return values


def parse_claim_block(lines: list[str]) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- "):
            if current:
                claims.append(current)
            current = {}
            item = stripped[2:].strip()
            if item:
                claim_key, claim_value = parse_key_value(item, default_key="statement")
                current[claim_key] = parse_scalar(claim_value)
            continue
        if current is None:
            continue
        claim_key, claim_value = parse_key_value(stripped, default_key="statement")
        current[claim_key] = parse_scalar(claim_value)
    if current:
        claims.append(current)
    return claims


def parse_key_value(text: str, default_key: str) -> tuple[str, str]:
    match = re.match(r"^([A-Za-z][A-Za-z0-9_-]*)\s*:\s*(.*)$", text)
    if match:
        return match.group(1), match.group(2).strip()
    return default_key, text


def strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def build_note_record(path: Path, metadata: dict[str, Any], body: str) -> NoteImportRecord:
    if not body:
        raise ValueError("Markdown note body must not be empty")
    note_seed = str(metadata.get("note_id") or path.stem)
    path_hash = short_hash(path.as_posix())
    chunk_id = string_field(metadata, "chunk_id") or f"chunk_note_{slug_identifier(note_seed)}_{path_hash}"
    paper_id = optional_string(metadata, "paper_id")
    source_type = string_field(metadata, "source_type", default="human_note")
    section = optional_string(metadata, "section") or first_heading(body) or "note"
    locator = optional_string(metadata, "locator") or f"note:{slug_identifier(note_seed)}"
    confidence = parse_confidence(metadata.get("confidence"), default=0.8)
    chunk = {
        "chunk_id": chunk_id,
        "paper_id": paper_id,
        "source_type": source_type,
        "section": section,
        "locator": locator,
        "text": body,
        "embedding_ref": optional_string(metadata, "embedding_ref"),
    }
    claims = build_claims(metadata, body, chunk_id, paper_id, confidence)
    evidence_links = [
        {
            "evidence_id": f"evidence_note_{slug_identifier(chunk_id)}",
            "source_type": "human_note",
            "source_id": chunk_id,
            "paper_id": paper_id,
            "chunk_id": chunk_id,
            "run_id": None,
            "problem_id": None,
            "locator": locator,
            "quote_or_snippet": snippet(body),
            "confidence": confidence,
        }
    ]
    for claim in claims:
        evidence_links.append(
            {
                "evidence_id": f"evidence_claim_{slug_identifier(claim['claim_id'])}",
                "source_type": "claim",
                "source_id": claim["claim_id"],
                "paper_id": paper_id,
                "chunk_id": chunk_id,
                "run_id": None,
                "problem_id": None,
                "locator": locator,
                "quote_or_snippet": snippet(claim["statement"]),
                "confidence": claim.get("confidence"),
            }
        )
    return NoteImportRecord(source=path, chunk=chunk, claims=claims, evidence_links=evidence_links)


def build_claims(
    metadata: dict[str, Any],
    body: str,
    chunk_id: str,
    paper_id: str | None,
    default_confidence: float,
) -> list[dict[str, Any]]:
    claim_inputs: list[dict[str, Any]] = []
    if metadata.get("claim"):
        claim_inputs.append(
            {
                "claim_type": metadata.get("claim_type", "method"),
                "statement": metadata["claim"],
                "confidence": metadata.get("claim_confidence", default_confidence),
                "created_by": metadata.get("created_by", "human"),
            }
        )
    claim_inputs.extend(normalize_claims_metadata(metadata.get("claims"), metadata))
    claim_inputs.extend(extract_body_claim_markers(body, metadata))

    claims: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw_claim in enumerate(claim_inputs, start=1):
        statement = str(raw_claim.get("statement", "")).strip()
        if not statement or statement.lower() in seen:
            continue
        seen.add(statement.lower())
        claim_type = str(raw_claim.get("claim_type") or raw_claim.get("type") or "method").strip()
        claim_confidence = parse_confidence(raw_claim.get("confidence"), default=default_confidence)
        created_by = raw_claim.get("created_by", metadata.get("created_by", "human"))
        generated_claim_id = f"claim_note_{slug_identifier(chunk_id)}_{index}"
        claims.append(
            {
                "claim_id": str(raw_claim.get("claim_id") or generated_claim_id),
                "claim_type": claim_type,
                "statement": statement,
                "paper_id": paper_id,
                "chunk_id": chunk_id,
                "confidence": claim_confidence,
                "created_by": created_by,
            }
        )
    return claims


def normalize_claims_metadata(value: Any, metadata: dict[str, Any]) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, list):
        claims: list[dict[str, Any]] = []
        for item in value:
            if isinstance(item, dict):
                claims.append(
                    {
                        "claim_type": item.get("claim_type")
                        or item.get("type")
                        or metadata.get("claim_type", "method"),
                        "statement": item.get("statement", ""),
                        "confidence": item.get("confidence", metadata.get("confidence")),
                        "created_by": item.get("created_by", metadata.get("created_by", "human")),
                    }
                )
            else:
                claims.append(
                    {
                        "claim_type": metadata.get("claim_type", "method"),
                        "statement": str(item),
                        "confidence": metadata.get("confidence"),
                        "created_by": metadata.get("created_by", "human"),
                    }
                )
        return claims
    if isinstance(value, str):
        statements = [item.strip() for item in value.split("|") if item.strip()]
        return [
            {
                "claim_type": metadata.get("claim_type", "method"),
                "statement": statement,
                "confidence": metadata.get("confidence"),
                "created_by": metadata.get("created_by", "human"),
            }
            for statement in statements
        ]
    return []


def extract_body_claim_markers(body: str, metadata: dict[str, Any]) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    pattern = re.compile(r"^\s*(?:[-*]\s*)?\[claim:(?P<type>[a-z_]+)]\s*(?P<statement>.+?)\s*$")
    for line in body.splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        claims.append(
            {
                "claim_type": match.group("type"),
                "statement": match.group("statement"),
                "confidence": metadata.get("confidence"),
                "created_by": metadata.get("created_by", "human"),
            }
        )
    return claims


def validate_note_record(record: NoteImportRecord) -> None:
    validate_chunk(record.chunk)
    for claim in record.claims:
        validate_claim(claim)
    for evidence in record.evidence_links:
        validate_evidence_link(evidence)


def validate_chunk(chunk: dict[str, Any]) -> None:
    for field in ("chunk_id", "source_type", "text"):
        if not isinstance(chunk.get(field), str) or not chunk[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    if chunk["source_type"] not in CHUNK_SOURCE_TYPES:
        raise ValueError(f"source_type must be one of: {', '.join(sorted(CHUNK_SOURCE_TYPES))}")
    for field in ("paper_id", "section", "locator", "embedding_ref"):
        value = chunk.get(field)
        if value is not None and not isinstance(value, str):
            raise ValueError(f"{field} must be a string or null")
    if contains_local_reference(chunk.get("locator")):
        raise ValueError("locator must not be a file URL or machine-local absolute path")
    if contains_local_reference(chunk.get("embedding_ref")):
        raise ValueError("embedding_ref must not be a file URL or machine-local absolute path")


def validate_claim(claim: dict[str, Any]) -> None:
    for field in ("claim_id", "claim_type", "statement"):
        if not isinstance(claim.get(field), str) or not claim[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    if claim["claim_type"] not in CLAIM_TYPES:
        raise ValueError(f"claim_type must be one of: {', '.join(sorted(CLAIM_TYPES))}")
    if claim.get("confidence") is not None and not 0 <= float(claim["confidence"]) <= 1:
        raise ValueError("confidence must be between 0 and 1")
    if claim.get("created_by") not in CREATED_BY_VALUES:
        raise ValueError("created_by must be human, llm, script, or null")


def validate_evidence_link(evidence: dict[str, Any]) -> None:
    for field in ("evidence_id", "source_type", "source_id"):
        if not isinstance(evidence.get(field), str) or not evidence[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    if evidence["source_type"] not in EVIDENCE_SOURCE_TYPES:
        raise ValueError(f"evidence source_type must be one of: {', '.join(sorted(EVIDENCE_SOURCE_TYPES))}")
    if evidence.get("confidence") is not None and not 0 <= float(evidence["confidence"]) <= 1:
        raise ValueError("confidence must be between 0 and 1")
    if contains_local_reference(evidence.get("locator")):
        raise ValueError("evidence locator must not be a file URL or machine-local absolute path")


def ensure_importable_schema(conn: sqlite3.Connection) -> None:
    required = {
        "chunks": CHUNK_TABLE_COLUMNS,
        "claims": CLAIM_TABLE_COLUMNS,
        "evidence_links": EVIDENCE_TABLE_COLUMNS,
    }
    for table, required_columns in required.items():
        if not table_exists(conn, table):
            raise RuntimeError(f"{table} table does not exist; initialize or map the schema first")
        columns = table_columns(conn, table)
        missing = sorted(required_columns - columns)
        if missing:
            raise RuntimeError(f"{table} is missing required columns: {', '.join(missing)}")


def existing_record_ids(conn: sqlite3.Connection) -> dict[str, set[str]]:
    return {
        "chunks": existing_ids(conn, "chunks", "chunk_id"),
        "claims": existing_ids(conn, "claims", "claim_id"),
        "evidence_links": existing_ids(conn, "evidence_links", "evidence_id"),
    }


def existing_ids(conn: sqlite3.Connection, table: str, id_column: str) -> set[str]:
    if not table_exists(conn, table) or id_column not in table_columns(conn, table):
        return set()
    rows = conn.execute(f"select {quote_identifier(id_column)} from {quote_identifier(table)}").fetchall()
    return {str(row[0]) for row in rows if row[0] is not None}


def plan_rows(
    records: list[NoteImportRecord],
    existing: dict[str, set[str]],
    write: bool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        chunk_action = action_for(record.chunk["chunk_id"], existing["chunks"], write)
        claim_actions = [action_for(claim["claim_id"], existing["claims"], write) for claim in record.claims]
        evidence_actions = [
            action_for(evidence["evidence_id"], existing["evidence_links"], write) for evidence in record.evidence_links
        ]
        rows.append(
            {
                "path": safe_path(record.source),
                "chunk_id": record.chunk["chunk_id"],
                "chunk_action": chunk_action,
                "claim_count": len(record.claims),
                "claim_actions": claim_actions,
                "evidence_link_count": len(record.evidence_links),
                "evidence_link_actions": evidence_actions,
                "action": "valid",
            }
        )
    return rows


def action_for(record_id: str, existing_ids_set: set[str], write: bool) -> str:
    action = "update" if record_id in existing_ids_set else "insert"
    return action if write else f"would_{action}"


def count_planned(rows: list[dict[str, Any]], prefix: str) -> dict[str, int]:
    counts = {"chunks": 0, "claims": 0, "evidence_links": 0}
    for row in rows:
        counts["chunks"] += int(row.get("chunk_action") == prefix)
        counts["claims"] += sum(1 for action in row.get("claim_actions", []) if action == prefix)
        counts["evidence_links"] += sum(1 for action in row.get("evidence_link_actions", []) if action == prefix)
    return counts


def upsert_chunk(conn: sqlite3.Connection, chunk: dict[str, Any], created_at: str) -> None:
    conn.execute(
        """
        insert into chunks(chunk_id, paper_id, source_type, section, locator, text, embedding_ref, created_at)
        values (?, ?, ?, ?, ?, ?, ?, ?)
        on conflict(chunk_id) do update set
            paper_id=excluded.paper_id,
            source_type=excluded.source_type,
            section=excluded.section,
            locator=excluded.locator,
            text=excluded.text,
            embedding_ref=excluded.embedding_ref,
            created_at=excluded.created_at
        """,
        (
            chunk["chunk_id"],
            chunk.get("paper_id"),
            chunk["source_type"],
            chunk.get("section"),
            chunk.get("locator"),
            chunk["text"],
            chunk.get("embedding_ref"),
            created_at,
        ),
    )


def upsert_claim(conn: sqlite3.Connection, claim: dict[str, Any], created_at: str) -> None:
    conn.execute(
        """
        insert into claims(claim_id, claim_type, statement, paper_id, chunk_id, confidence, created_by, created_at)
        values (?, ?, ?, ?, ?, ?, ?, ?)
        on conflict(claim_id) do update set
            claim_type=excluded.claim_type,
            statement=excluded.statement,
            paper_id=excluded.paper_id,
            chunk_id=excluded.chunk_id,
            confidence=excluded.confidence,
            created_by=excluded.created_by,
            created_at=excluded.created_at
        """,
        (
            claim["claim_id"],
            claim["claim_type"],
            claim["statement"],
            claim.get("paper_id"),
            claim.get("chunk_id"),
            claim.get("confidence"),
            claim.get("created_by"),
            created_at,
        ),
    )


def upsert_evidence_link(conn: sqlite3.Connection, evidence: dict[str, Any], created_at: str) -> None:
    conn.execute(
        """
        insert into evidence_links(
            evidence_id, source_type, source_id, paper_id, chunk_id, run_id, problem_id,
            locator, quote_or_snippet, confidence, created_at
        )
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        on conflict(evidence_id) do update set
            source_type=excluded.source_type,
            source_id=excluded.source_id,
            paper_id=excluded.paper_id,
            chunk_id=excluded.chunk_id,
            run_id=excluded.run_id,
            problem_id=excluded.problem_id,
            locator=excluded.locator,
            quote_or_snippet=excluded.quote_or_snippet,
            confidence=excluded.confidence,
            created_at=excluded.created_at
        """,
        (
            evidence["evidence_id"],
            evidence["source_type"],
            evidence["source_id"],
            evidence.get("paper_id"),
            evidence.get("chunk_id"),
            evidence.get("run_id"),
            evidence.get("problem_id"),
            evidence.get("locator"),
            evidence.get("quote_or_snippet"),
            evidence.get("confidence"),
            created_at,
        ),
    )


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "select 1 from sqlite_master where type='table' and name=? limit 1",
        (table,),
    ).fetchone()
    return row is not None


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"pragma table_info({quote_identifier(table)})").fetchall()
    return {str(row[1]) for row in rows}


def string_field(metadata: dict[str, Any], key: str, default: str | None = None) -> str | None:
    value = metadata.get(key, default)
    if value is None:
        return None
    return str(value).strip()


def optional_string(metadata: dict[str, Any], key: str) -> str | None:
    value = string_field(metadata, key)
    return value or None


def parse_confidence(value: Any, default: float) -> float:
    if value is None:
        return default
    return float(value)


def first_heading(body: str) -> str | None:
    for line in body.splitlines():
        match = re.match(r"^#{1,6}\s+(.+)$", line.strip())
        if match:
            return match.group(1).strip()
    return None


def snippet(text: str, limit: int = 240) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    return compact[:limit]


def slug_identifier(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", value.strip().lower()).strip("_")
    return slug or "unknown"


def short_hash(value: str, length: int = 10) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:length]


def contains_local_reference(value: Any) -> bool:
    return isinstance(value, str) and re.match(r"^(?:file://|[A-Za-z]:[\\/]|/)", value) is not None


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def quote_identifier(name: str) -> str:
    escaped = name.replace('"', '""')
    return f'"{escaped}"'


def safe_path(path: Path) -> str:
    return path.as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
