# Evaluation results

`gpt-5-mini` audits of the benchmark: 29 conversations, every mode scored on the same ones. Ground truth is the planted violations in `results/subsets/generator_qwen.json`.

## Overall

| Method | Recall | 95% CI | Precision | 95% CI | F1 | Clean chats flagged | Near-miss false alarms | Finding cites the planted turn | Severity exact | Weighted κ | Quotes found in cited turn | Mean tool calls | Cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Full transcript | **75%** | 58%–90% | **49%** | 35%–63% | 0.59 | 50% of 2 | 0% of 7 | 95% | 76% | 0.43 | 100% of 59 | 0.0 | $0.15 |
| RAG (fixed queries) | **50%** | 32%–68% | **40%** | 26%–55% | 0.44 | 100% of 2 | 14% of 7 | 93% | 79% | 0.24 | 100% of 41 | 0.0 | $0.13 |
| Agentic RAG (tools) | **68%** | 54%–83% | **45%** | 33%–59% | 0.54 | 100% of 2 | 0% of 7 | 89% | 89% | 0.47 | 96% of 55 | 1.5 | $0.22 |

A baseline that never flags anything has 0% recall, no false alarms and κ 0.

## Recall and precision by category

| Category | Full transcript | RAG (fixed queries) | Agentic RAG (tools) |
|---|---|---|---|
| Personal and payment data | R 88% · P 58% (8 planted) | R 50% · P 50% (8 planted) | R 75% · P 50% (8 planted) |
| Identity verification | R 100% · P 29% (4 planted) | R 100% · P 25% (4 planted) | R 100% · P 29% (4 planted) |
| Commitments and claims | R 50% · P 43% (6 planted) | R 33% · P 67% (6 planted) | R 33% · P 40% (6 planted) |
| Complaints and escalation | R 71% · P 100% (7 planted) | R 43% · P 60% (7 planted) | R 71% · P 71% (7 planted) |
| Honesty and conduct | R 67% · P 40% (3 planted) | R 33% · P 33% (3 planted) | R 67% · P 50% (3 planted) |

## Recall by subtlety and severity

| Planted as | Full transcript | RAG (fixed queries) | Agentic RAG (tools) |
|---|---|---|---|
| obvious | 91% | 64% | 73% |
| subtle | 65% | 41% | 65% |
| minor | 78% | 56% | 78% |
| major | 86% | 57% | 57% |
| critical | 40% | 20% | 80% |

## Benchmark

- Plans: {'near_miss': 7, 'clean': 2, 'violations': 20}
- Planted items: {'near_miss:personal_data': 1, 'near_miss:verification': 3, 'near_miss:conduct': 2, 'violation:conduct': 3, 'violation:promises': 6, 'violation:escalation': 7, 'violation:verification': 4, 'near_miss:promises': 1, 'violation:personal_data': 8}
- Violation severities: {'major': 14, 'critical': 5, 'minor': 9}; subtlety: {'subtle': 17, 'obvious': 11}
- Generator: `groq/openai/gpt-oss-20b + qwen/qwen3.8-27b`, independently re-checked: True; generation stats {'generated': 89, 'rejected': 42, 'dropped': 12}

Unmodified chats may contain real policy slips, which count as false positives, so precision is a lower bound.
