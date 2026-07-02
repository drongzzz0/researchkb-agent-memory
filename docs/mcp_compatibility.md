# MCP Compatibility

Scope and limits of the reference MCP server `researchkb/rk_mcp_server.py`.

## Protocol

| Aspect | Value |
| --- | --- |
| Transport | stdio (newline-delimited JSON-RPC 2.0) |
| Declared protocol version | `2025-03-26` |
| Capabilities | tools only |
| Resources | not implemented |
| Prompts | not implemented |
| Sampling / elicitation | not implemented |
| Structured content | not implemented (tool results are JSON serialized into text content) |
| Streaming / HTTP transports | not implemented |
| Authentication | none (local stdio process, inherits the invoking user) |
| Write tools | none by design |

Newer protocol revisions exist (2025-06-18, 2025-11-25). The server declares `2025-03-26`
and uses only features that are stable across these revisions (initialize handshake,
`tools/list`, `tools/call` with text content). Clients that negotiate a newer version
should interoperate for this tools-only surface; this has not been exhaustively verified.

## Tested Clients

| Client | Status |
| --- | --- |
| Scripted stdio JSON-RPC harness | verified in CI (`tests/test_rk_mcp_server.py`, including a real subprocess round trip) |
| Cursor | not yet verified end to end |
| Claude Code | not yet verified end to end |
| Codex | not yet verified end to end |

If you verify a client end to end, please open an issue or PR updating this table.

## Security Boundary

- **Local-only by default.** The server is a stdio child process of your agent client. It
  binds no ports and serves no remote traffic.
- **Read-only by construction.** The SQLite database is attached with `mode=ro`; the FTS
  index is built in memory. There are no write tools. Importers and schema changes are
  separate, explicit CLI operations.
- **No secrets involved.** The server needs no API keys or tokens. Keep your ResearchKB
  root outside Git; this repository's hygiene scan (`scripts/public_repo_scan.py`) exists
  to keep local paths and secrets out of public files.
- **Review client tool permissions.** Your MCP client decides when tools run. Treat tool
  output as data from your own local database, and remember that snippets can contain
  whatever you ingested, so scope the `--root` to libraries you trust.

## Known Limitations

- No `structuredContent` in tool results; consumers parse the JSON text payload.
- No pagination beyond the `limit` argument (capped at 50).
- Keyword search (FTS5 BM25, LIKE fallback); no embedding or semantic search layer.
- Single database root per server process; run one server per library if you need more.
