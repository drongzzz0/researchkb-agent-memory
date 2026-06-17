# Good Troubleshooting Answer

## Conclusion

The failure is most consistent with incompatible cache reuse across prompt templates, not random metric noise.

## Evidence

| Source | Locator | Evidence |
| --- | --- | --- |
| `run_example_negative_001` | `metrics.json:quality_retention` | Quality retention dropped after reuse was enabled. |
| `problem_example_cache_template_mismatch` | `final_solution` | The previous fix was prompt-template hash validation. |
| `paper_example_cache_001` | `section:Safety Discussion` | The synthetic paper recommends validating compatibility before reuse. |

## Reasoning

The run changed cache reuse behavior, the symptom matches a prior failure case, and the cited paper-memory example points to the same compatibility risk.

## Recommended Action

1. Add prompt-template hash validation before cache reuse.
2. Re-run the smoke benchmark with reuse enabled.
3. Compare `quality_retention`, `latency_ms`, and `peak_memory_mb`.

## Missing Context

- No real multi-tenant leakage test has been recorded.
- The current optimizer and decoding configuration are not attached to this synthetic example.

## Confidence

0.84
