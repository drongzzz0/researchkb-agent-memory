# Documentation

This directory describes the portable ResearchKB Agent Memory contracts. It should contain public design notes, templates, and schemas only.

## Core Docs

- [architecture.md](architecture.md): end-to-end loop and component boundaries.
- [quickstart.md](quickstart.md): 10-minute first-run loop.
- [schema_minimal.md](schema_minimal.md): minimal schema for papers, claims, runs, failure cases, and evidence links.
- [agent_tool_contracts.md](agent_tool_contracts.md): expected tool inputs and outputs for agents.
- [tool_matrix.md](tool_matrix.md): implemented vs planned tools across engine, CLI, MCP, and evals.
- [mcp_compatibility.md](mcp_compatibility.md): MCP transport, protocol version, tested clients, and security boundary.
- [../researchkb/contracts/experiment_metrics_contract.md](../researchkb/contracts/experiment_metrics_contract.md): generic experiment output contract.
- [../researchkb/contracts/kv_cache_reuse_metrics_contract.md](../researchkb/contracts/kv_cache_reuse_metrics_contract.md): KV-cache reuse metric and safety extension.
- [../schemas](../schemas): machine-checkable JSON Schemas for synthetic examples.

## Examples

See [../examples](../examples) for synthetic records and answer examples:

- `smoke-run/`: minimal experiment output.
- `standardized-run/`: normalized synthetic run record.
- `failure-case/`: reusable problem memory.
- `paper-memory/`: paper, chunk, claim, and evidence-link records.
- `agent-answers/`: good and bad troubleshooting responses.

## Bootstrap And CI

- [../scripts/init_researchkb_workspace.py](../scripts/init_researchkb_workspace.py): create the first smoke workspace.
- [../scripts/seed_demo_db.py](../scripts/seed_demo_db.py): seed a synthetic demo SQLite database.
- [../scripts/query_demo.py](../scripts/query_demo.py): query latest runs, failure cases, and evidence in the demo DB.
- [../scripts/standardize_run.py](../scripts/standardize_run.py): normalize mixed experiment outputs into `run_record.json`.
- [../scripts/validate_examples.py](../scripts/validate_examples.py): validate example JSON files against schemas.
- [../scripts/public_repo_scan.py](../scripts/public_repo_scan.py): run the same public hygiene scan used by CI.
- [../.github/workflows/ci.yml](../.github/workflows/ci.yml): compile scripts, run tests, validate example JSON, run the retrieval eval, and scan public files.

## Agent Access And Effectiveness

- [../researchkb/rk_mcp_server.py](../researchkb/rk_mcp_server.py): read-only MCP server implementing the agent tool contracts.
- [../researchkb/rk_query.py](../researchkb/rk_query.py): shared read-only query engine (FTS5 with LIKE fallback).
- [../scripts/session_brief.py](../scripts/session_brief.py): session-start brief with recent runs and open failure cases.
- [../evals/retrieval_eval.jsonl](../evals/retrieval_eval.jsonl): gold query set for retrieval metrics.
- [../scripts/eval_retrieval.py](../scripts/eval_retrieval.py): recall@k, MRR, precision@1, and guard pass rate.
- [../scripts/check_citations.py](../scripts/check_citations.py): citation validity audit for agent answers.

## Private Logs Are Not Tracked

Project and experiment logs are intentionally excluded from this public repository.

Keep machine-specific logs locally, for example:

- `docs/project-plan-log.md`
- `docs/experiment-log.md`

Those files may contain local paths, hostnames, experiment outputs, operational history, and other private context. Publish only sanitized summaries, templates, or synthetic examples.
