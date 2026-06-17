# Changelog

## Unreleased

- Added first-run bootstrap script for a local ResearchKB smoke workspace.
- Added GitHub Actions CI for compilation, tests, JSON validation, and public hygiene scanning.
- Split experiment metrics contracts into a generic contract and a KV-cache reuse extension.
- Added synthetic `examples/` for smoke runs, failure cases, paper memory, and evidence-grounded agent answers.
- Improved `rk_health.py` with readiness levels, missing-table tolerance, `--root`, `--strict`, and next actions.
- Added pytest coverage for empty, smoke, usable, mature, watch-list, and UTF-16 log cases.
- Added public project hygiene files: `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`, and `ROADMAP.md`.
- Cleaned public ignore rules to remove personal-project traces.
- Clarified the first-run onboarding loop in README files.
