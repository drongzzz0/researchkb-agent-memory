from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "researchkb"))

SPEC = importlib.util.spec_from_file_location("rk_mcp_server", REPO_ROOT / "researchkb" / "rk_mcp_server.py")
assert SPEC is not None
rk_mcp_server = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = rk_mcp_server
assert SPEC.loader is not None
SPEC.loader.exec_module(rk_mcp_server)

SEED_SPEC = importlib.util.spec_from_file_location("seed_demo_db_mcp", REPO_ROOT / "scripts" / "seed_demo_db.py")
assert SEED_SPEC is not None
seed_demo_db = importlib.util.module_from_spec(SEED_SPEC)
assert SEED_SPEC.loader is not None
SEED_SPEC.loader.exec_module(seed_demo_db)


@pytest.fixture()
def demo_root(tmp_path: Path) -> Path:
    root = tmp_path / "researchkb"
    seed_demo_db.seed_demo_db(root=root, examples_dir=REPO_ROOT / "examples", force=True)
    return root


def call(server: object, method: str, params: dict | None = None, request_id: int | None = 1) -> dict | None:
    message: dict = {"jsonrpc": "2.0", "method": method, "params": params or {}}
    if request_id is not None:
        message["id"] = request_id
    return server.handle(message)


def tool_payload(response: dict) -> dict:
    assert response["result"]["isError"] is False
    return json.loads(response["result"]["content"][0]["text"])


def test_initialize_and_tools_list(demo_root: Path) -> None:
    server = rk_mcp_server.McpServer(demo_root)

    init = call(server, "initialize")
    tools = call(server, "tools/list", request_id=2)

    assert init["result"]["protocolVersion"] == rk_mcp_server.PROTOCOL_VERSION
    assert init["result"]["serverInfo"]["name"] == "researchkb-agent-memory"
    names = [tool["name"] for tool in tools["result"]["tools"]]
    assert names == [
        "search_papers",
        "search_chunks",
        "search_claims",
        "find_failure_cases",
        "find_recent_runs",
        "compare_runs",
        "get_health",
    ]


def test_notifications_get_no_response(demo_root: Path) -> None:
    server = rk_mcp_server.McpServer(demo_root)

    assert call(server, "notifications/initialized", request_id=None) is None
    assert call(server, "unknown/notification", request_id=None) is None


def test_tool_calls_return_contract_payloads(demo_root: Path) -> None:
    server = rk_mcp_server.McpServer(demo_root)

    cases = tool_payload(
        call(server, "tools/call", {"name": "find_failure_cases", "arguments": {"symptom": "cache reuse quality"}})
    )
    runs = tool_payload(call(server, "tools/call", {"name": "find_recent_runs", "arguments": {"limit": 2}}))
    health = tool_payload(call(server, "tools/call", {"name": "get_health", "arguments": {}}))

    assert cases["cases"][0]["problem_id"] == "problem_example_cache_template_mismatch"
    assert len(runs["runs"]) == 2
    assert "effectiveness" in health["judgement"]


def test_unknown_tool_and_method_errors(demo_root: Path) -> None:
    server = rk_mcp_server.McpServer(demo_root)

    unknown_tool = call(server, "tools/call", {"name": "not_a_tool", "arguments": {}})
    unknown_method = call(server, "bogus/method")

    assert unknown_tool["error"]["code"] == -32602
    assert unknown_method["error"]["code"] == -32601


def test_missing_database_returns_tool_error(tmp_path: Path) -> None:
    server = rk_mcp_server.McpServer(tmp_path / "empty")

    response = call(server, "tools/call", {"name": "search_papers", "arguments": {"query": "anything"}})

    assert response["result"]["isError"] is True
    assert "not found" in response["result"]["content"][0]["text"]


def test_invalid_arguments_return_tool_error(demo_root: Path) -> None:
    server = rk_mcp_server.McpServer(demo_root)

    response = call(server, "tools/call", {"name": "search_papers", "arguments": {}})

    assert response["result"]["isError"] is True
    assert "Invalid arguments" in response["result"]["content"][0]["text"]


def test_stdio_round_trip(demo_root: Path) -> None:
    requests = "\n".join(
        [
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {"protocolVersion": "2025-03-26", "capabilities": {}},
                }
            ),
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}),
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": "search_chunks", "arguments": {"query": "prompt template compatibility"}},
                }
            ),
        ]
    )
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "researchkb" / "rk_mcp_server.py"), "--root", str(demo_root)],
        input=requests + "\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )

    assert proc.returncode == 0
    lines = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
    assert len(lines) == 2
    assert lines[0]["result"]["serverInfo"]["name"] == "researchkb-agent-memory"
    payload = json.loads(lines[1]["result"]["content"][0]["text"])
    assert payload["chunks"][0]["chunk_id"] == "chunk_example_cache_001"
