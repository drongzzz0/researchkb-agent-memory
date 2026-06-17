# ResearchKB Agent Memory

English | [简体中文](README.zh-CN.md)

A lightweight workflow template for giving Codex, Claude Code, Cursor, and other research agents access to local literature evidence, experiment history, and failure memory.

![ResearchKB Agent Memory workflow](assets/readme-workflow-v2.png)

## What This Repo Is

This is a public workflow starter kit for connecting local ResearchKB data to research agents.

It provides:

- public templates
- experiment output contracts
- health-check scripts
- launcher examples
- agent prompt patterns
- privacy rules

It does not provide:

- your private ResearchKB database
- private papers or PDFs
- Zotero profile data
- experiment logs
- API keys
- a hosted RAG service

## What It Does

Research agents are more useful when they can query evidence instead of relying only on the current chat. This repo provides public, portable glue for that workflow:

- **Literature memory:** ingest papers, PDFs, Zotero exports, and notes into ResearchKB.
- **Experiment memory:** harvest `metrics.json`, `results.json`, logs, and summaries from project output folders.
- **Failure memory:** record failed runs, symptoms, fixes, and final solutions as searchable cases.
- **Agent usage:** let Codex, Claude Code, or Cursor query ResearchKB before troubleshooting, planning, or checking novelty.

The actual database, PDFs, logs, secrets, and machine-specific config stay outside Git.

## Quick Start

```powershell
git clone https://github.com/drongzzz0/obsidian.git
cd obsidian
```

Point the helper scripts at your local ResearchKB installation:

```powershell
$env:RESEARCHKB_ROOT = "<ResearchKBRoot>"
```

Configure narrow auto-harvest paths:

```powershell
Copy-Item .\researchkb\auto_harvest_paths.example.txt "<ResearchKBRoot>\config\auto_harvest_paths.txt"
notepad "<ResearchKBRoot>\config\auto_harvest_paths.txt"
```

Example watch-list:

```text
<ResearchKBRoot>\exports
<ResearchKBRoot>\auto_ingest
<ProjectRoot>\results
<ProjectRoot>\docs\draft
```

Check whether the workflow is usable:

```powershell
.\researchkb\rk-health.cmd
.\researchkb\rk-health.cmd --json
```

Harvest a project manually:

```powershell
<ResearchKBRoot>\rk-harvest.cmd --project "Your Project" <workspace-or-output-dir>
```

## How To Use With Agents

Use direct prompts like these:

```text
This experiment failed. Search ResearchKB for similar failures and fixes before suggesting a solution.
```

```text
Based on recent experiment results and paper evidence, propose the next experiment plan.
```

```text
Check this idea against ResearchKB and public literature metadata. What is the closest prior work?
```

A good agent answer should cite evidence from recent runs, relevant papers, and failure cases when available.

## Experiment Output Contract

Experiments should emit at least one parseable artifact:

```text
metrics.json
results.json
summary.json
eval_results.json
```

or log lines like:

```text
METRIC accuracy=0.842
METRIC latency_ms=128.5
METRIC peak_memory_mb=9216
```

For KV-cache reuse work, see [researchkb/kv_experiment_metrics_contract.md](researchkb/kv_experiment_metrics_contract.md).

## Repository Layout

```text
.
|-- CHANGELOG.md
|-- CONTRIBUTING.md
|-- LICENSE
|-- ROADMAP.md
|-- SECURITY.md
|-- assets/
|   `-- readme-workflow-v2.png
|-- docs/
|   |-- architecture.md
|   |-- schema_minimal.md
|   `-- agent_tool_contracts.md
|-- launchers/
|   `-- Claude Code launcher templates
|-- researchkb/
|   |-- auto_harvest_paths.example.txt
|   |-- kv_experiment_metrics_contract.md
|   |-- rk-health.cmd
|   `-- rk_health.py
|-- scripts/
|   `-- cursor_mcp_smoke.py
|-- .gitignore
|-- README.zh-CN.md
`-- README.md
```

## Included Helpers

- `researchkb/rk-health.cmd`: checks ResearchKB, watched paths, logs, and recent experiment-memory coverage.
- `researchkb/auto_harvest_paths.example.txt`: safe watch-list template.
- `researchkb/kv_experiment_metrics_contract.md`: suggested metrics for KV-cache reuse experiments.
- `scripts/cursor_mcp_smoke.py`: lightweight Cursor MCP config smoke test.
- `launchers/`: optional Claude Code launcher templates. Keep real API keys outside this repo.

## Design Docs

- [docs/architecture.md](docs/architecture.md): project run -> harvest -> ResearchKB -> agent query loop.
- [docs/schema_minimal.md](docs/schema_minimal.md): minimal records and evidence provenance fields.
- [docs/agent_tool_contracts.md](docs/agent_tool_contracts.md): expected tool inputs, outputs, and evidence-grounded answer format.

## Privacy Rules

Do not commit:

- API keys or auth tokens
- SSH keys or local credentials
- local absolute paths
- personal usernames or hostnames
- ResearchKB databases
- Zotero profiles
- private PDFs
- experiment logs and generated artifacts

Use placeholders in public examples:

```text
<ResearchKBRoot>
<ProjectRoot>
<workspace-or-output-dir>
```

Suggested pre-push checks:

```powershell
rg -n "sk-|api[_-]?key|auth[_-]?token|password|secret|bearer" .
rg -n "<your-username>|<private-host>|<private-project-name>" .
git status -sb --ignored
```

## Development Checks

```powershell
python -m py_compile .\researchkb\rk_health.py .\scripts\cursor_mcp_smoke.py
```

```powershell
$env:RESEARCHKB_ROOT = "<ResearchKBRoot>"
.\researchkb\rk-health.cmd --json
```

## Day-1 Setup: Harvest One Run

Start by making one fake or real experiment run searchable. Do not configure the whole stack first.

```powershell
$env:RESEARCHKB_ROOT = "<ResearchKBRoot>"
$project = "<ProjectRoot>"
$run = "$project\runs\smoke-test"
New-Item -ItemType Directory -Force $run
```

Write one minimal result file:

```powershell
@'
{
  "experiment": "smoke-test",
  "status": "ok",
  "accuracy": 0.842,
  "latency_ms": 128.5,
  "notes": "first ResearchKB ingestion test"
}
'@ | Set-Content "$run\metrics.json" -Encoding UTF8
```

Add only that project output folder to the watch-list:

```powershell
Add-Content "<ResearchKBRoot>\config\auto_harvest_paths.txt" "$project\runs"
```

Run the two checks:

```powershell
.\researchkb\rk-health.cmd
<ResearchKBRoot>\rk-harvest.cmd --project "Smoke Test" "$run"
```

Then ask your agent:

```text
Find the latest Smoke Test run in ResearchKB and tell me what metrics were recorded.
```

If the agent can answer that, the loop works. Add real projects, Zotero exports, Obsidian notes, launchers, and scheduled harvesting only after this first run is queryable.

## Customize After The First Loop Works

| Next step | Do this only when |
| --- | --- |
| Add more watched folders | One run can already be harvested and queried |
| Add Zotero or PDF ingestion | You know the experiment-memory path works |
| Change schema mapping | Your ResearchKB tables or fields differ |
| Add domain metrics | The generic `metrics.json` is not enough |
| Add model launchers | You need separate local entrypoints for different providers |
