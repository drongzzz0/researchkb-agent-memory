# Obsidian / ResearchKB Research Agent Memory

这套仓库记录的是一个本机科研工作流，不是单纯的 Obsidian 笔记库，也不是几个零散脚本。

目标是把 **论文库、实验结果、失败经验、Codex/Claude/Cursor 的工作过程** 连成一个可持续复用的 `research agent memory`：以后做 KV-cache reuse 相关研究时，AI 助手不是只靠当前聊天上下文，而是能自动回到本地知识库里找论文证据、历史失败、近期实验结果和下一步计划。

核心方向目前是 **KV cache reuse / cross-model state transfer / prefix caching / LLM serving efficiency**，同时默认纳入 **安全、隐私、prompt leakage、多租户 KV sharing 风险**。

## What This Is For

这套 workflow 要解决两个实际问题：

1. **找 idea 和研究空白**
   把 Zotero / PDF / Excel 文献目录 / OpenReview / arXiv / 本地论文文件夹沉淀到 ResearchKB，再让 Codex 用这些证据做 idea generation、novelty check、limitations mining 和 next experiment planning。

2. **实验失败时快速定位问题**
   把真实实验输出、日志、失败类型、修复过程写进 `experiment_runs` 和 `problem_cases`。下次出现质量崩溃、OOM、timeout、NaN、指标异常、route failure、transfer failure 时，Codex 先查历史案例和相关论文，再给修复建议。

最终要达到的状态：

- 你正常做实验，不需要手动整理大段笔记。
- 实验输出自动进入 ResearchKB。
- 你问“这个实验为什么失败”时，Codex 自动查类似失败和论文证据。
- 你问“下一轮怎么做”时，Codex 自动结合最近实验、文献限制、安全风险和可测指标给计划。
- GitHub 里沉淀可迁移的工具、配置模板、健康检查和工作流记录。

## Workflow Diagram

![AI Research Workflow](assets/readme-workflow.png)

The image was generated with the OpenAI image generation workflow and committed as a static README asset.

## End-to-End Workflow

### 1. 文献进入 ResearchKB

文献来源可以是：

- Zotero + Better BibTeX export
- 本地 PDF 文件夹
- Excel 论文分类表
- arXiv / OpenReview / OpenAlex / Semantic Scholar / author pages
- 手动补充的重点论文

入库后形成几类数据：

- `papers`: 论文元数据
- `chunks`: PDF / abstract / table / appendix 等文本块
- `claims`: 方法、实验、限制、安全风险等结构化 claim
- `problem_cases`: 失败案例和解决经验
- `experiment_runs`: 实验运行记录、指标、日志路径、失败类型

### 2. Codex / Claude / Cursor 使用 ResearchKB

平时仍然在 Codex、Claude Code、Cursor 里工作，但遇到研究问题时，AI 助手应该优先查 ResearchKB。

典型触发：

- “这个实验失败了”
- “为什么质量崩了”
- “下一轮实验怎么做”
- “这个 idea 新不新”
- “有没有类似论文”
- “帮我做 ablation plan”
- “这个结果能不能写成 claim”

默认行为：

- 失败分析先查 `problem_cases` 和相关论文。
- 下一轮实验先查 `experiment_runs`、method claims、limitation claims、安全/隐私 claims。
- KV-cache reuse 方向默认额外检查 prompt leakage、multi-tenant KV sharing、confidential serving 等风险。

### 3. 实验输出自动沉淀

实验脚本应该尽量输出可解析结果：

- `metrics.json`
- `results.json`
- `summary.json`
- `eval_results.json`
- 或日志里的 `METRIC key=value`

本机定时任务 `ResearchKB-AutoHarvest` 每 5 分钟扫描 `<ResearchKBRoot>\config\auto_harvest_paths.txt` 里的窄目录，把结果写入 ResearchKB。

典型 watched paths 应使用占位符或环境变量，不要把个人用户名和真实项目绝对路径提交到 GitHub：

