# 项目进展

[English](project_status.md) | 简体中文

状态截至 **2026-07-02**，当前版本 **v0.3.0**。

本文档是项目的阶段性快照：目前做到哪、质量如何、接下来做什么。
逐版本明细见 [CHANGELOG.md](../CHANGELOG.md)，长期阶段规划见 [ROADMAP.md](../ROADMAP.md)。

## 这个项目是什么

一个本地优先的记忆层，让研究型 Agent（Codex、Claude Code、Cursor）能同时查询三类证据：
文献论断、实验运行、失败案例，每条结果都带溯源字段（`source_type`、`source_id`、
`locator`、`snippet`、`confidence`）。全部基于 SQLite 和 Python 标准库，私有数据不进 Git。

## 已交付内容

### v0.1.0（2026-06-17）：starter kit 基线

- 引导脚本、合成示例、六类记录的 JSON Schema。
- `rk_health.py` 就绪等级（`empty` / `smoke` / `usable` / `mature`）。
- CI：测试、schema 校验、公开仓库隐私扫描。

### v0.2.0：Agent 可查询，有效性可度量

- 只读 MCP server（纯标准库、stdio JSON-RPC），实现文档化的工具契约；SQLite 以
  `mode=ro` 挂载，FTS5 索引建在内存里，FTS5 不可用时降级为子串检索。
- 三层量化指标：
  1. 检索质量（CI 强制）：16 条金标查询集（含 4 条防误报负例）上的
     `recall_at_k`、`mrr`、`precision_at_1`、`guard_pass_rate`。
  2. 记忆库健康：`metrics_coverage`、`failure_documentation_rate`、
     `open_failure_cases`、`evidence_density`、`run_freshness_days`。
  3. 回答接地率：引用校验器输出 `citation_validity`。
- 失败记忆低摩擦捕获：失败 run 自动生成 `problem_case.draft.json` 草稿、会话开始简报命令。
- 仓库改名为 `researchkb-agent-memory`，补齐描述、topics 和 GitHub Release。

### v0.2.1：对齐与诚实度修复

- MCP server 补上 `search_evidence`（最核心的溯源查询接口）。
- 已实现/规划中工具明确分开；新增 [tool_matrix.md](tool_matrix.md) 和
  [mcp_compatibility.md](mcp_compatibility.md)。
- 明确"内置评测集只验证合成演示流程"；[../evals/README.md](../evals/README.md)
  说明如何编写用户自己的评测集。

### v0.3.0：可安装工具

- `src/researchkb_agent_memory/` 包结构；`pip install -e .` 提供 `rk-memory` 命令
  （16 个子命令：初始化、建演示库、运行标准化、健康检查、检索、对比、评测、
  引用校验、会话简报、MCP server）。
- 旧的 `researchkb/*.py` 和 `scripts/*.py` 保留为行为一致的兼容薄壳。
- CI 矩阵（ubuntu/windows × Python 3.10/3.13）每个任务都安装包并冒烟 CLI。

### v0.3.0 之后的未发布进展：第一批显式导入器

- `rk-memory import-runs` 可以预览并导入标准化后的 `run_record.json` 到
  `experiment_runs`。
- `rk-memory import-bibtex` 可以预览并导入 BibTeX / Zotero 论文元数据到 `papers`。
- `rk-memory import-notes` 可以预览并导入 curated Markdown 笔记到 `chunks`、`claims`
  和 `evidence_links`。
- 两个命令默认 dry-run；只有显式传入 `--write` 才写库。
- run 导入按 `run_id` upsert；BibTeX 导入按 DOI、arXiv 或 BibTeX key 派生出的稳定
  `paper_id` upsert；note 导入按稳定的 `chunk_id`、`claim_id` 和 `evidence_id` upsert。
- MCP server 仍然保持只读。

## 当前质量数据

均在合成演示库上测得（注意下方限定）：

| 指标 | 数值 |
| --- | --- |
| 测试 | 本地 76 个全过；未发布 importers 的 CI 矩阵待推送后验证 |
| 检索评测 | recall@k 1.0、MRR 0.96、precision@1 0.92、防误报通过率 1.0 |
| 引用有效率（好答案示例） | 1.0 |
| 演示库健康 | level `smoke`、指标覆盖率 1.0、证据密度 1.0 |
| 隐私扫描 | 公开文件无本机路径、密钥或私有痕迹 |

**限定：** 内置评测集只验证演示流程，尚无真实文献库/实验库上的基准数据；产出真实
基准是 v0.6 里程碑的目标。

## 已知限制

- Cursor、Claude Code、Codex 尚未对 MCP server 做过端到端验证；协议层行为由 CI 里的
  脚本化 stdio 测试覆盖。
- 目前只有关键词检索（FTS5 BM25 + LIKE 降级），暂不做语义/向量层（有意为之）。
- 包可本地安装，但尚未发布到 PyPI。
- 论文元数据、curated notes 和实验 run 入库已有显式 CLI 路径，但都要求已有私有数据库，
  且必须传入 `--write` 才会写入。
- 完整论文/PDF 解析仍在规划中；note importer 只处理整理过的 Markdown。

## 后续计划

### v0.4.0——真实数据导入（下一步）

- `rk-memory import-runs`：未发布版本已实现；下一步继续用真实项目测试并加固。
- `rk-memory import-bibtex`：未发布版本已实现；从 BibTeX / Zotero 导出种入 `papers`
  （只要元数据，不碰 PDF）。
- `rk-memory import-notes`：未发布版本已实现；把整理过的 Markdown 笔记导入为
  `chunks` / `claims` / `evidence_links`。
- `rk-memory schema check | init --dry-run`：显式、可选的 schema 管理。
- 贯穿文档和代码的硬规则：**MCP server 保持只读；所有写操作都是显式 CLI 命令。**

### v0.5.0——项目级记忆

- 新记录类型：`research_projects`（目标、当前假设、约束）、`decision_logs`
  （决策、理由、证据 ID、被否选项）、`open_questions`、`rejected_ideas`。
- 会话简报 v2：回答"做到哪了、什么被否了、下一步是什么"。
- 轻量 Obsidian/Markdown 导出（人读镜像，绝不作为主数据库）。

### v0.6.0——真实场景评测

- 用户评测集模板；decision eval 检查 Agent 回答的结构完整性：结论、证据、建议动作、
  缺失上下文、source ID。
- 基于引用校验器的无依据论断检测。
- 至少一个真实研究项目上的基准报告。

### 分发（需要所有者账号）

- 发布 PyPI（`pip install researchkb-agent-memory`、`uvx rk-memory`）。
- 至少一个客户端完成端到端验证后，登记 MCP 目录站。

### 现阶段刻意不做

PDF OCR / GROBID 解析、向量数据库、自动 idea 生成、写库型 MCP 工具、Web UI。
当前优先级是证明最小本地证据闭环在真实项目中稳定有用。

## 如何复核本状态

```bash
python -m pip install -e .
rk-memory init
rk-memory standardize-run .runtime/example-project/runs/smoke-test
rk-memory seed-demo --include-run .runtime/example-project/runs/smoke-test/run_record.json
rk-memory import-runs .runtime/example-project/runs --root .runtime/researchkb
rk-memory import-bibtex examples/paper-memory/demo.bib --root .runtime/researchkb
rk-memory import-notes examples/note-memory/synthetic-cache-note.md --root .runtime/researchkb
rk-memory eval --root .runtime/researchkb --min-recall 0.9 --min-mrr 0.75
rk-memory check-citations examples/agent-answers/good_troubleshooting_answer.md --root .runtime/researchkb --min-validity 1.0
python -m pytest -q
```
