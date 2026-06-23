# Documentation

This directory describes the portable ResearchKB Agent Memory contracts. It should contain public design notes, templates, and schemas only.

## Core Docs

- [architecture.md](architecture.md): end-to-end loop and component boundaries.
- [quickstart.md](quickstart.md): 10-minute first-run loop.
- [schema_minimal.md](schema_minimal.md): minimal schema for papers, claims, runs, failure cases, and evidence links.
- [agent_tool_contracts.md](agent_tool_contracts.md): expected tool inputs and outputs for agents.
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
- [../.github/workflows/ci.yml](../.github/workflows/ci.yml): compile scripts, run tests, validate example JSON, and scan public files.

## Private Logs Are Not Tracked

Project and experiment logs are intentionally excluded from this public repository.

Keep machine-specific logs locally, for example:

- `docs/project-plan-log.md`
- `docs/experiment-log.md`

Those files may contain local paths, hostnames, experiment outputs, operational history, and other private context. Publish only sanitized summaries, templates, or synthetic examples.
