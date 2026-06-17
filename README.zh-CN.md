# ResearchKB Agent Memory

[English](README.md) | 简体中文

一个轻量级工作流模板，用来让 Codex、Claude Code、Cursor 等 research agent 能查询本地文献证据、实验历史和失败经验。

![ResearchKB Agent Memory workflow](assets/readme-workflow-v2.png)

## 它解决什么问题

Agent 只看当前对话时，很容易忘记论文、历史实验和以前踩过的坑。这个仓库提供的是可公开、可迁移的连接层：

- **文献记忆：** 把论文、PDF、Zotero 导出和笔记沉淀到 ResearchKB。
- **实验记忆：** 从项目输出目录采集 `metrics.json`、`results.json`、日志和 summary。
- **失败记忆：** 把失败现象、原因、尝试过的修复和最终方案记录成可检索案例。
- **Agent 使用：** Codex、Claude Code、Cursor 在排错、规划实验、查新时先查询 ResearchKB。

真实数据库、PDF、日志、密钥和机器相关配置都不放进 Git。

## 快速开始

```powershell
git clone https://github.com/drongzzz0/obsidian.git
cd obsidian
```

指定你的本地 ResearchKB 目录：

```powershell
$env:RESEARCHKB_ROOT = "<ResearchKBRoot>"
```

配置自动采集目录：

```powershell
Copy-Item .\researchkb\auto_harvest_paths.example.txt "<ResearchKBRoot>\config\auto_harvest_paths.txt"
notepad "<ResearchKBRoot>\config\auto_harvest_paths.txt"
```

示例 watch-list：

```text
<ResearchKBRoot>\exports
<ResearchKBRoot>\auto_ingest
<ProjectRoot>\results
<ProjectRoot>\docs\draft
```

检查系统是否可用：

```powershell
.\researchkb\rk-health.cmd
.\researchkb\rk-health.cmd --json
```

手动采集一个项目：

```powershell
<ResearchKBRoot>\rk-harvest.cmd --project "Your Project" <workspace-or-output-dir>
```

## 怎么让 Agent 用它

可以直接这样问：

```text
这个实验失败了。先从 ResearchKB 找类似失败案例和修复方法，再给解决方案。
```

```text
根据最近实验结果和论文证据，给我下一轮实验计划。
```

```text
用 ResearchKB 和公开文献元数据检查这个 idea，最近的 prior work 是什么？
```

好的回答应该尽量引用最近 runs、相关论文和历史失败案例，而不是只给泛泛建议。

## 实验输出约定

实验最好输出至少一个可解析文件：

```text
metrics.json
results.json
summary.json
eval_results.json
```

或者在日志里打印：

```text
METRIC accuracy=0.842
METRIC latency_ms=128.5
METRIC peak_memory_mb=9216
```

KV-cache reuse 相关实验可以参考 [researchkb/kv_experiment_metrics_contract.md](researchkb/kv_experiment_metrics_contract.md)。

## 仓库结构

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

## 包含的工具

- `researchkb/rk-health.cmd`: 检查 ResearchKB、watched paths、日志和最近实验记忆覆盖率。
- `researchkb/auto_harvest_paths.example.txt`: 安全的 watch-list 模板。
- `researchkb/kv_experiment_metrics_contract.md`: KV-cache reuse 实验指标建议。
- `scripts/cursor_mcp_smoke.py`: Cursor MCP 配置 smoke test。
- `launchers/`: 可选 Claude Code 启动器模板。真实 API key 不要放进仓库。

## 隐私规则

不要提交：

- API key 或 auth token
- SSH key 或本地凭据
- 本机绝对路径
- 个人用户名或主机名
- ResearchKB 数据库
- Zotero profile
- 私有 PDF
- 实验日志和生成产物

公开示例里使用占位符：

```text
<ResearchKBRoot>
<ProjectRoot>
<workspace-or-output-dir>
```

提交前建议检查：

```powershell
rg -n "sk-|api[_-]?key|auth[_-]?token|password|secret|bearer" .
rg -n "<your-username>|<private-host>|<private-project-name>" .
git status -sb --ignored
```

## 开发检查

```powershell
python -m py_compile .\researchkb\rk_health.py .\scripts\cursor_mcp_smoke.py
```

```powershell
$env:RESEARCHKB_ROOT = "<ResearchKBRoot>"
.\researchkb\rk-health.cmd --json
```

## 最小可用配置

第一天不需要把所有东西都配置完。先只做三个决定：

1. **ResearchKB root：** 本地知识库放在哪里。
2. **一个 watched folder：** 先选一个正在做的项目输出目录。
3. **一个 metrics 格式：** 先统一成小的 `metrics.json`，或者日志里的 `METRIC key=value`。

在 health check 通过、一个实验 run 能被采集之前，可以先不管 `launchers/`、Zotero 导出、Obsidian 组织方式和复杂 schema 映射。

## 后续再自定义什么

| 部分 | 先怎么用 | 什么时候再改 |
| --- | --- | --- |
| ResearchKB schema | 先按 `papers`、`chunks`、`claims`、`experiment_runs`、`problem_cases` 理解 | 你的数据库表名或字段名不一样时 |
| 入库命令 | 先手动跑 `rk-harvest.cmd` | 需要定时采集或远程采集时 |
| 实验指标 | 先写 `metrics.json` | 需要领域特定指标时 |
| Agent prompt | 先用上面的示例 | 团队形成固定排错或实验规划流程后 |
| 模型启动器 | 可以先忽略 | 需要给不同供应商准备独立入口时 |

推荐路径是：clone 仓库，设置 `RESEARCHKB_ROOT`，监听一个输出目录，采集一个 run，确认闭环跑通后再逐步加自动化。
