# Quickstart

This guide gets the minimum loop running in about 10 minutes:

```text
clone repo -> create smoke run -> health check -> harvest -> ask an agent
```

The goal is not to configure a full literature database on day one. The goal is to prove that one experiment result can become searchable memory.

## 1. Clone

```powershell
git clone https://github.com/drongzzz0/researchkb-agent-memory.git
cd researchkb-agent-memory
```

## 2. Create A Smoke Workspace

If you do not have a ResearchKB directory yet, run:

```powershell
python .\scripts\init_researchkb_workspace.py
python .\scripts\standardize_run.py .\.runtime\example-project\runs\smoke-test
python .\scripts\seed_demo_db.py --include-run .\.runtime\example-project\runs\smoke-test\run_record.json
```

Bash equivalent:

```bash
python scripts/init_researchkb_workspace.py
python scripts/standardize_run.py .runtime/example-project/runs/smoke-test
python scripts/seed_demo_db.py --include-run .runtime/example-project/runs/smoke-test/run_record.json
```

This creates local files under `.runtime/`, which is ignored by git:

```text
.runtime/
|-- researchkb/
|   `-- config/auto_harvest_paths.txt
`-- example-project/
    `-- runs/smoke-test/
        |-- metrics.json
        |-- run_record.json
        `-- summary.json
```

It also creates a synthetic demo database:

```text
.runtime/researchkb/db/literature.sqlite
```

If you already have ResearchKB installed, point the bootstrap script at your own directories:

```powershell
python .\scripts\init_researchkb_workspace.py --root "<ResearchKBRoot>" --project-root "<ProjectRoot>"
```

## 3. Run The Health Check

```powershell
python .\researchkb\rk_health.py --root .\.runtime\researchkb
python .\scripts\query_demo.py --root .\.runtime\researchkb latest-runs
python .\scripts\query_demo.py --root .\.runtime\researchkb failure-cases cache
python .\scripts\query_demo.py --root .\.runtime\researchkb evidence compatibility
```

Bash equivalent:

```bash
python researchkb/rk_health.py --root .runtime/researchkb
python scripts/query_demo.py --root .runtime/researchkb latest-runs
python scripts/query_demo.py --root .runtime/researchkb failure-cases cache
python scripts/query_demo.py --root .runtime/researchkb evidence compatibility
```

Expected first health result:

```text
Level: smoke
watch paths: present
database: present
latest run: run_smoke_001
```

This confirms that the synthetic demo DB is queryable and includes the freshly standardized smoke run. It does not contain private papers, private logs, or real experiment results.

## 4. Harvest The Smoke Run

If your run output is already clean `metrics.json`, you can harvest it directly. If it is a mixed output folder with `results.json`, `summary.json`, `eval_results.json`, or logs containing `METRIC key=value`, standardize it first:

```powershell
python .\scripts\standardize_run.py "<ProjectRoot>\runs\<run-id>"
```

This writes:

```text
<ProjectRoot>\runs\<run-id>\run_record.json
```

Use `run_record.json` as the normalized artifact for ResearchKB ingestion.

For unattended local use, standardize every watched folder before harvesting:

```powershell
python .\scripts\auto_standardize_runs.py --paths-file "<ResearchKBRoot>\config\auto_harvest_paths.txt" --project "<ProjectName>"
```

The command scans recent run folders, writes missing or stale `run_record.json` files, and skips fresh folders. Put it before your ResearchKB harvest command in a scheduled task, cron job, or experiment wrapper.

Bash equivalent:

```bash
python scripts/auto_standardize_runs.py --paths-file "<ResearchKBRoot>/config/auto_harvest_paths.txt" --project "<ProjectName>"
```

If your ResearchKB installation provides `rk-harvest.cmd`, run the command printed by the bootstrap script. It has this shape:

```powershell
"<ResearchKBRoot>\rk-harvest.cmd" --project "Smoke Test" "<ProjectRoot>\runs\smoke-test"
```

If you do not have the harvester yet, use the generated smoke run as the target format for your own ingestion command. The important file is:

```text
<ProjectRoot>\runs\smoke-test\metrics.json
```

It follows the generic experiment output contract:

```json
{
  "project": "Smoke Test",
  "experiment": "smoke-test",
  "status": "completed_positive",
  "metrics": {
    "accuracy": 0.842,
    "latency_ms": 128.5
  },
  "decision": "continue",
  "next_action": "Replace this smoke run with one real project output folder."
}
```

## 5. Connect An Agent Via MCP

Register the read-only MCP server in Cursor (`~/.cursor/mcp.json`) or Claude Code (`.mcp.json`):

```json
{
  "mcpServers": {
    "researchkb": {
      "command": "python",
      "args": ["<RepoRoot>/researchkb/rk_mcp_server.py", "--root", "<ResearchKBRoot>"]
    }
  }
}
```

For the demo, point `--root` at `<RepoRoot>/.runtime/researchkb`. The agent gets
`search_papers`, `search_chunks`, `search_claims`, `search_evidence`, `find_failure_cases`,
`find_recent_runs`, `compare_runs`, and `get_health`, all read-only. Coverage and
compatibility details: [tool_matrix.md](tool_matrix.md), [mcp_compatibility.md](mcp_compatibility.md).

Verify retrieval quality and grounding with the built-in metrics:

```powershell
python .\scripts\eval_retrieval.py --root .\.runtime\researchkb --min-recall 0.9 --min-mrr 0.75
python .\scripts\check_citations.py .\examples\agent-answers\good_troubleshooting_answer.md --root .\.runtime\researchkb
python .\scripts\session_brief.py --root .\.runtime\researchkb
```

Bash equivalent:

```bash
python scripts/eval_retrieval.py --root .runtime/researchkb --min-recall 0.9 --min-mrr 0.75
python scripts/check_citations.py examples/agent-answers/good_troubleshooting_answer.md --root .runtime/researchkb
python scripts/session_brief.py --root .runtime/researchkb
```

## 6. Ask An Agent

After the smoke run is harvested, ask your agent:

```text
Find the latest Smoke Test run in ResearchKB and tell me what metrics were recorded.
```

Then try:

```text
This experiment failed. Search ResearchKB for similar failures and fixes before suggesting a solution.
```

```text
Based on recent experiment results and paper evidence, propose the next experiment plan.
```

## 7. Add Real Project Outputs

Once the smoke run works, replace it with a real project output folder.

Good output files:

- `metrics.json`
- `results.json`
- `summary.json`
- `eval_results.json`

Good log fallback:

```text
METRIC accuracy=0.842
METRIC latency_ms=128.5
METRIC failure_type=timeout
METRIC decision=rerun
```

## 8. Keep Public And Private Data Separate

Commit templates and scripts.

Do not commit:

- local ResearchKB databases
- papers or PDFs
- experiment logs
- local absolute paths
- API keys or auth tokens
- personal usernames or hostnames

Run before pushing:

```powershell
python .\scripts\public_repo_scan.py .
python -m pytest -vv --tb=short
```
