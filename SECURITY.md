# Security Policy

This repository is a public workflow template. Do not submit issues, pull requests, screenshots, logs, or examples that contain private data.

## Do Not Submit

- API keys or auth tokens
- SSH keys or local credentials
- ResearchKB database files
- Zotero profile files
- private PDFs or copyrighted papers
- experiment logs from private projects
- local absolute paths
- personal usernames or hostnames
- model-provider account details

## Safe Examples

Use placeholders in public reports and examples:

```text
<ResearchKBRoot>
<ProjectRoot>
<workspace-or-output-dir>
<private-host>
<your-username>
```

Synthetic examples are preferred. If a bug requires real structure, redact content and keep only the minimal schema needed to reproduce the issue.

## Reporting Sensitive Issues

If you accidentally exposed a secret or private file in an issue or pull request, delete or redact it immediately and rotate the affected secret. Git history, screenshots, and notification emails may retain copies, so treat exposed credentials as compromised.
