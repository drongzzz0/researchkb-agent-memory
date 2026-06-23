# ResearchKB Agent Memory

[![CI](https://github.com/drongzzz0/obsidian/actions/workflows/ci.yml/badge.svg)](https://github.com/drongzzz0/obsidian/actions/workflows/ci.yml)

[English](README.md) | 简体中文

一个轻量级工作流模板，用来让 Codex、Claude Code、Cursor 等 research agent 能查询本地文献证据、实验历史和失败经验。

![ResearchKB Agent Memory workflow](assets/readme-workflow-v2.png)

## 这个仓库是什么

这是一个公开的 workflow starter kit，用来把本地 ResearchKB 数据接入 research agents。

它提供：

- 公开模板
- 实验输出约定
- 健康检查脚本
- launcher 示例
- agent 使用 prompt
- 隐私边界规则

它不提供：

- 你的私有 ResearchKB 数据库
- 私有论文 PDF
- Zotero profile
- 实验日志
- API key
- 托管版 RAG 服务

本仓库生成的 demo database 完全是 synthetic，只用于验证流程。真实 ResearchKB 不在仓库内，应该保留在你的本地私有目录。

## 它解决什么问题

Agent 只看当前对话时，很容易忘记论文、历史实验和以前踩过的坑。这个仓库提供的是可公开、可迁移的连接层：

- **文献记忆：** 把论文、PDF、Zotero 导出和笔记沉淀到 ResearchKB。
- **实验记忆：** 从项目输出目录采集 `metrics.json`、`results.json`、日志和 summary。
- **失败记忆：** 把失败现象、原因、尝试过的修复和最终方案记录成可检索案例。
- **Agent 使用：** Codex、Claude Code、Cursor 在排错、规划实验、查新时先查询 ResearchKB。

真实数据库、PDF、日志、密钥和机器相关配置都不放进 Git。

## 快速开始

### PowerShell

```powershell
git clone https://github.com/drongzzz0/obsidian.git
cd obsidian
```

创建 synthetic demo database 并查询：

```powershell
python .\scripts\init_researchkb_workspace.py
python .\scripts\standardize_run.py .\.runtime\example-project\runs\smoke-test
python .\scripts\auto_standardize_runs.py --paths-file .\.runtime\researchkb\config\auto_harvest_paths.txt --project "Smoke Test"
python .\scripts\seed_demo_db.py
python .\researchkb\rk_health.py --root .\.runtime\researchkb
python .\scripts\query_demo.py --root .\.runtime\researchkb latest-runs
```

### Bash

```bash
git clone https://github.com/drongzzz0/obsidian.git
cd obsidian
python scripts/init_researchkb_workspace.py
python scripts/standardize_run.py .runtime/example-project/runs/smoke-test
python scripts/auto_standardize_runs.py --paths-file .runtime/researchkb/config/auto_harvest_paths.txt --project "Smoke Test"
python scripts/seed_demo_db.py
python researchkb/rk_health.py --root .runtime/researchkb
python scripts/query_demo.py --root .runtime/researchkb latest-runs
```

生成的 demo 会创建：

- 本地 `.runtime/researchkb` scaffold
- 本地 `.runtime/example-project/runs/smoke-test` run
- `config/auto_harvest_paths.txt`
- 可解析的 `metrics.json` 和 `summary.json`
- 标准化后的 `run_record.json`
- synthetic `.runtime/researchkb/db/literature.sqlite` 数据库

这个公开 demo DB 只包含 synthetic papers、chunks、claims、evidence links、experiment runs 和 failure cases，不是你的真实 ResearchKB。

demo 跑通后，再接入你自己的私有 ResearchKB：

```powershell
python .\scripts\init_researchkb_workspace.py --root "<ResearchKBRoot>" --project-root "<ProjectRoot>"
```

完整 10 分钟闭环见 [docs/quickstart.md](docs/quickstart.md)。

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

如果项目输出比较杂，既有 `metrics.json`、`results.json`、`eval_results.json`、`summary.json`，又有 `METRIC key=value` 日志，可以先标准化一个 run 目录：

```powershell
python .\scripts\standardize_run.py "<ProjectRoot>\runs\<run-id>"
```

它会写出 `run_record.json`，统一包含 `run_id`、`dataset`、`model`、`sample_count`、`quality_retention`、`latency_ms`、`failure_type`、`decision` 和 `next_action` 等字段。

如果想接近“无感接入”，把批量标准化器指向 watched paths：

```powershell
python .\scripts\auto_standardize_runs.py --paths-file "<ResearchKBRoot>\config\auto_harvest_paths.txt" --project "<ProjectName>"
```

把这条命令放在 ResearchKB harvest 命令前面，由 scheduled task、cron 或实验 wrapper 定期调用。新的或已变更的 run 目录会自动生成 `run_record.json`，已经是最新的目录会跳过。

通用实验输出约定见 [researchkb/contracts/experiment_metrics_contract.md](researchkb/contracts/experiment_metrics_contract.md)。
KV-cache reuse 相关实验见 [researchkb/contracts/kv_cache_reuse_metrics_contract.md](researchkb/contracts/kv_cache_reuse_metrics_contract.md)。

## 仓库结构

```text
.
|-- CHANGELOG.md
|-- CONTRIBUTING.md
|-- LICENSE
|-- ROADMAP.md
|-- SECURITY.md
|-- pyproject.toml
|-- .github/
|   `-- workflows/
|       `-- ci.yml
|-- assets/
|   `-- readme-workflow-v2.png
|-- docs/
|   |-- quickstart.md
|   |-- architecture.md
|   |-- schema_minimal.md
|   `-- agent_tool_contracts.md
|-- schemas/
|   |-- experiment_metrics.schema.json
|   |-- problem_case.schema.json
|   |-- paper.schema.json
|   |-- chunk.schema.json
|   |-- claim.schema.json
|   `-- evidence_link.schema.json
|-- examples/
|   |-- smoke-run/
|   |-- failure-case/
|   |-- paper-memory/
|   `-- agent-answers/
|-- launchers/
|   `-- Claude Code launcher templates
|-- researchkb/
|   |-- contracts/
|   |   |-- experiment_metrics_contract.md
|   |   `-- kv_cache_reuse_metrics_contract.md
|   |-- auto_harvest_paths.example.txt
|   |-- kv_experiment_metrics_contract.md
|   |-- rk-health.cmd
|   `-- rk_health.py
|-- scripts/
|   |-- auto_standardize_runs.py
|   |-- cursor_mcp_smoke.py
|   |-- init_researchkb_workspace.py
|   |-- public_repo_scan.py
|   |-- query_demo.py
|   |-- seed_demo_db.py
|   |-- standardize_run.py
|   `-- validate_examples.py
|-- tests/
|   |-- test_init_researchkb_workspace.py
|   |-- test_public_repo_scan.py
|   `-- test_rk_health.py
|-- .gitignore
|-- .public-scan-local.example.txt
|-- README.zh-CN.md
`-- README.md
```

## 包含的工具

- `researchkb/rk-health.cmd`: 检查 ResearchKB、watched paths、日志和最近实验记忆覆盖率。
- `researchkb/auto_harvest_paths.example.txt`: 安全的 watch-list 模板。
- `researchkb/contracts/experiment_metrics_contract.md`: 通用实验输出约定。
- `researchkb/contracts/kv_cache_reuse_metrics_contract.md`: KV-cache reuse 指标和安全扩展约定。
- `researchkb/kv_experiment_metrics_contract.md`: 旧链接兼容入口。
- `scripts/init_researchkb_workspace.py`: 创建本地 smoke workspace，并打印下一步 health/harvest 命令。
- `scripts/seed_demo_db.py`: 在 `.runtime/researchkb` 下创建完全 synthetic 的 demo SQLite 数据库。
- `scripts/query_demo.py`: 查询 synthetic demo DB。
- `scripts/standardize_run.py`: 把混合实验输出和 `METRIC key=value` 日志转换成 `run_record.json`。
- `scripts/auto_standardize_runs.py`: 扫描 watched paths，增量生成缺失或过期的 `run_record.json`。
- `scripts/validate_examples.py`: 用 schemas 校验 example JSON。
- `scripts/public_repo_scan.py`: 扫描公开文件里的本机路径、疑似密钥和私有痕迹。
- `scripts/cursor_mcp_smoke.py`: Cursor MCP 配置 smoke test。
- `launchers/`: 可选 Claude Code 启动器模板。真实 API key 不要放进仓库。

## 示例

- [examples/smoke-run](examples/smoke-run): 第一次入库测试用的最小 `metrics.json` 和 `summary.json`。
- [examples/standardized-run](examples/standardized-run): synthetic 标准化 `run_record.json` 输出。
- [examples/failure-case](examples/failure-case): 虚构的可复用失败案例。
- [examples/paper-memory](examples/paper-memory): paper、chunk、claim、evidence-link 记录示例。
- [examples/agent-answers](examples/agent-answers): 好的和坏的 troubleshooting answer 对比。

## 核心设计文档

- [docs/quickstart.md](docs/quickstart.md): clone -> bootstrap -> health check -> harvest -> agent prompt。
- [docs/architecture.md](docs/architecture.md): project run -> harvest -> ResearchKB -> agent query 闭环。
- [docs/schema_minimal.md](docs/schema_minimal.md): 最小记录结构和 evidence provenance 字段。
- [docs/agent_tool_contracts.md](docs/agent_tool_contracts.md): agent 工具输入输出和 evidence-grounded answer 格式。

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
python -m py_compile .\researchkb\rk_health.py .\scripts\cursor_mcp_smoke.py .\scripts\init_researchkb_workspace.py .\scripts\public_repo_scan.py .\scripts\seed_demo_db.py .\scripts\query_demo.py .\scripts\standardize_run.py .\scripts\validate_examples.py
python -m ruff check .
python -m pytest -vv --tb=short
python .\scripts\validate_examples.py
python .\scripts\public_repo_scan.py .
```

```powershell
$env:RESEARCHKB_ROOT = "<ResearchKBRoot>"
.\researchkb\rk-health.cmd --json
```

## 第一天怎么跑通

先让一个 fake run 或真实 run 能被 ResearchKB 采集和查询。不要一开始就配置整套系统。

```powershell
python .\scripts\init_researchkb_workspace.py --root "<ResearchKBRoot>" --project-root "<ProjectRoot>"
```

脚本会打印准确的下一步命令，大致等价于：

```powershell
python .\researchkb\rk_health.py --root "<ResearchKBRoot>"
"<ResearchKBRoot>\rk-harvest.cmd" --project "Smoke Test" "<ProjectRoot>\runs\smoke-test"
```

然后问 agent：

```text
在 ResearchKB 里找到最新的 Smoke Test run，告诉我记录了哪些 metrics。
```

如果 agent 能回答，说明闭环已经跑通。真实项目、Zotero 导出、Obsidian 笔记、launchers 和定时采集都可以等这个最小闭环成功后再加。

## 跑通以后再加什么

| 下一步 | 什么时候做 |
| --- | --- |
| 加更多 watched folders | 一个 run 已经能被采集和查询后 |
| 加 Zotero 或 PDF 入库 | 实验记忆路径已经确认可用后 |
| 改 schema 映射 | 你的 ResearchKB 表名或字段名不一致时 |
| 加领域特定 metrics | 通用 `metrics.json` 不够用时 |
| 加模型启动器 | 需要给不同供应商准备独立入口时 |
