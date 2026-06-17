# ResearchKB Agent Memory

English | [简体中文](README.zh-CN.md)

A lightweight workflow template for giving Codex, Claude Code, Cursor, and other research agents access to local literature evidence, experiment history, and failure memory.

![ResearchKB Agent Memory workflow](assets/readme-workflow-v2.png)

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
|-- assets/
|   `-- readme-workflow-v2.png
|-- launchers/
|   `-- Claude Code launcher templates
|-- researchkb/
|   |-- auto_harvest_paths.example.txt
|   |-- kv_experiment_metrics_contract.md
|   |-- rk-health.cmd
|   `-- rk_health.py
|-- scripts/
|   `-- cursor_mcp_smoke.py
|-- README.zh-CN.md
`-- README.md
```

## Included Helpers

- `researchkb/rk-health.cmd`: checks ResearchKB, watched paths, logs, and recent experiment-memory coverage.
- `researchkb/auto_harvest_paths.example.txt`: safe watch-list template.
- `researchkb/kv_experiment_metrics_contract.md`: suggested metrics for KV-cache reuse experiments.
- `scripts/cursor_mcp_smoke.py`: lightweight Cursor MCP config smoke test.
- `launchers/`: optional Claude Code launcher templates. Keep real API keys outside this repo.

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

## Minimum Viable Setup

You do not need to customize everything on day one. Start with only three choices:

1. **ResearchKB root:** where your local knowledge base lives.
2. **One watched folder:** the output directory of one active project.
3. **One metrics format:** a small `metrics.json` or `METRIC key=value` convention.

Ignore `launchers/`, Zotero export, Obsidian organization, and advanced schema mapping until the health check works and one experiment run can be harvested.

## What To Customize Later

| Area | Start with | Customize when |
| --- | --- | --- |
| ResearchKB schema | `papers`, `chunks`, `claims`, `experiment_runs`, `problem_cases` | Your database uses different table or field names |
| Ingestion | Manual `rk-harvest.cmd` | You want scheduled or remote harvesting |
| Metrics | `metrics.json` | Your experiments need domain-specific metrics |
| Agent prompts | The examples above | Your team has a stable debugging or planning routine |
| Model launchers | Ignore them | You need separate local entrypoints for different providers |

The intended path is: clone the repo, set `RESEARCHKB_ROOT`, watch one folder, harvest one run, then add more automation only after the first loop works.