```text
<ResearchKBRoot>\exports
<ResearchKBRoot>\auto_ingest
<ProjectRoot>\results
<ProjectRoot>\docs\draftkv
```

远程 GPU 服务器上的实验不会被 Windows 定时任务直接扫描，需要：

- 把结果同步回本机 watched path；或
- 在远端单独部署同类 harvester；或
- Codex 在实验结束后显式运行 `rk-harvest`。

### 4. 失败案例进入 problem memory

失败不是只留在聊天里，而是要变成可检索经验。

应该记录：

- symptom: 表面现象，例如 quality collapse / empty patch layers / route failure
- context: 数据集、模型、配置、运行环境
- suspected causes: 可能原因
- tried fixes: 试过的修复
- final solution: 最终有效方案
- evidence: 日志证据和论文证据

这样下次 Codex 看到类似错误时，可以优先复用已有经验，而不是重新猜。

### 5. 下一轮实验计划

一个合格的 next experiment plan 不应该只是“多试几个参数”。

它应该包含：

- dataset 和样本量
- baseline / oracle / reuse-only / proposed method
- quality metric，例如 F1、EM、accuracy、retention
- efficiency metric，例如 TTFT、total latency、memory、payload size
- success criterion
- failure criterion
- ablation
- safety/privacy check
- expected evidence：跑完以后能支持或否定什么 claim

KV-cache reuse 实验建议遵循 [researchkb/kv_experiment_metrics_contract.md](researchkb/kv_experiment_metrics_contract.md)。

## Daily Usage

### 检查这套系统是否还活着

```powershell
$env:RESEARCHKB_ROOT = "<ResearchKBRoot>"
.\researchkb\rk-health.cmd
.\researchkb\rk-health.cmd --json
```

它会检查：

- `ResearchKB-AutoHarvest` 是否存在、是否运行成功
- watched paths 是否存在
- auto-harvest 日志是否有 parse failure
- SQLite 数据库里 papers / chunks / claims / problem_cases / experiment_runs 数量
- 最近实验记录
- `with_metrics / experiment_runs` 覆盖率

### 让新实验能被自动记录

把实验结果写入 watched path，或者让 Codex 在实验结束后运行：

```powershell
<ResearchKBRoot>\rk-harvest.cmd --project "KV Cache Reuse" <workspace-or-output-dir>
```

如果是新项目，只添加窄目录到：

```text
<ResearchKBRoot>\config\auto_harvest_paths.txt
```

不要扫描整个 Desktop、Documents 或用户目录。

### 失败时应该怎么问

直接说：

```text
这个实验失败了，帮我从 ResearchKB 里找类似失败案例和解决方法。
```

或者更自然：

```text
为什么这个 run 质量崩了？
```

Codex 应该自动组合三类证据：

- 当前 log / stack trace
- ResearchKB 的历史 `problem_cases`
- 相关论文 claim / limitation / safety evidence

### 做下一轮计划时应该怎么问

```text
根据最近实验结果和文献，给我下一轮实验计划。
```

Codex 应该输出：

- 当前路线是否继续
- 哪个失败要先排除
- 下一组实验表
- 每个实验的 metric、成功标准、风险
- 是否需要安全/隐私/泄漏检查

## How To Measure Whether It Works

这套系统不能只看“有没有搭起来”，要看它是否减少重复劳动、减少重复踩坑、提高实验决策质量。

### Infrastructure Health

- 定时任务最新结果为 `0`
- auto-harvest `parse_failed=0`
- watched paths 都存在
- ResearchKB MCP / CLI 能返回 evidence

### Knowledge Coverage

- papers / chunks / claims 是否持续增长
- KV-cache reuse 相关论文是否能被检索到
- safety/privacy/leakage 证据是否覆盖
- novelty check 是否能找到 closest prior work

### Experiment Memory Quality

关键指标：

```text
with_metrics / experiment_runs
```

目标：

- 当前可用阈值：能查到 recent runs 和 failure cases
- 短期目标：结构化 metrics 覆盖率超过 `0.70`
- 长期目标：每次失败都有 `failure_type`，每次关键实验都有质量、速度、内存和安全字段

