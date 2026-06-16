# Claude Code Dual Launchers

This directory provides two local launcher entries for the installed `claude` CLI without changing the global `%USERPROFILE%\.claude\settings.json`.

## Entries

- `claude-gpt54.cmd`
  - Keeps using the current GPT route from your existing `~/.claude/settings.json`.
- `claude-claude-openrouter.cmd`
  - Routes Claude Code through OpenRouter and defaults to `anthropic/claude-sonnet-4.6`.
  - Requires `OPENROUTER_API_KEY` to already exist in your environment.

## Usage

From this directory:

```powershell
.\claude-gpt54.cmd
.\claude-claude-openrouter.cmd
```

To inspect the effective launcher config without starting an interactive session:

```powershell
.\claude-gpt54.cmd --show-config
.\claude-claude-openrouter.cmd --show-config
```

Any extra arguments are forwarded to `claude`, for example:

```powershell
.\claude-claude-openrouter.cmd --print "say hello"
```

## Design Notes

- Both launchers reuse your existing non-secret Claude Code settings such as permissions and enabled plugins.
- Both launchers skip loading user-scope settings directly and instead inject runtime overrides, so the two entries do not fight over one global model route.
- No API key is written into this workspace.
