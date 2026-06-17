# ResearchKB Agent Memory Workflow

Turn papers, experiment outputs, and failure cases into reusable memory for AI research agents.

This repository is a starter workflow for connecting a local research knowledge base with tools such as Codex, Claude Code, Cursor, Obsidian, and Zotero. The goal is not to build another note-taking vault. The goal is to make research agents remember useful evidence:

- what papers say
- which methods have worked before
- which experiments failed and why
- which metrics changed across runs
- what to try in the next experiment

The default example domain is LLM systems research, especially KV-cache reuse, prefix caching, cross-model state transfer, serving efficiency, and related safety/privacy risks. The workflow is domain-agnostic: replace the papers, watched folders, and metrics contract with your own research area.

![Research agent memory workflow](assets/readme-workflow.png)

## Who This Is For

Use this if you want an AI coding/research assistant to do more than answer from the current chat context.

Typical use cases:

- You have many PDFs and want an agent to search them for ideas, limitations, and related work.
- You run experiments and want the outputs to become structured memory.
- You repeatedly debug similar training/evaluation failures and want previous fixes to be reusable.
- You want next-round experiment plans grounded in recent runs and literature evidence.
- You use Obsidian or Zotero for human organization, but need a more machine-queryable layer for agents.

## What This Repository Contains

```text
.
|-- assets/
|   `-- readme-workflow.png
|-- docs/
|   `-- README.md
|-- launchers/
|   |-- README.md
|   |-- claude-gpt54.cmd
|   |-- claude-gpt54.ps1
|   |-- claude-claude-openrouter.cmd
|   |-- claude-claude-openrouter.ps1
|   `-- claude-launcher-common.ps1
|-- researchkb/
|   |-- auto_harvest_paths.example.txt
|   |-- kv_experiment_metrics_contract.md
|   |-- rk-health.cmd
|   `-- rk_health.py
|-- scripts/
|   `-- cursor_mcp_smoke.py
|-- .gitignore
`-- README.md
```

Important boundary: this repository contains portable templates and helper scripts only. It does not contain your actual ResearchKB database, PDFs, Zotero profile, experiment logs, API keys, private config, or machine-specific paths.

## Core Idea

Most research assistants forget useful context because the evidence lives in disconnected places:

- Papers live in Zotero, PDFs, spreadsheets, or browser tabs.
- Experiment results live in output folders.
- Debugging knowledge lives in chat transcripts.
- Ideas and decisions live in notes.

This workflow adds a structured memory layer between those sources and your AI agent.

```text
Papers / PDFs / Zotero / notes
        |
        v
ResearchKB ingestion
        |
        v
papers + chunks + claims + experiment_runs + problem_cases
        |
        v
Codex / Claude Code / Cursor queries ResearchKB when needed
        |
        v
better troubleshooting, idea search, novelty checks, and experiment plans
```

## Quick Start

### 1. Clone This Repository

```powershell
git clone https://github.com/drongzzz0/obsidian.git
cd obsidian
```

### 2. Point The Tools At Your ResearchKB Root

Set `RESEARCHKB_ROOT` to the directory where your ResearchKB installation lives.

PowerShell:

```powershell
$env:RESEARCHKB_ROOT = "<ResearchKBRoot>"
```

Optional persistent setup:

```powershell
[Environment]::SetEnvironmentVariable("RESEARCHKB_ROOT", "<ResearchKBRoot>", "User")
```

Do not commit your real absolute path. Use placeholders in public docs and examples.

### 3. Configure Auto-Harvest Paths

Copy the example watch-list into your ResearchKB config directory and edit it for your own projects.

```powershell
Copy-Item .\researchkb\auto_harvest_paths.example.txt "<ResearchKBRoot>\config\auto_harvest_paths.txt"
notepad "<ResearchKBRoot>\config\auto_harvest_paths.txt"
```

Example:

```text
<ResearchKBRoot>\exports
<ResearchKBRoot>\auto_ingest
<ProjectRoot>\results
<ProjectRoot>\docs\draft
```

Keep the paths narrow. Do not watch an entire home directory, Desktop, Documents folder, or large shared drive.

### 4. Check System Health

```powershell
.\researchkb\rk-health.cmd
```

JSON output:

```powershell
.\researchkb\rk-health.cmd --json
```

The health check reports whether ResearchKB is usable, whether watched paths exist, whether harvest logs show parse failures, and whether recent experiment memory contains structured metrics.

### 5. Make Experiments Emit Parseable Results

Your experiment should write at least one small structured artifact:

```text
metrics.json
results.json
summary.json
eval_results.json
```

or print parseable metric lines:

```text
METRIC accuracy=0.842
METRIC latency_ms=128.5
METRIC peak_memory_mb=9216
```

For KV-cache reuse experiments, use the suggested fields in [researchkb/kv_experiment_metrics_contract.md](researchkb/kv_experiment_metrics_contract.md).

### 6. Harvest Results

If you do not use a scheduler, harvest manually:

```powershell
<ResearchKBRoot>\rk-harvest.cmd --project "Your Project Name" <workspace-or-output-dir>
```

After ingestion, future agent sessions can query recent runs, metrics, failures, and related evidence.

## Agent Workflows

