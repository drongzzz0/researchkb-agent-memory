# Agent Tool Contracts

This document defines the tool behavior expected by Codex, Claude Code, Cursor, or any other agent that queries ResearchKB.

The contracts are implementation-neutral. They can be exposed through MCP, a CLI, local Python functions, or another local API.

## Common Output Rules

Every tool that returns evidence should include:

- `source_type`
- `source_id`
- `locator`
- `snippet`
- `confidence`

Every tool should also return:

- `missing_context`: what was needed but not found
- `warnings`: privacy, quality, or ambiguity warnings

## Tool Index

| Tool | Purpose |
| --- | --- |
| `search_papers` | Find paper metadata by topic, title, author, tag, or year |
| `search_chunks` | Retrieve source text chunks |
| `search_claims` | Retrieve structured claims |
| `find_methods` | Find methods for a topic or problem |
| `find_limitations` | Find limitations and failure modes |
| `find_failure_cases` | Find similar historical failures |
| `find_recent_runs` | Retrieve recent experiment runs |
| `compare_runs` | Compare metrics or decisions across runs |
| `suggest_next_experiment` | Propose next experiment plan from runs and literature |

## Contracts

### `search_papers`

Input:

```json
{
  "query": "KV cache reuse",
  "filters": {
    "year_min": 2020,
    "tags": ["llm-serving"]
  },
  "limit": 10
}
```

Output:

```json
{
  "papers": [
    {
      "paper_id": "paper_example_001",
      "title": "Example Paper Title",
      "year": 2025,
      "venue": "Example Venue",
      "url": "https://example.org/paper",
      "tags": ["llm-serving", "cache"]
    }
  ],
  "missing_context": [],
  "warnings": []
}
```

### `search_chunks`

Input:

```json
{
  "query": "multi-tenant KV cache leakage",
  "filters": {
    "paper_id": "optional",
    "source_type": "paper_text"
  },
  "limit": 10
}
```

Output:

```json
{
  "chunks": [
    {
      "chunk_id": "chunk_example_001",
      "paper_id": "paper_example_001",
      "section": "Security Discussion",
      "locator": "section:Security Discussion",
      "snippet": "The paper discusses cache sharing risks in multi-tenant serving.",
      "confidence": 0.86
    }
  ],
  "missing_context": [],
  "warnings": []
}
```

### `search_claims`

Input:

```json
{
  "query": "prefix cache reuse improves latency",
  "claim_type": "experiment",
  "filters": {
    "topic": "llm-serving"
  },
  "limit": 10
}
```

Output:

```json
{
  "claims": [
    {
      "claim_id": "claim_example_001",
      "claim_type": "experiment",
      "statement": "Prefix reuse reduces time to first token under repeated prompts.",
      "source_type": "claim",
      "source_id": "claim_example_001",
      "locator": "paper_example_001:section:Evaluation",
      "snippet": "Evaluation reports lower time to first token for repeated prefixes.",
      "confidence": 0.81
    }
  ],
  "missing_context": [],
  "warnings": []
}
```

### `find_failure_cases`

Input:

```json
{
  "symptom": "quality drops after enabling cache reuse",
  "project": "optional",
  "model": "optional",
  "limit": 10
}
```

Output:

```json
{
  "cases": [
    {
      "problem_id": "problem_example_001",
      "symptom": "Quality dropped after enabling reuse-only decoding.",
      "root_cause": "Cache state was reused across incompatible prompt templates.",
      "fix": "Add template hash validation before reuse.",
      "linked_runs": ["run_example_001"],
      "linked_papers": ["paper_example_001"],
      "evidence": [
        {
          "source_type": "run",
          "source_id": "run_example_001",
          "locator": "metrics.json:quality_retention",
          "snippet": "\"quality_retention\": 0.71",
          "confidence": 0.92
        }
      ],
      "confidence": 0.84
    }
  ],
  "missing_context": [],
  "warnings": []
}
```

### `find_recent_runs`

Input:

```json
{
  "project": "KV Cache Reuse",
  "status": "completed_negative",
  "limit": 5
}
```

Output:

```json
{
  "runs": [
    {
      "run_id": "run_example_001",
      "project": "KV Cache Reuse",
      "experiment": "reuse smoke test",
      "status": "completed_negative",
      "metrics": {
        "quality_retention": 0.71,
        "latency_ms": 128.5
      },
      "decision": "redesign",
      "next_action": "Validate prompt-template compatibility before reuse."
    }
  ],
  "missing_context": [],
  "warnings": []
}
```

### `compare_runs`

Input:

```json
{
  "run_a": "run_example_001",
  "run_b": "run_example_002",
  "metrics": ["accuracy", "latency_ms", "peak_memory_mb"]
}
```

Output:

```json
{
  "comparison": {
    "run_a": "run_example_001",
    "run_b": "run_example_002",
    "deltas": {
      "accuracy": -0.012,
      "latency_ms": -34.5,
      "peak_memory_mb": 512
    }
  },
  "evidence": [
    {
      "source_type": "run",
      "source_id": "run_example_001",
      "locator": "metrics.json",
      "snippet": "accuracy and latency metrics parsed from run output",
      "confidence": 0.95
    }
  ],
  "missing_context": [],
  "warnings": []
}
```

### `suggest_next_experiment`

Input:

```json
{
  "project": "KV Cache Reuse",
  "constraints": {
    "budget": "one GPU-day",
    "must_include_safety_check": true
  },
  "limit_evidence": 10
}
```

Output:

```json
{
  "plan": {
    "decision": "redesign",
    "experiment": "template-hash guarded reuse",
    "dataset": "synthetic repeated-prefix benchmark",
    "baseline": "full recomputation",
    "variant": "reuse with prompt-template hash guard",
    "metrics": ["quality_retention", "ttft_speedup_vs_full", "privacy_or_leakage_checked"],
    "success_criterion": "quality_retention >= 0.98 and ttft_speedup_vs_full >= 1.20",
    "failure_criterion": "any cross-template reuse or quality_retention < 0.95",
    "next_action": "Implement hash guard and run 100 prompt pairs."
  },
  "evidence": [
    {
      "source_type": "problem_case",
      "source_id": "problem_example_001",
      "locator": "final_solution",
      "snippet": "Add template hash validation before reuse.",
      "confidence": 0.84
    }
  ],
  "missing_context": ["No real multi-tenant leakage test has been recorded yet."],
  "warnings": ["Safety evidence is incomplete."]
}
```

## Good Agent Answer Format

Agents should return:

1. Direct answer
2. Evidence table
3. Reasoning based on evidence
4. Recommended action
5. Risks and missing context
6. Source IDs

Minimal example:

```text
Conclusion:
The failure is more consistent with incompatible cache reuse than with random noise.

Evidence:
- source_type=run, source_id=run_example_001, locator=metrics.json:quality_retention
- source_type=problem_case, source_id=problem_example_001, locator=final_solution

Recommended action:
Add prompt-template hash validation, rerun the smoke benchmark, and compare quality_retention.

Missing context:
No safety check for multi-tenant reuse has been recorded.
```
