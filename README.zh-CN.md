# ResearchKB Agent Memory Workflow

[English](README.md) | 简体中文

把论文、实验结果和失败案例变成 AI research agent 可以反复检索和复用的长期记忆。

这个仓库不是 Obsidian 笔记库，也不是文献管理器本身。它是一个可迁移的工作流模板，用来把 ResearchKB、Obsidian、Zotero、Codex、Claude Code、Cursor 和实验输出连接起来，让 AI 助手在做科研时不只依赖当前聊天上下文，而是能回到本地知识库中查证据、查历史失败、查最近实验结果，再给出下一步计划。

默认示例方向是 LLM 系统研究，尤其是 KV-cache reuse、prefix caching、cross-model state transfer、LLM serving efficiency，以及相关的安全、隐私、prompt leakage、多租户 KV sharing 风险。你可以把这套流程替换到任何研究方向。

![Research agent memory workflow](assets/readme-workflow-v2.png)

## 适合谁

如果你希望 AI 编程或科研助手具备“项目记忆”，而不是每次只根据当前对话临时推理，这个工作流会有用。

典型场景：

- 你有一批 PDF，希望 agent 能从里面找 idea、限制、相关工作和实验依据。
- 你经常跑实验，希望实验输出自动变成结构化记忆。
- 你反复遇到类似训练、评测、部署失败，希望以前的修复经验能被复用。
- 你希望下一轮实验计划基于最近结果和文献证据，而不是泛泛建议。
- 你使用 Obsidian 或 Zotero 做人工整理，但还需要一个更适合机器查询的知识层。

## 仓库里有什么

```text
.
|-- assets/
|   |-- readme-workflow.png
|   `-- readme-workflow-v2.png
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
|-- README.zh-CN.md
`-- README.md
```

重要边界：这个仓库只保存可公开、可迁移的模板和辅助脚本。它不应该包含真实 ResearchKB 数据库、PDF、Zotero profile、实验日志、API key、私有配置或本机绝对路径。

## 核心思路

大多数 research agent 不够稳定，是因为证据散落在不同地方：

- 论文在 Zotero、PDF 文件夹、Excel 表格或浏览器标签页里。
- 实验结果在不同输出目录里。
- 调试经验留在聊天记录里。
- idea 和决策散落在笔记里。

这个工作流在这些来源和 AI agent 之间加一层结构化记忆。

```text
论文 / PDF / Zotero / 笔记
        |
        v
ResearchKB 入库
        |
        v
papers + chunks + claims + experiment_runs + problem_cases
        |
        v
Codex / Claude Code / Cursor 在需要时查询 ResearchKB
        |
        v
更可靠的失败排查、idea 搜索、查新和下一轮实验计划
```

## 快速开始

### 1. 克隆仓库

```powershell
git clone https://github.com/drongzzz0/obsidian.git
cd obsidian
```

### 2. 指定 ResearchKB 位置

把 `RESEARCHKB_ROOT` 设置为你的 ResearchKB 安装目录。

PowerShell 临时设置：

```powershell
$env:RESEARCHKB_ROOT = "<ResearchKBRoot>"
```

可选：写入用户环境变量。

```powershell
[Environment]::SetEnvironmentVariable("RESEARCHKB_ROOT", "<ResearchKBRoot>", "User")
```

不要把真实绝对路径提交到公开仓库。文档和模板里只使用占位符。

### 3. 配置自动采集目录

复制示例 watch-list 到 ResearchKB 配置目录，然后改成你自己的项目目录。

```powershell
Copy-Item .\researchkb\auto_harvest_paths.example.txt "<ResearchKBRoot>\config\auto_harvest_paths.txt"
notepad "<ResearchKBRoot>\config\auto_harvest_paths.txt"
```

示例：

```text
<ResearchKBRoot>\exports
<ResearchKBRoot>\auto_ingest
<ProjectRoot>\results
<ProjectRoot>\docs\draft
```

目录要窄。不要扫描整个 home、Desktop、Documents 或大型共享盘。

### 4. 检查系统健康状态

```powershell
.\researchkb\rk-health.cmd
```

JSON 输出：

```powershell
.\researchkb\rk-health.cmd --json
```

健康检查会报告 ResearchKB 是否可用、watched paths 是否存在、harvest 日志是否有解析失败、最近实验记录是否有结构化 metrics。

### 5. 让实验输出可解析结果

实验脚本至少应该写出一个小的结构化结果文件：

```text
metrics.json
results.json
summary.json
eval_results.json
```

或者在日志里打印可解析指标：

```text
METRIC accuracy=0.842
METRIC latency_ms=128.5
METRIC peak_memory_mb=9216
```

KV-cache reuse 相关实验建议参考 [researchkb/kv_experiment_metrics_contract.md](researchkb/kv_experiment_metrics_contract.md)。

### 6. 采集实验结果

如果没有定时任务，可以手动采集：

```powershell
<ResearchKBRoot>\rk-harvest.cmd --project "Your Project Name" <workspace-or-output-dir>
```

入库后，后续 agent 会话就可以查询最近 runs、metrics、failures 和相关证据。

## Agent 应该怎么用

### 失败排查

可以这样问：

