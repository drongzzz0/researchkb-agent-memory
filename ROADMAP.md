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

## Phase 6: Read-Only CLI And MCP Server

- Provide a read-only CLI for querying runs, failure cases, papers, claims, and evidence.
- Provide a minimal MCP-compatible read-only server for Codex, Claude Code, Cursor, and similar tools.
- Keep write operations explicit and separate from evidence lookup.
- Keep private data local.
- Make evidence-grounded answers auditable.
