# KV Cache Reuse Metrics Contract

Purpose: extend the generic [experiment_metrics_contract.md](experiment_metrics_contract.md) for KV-cache reuse, prefix caching, cross-model state transfer, and LLM serving-efficiency experiments.

Use the generic fields first, then add the KV-specific metrics below.

## Recommended JSON Shape

```json
{
  "project": "KV Cache Reuse",
  "experiment": "short_unique_name",
  "run_id": "stable_run_id",
  "status": "completed_positive | completed_negative | failed",
  "dataset": "dataset name and sample count",
  "model": "producer -> consumer",
  "seed": "",
  "metrics": {
    "quality_metric": 0.0,
    "quality_retention": 0.0,
    "ttft_ms": 0.0,
    "ttft_speedup_vs_full": 0.0,
    "total_ms": 0.0,
    "total_speedup_vs_full": 0.0,
    "memory_mb": 0.0,
    "cache_hit_rate": 0.0,
    "reuse_accept_rate": 0.0
  },
  "failure_type": "",
  "decision": "continue | stop | redesign | rerun | unknown",
  "next_action": "one concrete next step",
  "safety": {
    "privacy_or_leakage_checked": false,
    "multi_tenant_risk": "",
    "prompt_template_guard": false,
    "cache_scope": "single_user | same_project | multi_tenant | unknown",
    "mitigation": ""
  },
  "artifacts": [],
  "notes": ""
}
```

## KV-Specific Metrics

| Metric | Description |
| --- | --- |
| `quality_metric` | Primary task metric such as accuracy, F1, EM, win rate, or pass rate |
| `quality_retention` | Quality relative to full recomputation |
| `ttft_ms` | Time to first token |
| `ttft_speedup_vs_full` | TTFT speedup over full recomputation |
| `total_ms` | Total generation or serving latency |
| `total_speedup_vs_full` | Total latency speedup over full recomputation |
| `memory_mb` | Peak or steady memory usage |
| `cache_hit_rate` | Fraction of requests that reused cache |
| `reuse_accept_rate` | Fraction of candidate reuse attempts accepted after guards |

## Safety Fields

KV-cache reuse can create privacy and correctness risks. Record safety checks explicitly.

| Field | Description |
| --- | --- |
| `privacy_or_leakage_checked` | Whether the run included a privacy or leakage check |
| `multi_tenant_risk` | Risk summary for cross-user or cross-tenant sharing |
| `prompt_template_guard` | Whether prompt-template compatibility was validated |
| `cache_scope` | Where reuse was allowed |
| `mitigation` | Guardrail or mitigation used |

## Plain Log Fallback

```text
METRIC quality_retention=0.92
METRIC ttft_speedup_vs_full=2.4
METRIC total_speedup_vs_full=1.8
METRIC memory_mb=9216
METRIC privacy_or_leakage_checked=false
METRIC failure_type=quality_collapse
METRIC decision=redesign
```

## Publishable Run Checklist

- Quality metric and quality retention are present.
- TTFT or total latency is present.
- Memory usage is present.
- `failure_type` is present for negative or failed runs.
- `decision` and `next_action` are present.
- Safety or leakage status is explicitly recorded.
