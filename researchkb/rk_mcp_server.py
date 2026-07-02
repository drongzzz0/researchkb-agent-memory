"""Read-only MCP server exposing ResearchKB evidence tools over stdio.

Implements the tool contracts documented in docs/agent_tool_contracts.md
using only the Python standard library. The server never writes to the
ResearchKB database: lookups run through rk_query, which opens the SQLite
file in read-only mode.

Usage:
    python researchkb/rk_mcp_server.py --root <ResearchKBRoot>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import rk_health
from rk_query import QueryEngine

PROTOCOL_VERSION = "2025-03-26"
SERVER_INFO = {"name": "researchkb-agent-memory", "version": "0.2.0"}
INSTRUCTIONS = (
    "Query local ResearchKB evidence before troubleshooting, planning, or novelty checks. "
    "Every result carries source_type, source_id, locator, snippet, and confidence; cite these "
    "IDs in answers. missing_context lists what was searched but not found. All tools are read-only."
)

TOOLS: list[dict[str, Any]] = [
    {
        "name": "search_papers",
        "description": "Find paper metadata by topic, title, venue, or tag keywords.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keyword query."},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_chunks",
        "description": "Retrieve source text chunks from papers and notes matching a keyword query.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keyword query."},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_claims",
        "description": "Retrieve structured claims extracted from sources, with provenance locators.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keyword query."},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "find_failure_cases",
        "description": "Find similar historical failure cases by symptom keywords, with fixes and linked runs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symptom": {"type": "string", "description": "Observed symptom keywords."},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["symptom"],
        },
    },
    {
        "name": "find_recent_runs",
        "description": "Retrieve recent experiment runs, optionally filtered by project or status.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "status": {
                    "type": "string",
                    "description": "running, completed_positive, completed_negative, or failed.",
                },
                "limit": {"type": "integer", "default": 5},
            },
        },
    },
    {
        "name": "compare_runs",
        "description": "Compare metrics between two experiment runs and return numeric deltas (run_b - run_a).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_a": {"type": "string"},
                "run_b": {"type": "string"},
                "metrics": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["run_a", "run_b"],
        },
    },
    {
        "name": "get_health",
        "description": "Report ResearchKB readiness level, coverage, and effectiveness metrics.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "strict": {"type": "boolean", "default": False},
            },
        },
    },
]


class McpServer:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()
        self._engine: QueryEngine | None = None
        self._engine_mtime: float | None = None

    # -- engine lifecycle --------------------------------------------------

    def engine(self) -> QueryEngine:
        db_path = self.root / "db" / "literature.sqlite"
        mtime = db_path.stat().st_mtime if db_path.exists() else None
        if self._engine is not None and mtime != self._engine_mtime:
            self._engine.close()
            self._engine = None
        if self._engine is None:
            self._engine = QueryEngine(self.root)
            self._engine_mtime = mtime
        return self._engine

    def close(self) -> None:
        if self._engine is not None:
            self._engine.close()
            self._engine = None

    # -- JSON-RPC handling ---------------------------------------------------

    def handle(self, message: dict[str, Any]) -> dict[str, Any] | None:
        method = message.get("method")
        request_id = message.get("id")
        is_notification = "id" not in message
        try:
            if method == "initialize":
                return self._result(
                    request_id,
                    {
                        "protocolVersion": PROTOCOL_VERSION,
                        "capabilities": {"tools": {}},
                        "serverInfo": SERVER_INFO,
                        "instructions": INSTRUCTIONS,
                    },
                )
            if method in ("notifications/initialized", "notifications/cancelled"):
                return None
            if method == "ping":
                return self._result(request_id, {})
            if method == "tools/list":
                return self._result(request_id, {"tools": TOOLS})
            if method == "tools/call":
                if is_notification:
                    return None
                return self._handle_tool_call(request_id, message.get("params") or {})
            if is_notification:
                return None
            return self._error(request_id, -32601, f"Method not found: {method}")
        except Exception as exc:  # noqa: BLE001 - protocol boundary
            if is_notification:
                return None
            return self._error(request_id, -32603, f"Internal error: {exc}")

    def _handle_tool_call(self, request_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        arguments = params.get("arguments") or {}
        try:
            payload = self._dispatch_tool(name, arguments)
        except FileNotFoundError as exc:
            return self._tool_error(request_id, f"{exc} Run seed_demo_db.py or point --root at a ResearchKB root.")
        except KeyError as exc:
            return self._tool_error(request_id, f"Invalid arguments for {name}: missing {exc}")
        except (TypeError, ValueError) as exc:
            return self._tool_error(request_id, f"Invalid arguments for {name}: {exc}")
        if payload is None:
            return self._error(request_id, -32602, f"Unknown tool: {name}")
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        return self._result(request_id, {"content": [{"type": "text", "text": text}], "isError": False})

    def _dispatch_tool(self, name: str | None, arguments: dict[str, Any]) -> dict[str, Any] | None:
        if name == "get_health":
            return rk_health.build_report(
                root=self.root,
                strict=bool(arguments.get("strict", False)),
                check_scheduled=False,
            )
        engine = self.engine()
        if name == "search_papers":
            return engine.search_papers(str(arguments["query"]), int(arguments.get("limit", 10)))
        if name == "search_chunks":
            return engine.search_chunks(str(arguments["query"]), int(arguments.get("limit", 10)))
        if name == "search_claims":
            return engine.search_claims(str(arguments["query"]), int(arguments.get("limit", 10)))
        if name == "find_failure_cases":
            return engine.find_failure_cases(str(arguments["symptom"]), int(arguments.get("limit", 10)))
        if name == "find_recent_runs":
            return engine.find_recent_runs(
                project=arguments.get("project"),
                status=arguments.get("status"),
                limit=int(arguments.get("limit", 5)),
            )
        if name == "compare_runs":
            metrics = arguments.get("metrics")
            if metrics is not None and not isinstance(metrics, list):
                raise ValueError("metrics must be an array of metric names")
            return engine.compare_runs(str(arguments["run_a"]), str(arguments["run_b"]), metrics)
        return None

    @staticmethod
    def _result(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    @staticmethod
    def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}

    @staticmethod
    def _tool_error(request_id: Any, message: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"content": [{"type": "text", "text": message}], "isError": True},
        }


def resolve_root(root: Path | None) -> Path:
    if root is not None:
        return root.expanduser().resolve()
    env_root = os.environ.get("RESEARCHKB_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()
    return (Path.home() / "ResearchKB").resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only ResearchKB MCP server (stdio).")
    parser.add_argument("--root", type=Path, help="ResearchKB root directory. Overrides RESEARCHKB_ROOT.")
    args = parser.parse_args()

    server = McpServer(resolve_root(args.root))
    stdout = sys.stdout
    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError as exc:
                response: dict[str, Any] | None = McpServer._error(None, -32700, f"Parse error: {exc}")
            else:
                response = server.handle(message)
            if response is not None:
                stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
                stdout.flush()
    finally:
        server.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
