"""Read-only query engine for ResearchKB SQLite databases.

Opens the source database in read-only mode and builds an in-memory FTS5
index over searchable tables, so agent queries never modify the library.
Falls back to token-based LIKE search when FTS5 is unavailable.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")
SNIPPET_WINDOW = 120
MAX_LIMIT = 50

# table -> (id column, searchable text columns)
SEARCH_SPECS = {
    "papers": ("paper_id", ["title", "venue", "tags_json", "authors_json"]),
    "chunks": ("chunk_id", ["text", "section", "locator"]),
    "claims": ("claim_id", ["statement", "claim_type"]),
    "problem_cases": (
        "problem_id",
        ["symptom", "final_solution", "context_json", "suspected_causes_json", "tried_fixes_json"],
    ),
    "evidence_links": ("evidence_id", ["quote_or_snippet", "locator"]),
}


class QueryEngine:
    """Evidence lookup over one ResearchKB database, tolerant to partial schemas."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.db_path = self.root / "db" / "literature.sqlite"
        if not self.db_path.exists():
            raise FileNotFoundError(f"ResearchKB database not found: {self.db_path}")
        self.conn = sqlite3.connect("file::memory:", uri=True)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("attach ? as src", (f"file:{self.db_path.as_posix()}?mode=ro",))
        self.tables = self._source_tables()
        self.columns = {table: self._source_columns(table) for table in self.tables}
        self.fts_available = self._detect_fts5()
        self.indexed_tables: set[str] = set()
        if self.fts_available:
            self._build_fts_index()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> QueryEngine:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # -- schema discovery -------------------------------------------------

    def _source_tables(self) -> set[str]:
        rows = self.conn.execute("select name from src.sqlite_master where type='table'").fetchall()
        return {str(row["name"]) for row in rows}

    def _source_columns(self, table: str) -> set[str]:
        rows = self.conn.execute(f"pragma src.table_info({quote_identifier(table)})").fetchall()
        return {str(row["name"]) for row in rows}

    def _detect_fts5(self) -> bool:
        try:
            self.conn.execute("create virtual table fts_probe using fts5(x)")
            self.conn.execute("drop table fts_probe")
            return True
        except sqlite3.OperationalError:
            return False

    def _build_fts_index(self) -> None:
        for table, (id_column, text_columns) in SEARCH_SPECS.items():
            if table not in self.tables or id_column not in self.columns[table]:
                continue
            available = [column for column in text_columns if column in self.columns[table]]
            if not available:
                continue
            fts_name = f"fts_{table}"
            column_sql = ", ".join(["record_id UNINDEXED", *available])
            self.conn.execute(f"create virtual table {fts_name} using fts5({column_sql})")
            select_sql = ", ".join([quote_identifier(id_column), *[quote_identifier(c) for c in available]])
            rows = self.conn.execute(f"select {select_sql} from src.{quote_identifier(table)}").fetchall()
            placeholders = ", ".join(["?"] * (len(available) + 1))
            self.conn.executemany(
                f"insert into {fts_name} values ({placeholders})",
                [tuple(str(value) if value is not None else "" for value in row) for row in rows],
            )
            self.indexed_tables.add(table)

    # -- generic search ---------------------------------------------------

    def _search_ids(self, table: str, query: str, limit: int) -> list[str]:
        tokens = TOKEN_RE.findall(query)
        if not tokens:
            return []
        if self.fts_available and table in self.indexed_tables:
            match = " OR ".join(f'"{token}"' for token in tokens)
            rows = self.conn.execute(
                f"select record_id from fts_{table} where fts_{table} match ? order by rank limit ?",
                (match, limit),
            ).fetchall()
            return [str(row["record_id"]) for row in rows]
        return self._search_ids_like(table, tokens, limit)

    def _search_ids_like(self, table: str, tokens: list[str], limit: int) -> list[str]:
        id_column, text_columns = SEARCH_SPECS[table]
        if table not in self.tables or id_column not in self.columns[table]:
            return []
        available = [column for column in text_columns if column in self.columns[table]]
        if not available:
            return []
        clauses = []
        params: list[str] = []
        for token in tokens:
            escaped = token.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            for column in available:
                clauses.append(f"lower(coalesce({quote_identifier(column)}, '')) like ? escape '\\'")
                params.append(f"%{escaped.lower()}%")
        sql = (
            f"select {quote_identifier(id_column)} as record_id from src.{quote_identifier(table)} "
            f"where {' or '.join(clauses)} limit ?"
        )
        rows = self.conn.execute(sql, (*params, limit)).fetchall()
        return [str(row["record_id"]) for row in rows]

    def _fetch_rows(self, table: str, ids: list[str]) -> list[dict[str, Any]]:
        if not ids:
            return []
        id_column = SEARCH_SPECS[table][0]
        placeholders = ", ".join(["?"] * len(ids))
        rows = self.conn.execute(
            f"select * from src.{quote_identifier(table)} where {quote_identifier(id_column)} in ({placeholders})",
            ids,
        ).fetchall()
        by_id = {str(row[id_column]): dict(row) for row in rows}
        return [by_id[record_id] for record_id in ids if record_id in by_id]

    def _base_warnings(self, table: str) -> list[str]:
        warnings: list[str] = []
        if table not in self.tables:
            warnings.append(f"Table '{table}' does not exist in this ResearchKB database.")
        elif not self.fts_available:
            warnings.append("SQLite FTS5 is unavailable; falling back to substring search.")
        return warnings

    # -- contract tools ---------------------------------------------------

    def search_papers(self, query: str, limit: int = 10) -> dict[str, Any]:
        limit = clamp_limit(limit)
        rows = self._fetch_rows("papers", self._search_ids("papers", query, limit))
        tokens = TOKEN_RE.findall(query)
        papers = [
            {
                "paper_id": row.get("paper_id"),
                "title": row.get("title"),
                "year": row.get("year"),
                "venue": row.get("venue"),
                "url": row.get("url"),
                "tags": parse_json_list(row.get("tags_json")),
                "source_type": "paper",
                "source_id": row.get("paper_id"),
                "locator": f"paper:{row.get('paper_id')}",
                "snippet": make_snippet(str(row.get("title") or ""), tokens),
                "confidence": rank_confidence(index),
            }
            for index, row in enumerate(rows)
        ]
        return {
            "papers": papers,
            "missing_context": [] if papers else [f"No papers matched query: {query!r}."],
            "warnings": self._base_warnings("papers"),
        }

    def search_chunks(self, query: str, limit: int = 10) -> dict[str, Any]:
        limit = clamp_limit(limit)
        rows = self._fetch_rows("chunks", self._search_ids("chunks", query, limit))
        tokens = TOKEN_RE.findall(query)
        chunks = [
            {
                "chunk_id": row.get("chunk_id"),
                "paper_id": row.get("paper_id"),
                "section": row.get("section"),
                "source_type": "chunk",
                "source_id": row.get("chunk_id"),
                "locator": row.get("locator") or f"chunk:{row.get('chunk_id')}",
                "snippet": make_snippet(str(row.get("text") or ""), tokens),
                "confidence": rank_confidence(index),
            }
            for index, row in enumerate(rows)
        ]
        return {
            "chunks": chunks,
            "missing_context": [] if chunks else [f"No chunks matched query: {query!r}."],
            "warnings": self._base_warnings("chunks"),
        }

    def search_claims(self, query: str, limit: int = 10) -> dict[str, Any]:
        limit = clamp_limit(limit)
        rows = self._fetch_rows("claims", self._search_ids("claims", query, limit))
        tokens = TOKEN_RE.findall(query)
        claims = [
            {
                "claim_id": row.get("claim_id"),
                "claim_type": row.get("claim_type"),
                "statement": row.get("statement"),
                "paper_id": row.get("paper_id"),
                "chunk_id": row.get("chunk_id"),
                "source_type": "claim",
                "source_id": row.get("claim_id"),
                "locator": claim_locator(row),
                "snippet": make_snippet(str(row.get("statement") or ""), tokens),
                "confidence": stored_or_rank_confidence(row.get("confidence"), index),
            }
            for index, row in enumerate(rows)
        ]
        return {
            "claims": claims,
            "missing_context": [] if claims else [f"No claims matched query: {query!r}."],
            "warnings": self._base_warnings("claims"),
        }

    def find_failure_cases(self, symptom: str, limit: int = 10) -> dict[str, Any]:
        limit = clamp_limit(limit)
        rows = self._fetch_rows("problem_cases", self._search_ids("problem_cases", symptom, limit))
        tokens = TOKEN_RE.findall(symptom)
        cases = [
            {
                "problem_id": row.get("problem_id"),
                "symptom": row.get("symptom"),
                "context": parse_json_value(row.get("context_json")),
                "suspected_causes": parse_json_list(row.get("suspected_causes_json")),
                "tried_fixes": parse_json_list(row.get("tried_fixes_json")),
                "fix": row.get("final_solution"),
                "linked_runs": parse_json_list(row.get("linked_runs_json")),
                "linked_papers": parse_json_list(row.get("linked_papers_json")),
                "source_type": "problem_case",
                "source_id": row.get("problem_id"),
                "locator": f"problem_case:{row.get('problem_id')}",
                "snippet": make_snippet(str(row.get("symptom") or ""), tokens),
                "confidence": stored_or_rank_confidence(row.get("confidence"), index),
            }
            for index, row in enumerate(rows)
        ]
        return {
            "cases": cases,
            "missing_context": [] if cases else [f"No failure cases matched symptom: {symptom!r}."],
            "warnings": self._base_warnings("problem_cases"),
        }

    def search_evidence(self, query: str, limit: int = 10) -> dict[str, Any]:
        limit = clamp_limit(limit)
        rows = self._fetch_rows("evidence_links", self._search_ids("evidence_links", query, limit))
        tokens = TOKEN_RE.findall(query)
        links = [
            {
                "evidence_id": row.get("evidence_id"),
                "paper_id": row.get("paper_id"),
                "chunk_id": row.get("chunk_id"),
                "run_id": row.get("run_id"),
                "problem_id": row.get("problem_id"),
                "source_type": row.get("source_type") or "evidence_link",
                "source_id": row.get("source_id") or row.get("evidence_id"),
                "locator": row.get("locator") or f"evidence:{row.get('evidence_id')}",
                "snippet": make_snippet(str(row.get("quote_or_snippet") or ""), tokens),
                "confidence": stored_or_rank_confidence(row.get("confidence"), index),
            }
            for index, row in enumerate(rows)
        ]
        chunk_result = self.search_chunks(query, limit)
        missing: list[str] = []
        if not links and not chunk_result["chunks"]:
            missing.append(f"No evidence links or chunks matched query: {query!r}.")
        return {
            "evidence_links": links,
            "chunks": chunk_result["chunks"],
            "missing_context": missing,
            "warnings": self._base_warnings("evidence_links"),
        }

    def find_recent_runs(
        self,
        project: str | None = None,
        status: str | None = None,
        limit: int = 5,
    ) -> dict[str, Any]:
        limit = clamp_limit(limit)
        warnings = self._base_warnings("experiment_runs") if "experiment_runs" not in self.tables else []
        if "experiment_runs" not in self.tables:
            return {"runs": [], "missing_context": ["No experiment_runs table available."], "warnings": warnings}
        columns = self.columns["experiment_runs"]
        clauses: list[str] = []
        params: list[Any] = []
        if project and "project" in columns:
            clauses.append("lower(project) = ?")
            params.append(project.lower())
        if status and "status" in columns:
            clauses.append("lower(status) = ?")
            params.append(status.lower())
        where_sql = f" where {' and '.join(clauses)}" if clauses else ""
        order_sql = " order by created_at desc" if "created_at" in columns else ""
        rows = self.conn.execute(
            f"select * from src.experiment_runs{where_sql}{order_sql} limit ?",
            (*params, limit),
        ).fetchall()
        runs = []
        for row in rows:
            record = dict(row)
            runs.append(
                {
                    "run_id": record.get("run_id"),
                    "project": record.get("project"),
                    "experiment": record.get("experiment"),
                    "status": record.get("status"),
                    "dataset": record.get("dataset"),
                    "model": record.get("model"),
                    "metrics": parse_json_value(record.get("metrics_json")) or {},
                    "failure_type": record.get("failure_type"),
                    "decision": record.get("decision"),
                    "next_action": record.get("next_action"),
                    "created_at": record.get("created_at"),
                    "source_type": "run",
                    "source_id": record.get("run_id"),
                    "locator": f"experiment_runs:{record.get('run_id')}",
                }
            )
        missing: list[str] = []
        if not runs:
            missing.append("No runs matched the requested filters.")
        return {"runs": runs, "missing_context": missing, "warnings": warnings}

    def compare_runs(self, run_a: str, run_b: str, metrics: list[str] | None = None) -> dict[str, Any]:
        if "experiment_runs" not in self.tables:
            return {
                "comparison": None,
                "evidence": [],
                "missing_context": ["No experiment_runs table available."],
                "warnings": self._base_warnings("experiment_runs"),
            }
        missing_context: list[str] = []
        records: dict[str, dict[str, Any] | None] = {}
        for run_id in (run_a, run_b):
            row = self.conn.execute(
                "select * from src.experiment_runs where run_id = ?",
                (run_id,),
            ).fetchone()
            records[run_id] = dict(row) if row else None
            if row is None:
                missing_context.append(f"Run not found: {run_id}.")
        if records[run_a] is None or records[run_b] is None:
            return {"comparison": None, "evidence": [], "missing_context": missing_context, "warnings": []}

        metrics_a = parse_json_value(records[run_a].get("metrics_json")) or {}
        metrics_b = parse_json_value(records[run_b].get("metrics_json")) or {}
        requested = metrics or sorted(set(metrics_a) | set(metrics_b))
        deltas: dict[str, float] = {}
        for name in requested:
            value_a = to_float(metrics_a.get(name))
            value_b = to_float(metrics_b.get(name))
            if value_a is None or value_b is None:
                missing_context.append(f"Metric '{name}' is not numeric in both runs.")
                continue
            deltas[name] = round(value_b - value_a, 6)
        evidence = [
            {
                "source_type": "run",
                "source_id": run_id,
                "locator": f"experiment_runs:{run_id}:metrics_json",
                "snippet": json.dumps(metrics, ensure_ascii=False)[:200],
                "confidence": 0.95,
            }
            for run_id, metrics in ((run_a, metrics_a), (run_b, metrics_b))
        ]
        return {
            "comparison": {"run_a": run_a, "run_b": run_b, "deltas": deltas},
            "evidence": evidence,
            "missing_context": missing_context,
            "warnings": [],
        }


