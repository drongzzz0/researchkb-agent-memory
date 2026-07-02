# Retrieval Evals

`retrieval_eval.jsonl` is the gold query set consumed by `scripts/eval_retrieval.py`.

**The bundled set is synthetic.** It validates the demo workflow only and says nothing about
retrieval quality on a real literature or experiment library. Real deployments should add
their own `evals/*.jsonl` built from queries they actually ask and IDs they know should be
returned.

## Case Format

One JSON object per line:

```json
{"id": "unique_case_name", "tool": "search_chunks", "query": "keywords to search", "expected_source_ids": ["chunk_yourlib_001"], "k": 5}
```

Fields:

- `id`: unique case name, shown in reports.
- `tool`: one of `search_papers`, `search_chunks`, `search_claims`, `search_evidence`,
  `find_failure_cases`, `find_recent_runs`.
- `query`: keyword query (omit for `find_recent_runs`).
- `arguments`: optional dict for `find_recent_runs` (`project`, `status`, `limit`).
- `expected_source_ids`: IDs that must appear in the top `k` results. An **empty list turns
  the case into a negative guard**: it passes only when nothing is returned.
- `k`: cutoff for recall (default 5).

## Positive Case Example

Ask something your library should answer, and list the IDs that prove it:

```json
{"id": "kv_reuse_quality", "tool": "find_failure_cases", "query": "quality drops after enabling cache reuse", "expected_source_ids": ["problem_example_cache_template_mismatch"], "k": 5}
```

## Negative Guard Example

Ask something your library should NOT answer, so a degenerate "return everything" retriever
fails the eval:

```json
{"id": "unrelated_topic_guard", "tool": "search_chunks", "query": "kubernetes ingress webhook", "expected_source_ids": [], "k": 5}
```

Aim for at least one guard per searchable table.

## Running

```powershell
python .\scripts\eval_retrieval.py --root "<ResearchKBRoot>" --eval-file .\evals\my_eval.jsonl --min-recall 0.9 --min-mrr 0.75
```

Reported metrics: `recall_at_k`, `mrr`, `precision_at_1`, `guard_pass_rate`, `pass_rate`,
`avg_latency_ms`. Non-zero exit when thresholds are not met, so the eval can gate CI.
