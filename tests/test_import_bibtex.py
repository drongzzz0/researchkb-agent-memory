from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from researchkb_agent_memory import demo, import_bibtex  # noqa: E402


def write_bib(path: Path, title: str = "Synthetic Cache Reuse Study") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""@article{{cache2026,
  title = {{{title}}},
  author = {{Example Author and Sample Researcher}},
  year = {{2026}},
  journal = {{Synthetic Journal}},
  doi = {{10.1234/synthetic.cache.001}},
  keywords = {{cache-reuse, llm-serving}}
}}

@inproceedings{{arxivExample,
  title = {{Synthetic Safety Analysis}},
  author = {{Safety Author}},
  year = {{2025}},
  booktitle = {{Synthetic Conference}},
  eprint = {{2501.00001}},
  archivePrefix = {{arXiv}},
  primaryClass = {{cs.CL}},
  url = {{https://arxiv.org/abs/2501.00001}}
}}
""",
        encoding="utf-8",
    )
    return path


def fetch_paper(root: Path, paper_id: str) -> sqlite3.Row | None:
    conn = sqlite3.connect(root / "db" / "literature.sqlite")
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("select * from papers where paper_id = ?", (paper_id,)).fetchone()
    finally:
        conn.close()


@pytest.fixture()
def demo_root(tmp_path: Path) -> Path:
    root = tmp_path / "researchkb"
    demo.seed_demo_db(root=root, examples_dir=REPO_ROOT / "examples", force=True)
    return root


def test_import_bibtex_dry_run_does_not_write(demo_root: Path, tmp_path: Path) -> None:
    bib_path = write_bib(tmp_path / "export.bib")

    summary = import_bibtex.import_bibtex_files(root=demo_root, paths=[bib_path], write=False)

    assert summary["write"] is False
    assert summary["valid"] == 2
    assert summary["would_insert"] == 2
    assert fetch_paper(demo_root, "paper_doi_10_1234_synthetic_cache_001") is None


def test_import_bibtex_write_inserts_and_updates(demo_root: Path, tmp_path: Path) -> None:
    bib_path = write_bib(tmp_path / "export.bib")

    first = import_bibtex.import_bibtex_files(root=demo_root, paths=[bib_path], write=True)
    assert first["inserted"] == 2
    assert first["updated"] == 0
    row = fetch_paper(demo_root, "paper_doi_10_1234_synthetic_cache_001")
    assert row is not None
    assert row["title"] == "Synthetic Cache Reuse Study"
    assert json.loads(row["authors_json"]) == ["Example Author", "Sample Researcher"]
    assert json.loads(row["tags_json"]) == ["cache-reuse", "llm-serving"]

    write_bib(bib_path, title="Synthetic Cache Reuse Study Updated")
    second = import_bibtex.import_bibtex_files(root=demo_root, paths=[bib_path], write=True)
    assert second["inserted"] == 0
    assert second["updated"] == 2
    row = fetch_paper(demo_root, "paper_doi_10_1234_synthetic_cache_001")
    assert row is not None
    assert row["title"] == "Synthetic Cache Reuse Study Updated"


def test_import_bibtex_rejects_missing_title(tmp_path: Path) -> None:
    bib_path = tmp_path / "bad.bib"
    bib_path.write_text("@misc{bad, author = {Example Author}, year = {2026}}\n", encoding="utf-8")

    summary = import_bibtex.import_bibtex_files(root=tmp_path / "researchkb", paths=[bib_path])

    assert summary["valid"] == 0
    assert summary["invalid"] == 1
    assert "title" in summary["records"][0]["error"]


def test_import_bibtex_rejects_file_url(tmp_path: Path) -> None:
    bib_path = tmp_path / "bad-url.bib"
    bib_path.write_text(
        """@misc{badUrl,
  title = {Bad Local URL},
  author = {Example Author},
  url = {file:///private/paper.pdf}
}
""",
        encoding="utf-8",
    )

    summary = import_bibtex.import_bibtex_files(root=tmp_path / "researchkb", paths=[bib_path])

    assert summary["valid"] == 0
    assert summary["invalid"] == 1
    assert "file URL" in summary["records"][0]["error"]


def test_import_bibtex_requires_schema_for_write(tmp_path: Path) -> None:
    root = tmp_path / "researchkb"
    db_dir = root / "db"
    db_dir.mkdir(parents=True)
    sqlite3.connect(db_dir / "literature.sqlite").close()
    bib_path = write_bib(tmp_path / "export.bib")

    with pytest.raises(RuntimeError, match="papers table"):
        import_bibtex.import_bibtex_files(root=root, paths=[bib_path], write=True)