# -- helpers ---------------------------------------------------------------


def quote_identifier(name: str) -> str:
    escaped = name.replace('"', '""')
    return f'"{escaped}"'


def clamp_limit(limit: int) -> int:
    return max(1, min(int(limit), MAX_LIMIT))


def rank_confidence(index: int) -> float:
    return round(max(0.3, 0.9 - 0.1 * index), 2)


def stored_or_rank_confidence(stored: Any, index: int) -> float:
    value = to_float(stored)
    if value is not None:
        return round(value, 4)
    return rank_confidence(index)


def claim_locator(row: dict[str, Any]) -> str:
    paper_id = row.get("paper_id")
    chunk_id = row.get("chunk_id")
    if paper_id and chunk_id:
        return f"{paper_id}:{chunk_id}"
    return f"claim:{row.get('claim_id')}"


def make_snippet(text: str, tokens: list[str]) -> str:
    if not text:
        return ""
    lowered = text.lower()
    position = -1
    for token in tokens:
        position = lowered.find(token.lower())
        if position >= 0:
            break
    if position < 0:
        position = 0
    start = max(0, position - SNIPPET_WINDOW)
    end = min(len(text), position + SNIPPET_WINDOW)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return f"{prefix}{text[start:end].strip()}{suffix}"


def parse_json_value(value: Any) -> Any:
    if value is None or value == "":
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value


def parse_json_list(value: Any) -> list[Any]:
    parsed = parse_json_value(value)
    if isinstance(parsed, list):
        return parsed
    if parsed in (None, ""):
        return []
    return [parsed]


def to_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None
