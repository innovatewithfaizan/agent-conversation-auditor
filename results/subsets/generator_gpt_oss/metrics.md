# Evaluation results

`gpt-5-mini` audits of the benchmark: 31 conversations, every mode scored on the same ones. Ground truth is the planted violations in `results/subsets/generator_gpt_oss.json`.

## Overall

| Method | Recall | 95% CI | Precision | 95% CI | F1 | Clean chats flagged | Near-miss false alarms | Finding cites the planted turn | Severity exact | Weighted κ | Quotes found in cited turn | Mean tool calls | Cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Full transcript | **95%** | 84%–100% | **51%** | 36%–67% | 0.67 | 40% of 5 | 0% of 8 | 95% | 100% | 0.65 | 100% of 47 | 0.0 | $0.14 |
| RAG (fixed queries) | **55%** | 33%–76% | **35%** | 21%–49% | 0.43 | 40% of 5 | 12% of 8 | 92% | 92% | 0.41 | 100% of 41 | 0.0 | $0.12 |
| Agentic RAG (tools) | **73%** | 52%–92% | **40%** | 28%–52% | 0.52 | 40% of 5 | 12% of 8 | 100% | 94% | 0.44 | 100% of 43 | 1.3 | $0.19 |

A baseline that never flags anything has 0% recall, no false alarms and κ 0.

## Recall and precision by category

| Category | Full transcript | RAG (fixed queries) | Agentic RAG (tools) |
|---|---|---|---|
| Personal and payment data | R 100% · P 44% (4 planted) | R 100% · P 57% (4 planted) | R 100% · P 44% (4 planted) |
| Identity verification | R 100% · P 31% (4 planted) | R 100% · P 24% (4 planted) | R 100% · P 24% (4 planted) |
| Commitments and claims | R 100% · P 55% (6 planted) | R 33% · P 40% (6 planted) | R 67% · P 67% (6 planted) |
| Complaints and escalation | R 67% · P 100% (3 planted) | R 33% · P 50% (3 planted) | R 33% · P 50% (3 planted) |
| Honesty and conduct | R 100% · P 83% (5 planted) | R 20% · P 33% (5 planted) | R 60% · P 50% (5 planted) |

## Recall by subtlety and severity

| Planted as | Full transcript | RAG (fixed queries) | Agentic RAG (tools) |
|---|---|---|---|
| obvious | 94% | 50% | 62% |
| subtle | 100% | 67% | 100% |
| minor | 83% | 33% | 67% |
| major | 100% | 57% | 71% |
| critical | 100% | 100% | 100% |

## Benchmark

- Plans: {'near_miss': 8, 'violations': 18, 'clean': 5}
- Planted items: {'near_miss:promises': 2, 'violation:conduct': 5, 'violation:personal_data': 4, 'near_miss:escalation': 3, 'violation:escalation': 3, 'violation:promises': 6, 'violation:verification': 4, 'near_miss:personal_data': 2, 'near_miss:conduct': 1}
- Violation severities: {'major': 14, 'minor': 6, 'critical': 2}; subtlety: {'obvious': 16, 'subtle': 6}
- Generator: `groq/openai/gpt-oss-20b + qwen/qwen3.8-27b`, independently re-checked: True; generation stats {'generated': 89, 'rejected': 42, 'dropped': 12}

Unmodified chats may contain real policy slips, which count as false positives, so precision is a lower bound.
