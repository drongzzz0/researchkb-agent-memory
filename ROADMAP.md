# Roadmap

This project is intended to grow from a workflow template into a small, verifiable ResearchKB Agent Memory starter kit.

## Phase 1: Smoke Loop

- Run one fake or real experiment output through `rk-harvest`.
- Verify the run is queryable by an agent.
- Keep setup local and private by default.

## Phase 2: Schema Contracts

- Document minimal tables for papers, chunks, claims, experiment runs, failure cases, and evidence links.
- Provide synthetic JSON examples for each record type.
- Make evidence provenance explicit.

## Phase 3: Agent Tool Contracts

- Specify expected tool inputs and outputs for paper search, failure search, recent-run lookup, and next-experiment planning.
- Require source IDs, locators, snippets, confidence, and missing-context fields.

## Phase 4: Diagnostics And Tests

- Improve `rk_health.py` with readiness levels such as `empty`, `smoke`, `usable`, and `mature`.
- Add tests for missing databases, missing tables, smoke runs, mature libraries, and metric coverage.
- Add lightweight CI.

## Phase 5: Run Standardization And Adapters

- Normalize mixed experiment outputs into `run_record.json`.
- Add small adapters for common result layouts without storing private paths.
- Improve metrics coverage, failure labels, decisions, and next-action fields before ingestion.
- Keep schema migration helpers read-only or explicitly opt-in.

## Phase 6: Read-Only CLI And MCP Server (shipped)

- Provide a read-only CLI for querying runs, failure cases, papers, claims, and evidence. (`scripts/query_demo.py`)
- Provide a minimal MCP-compatible read-only server for Codex, Claude Code, Cursor, and similar tools. (`researchkb/rk_mcp_server.py`)
- Keep write operations explicit and separate from evidence lookup.
- Keep private data local.
- Make evidence-grounded answers auditable. (`scripts/check_citations.py`)

## Phase 7: Measurable Effectiveness (shipped)

- Gold retrieval eval with recall@k, MRR, precision@1, and false-positive guards in CI. (`scripts/eval_retrieval.py`)
- Library health effectiveness metrics: metrics coverage, failure documentation rate, evidence density, run freshness. (`researchkb/rk_health.py`)
- Citation validity audit for agent answers. (`scripts/check_citations.py`)

## Phase 8: Importers And Distribution

- Import standardized `run_record.json` files into `experiment_runs`. (unreleased: `rk-memory import-runs`)
- Import runs from MLflow file stores and W&B exports into `run_record.json`.
- Seed paper metadata from Zotero or BibTeX exports. (unreleased: `rk-memory import-bibtex`)
- Import curated Markdown notes into chunks, claims, and evidence links.
- Publish a pip-installable package with console entry points. (local install shipped in v0.3.0: `pip install -e .` provides `rk-memory`; PyPI publication pending)
- Register the MCP server in public MCP directories.
