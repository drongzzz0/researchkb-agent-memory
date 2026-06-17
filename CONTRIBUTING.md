# Contributing

Contributions are welcome when they keep the project portable, private-by-default, and easy to run locally.

## Good Contributions

- clearer documentation
- safer templates
- better ResearchKB health checks
- schema and tool-contract examples
- tests for helper scripts
- synthetic examples that do not contain private data

## Before Opening A Pull Request

Run:

```powershell
python -m py_compile .\researchkb\rk_health.py .\scripts\cursor_mcp_smoke.py
rg -n "sk-|api[_-]?key|auth[_-]?token|password|secret|bearer" .
rg -n "<your-username>|<private-host>|<private-project-name>" .
git status -sb --ignored
```

Also check that new examples are synthetic and do not include private PDFs, local databases, real experiment logs, personal usernames, hostnames, or absolute paths.

## Pull Request Checklist

- The change is useful outside one private machine.
- No API keys, tokens, logs, PDFs, databases, or local paths are committed.
- README or docs are updated when behavior changes.
- Helper scripts still compile.
- Examples are small and synthetic.

## Issue Reports

When reporting a bug, include:

- operating system
- Python version
- command that failed
- sanitized error message
- expected behavior
- minimal synthetic config or schema when relevant

Do not paste private logs or database dumps.