### Troubleshoot A Failed Experiment

Ask your agent:

```text
This experiment failed. Search ResearchKB for similar failure cases and related paper evidence before proposing a fix.
```

A good agent response should combine:

- the current log or stack trace
- similar `problem_cases` from ResearchKB
- relevant paper claims, limitations, or safety evidence
- a concrete fix plan and verification command

### Plan The Next Experiment

Ask:

```text
Based on recent experiment results and literature evidence, propose the next experiment plan.
```

A useful plan should include:

- dataset
- baseline
- method variant
- ablation
- metric
- success criterion
- failure criterion
- safety/privacy check when relevant
- expected evidence for or against the research claim

### Check Whether An Idea Is Novel

Ask:

```text
Check this idea against ResearchKB and public literature metadata. Identify closest prior work and the real novelty gap.
```

A useful novelty check should not simply say "looks new". It should identify the closest related work, explain the difference, and point out what evidence would be needed to make the claim credible.

## ResearchKB Data Model

This workflow assumes the knowledge base can store or expose these record types:

- `papers`: paper metadata
- `chunks`: searchable text chunks from abstracts, PDFs, appendices, tables, or notes
- `claims`: structured method, limitation, experiment, and safety claims
- `experiment_runs`: experiment configs, outputs, metrics, logs, and status
- `problem_cases`: failure symptoms, causes, attempted fixes, and final solutions

The exact implementation can vary. The important part is that agents can query these records during normal work.

## Role Of Each Tool

### ResearchKB

The machine-readable memory layer. It stores literature evidence, experiment records, and failure cases.

### Obsidian

The human-facing note layer. Use it for reading, summaries, idea sketches, and manual review. Do not rely on it as the only structured database.

### Zotero

The paper-management layer. Use it to collect PDFs and metadata. Better BibTeX or similar export tools can feed ResearchKB.

### Codex / Claude Code / Cursor

The agent interface. These tools run commands, edit code, inspect logs, query ResearchKB, and write plans or fixes.

### GitHub

The portable workflow layer. Keep templates, helper scripts, diagrams, and sanitized docs here. Do not commit real databases, PDFs, auth files, or personal machine paths.

## Claude Code Launcher Templates

The `launchers/` directory contains optional Claude Code launcher templates.

They are useful if you want separate local entrypoints for different model providers or API routes. They are not required for ResearchKB itself.

Read [launchers/README.md](launchers/README.md) before using them.

Rules:

- Keep API keys in environment variables or local private config.
- Do not commit provider tokens.
- Treat these scripts as templates and adapt them to your own provider setup.

## Cursor MCP Smoke Test

Use `scripts/cursor_mcp_smoke.py` to sanity-check MCP server definitions from a Cursor MCP config.

```powershell
python .\scripts\cursor_mcp_smoke.py --help
```

This is a lightweight check. It does not replace end-to-end testing inside Cursor.

## How To Measure Whether The Workflow Works

The workflow is useful only if it improves research decisions. Track these signals:

### Infrastructure Health

- Health check passes.
- Auto-harvest runs successfully.
- Watched paths exist.
- Parse failures stay near zero.
- ResearchKB queries return evidence.

### Knowledge Coverage

- Paper count, chunk count, and claim count increase over time.
- Important papers can be retrieved by topic.
- Limitation and safety claims are searchable.
- Closest-prior-work queries return meaningful results.

### Experiment Memory Quality

Track:

```text
structured_metrics_runs / total_experiment_runs
```

Suggested target:

```text
>= 0.70
```

Also track whether failed runs include:

- `failure_type`
- log path
- config path
- final fix
- affected metric

### Research Utility

The workflow is working when:

- repeated failures are diagnosed faster the second time
- next experiment plans cite recent runs and paper evidence
- idea checks identify closest prior work instead of giving generic advice
- experiment decisions become `continue`, `stop`, or `redesign`, not vague suggestions

## Privacy And Security

Do not commit:

- API keys
- auth tokens
- private SSH keys
- local absolute paths
- personal usernames
- machine-specific logs
- ResearchKB SQLite databases
- Zotero profiles
- PDFs that you do not have permission to redistribute
- large generated artifacts

Before pushing changes, run:

```powershell
rg -n "sk-|api[_-]?key|auth[_-]?token|password|secret|bearer" .
rg -n "<your-username>|<private-host>|<private-project-name>" .
git status -sb --ignored
```

Use placeholders in committed examples:

```text
<ResearchKBRoot>
<ProjectRoot>
<workspace-or-output-dir>
```

## Development Checks

Compile the Python helper scripts:

```powershell
python -m py_compile .\researchkb\rk_health.py .\scripts\cursor_mcp_smoke.py
```

Run the ResearchKB health check:

```powershell
$env:RESEARCHKB_ROOT = "<ResearchKBRoot>"
.\researchkb\rk-health.cmd --json
```

## Project Status

This repository is a workflow template, not a packaged product. Expect to adapt:

- ingestion commands
- ResearchKB schema details
- watched paths
- model-provider launchers
- experiment metrics
- agent prompt conventions

The core design principle should stay the same: keep private data local, commit only portable workflow code, and make research evidence queryable by agents during normal work.
