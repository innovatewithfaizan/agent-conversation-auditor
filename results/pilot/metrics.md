# Evaluation results

`gpt-5-mini` audits of the benchmark: 10 conversations, every mode scored on the same ones. Ground truth is the planted violations in `results/pilot/manifest.json`.

## Overall

| Method | Recall | 95% CI | Precision | 95% CI | F1 | Clean chats flagged | Near-miss false alarms | Finding cites the planted turn | Severity exact | Weighted κ | Quotes found in cited turn | Mean tool calls | Cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Full transcript | **100%** | 100%–100% | **50%** | 25%–68% | 0.67 | 100% of 2 | 0% of 2 | 89% | 78% | 0.58 | 100% of 23 | 0.0 | $0.06 |
| RAG (fixed queries) | **67%** | 40%–100% | **40%** | 17%–55% | 0.50 | 100% of 2 | 0% of 2 | 83% | 83% | 0.38 | 100% of 20 | 0.0 | $0.05 |
| Agentic RAG (tools) | **67%** | 40%–100% | **38%** | 17%–50% | 0.48 | 100% of 2 | 0% of 2 | 83% | 100% | 0.47 | 100% of 17 | 1.6 | $0.08 |

A baseline that never flags anything has 0% recall, no false alarms and κ 0.

## Recall and precision by category

| Category | Full transcript | RAG (fixed queries) | Agentic RAG (tools) |
|---|---|---|---|
| Personal and payment data | R 100% · P 50% (2 planted) | R 50% · P 50% (2 planted) | R 50% · P 50% (2 planted) |
| Identity verification | R 100% · P 29% (2 planted) | R 100% · P 25% (2 planted) | R 100% · P 25% (2 planted) |
| Commitments and claims | R 100% · P 50% (2 planted) | R 50% · P 100% (2 planted) | R 50% · P 50% (2 planted) |
| Complaints and escalation | R 100% · P 100% (3 planted) | R 67% · P 67% (3 planted) | R 67% · P 67% (3 planted) |
| Honesty and conduct | R — · P — (0 planted) | R — · P 0% (0 planted) | R — · P 0% (0 planted) |

## Recall by subtlety and severity

| Planted as | Full transcript | RAG (fixed queries) | Agentic RAG (tools) |
|---|---|---|---|
| obvious | 100% | 67% | 67% |
| subtle | 100% | 67% | 67% |
| minor | 100% | 50% | 50% |
| major | 100% | 67% | 67% |
| critical | 100% | 100% | 100% |

## Benchmark

- Plans: {'near_miss': 2, 'clean': 2, 'violations': 6}
- Planted items: {'near_miss:conduct': 2, 'violation:verification': 2, 'violation:escalation': 3, 'violation:promises': 2, 'violation:personal_data': 2}
- Violation severities: {'major': 6, 'critical': 1, 'minor': 2}; subtlety: {'subtle': 6, 'obvious': 3}
- Generator: `groq/qwen/qwen3.8-27b`, independently re-checked: True; generation stats {'generated': 13, 'rejected': 6, 'dropped': 1}

Unmodified chats may contain real policy slips, which count as false positives, so precision is a lower bound.
