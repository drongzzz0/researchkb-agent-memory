# Tool Matrix

Per-surface implementation status for the agent tool contracts in
[agent_tool_contracts.md](agent_tool_contracts.md). "Eval coverage" refers to the gold query
set in [../evals/retrieval_eval.jsonl](../evals/retrieval_eval.jsonl); tools without gold
cases are still covered by unit tests.

| Tool | QueryEngine (`rk_query.py`) | CLI (`query_demo.py`) | MCP server (`rk_mcp_server.py`) | Eval coverage | Status | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `search_papers` | yes | `papers` | yes | 3 positive + 1 guard | implemented | |
| `search_chunks` | yes | included in `evidence` output | yes | 2 positive + 1 guard | implemented | |
| `search_claims` | yes | `claims` | yes | 2 positive | implemented | |
| `search_evidence` | yes | `evidence` | yes | 1 positive | implemented | Returns evidence links plus matching chunks |
| `find_failure_cases` | yes | `failure-cases` | yes | 3 positive + 1 guard | implemented | |
| `find_recent_runs` | yes | `latest-runs` | yes | 2 positive | implemented | Supports project/status filters |
| `compare_runs` | yes | `compare-runs` | yes | unit tests only | implemented | Numeric deltas; non-shared metrics reported in `missing_context` |
| `get_health` | via `rk_health.py` | `rk_health.py` CLI | yes | unit tests only | implemented | Includes `judgement.effectiveness` metrics |
| `find_methods` | no | no | no | none | planned | Compose from `search_claims` + `search_chunks` for now |
| `find_limitations` | no | no | no | none | planned | Compose from `search_claims` + `find_failure_cases` for now |
| `suggest_next_experiment` | no | no | no | none | planned | Compose from `find_recent_runs` + `find_failure_cases` + `search_claims` for now |

Update this table whenever a tool is added to `rk_query.py`, `query_demo.py`,
`rk_mcp_server.py`, or the eval set, and keep it consistent with
`tests/test_rk_mcp_server.py::test_initialize_and_tools_list`.
