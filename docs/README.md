# Documentation

This directory describes the portable ResearchKB Agent Memory contracts. It should contain public design notes, templates, and schemas only.

## Core Docs

- [architecture.md](architecture.md): end-to-end loop and component boundaries.
- [schema_minimal.md](schema_minimal.md): minimal schema for papers, claims, runs, failure cases, and evidence links.
- [agent_tool_contracts.md](agent_tool_contracts.md): expected tool inputs and outputs for agents.

## Examples

See [../examples](../examples) for synthetic records and answer examples:

- `smoke-run/`: minimal experiment output.
- `failure-case/`: reusable problem memory.
- `paper-memory/`: paper, chunk, claim, and evidence-link records.
- `agent-answers/`: good and bad troubleshooting responses.

## Private Logs Are Not Tracked

Project and experiment logs are intentionally excluded from this public repository.

Keep machine-specific logs locally, for example:

- `docs/project-plan-log.md`
- `docs/experiment-log.md`

Those files may contain local paths, hostnames, experiment outputs, operational history, and other private context. Publish only sanitized summaries, templates, or synthetic examples.
