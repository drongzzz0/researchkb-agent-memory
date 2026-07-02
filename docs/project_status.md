# Project Status

English | [简体中文](project_status.zh-CN.md)

Status as of **2026-07-02**, current release **v0.3.0**.

This document is the periodic snapshot of where the project stands and what comes next.
For per-release detail see [CHANGELOG.md](../CHANGELOG.md); for the long-term phase list see
[ROADMAP.md](../ROADMAP.md).

## What This Project Is

A local-first memory layer that lets research agents (Codex, Claude Code, Cursor) query
three kinds of evidence together: literature claims, experiment runs, and failure cases,
each carrying provenance (`source_type`, `source_id`, `locator`, `snippet`, `confidence`).
Everything runs on SQLite plus the Python standard library; private data never enters Git.

## Delivered So Far

### v0.1.0 (2026-06-17): starter kit baseline

- Bootstrap script, synthetic examples, JSON Schemas for the six record types.
- `rk_health.py` readiness levels (`empty` / `smoke` / `usable` / `mature`).
- CI with tests, schema validation, and a public hygiene scan.

### v0.2.0: agents can query, effectiveness is measurable

- Read-only MCP server (stdlib-only, stdio JSON-RPC) implementing the documented tool
  contracts; SQLite attached `mode=ro`, FTS5 index built in memory, LIKE fallback.
- Three quantified metric layers:
  1. Retrieval quality, CI-gated: `recall_at_k`, `mrr`, `precision_at_1`,
     `guard_pass_rate` over a 16-case gold set (4 negative guards).
  2. Library health: `metrics_coverage`, `failure_documentation_rate`,
     `open_failure_cases`, `evidence_density`, `run_freshness_days`.
  3. Answer grounding: `citation_validity` via the citation checker.
- Failure-memory ergonomics: auto-scaffolded `problem_case.draft.json` for failed runs,
  session-start brief command.
- Repository renamed to `researchkb-agent-memory`; description, topics, and GitHub
  Releases published.

### v0.2.1: alignment and honesty pass

- `search_evidence` added to the MCP server (the core provenance lookup).
- Implemented vs planned tools split; [tool_matrix.md](tool_matrix.md) and
  [mcp_compatibility.md](mcp_compatibility.md) added.
- Synthetic-eval caveat documented; [../evals/README.md](../evals/README.md) explains how
  to build user-specific eval sets.

### v0.3.0: installable tool

- `src/researchkb_agent_memory/` package; `pip install -e .` provides the `rk-memory` CLI
  (16 subcommands covering init, seeding, standardization, health, search, comparison,
  eval, citation check, session brief, and the MCP server).
- Legacy `researchkb/*.py` and `scripts/*.py` kept as behavior-identical wrappers.
- CI matrix (ubuntu/windows x Python 3.10/3.13) installs the package and smoke-tests the
  CLI on every job.

### Unreleased after v0.3.0: first explicit importer

- `rk-memory import-runs` previews and imports standardized `run_record.json` files into
  `experiment_runs`.
- The command is dry-run by default; database writes require explicit `--write` and upsert
  by `run_id`.
- The MCP server remains read-only.

## Current Quality Numbers

All measured on the synthetic demo database (see caveat below):

| Metric | Value |
| --- | --- |
| Tests | 66 passing locally; CI matrix pending for the unreleased importer |
| Retrieval eval | recall@k 1.0, MRR 0.96, precision@1 0.92, guard pass rate 1.0 |
| Citation validity (good-answer example) | 1.0 |
| Demo library health | level `smoke`, metrics coverage 1.0, evidence density 1.0 |
| Hygiene scan | no local paths, secrets, or private traces in public files |

**Caveat:** the bundled eval set validates the demo workflow only. No real-library
benchmark exists yet; producing one is the goal of the v0.6 milestone.

## Known Limitations

- Cursor, Claude Code, and Codex have not been verified end to end against the MCP server;
  protocol-level behavior is covered by a scripted stdio harness in CI.
- Keyword search only (FTS5 BM25 with LIKE fallback); no semantic/embedding layer by design
  for now.
- The package installs locally but is not yet published to PyPI.
- Paper and note ingestion into SQLite is still planned. Experiment-run ingestion now has
  an explicit CLI path, but it requires an existing private database and `--write`.

## Plan

### v0.4.0 - real data importers (next up)

- `rk-memory import-runs`: shipped in unreleased form; keep hardening real-project tests.
- `rk-memory import-bibtex`: seed `papers` from BibTeX / Zotero exports (metadata only,
  no PDFs).
- `rk-memory import-notes`: turn curated Markdown notes into `chunks` / `claims` /
  `evidence_links`.
- `rk-memory schema check | init --dry-run`: explicit, opt-in schema management.
- Hard rule carried through docs and code: **the MCP server stays read-only; all writes
  are explicit CLI operations.**

### v0.5.0 - project memory

- New record types: `research_projects` (goal, active hypothesis, constraints),
  `decision_logs` (decision, rationale, evidence IDs, rejected options),
  `open_questions`, and `rejected_ideas`.
- Session brief v2 that answers "where are we, what was ruled out, what is next".
- Lightweight Obsidian/Markdown export (human-readable mirror, never the primary store).

### v0.6.0 - real-world evaluation

- User eval-set templates and a decision-eval that checks agent answers for structure:
  conclusion, evidence, recommended action, missing context, source IDs.
- Unsupported-claim detection built on the citation checker.
- A published benchmark report from at least one real research project.

### Distribution (pending owner accounts)

- PyPI publication (`pip install researchkb-agent-memory`, `uvx rk-memory`).
- MCP directory registration once at least one client is verified end to end.

### Deliberately Out Of Scope For Now

PDF OCR / GROBID parsing, vector databases, automatic idea generation, write-capable MCP
tools, and a web UI. The current priority is proving the minimal local evidence loop is
stable and useful on real projects.

## How To Verify This Status

```bash
python -m pip install -e .
rk-memory init
rk-memory standardize-run .runtime/example-project/runs/smoke-test
rk-memory seed-demo --include-run .runtime/example-project/runs/smoke-test/run_record.json
rk-memory import-runs .runtime/example-project/runs --root .runtime/researchkb
rk-memory eval --root .runtime/researchkb --min-recall 0.9 --min-mrr 0.75
rk-memory check-citations examples/agent-answers/good_troubleshooting_answer.md --root .runtime/researchkb --min-validity 1.0
python -m pytest -q
```
