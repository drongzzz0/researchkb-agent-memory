# KV Cache Reuse Experiment Metrics Contract

Purpose: make every KV-cache reuse experiment harvestable and comparable by ResearchKB.

Every experiment output directory should include at least one of:

- `metrics.json`
- `results.json`
- `summary.json`
- `eval_results.json`

Minimum recommended JSON fields:

```json
{
  "project": "KV Cache Reuse",
  "experiment": "short_unique_name",
  "gate": "Gxxx_or_named_gate",
  "status": "completed_positive | completed_negative | failed | pass | fail",
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
    "memory_mb": 0.0
  },
  "failure_type": "",
  "decision": "continue | stop | redesign | rerun",
  "next_action": "one concrete next step",
  "safety": {
    "privacy_or_leakage_checked": false,
    "multi_tenant_risk": "",
    "mitigation": ""
  }
}
```

If writing a plain log instead of JSON, emit parseable metric lines:

```text
METRIC quality_retention=0.92
METRIC ttft_speedup_vs_full=2.4
METRIC failure_type=quality_collapse
```

Health target:

- `with_metrics / experiment_runs >= 0.70`
- every failed run should include `failure_type`
- every publishable run should include quality, latency, and safety/leakage notes
