"""Import BibTeX paper metadata into a ResearchKB SQLite database.

Writes are explicit: the command defaults to dry-run mode and only modifies the
database when `--write` is supplied. This importer stores metadata only; it does
not copy PDFs, notes, or machine-local file paths.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path(".runtime") / "researchkb"
PAPER_TABLE_COLUMNS = {
    "paper_id",
    "title",
    "authors_json",
    "year",
    "venue",
    "doi",
    "arxiv_id",
    "url",
    "tags_json",
    "created_at",
}
ENTRY_TYPES_TO_SKIP = {"comment", "preamble", "string"}


@dataclass(frozen=True)
class BibEntry:
    source: Path
    entry_type: str
    key: str
    fields: dict[str, str]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import BibTeX paper metadata into papers.")
    parser.add_argument("paths", nargs="+", type=Path, help="BibTeX .bib files.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="ResearchKB root.")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Actually write to SQLite. Omit for dry-run planning.",
    )
    args = parser.parse_args(argv)

    summary = import_bibtex_files(root=args.root, paths=args.paths, write=args.write)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["invalid"] == 0 else 1


def import_bibtex_files(root: Path, paths: list[Path], write: bool = False) -> dict[str, Any]:
    root = root.resolve()
    db_path = root / "db" / "literature.sqlite"
    entries: list[BibEntry] = []
    rows: list[dict[str, Any]] = []
    valid_records: list[tuple[BibEntry, dict[str, Any]]] = []

    for path in paths:
        try:
            entries.extend(read_bibtex_file(path))
        except Exception as exc:
            rows.append(
                {
                    "path": safe_path(path),
                    "paper_id": None,
                    "action": "invalid",
                    "error": str(exc),
                }
            )

    for entry in entries:
        try:
            paper = bib_entry_to_paper(entry)
            validate_paper_record(paper)
        except Exception as exc:
            rows.append(
                {
                    "path": safe_path(entry.source),
                    "bibkey": entry.key,
                    "paper_id": None,
                    "action": "invalid",
                    "error": str(exc),
                }
            )
            continue
        valid_records.append((entry, paper))

    existing_ids: set[str] = set()
    if db_path.exists() and valid_records:
        with sqlite3.connect(db_path) as conn:
            if table_exists(conn, "papers") and "paper_id" in table_columns(conn, "papers"):
                existing_ids = existing_paper_ids(conn)

    for entry, paper in valid_records:
        action = "update" if paper["paper_id"] in existing_ids else "insert"
        rows.append(
            {
                "path": safe_path(entry.source),
                "bibkey": entry.key,
                "paper_id": paper["paper_id"],
                "title": paper["title"],
                "year": paper.get("year"),
                "action": action if write else f"would_{action}",
            }
        )

    inserted = 0
    updated = 0
    if write and valid_records:
        if not db_path.exists():
            raise FileNotFoundError(f"ResearchKB database not found: {db_path}")
        with sqlite3.connect(db_path) as conn:
            ensure_importable_schema(conn)
            created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            existing_ids = existing_paper_ids(conn)
            for _entry, paper in valid_records:
                if paper["paper_id"] in existing_ids:
                    updated += 1
                else:
                    inserted += 1
                upsert_paper(conn, paper, created_at)
            conn.commit()

    invalid = sum(1 for row in rows if row["action"] == "invalid")
    would_insert = sum(1 for row in rows if row["action"] == "would_insert")
    would_update = sum(1 for row in rows if row["action"] == "would_update")
    return {
        "root": str(root),
        "db_path": str(db_path),
        "write": write,
        "discovered": len(entries),
        "valid": len(valid_records),
        "invalid": invalid,
        "inserted": inserted,
        "updated": updated,
        "would_insert": would_insert,
        "would_update": would_update,
        "records": rows,
    }


def read_bibtex_file(path: Path) -> list[BibEntry]:
    path = path.expanduser()
    if not path.exists():
        raise FileNotFoundError(f"BibTeX file not found: {path}")
    if not path.is_file():
        raise ValueError(f"BibTeX path is not a file: {path}")
    return parse_bibtex(path.read_text(encoding="utf-8"), path)


def parse_bibtex(text: str, source: Path) -> list[BibEntry]:
    entries: list[BibEntry] = []
    offset = 0
    while True:
        at_index = text.find("@", offset)
        if at_index < 0:
            break
        match = re.match(r"@([A-Za-z]+)\s*([({])", text[at_index:])
        if not match:
            offset = at_index + 1
            continue
        entry_type = match.group(1).lower()
        opener = match.group(2)
        open_index = at_index + match.end() - 1
        close_index = find_matching_delimiter(text, open_index, opener)
        if close_index < 0:
            raise ValueError(f"Unclosed BibTeX entry starting at character {at_index}")
        body = text[open_index + 1 : close_index].strip()
        offset = close_index + 1
        if entry_type in ENTRY_TYPES_TO_SKIP:
            continue
        key, fields_text = split_entry_body(body)
        entries.append(BibEntry(source=source, entry_type=entry_type, key=key, fields=parse_fields(fields_text)))
    return entries


def find_matching_delimiter(text: str, open_index: int, opener: str) -> int:
    closer = "}" if opener == "{" else ")"
    depth = 0
    in_quote = False
    escaped = False
    for index in range(open_index, len(text)):
        char = text[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_quote = not in_quote
            continue
        if in_quote:
            continue
        if char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return index
    return -1


def split_entry_body(body: str) -> tuple[str, str]:
    comma = body.find(",")
    if comma < 0:
        raise ValueError("BibTeX entry is missing field list")
    key = body[:comma].strip()
    if not key:
        raise ValueError("BibTeX entry key is empty")
    return key, body[comma + 1 :]


def parse_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    index = 0
    while index < len(text):
        index = skip_separators(text, index)
        if index >= len(text):
            break
        name_match = re.match(r"([A-Za-z][A-Za-z0-9_:-]*)\s*=", text[index:])
        if not name_match:
            break
        name = name_match.group(1).lower()
        index += name_match.end()
        value, index = parse_value_expression(text, index)
        fields[name] = clean_bibtex_value(value)
        index = skip_to_next_field(text, index)
    return fields


def parse_value_expression(text: str, index: int) -> tuple[str, int]:
    parts: list[str] = []
    while True:
        index = skip_whitespace(text, index)
        value, index = parse_single_value(text, index)
        parts.append(value)
        index = skip_whitespace(text, index)
        if index >= len(text) or text[index] != "#":
            break
        index += 1
    return " ".join(part for part in parts if part.strip()), index


def parse_single_value(text: str, index: int) -> tuple[str, int]:
    if index >= len(text):
        return "", index
    char = text[index]
    if char == "{":
        close_index = find_matching_delimiter(text, index, "{")
        if close_index < 0:
            raise ValueError("Unclosed braced BibTeX value")
        return text[index + 1 : close_index], close_index + 1
    if char == '"':
        return parse_quoted_value(text, index)
    start = index
    while index < len(text) and text[index] not in ",#\r\n":
        index += 1
    return text[start:index].strip(), index


def parse_quoted_value(text: str, index: int) -> tuple[str, int]:
    index += 1
    chars: list[str] = []
    escaped = False
    while index < len(text):
        char = text[index]
        index += 1
        if escaped:
            chars.append(char)
            escaped = False
            continue
        if char == "\\":
            escaped = True
            chars.append(char)
            continue
        if char == '"':
            return "".join(chars), index
        chars.append(char)
    raise ValueError("Unclosed quoted BibTeX value")


def skip_separators(text: str, index: int) -> int:
    while index < len(text) and (text[index].isspace() or text[index] == ","):
        index += 1
    return index


def skip_whitespace(text: str, index: int) -> int:
    while index < len(text) and text[index].isspace():
        index += 1
    return index


def skip_to_next_field(text: str, index: int) -> int:
    while index < len(text) and text[index] != ",":
        index += 1
    if index < len(text) and text[index] == ",":
        index += 1
    return index


def clean_bibtex_value(value: str) -> str:
    value = value.replace("\\&", "&").replace("\\_", "_").replace("\\%", "%")
    value = value.replace("{", "").replace("}", "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def bib_entry_to_paper(entry: BibEntry) -> dict[str, Any]:
    fields = entry.fields
    title = fields.get("title", "")
    doi = normalize_doi(fields.get("doi"))
    arxiv_id = normalize_arxiv_id(fields.get("eprint"), fields.get("archiveprefix"), fields.get("url"))
    return {
        "paper_id": paper_id_for_entry(entry.key, doi=doi, arxiv_id=arxiv_id),
        "title": title,
        "authors": split_authors(fields.get("author")),
        "year": parse_year(fields.get("year")),
        "venue": first_non_empty(fields, ("venue", "journal", "booktitle", "publisher")),
        "doi": doi,
        "arxiv_id": arxiv_id,
        "url": fields.get("url"),
        "tags": parse_tags(fields),
    }


def validate_paper_record(paper: dict[str, Any]) -> None:
    for field in ("paper_id", "title"):
        if not isinstance(paper.get(field), str) or not paper[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    if paper.get("year") is not None and not isinstance(paper["year"], int):
        raise ValueError("year must be an integer or null")
    for field in ("venue", "doi", "arxiv_id", "url"):
        value = paper.get(field)
        if value is not None and not isinstance(value, str):
            raise ValueError(f"{field} must be a string or null")
    if contains_local_reference(paper.get("url")):
        raise ValueError("url must not be a file URL or machine-local absolute path")
    for field in ("authors", "tags"):
        value = paper.get(field, [])
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise ValueError(f"{field} must be a list of strings")


def paper_id_for_entry(key: str, doi: str | None, arxiv_id: str | None) -> str:
    if doi:
        return "paper_doi_" + slug_identifier(doi)
    if arxiv_id:
        return "paper_arxiv_" + slug_identifier(arxiv_id)
    return "paper_bib_" + slug_identifier(key)


def slug_identifier(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", value.strip().lower()).strip("_")
    return slug or "unknown"


def split_authors(value: str | None) -> list[str]:
    if not value:
        return []
    return [author.strip() for author in re.split(r"\s+and\s+", value) if author.strip()]


def parse_year(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"\d{4}", value)
    return int(match.group(0)) if match else None


def normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    doi = value.strip()
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE)
    return doi.lower() or None


def normalize_arxiv_id(eprint: str | None, archive_prefix: str | None, url: str | None) -> str | None:
    if eprint and (not archive_prefix or archive_prefix.lower() == "arxiv" or looks_like_arxiv_id(eprint)):
        return eprint.strip()
    if url:
        match = re.search(r"arxiv\.org/(?:abs|pdf)/([^?#.\s]+(?:\.[^?#.\s]+)?)", url, re.IGNORECASE)
        if match:
            return match.group(1).removesuffix(".pdf")
    return None


def looks_like_arxiv_id(value: str) -> bool:
    return re.match(r"^(?:\d{4}\.\d{4,5}(?:v\d+)?|[A-Za-z-]+/\d{7})$", value.strip()) is not None


def first_non_empty(fields: dict[str, str], names: tuple[str, ...]) -> str | None:
    for name in names:
        value = fields.get(name)
        if value:
            return value
    return None


def parse_tags(fields: dict[str, str]) -> list[str]:
    values: list[str] = []
    for name in ("keywords", "tags"):
        if fields.get(name):
            values.extend(re.split(r"[,;]", fields[name]))
    if fields.get("primaryclass"):
        values.append(fields["primaryclass"])
    seen: set[str] = set()
    tags: list[str] = []
    for raw_tag in values:
        tag = raw_tag.strip()
        if not tag or tag.lower() in seen:
            continue
        seen.add(tag.lower())
        tags.append(tag)
    return tags


def contains_local_reference(value: str | None) -> bool:
    if not value:
        return False
    return bool(re.match(r"^(?:file://|[A-Za-z]:[\\/]|/)", value))


def ensure_importable_schema(conn: sqlite3.Connection) -> None:
    if not table_exists(conn, "papers"):
        raise RuntimeError("papers table does not exist; initialize or map the schema first")
    columns = table_columns(conn, "papers")
    missing = sorted(PAPER_TABLE_COLUMNS - columns)
    if missing:
        raise RuntimeError("papers is missing required columns: " + ", ".join(missing))


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "select 1 from sqlite_master where type='table' and name=? limit 1",
        (table,),
    ).fetchone()
    return row is not None


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"pragma table_info({quote_identifier(table)})").fetchall()
    return {str(row[1]) for row in rows}


def existing_paper_ids(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("select paper_id from papers").fetchall()
    return {str(row[0]) for row in rows if row[0] is not None}


def upsert_paper(conn: sqlite3.Connection, paper: dict[str, Any], created_at: str) -> None:
    conn.execute(
        """
        insert into papers(
            paper_id, title, authors_json, year, venue, doi, arxiv_id, url, tags_json, created_at
        )
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        on conflict(paper_id) do update set
            title=excluded.title,
            authors_json=excluded.authors_json,
            year=excluded.year,
            venue=excluded.venue,
            doi=excluded.doi,
            arxiv_id=excluded.arxiv_id,
            url=excluded.url,
            tags_json=excluded.tags_json,
            created_at=excluded.created_at
        """,
        (
            paper["paper_id"],
            paper["title"],
            dumps(paper.get("authors", [])),
            paper.get("year"),
            paper.get("venue"),
            paper.get("doi"),
            paper.get("arxiv_id"),
            paper.get("url"),
            dumps(paper.get("tags", [])),
            created_at,
        ),
    )


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def quote_identifier(name: str) -> str:
    escaped = name.replace('"', '""')
    return f'"{escaped}"'


def safe_path(path: Path) -> str:
    return path.as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
