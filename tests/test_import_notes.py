from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from researchkb_agent_memory import demo, import_notes  # noqa: E402


def write_note(path: Path, statement: str = "Cache reuse needs compatibility checks.") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""---
note_id: import-note-001
paper_id: paper_example_cache_001
section: Import note
confidence: 0.87
created_by: human
claim: {statement}
claim_type: safety
---

# Import Note

This is a synthetic Markdown note about cache reuse safety.

- [claim:limitation] Reusing incompatible prefixes can reduce generation quality.
""",
        encoding="utf-8",
    )
    return path


def fetch_one(root: Path, table: str, id_column: str, record_id: str) -> sqlite3.Row | None:
    conn = sqlite3.connect(root / "db" / "literature.sqlite")
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(f"select * from {table} where {id_column} = ?", (record_id,)).fetchone()
    finally:
        conn.close()


@pytest.fixture()
def demo_root(tmp_path: Path) -> Path:
    root = tmp_path / "researchkb"
    demo.seed_demo_db(root=root, examples_dir=REPO_ROOT / "examples", force=True)
    return root


def test_import_notes_dry_run_does_not_write(demo_root: Path, tmp_path: Path) -> None:
    note_path = write_note(tmp_path / "notes" / "cache.md")

    summary = import_notes.import_markdown_notes(root=demo_root, paths=[note_path], write=False)

    assert summary["write"] is False
    assert summary["valid"] == 1
    assert summary["would_insert"]["chunks"] == 1
    assert summary["would_insert"]["claims"] == 2
    assert summary["would_insert"]["evidence_links"] == 3
    chunk_id = summary["records"][0]["chunk_id"]
    assert fetch_one(demo_root, "chunks", "chunk_id", chunk_id) is None


def test_import_notes_write_inserts_and_updates(demo_root: Path, tmp_path: Path) -> None:
    note_path = write_note(tmp_path / "notes" / "cache.md")

    first = import_notes.import_markdown_notes(root=demo_root, paths=[note_path], write=True)
    assert first["inserted"]["chunks"] == 1
    assert first["inserted"]["claims"] == 2
    assert first["inserted"]["evidence_links"] == 3
    chunk_id = first["records"][0]["chunk_id"]
    row = fetch_one(demo_root, "chunks", "chunk_id", chunk_id)
    assert row is not None
    assert row["source_type"] == "human_note"
    assert row["paper_id"] == "paper_example_cache_001"
    assert "Markdown note" in row["text"]

    write_note(note_path, statement="Cache reuse needs a stricter compatibility gate.")
    second = import_notes.import_markdown_notes(root=demo_root, paths=[note_path], write=True)
    assert second["inserted"]["chunks"] == 0
    assert second["updated"]["chunks"] == 1
    assert second["updated"]["claims"] == 2
    assert second["updated"]["evidence_links"] == 3


def test_import_notes_rejects_local_locator(tmp_path: Path) -> None:
    note_path = tmp_path / "bad.md"
    note_path.write_text(
        """---
locator: file:///private/note.md
---

# Bad Note

This note has a private local locator.
""",
        encoding="utf-8",
    )

    summary = import_notes.import_markdown_notes(root=tmp_path / "researchkb", paths=[note_path])

    assert summary["valid"] == 0
    assert summary["invalid"] == 1
    assert "locator" in summary["records"][0]["error"]


def test_import_notes_discovers_direct_directory_notes(demo_root: Path, tmp_path: Path) -> None:
    notes_root = tmp_path / "notes"
    write_note(notes_root / "a.md")
    write_note(notes_root / "b.md")

    summary = import_notes.import_markdown_notes(root=demo_root, paths=[notes_root])

    assert summary["discovered"] == 2
    assert summary["valid"] == 2


def test_import_notes_requires_schema_for_write(tmp_path: Path) -> None:
    root = tmp_path / "researchkb"
    db_dir = root / "db"
    db_dir.mkdir(parents=True)
    sqlite3.connect(db_dir / "literature.sqlite").close()
    note_path = write_note(tmp_path / "notes" / "cache.md")

    with pytest.raises(RuntimeError, match="chunks table"):
        import_notes.import_markdown_notes(root=root, paths=[note_path], write=True)