### Research Utility

有用的表现：

- 同类 failure 第二次出现时，不再从零分析
- next experiment plan 能引用最近 run 和论文证据
- idea check 能指出 closest prior work 和差异点
- 实验计划能明确 stop / continue / redesign，而不是泛泛建议

## Repository Layout

```text
.
|-- launchers/
|   |-- claude-gpt54.cmd
|   |-- claude-gpt54.ps1
|   |-- claude-claude-openrouter.cmd
|   |-- claude-claude-openrouter.ps1
|   `-- claude-launcher-common.ps1
|-- researchkb/
|   |-- rk_health.py
|   |-- rk-health.cmd
|   |-- auto_harvest_paths.example.txt
|   `-- kv_experiment_metrics_contract.md
|-- scripts/
|   `-- cursor_mcp_smoke.py
|-- assets/
|   `-- README images and static visual assets
|-- docs/
|   `-- README.md
|-- .gitignore
`-- README.md
```

## Components

### ResearchKB

Lives outside this repository. Set its location with `RESEARCHKB_ROOT`.

This repository keeps portable helper files and documentation, but the actual DB, PDFs, logs and venv stay outside Git.

### Obsidian

Used as a human-facing knowledge layer and optional review surface. It is not the core database. The core machine-readable memory is ResearchKB.

### Zotero

Used for paper management and metadata export. Better BibTeX can export bibliography data into ResearchKB.

### Codex / Claude / Cursor

Used as the active research agent interface. They call tools, inspect logs, write code, run experiments, query ResearchKB and update records.

### GitHub

Used to version:

- launcher scripts
- workflow templates
- health tooling
- sanitized documentation
- README and diagrams

It should not store secrets, large PDFs, local DB files, personal caches, machine-specific logs, or personal absolute paths.

## Claude Code Launchers

The `launchers/` directory provides two local Claude Code entrypoints:

- `claude-gpt54.cmd`: reuses the current GPT route from the local Claude user settings.
- `claude-claude-openrouter.cmd`: routes Claude Code through OpenRouter and defaults to `anthropic/claude-sonnet-4.6`.

Usage:

```powershell
.\launchers\claude-gpt54.cmd
.\launchers\claude-claude-openrouter.cmd
```

Design notes:

- The launchers preserve non-secret settings such as permissions and enabled plugins.
- API credentials are read from runtime environment variables or existing local user settings.
- No API key is intended to be committed into this repository.

See [launchers/README.md](launchers/README.md) for details.

## Other Scripts

### `scripts/cursor_mcp_smoke.py`

Runs a lightweight MCP server smoke test from a Cursor MCP configuration file.

## Security and Privacy

This repository intentionally excludes:

- `tmp/`
- Python bytecode and cache directories
- local installers and downloaded binaries
- generated PDFs, ZIPs, PNGs and render caches
- actual ResearchKB SQLite DB / PDFs / Zotero profile data
- API keys and auth files

Before pushing future changes, run:

```powershell
rg -n "sk-|api[_-]?key|auth[_-]?token|password|secret|bearer" . -g "!tmp/**" -g "!**/__pycache__/**"
git status -sb --ignored
```

## Current Known Limitation

The workflow is operational, but the main bottleneck is not infrastructure. It is **structured experiment quality**.

If future experiments only leave unstructured logs, ResearchKB can still harvest them, but automatic comparison and planning will be weak. The practical fix is to make every important experiment emit a small JSON result file following [researchkb/kv_experiment_metrics_contract.md](researchkb/kv_experiment_metrics_contract.md).

## Development Loop

```powershell
git status -sb
python -m py_compile .\researchkb\rk_health.py .\scripts\cursor_mcp_smoke.py
.\researchkb\rk-health.cmd
git add -A
git commit -m "Describe the workflow change"
git push
```

## License

No explicit open-source license has been selected yet. Add a `LICENSE` file before treating this as reusable third-party open-source code.
