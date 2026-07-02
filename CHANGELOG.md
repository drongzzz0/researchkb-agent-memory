# Changelog

## v0.2.0 - 2026-07-02

- Renamed the repository from `obsidian` to `researchkb-agent-memory`; old GitHub URLs redirect automatically.
- Added `researchkb/rk_mcp_server.py`: a stdlib-only read-only MCP server implementing the agent tool contracts (papers, chunks, claims, failure cases, runs, comparisons, health).
- Added `researchkb/rk_query.py`: shared read-only query engine with in-memory FTS5 indexing, LIKE fallback, and provenance-shaped results.
- Added quantified effectiveness metrics: retrieval eval gold set (`evals/retrieval_eval.jsonl` + `scripts/eval_retrieval.py` with recall@k, MRR, precision@1, guard pass rate), library health effectiveness (`failure_documentation_rate`, `open_failure_cases`, `evidence_density`, `run_freshness_days`), and citation validity audit (`scripts/check_citations.py`).
- Added `scripts/session_brief.py` for compact session-start context injection.
- `standardize_run.py` and `auto_standardize_runs.py` now scaffold `problem_case.draft.json` for runs with a failure type.
- Rewrote `scripts/query_demo.py` on the shared engine and added `papers`, `claims`, and `compare-runs` subcommands.
- Seeded a linked negative run (`run_example_negative_001`) so every ID cited by the examples resolves in the demo database.
- CI now runs an os/python matrix (ubuntu/windows x 3.10/3.13), the quickstart demo loop, the retrieval eval, and the citation check.
- Masked substituted input values such as GitHub PATs in `cursor_mcp_smoke.py` command, error, and stderr output, and added tests for the script.
- Made `rk_health.py --strict` meaningful: strict mode now requires the `mature` readiness level before reporting the library as usable.
- Made `auto_standardize_runs.py` tolerate unreadable directories and vanished files during unattended scans.
- Removed the unreferenced legacy README workflow image to shrink clone size.
- Added `seed_demo_db.py --include-run` so the Quick Start demo database can include the freshly standardized smoke run.
- Made generated `run_id` values independent of machine-local absolute paths.
- Added an end-to-end Quick Start demo test.
- Updated contribution checks and Quick Start documentation.

## v0.1.0 - 2026-06-17

- Added first-run bootstrap script for a local ResearchKB smoke workspace.
- Added GitHub Actions CI for compilation, tests, JSON validation, and public hygiene scanning.
- Split experiment metrics contracts into a generic contract and a KV-cache reuse extension.
- Added synthetic `examples/` for smoke runs, failure cases, paper memory, and evidence-grounded agent answers.
- Improved `rk_health.py` with readiness levels, missing-table tolerance, `--root`, `--strict`, and next actions.
- Added pytest coverage for empty, smoke, usable, mature, watch-list, and UTF-16 log cases.
- Added public project hygiene files: `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`, and `ROADMAP.md`.
- Cleaned public ignore rules to remove personal-project traces.
- Clarified the first-run onboarding loop in README files.