```text
这个实验失败了。先从 ResearchKB 找类似失败案例和相关论文证据，再给修复方案。
```

合格的回答应该结合：

- 当前 log 或 stack trace
- ResearchKB 里的相似 `problem_cases`
- 相关论文 claim、limitation 或 safety evidence
- 具体修复步骤和验证命令

### 下一轮实验计划

可以这样问：

```text
根据最近实验结果和文献证据，给我下一轮实验计划。
```

合格的计划应该包含：

- dataset
- baseline
- method variant
- ablation
- metric
- success criterion
- failure criterion
- 必要时的 safety/privacy check
- 跑完后能支持或否定什么 claim

### idea 查新

可以这样问：

```text
用 ResearchKB 和公开文献元数据检查这个 idea，找 closest prior work 和真正的新意空间。
```

好的 novelty check 不应该只说“看起来挺新”，而应该指出最接近的已有工作、差异点，以及还缺什么证据。

## ResearchKB 数据模型

这套流程假设知识库能存储或暴露几类记录：

- `papers`: 论文元数据
- `chunks`: abstract、PDF、appendix、table、note 等文本块
- `claims`: 方法、限制、实验、安全等结构化 claim
- `experiment_runs`: 实验配置、输出、metrics、日志和状态
- `problem_cases`: 失败症状、原因、尝试过的修复和最终方案

具体实现可以变化。关键是 agent 在正常工作时能查询这些记录。

## 各工具的角色

### ResearchKB

机器可查询的记忆层。保存文献证据、实验记录和失败案例。

### Obsidian

面向人的笔记层。适合阅读、总结、idea 草稿和人工复盘，但不应该作为唯一结构化数据库。

### Zotero

论文管理层。负责收集 PDF 和元数据。可以通过 Better BibTeX 等工具导出到 ResearchKB。

### Codex / Claude Code / Cursor

agent 入口。负责运行命令、改代码、查日志、查询 ResearchKB、写修复方案和实验计划。

### GitHub

公开工作流层。只保存模板、辅助脚本、图示和脱敏文档。不保存真实数据库、PDF、auth 文件或个人路径。

## Claude Code 启动器模板

`launchers/` 目录包含可选的 Claude Code launcher 模板。

它们适用于你想为不同模型供应商或 API 路由准备独立入口的场景。ResearchKB 本身不依赖这些启动器。

使用前请阅读 [launchers/README.md](launchers/README.md)。

规则：

- API key 放在环境变量或本地私有配置里。
- 不要提交 provider token。
- 把这些脚本当作模板，根据自己的供应商配置调整。

## Cursor MCP Smoke Test

`scripts/cursor_mcp_smoke.py` 用来对 Cursor MCP 配置做轻量级连通性检查。

```powershell
python .\scripts\cursor_mcp_smoke.py --help
```

它只是 smoke test，不能替代 Cursor 内部完整端到端验证。

## 怎么衡量这套东西有没有用

这套系统不是“搭起来就算成功”，而是要看它是否改善科研决策。

### 基础设施健康

- health check 通过
- auto-harvest 能正常运行
- watched paths 存在
- parse failure 接近 0
- ResearchKB 查询能返回 evidence

### 知识覆盖

- papers、chunks、claims 数量持续增长
- 重点论文能按 topic 检索到
- limitation 和 safety claims 可检索
- closest-prior-work 查询能返回有意义结果

### 实验记忆质量

建议跟踪：

```text
structured_metrics_runs / total_experiment_runs
```

建议目标：

```text
>= 0.70
```

失败 run 最好包含：

- `failure_type`
- log path
- config path
- final fix
- affected metric

### 科研实用性

这套流程真正有用时，应该能看到：

- 同类失败第二次出现时诊断更快
- 下一轮实验计划能引用最近 runs 和论文证据
- idea check 能找 closest prior work，而不是泛泛建议
- 实验决策变成明确的 `continue`、`stop` 或 `redesign`

## 隐私和安全

不要提交：

- API key
- auth token
- SSH private key
- 本机绝对路径
- 个人用户名
- 机器相关日志
- ResearchKB SQLite 数据库
- Zotero profile
- 没有再分发权限的 PDF
- 大型生成产物

提交前建议检查：

```powershell
rg -n "sk-|api[_-]?key|auth[_-]?token|password|secret|bearer" .
rg -n "<your-username>|<private-host>|<private-project-name>" .
git status -sb --ignored
```

公开示例里使用占位符：

```text
<ResearchKBRoot>
<ProjectRoot>
<workspace-or-output-dir>
```

## 开发检查

编译 Python 辅助脚本：

```powershell
python -m py_compile .\researchkb\rk_health.py .\scripts\cursor_mcp_smoke.py
```

运行 ResearchKB health check：

```powershell
$env:RESEARCHKB_ROOT = "<ResearchKBRoot>"
.\researchkb\rk-health.cmd --json
```

## 项目状态

这是一个工作流模板，不是完整产品。实际使用时通常需要按你的环境调整：

- 入库命令
- ResearchKB schema 细节
- watched paths
- 模型供应商启动器
- 实验 metrics
- agent prompt 约定

核心原则保持不变：私有数据留在本地，GitHub 只保存可迁移的 workflow code，让科研证据能在日常 agent 工作中被查询和复用。
