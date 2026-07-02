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
python .\scripts\seed_demo_db.py --include-run .\.runtime\example-project\runs\smoke-test\run_record.json
python .\researchkb\rk_health.py --root .\.runtime\researchkb
python .\scripts\query_demo.py --root .\.runtime\researchkb latest-runs
```

### Bash

```bash
git clone https://github.com/drongzzz0/obsidian.git
cd obsidian
python scripts/init_researchkb_workspace.py
python scripts/standardize_run.py .runtime/example-project/runs/smoke-test
python scripts/seed_demo_db.py --include-run .runtime/example-project/runs/smoke-test/run_record.json
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

这个公开 demo DB 只包含 synthetic papers、chunks、claims、evidence links、experiment runs 和 failure cases。`latest-runs` 查询应该能看到刚标准化出来的 `run_smoke_001` 记录。它不是你的真实 ResearchKB。

demo 跑通后，再接入你自己的私有 ResearchKB：

```powershell
python .\scripts\init_researchkb_workspace.py --root "<ResearchKBRoot>" --project-root "<ProjectRoot>"
```

完整 10 分钟闭环见 [docs/quickstart.md](docs/quickstart.md)。

## 只读 MCP Server

Agent 可以通过一个纯标准库实现的 MCP server 直接查询 ResearchKB。它以只读模式打开 SQLite
数据库，在内存中构建 FTS5 索引，并实现 [docs/agent_tool_contracts.md](docs/agent_tool_contracts.md)
中定义的工具契约：

`search_papers`、`search_chunks`、`search_claims`、`find_failure_cases`、`find_recent_runs`、
`compare_runs`、`get_health`。

在 Cursor（`~/.cursor/mcp.json`）或 Claude Code（`.mcp.json`）中注册：

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

每个工具结果都带 `source_type`、`source_id`、`locator`、`snippet`、`confidence`，以及
`missing_context` 和 `warnings`，保证 Agent 回答可审计。server 不会写数据库。

会话开始时注入上下文（最近 runs、未解决失败案例、下一步建议）：

```powershell
python .\scripts\session_brief.py --root "<ResearchKBRoot>"
```

## 有效性度量

三层量化指标，让"这套记忆系统有没有用"成为一个数字而不是感觉：

1. **检索质量**（CI 强制）：`scripts/eval_retrieval.py` 跑
   [evals/retrieval_eval.jsonl](evals/retrieval_eval.jsonl) 金标查询集，报告 `recall_at_k`、
   `mrr`、`precision_at_1`、`guard_pass_rate`（防误报）和 `avg_latency_ms`。

```powershell
python .\scripts\eval_retrieval.py --root .\.runtime\researchkb --min-recall 0.9 --min-mrr 0.75
```

2. **记忆库健康**（`rk_health.py` 的 judgement.effectiveness）：`metrics_coverage`、
   `failure_documentation_rate`、`open_failure_cases`、`evidence_density`、
   `run_freshness_days`，量化记忆的完整度和新鲜度。

3. **回答接地率**：`scripts/check_citations.py` 从 Agent 回答里抽取引用的 source ID，
   逐个对照数据库验证，报告 `citation_validity`。

```powershell
python .\scripts\check_citations.py answer.md --root "<ResearchKBRoot>" --min-validity 1.0
```

## 与同类工具的区别

| 工具 | 覆盖范围 | 本工具包的差异 |
| --- | --- | --- |
| Mem0、Zep、Letta | 通用对话式 agent 记忆 | 类型化研究记录：runs、失败案例、带溯源的论断 |
| Engram 类 SQLite 记忆 server | 本地优先的通用教训 | 研究 schema + 实验/文献/失败三者合流 |
| W&B / MLflow MCP server | 实验 runs 与 traces | 本地优先、不绑平台，且与论文和失败记忆连接 |
| zotero-mcp、paper-search-mcp | 文献检索 | 与论文证据联动的实验记忆和失败记忆 |
| InternAgent 记忆模块 | 框架内部实验记忆 | 可移植契约，任何 agent 栈都能通过 MCP 查询 |

定位：一个本地、私有、可审计的证据库，让文献论断、实验运行和失败案例一起回答问题。

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
|   |-- README.md
|   |-- quickstart.md
|   |-- architecture.md
|   |-- schema_minimal.md
|   `-- agent_tool_contracts.md
|-- evals/
|   `-- retrieval_eval.jsonl
|-- schemas/
|   `-- 6 个 JSON Schema（papers、chunks、claims、evidence links、metrics、problem cases）
|-- examples/
|   |-- smoke-run/
|   |-- standardized-run/
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
|   |-- rk_health.py
|   |-- rk_query.py
|   `-- rk_mcp_server.py
|-- scripts/
|   |-- auto_standardize_runs.py
|   |-- check_citations.py
|   |-- cursor_mcp_smoke.py
|   |-- eval_retrieval.py
|   |-- init_researchkb_workspace.py
|   |-- public_repo_scan.py
|   |-- query_demo.py
|   |-- seed_demo_db.py
|   |-- session_brief.py
|   |-- standardize_run.py
|   `-- validate_examples.py
|-- tests/
|   `-- 覆盖上述所有工具的 pytest 测试
|-- .gitignore
|-- .public-scan-local.example.txt
|-- README.zh-CN.md
`-- README.md
```

## 包含的工具

- `researchkb/rk_mcp_server.py`: 只读 MCP server，把证据查询工具暴露给 Codex、Claude Code、Cursor。
- `researchkb/rk_query.py`: 共享只读查询引擎，内存 FTS5 索引，FTS5 不可用时降级为子串检索。
- `researchkb/rk-health.cmd`: 检查 ResearchKB、watched paths、日志和最近实验记忆覆盖率。
- `researchkb/auto_harvest_paths.example.txt`: 安全的 watch-list 模板。
- `researchkb/contracts/experiment_metrics_contract.md`: 通用实验输出约定。
- `researchkb/contracts/kv_cache_reuse_metrics_contract.md`: KV-cache reuse 指标和安全扩展约定。
- `researchkb/kv_experiment_metrics_contract.md`: 旧链接兼容入口。
- `scripts/init_researchkb_workspace.py`: 创建本地 smoke workspace，并打印下一步 health/harvest 命令。
- `scripts/seed_demo_db.py`: 在 `.runtime/researchkb` 下创建完全 synthetic 的 demo SQLite 数据库，也可以 include 生成出的 `run_record.json`。
- `scripts/query_demo.py`: 查询 synthetic demo DB。
- `scripts/standardize_run.py`: 把混合实验输出和 `METRIC key=value` 日志转换成 `run_record.json`，失败 run 自动生成 `problem_case.draft.json` 草稿。
- `scripts/auto_standardize_runs.py`: 扫描 watched paths，增量生成缺失或过期的 `run_record.json`。
- `scripts/session_brief.py`: 会话开始简报，含最近 runs、未解决失败案例和有效性指标。
- `scripts/eval_retrieval.py`: 检索质量评测（recall@k、MRR、precision@1、防误报通过率）。
- `scripts/check_citations.py`: 对照数据库验证 Agent 回答中引用的 source ID。
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
python -m py_compile .\researchkb\rk_health.py @((Get-ChildItem .\scripts\*.py).FullName)
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
