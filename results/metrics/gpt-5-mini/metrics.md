# Evaluation results

`gpt-5-mini` audits of the benchmark: 80 conversations, every mode scored on the same ones. Ground truth is the planted violations in `data/benchmark/manifest.json`.

## Overall

| Method | Recall | 95% CI | Precision | 95% CI | F1 | Clean chats flagged | Near-miss false alarms | Finding cites the planted turn | Severity exact | Weighted κ | Quotes found in cited turn | Mean tool calls | Cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Full transcript | **84%** | 73%–93% | **40%** | 31%–50% | 0.55 | 63% of 27 | 0% of 15 | 95% | 88% | 0.48 | 100% of 133 | 0.0 | $0.37 |
| RAG (fixed queries) | **52%** | 39%–66% | **29%** | 20%–38% | 0.37 | 70% of 27 | 13% of 15 | 92% | 85% | 0.29 | 100% of 110 | 0.0 | $0.32 |
| Agentic RAG (tools) | **70%** | 58%–82% | **35%** | 27%–43% | 0.47 | 63% of 27 | 7% of 15 | 94% | 91% | 0.42 | 98% of 121 | 1.5 | $0.55 |

A baseline that never flags anything has 0% recall, no false alarms and κ 0.

## Recall and precision by category

| Category | Full transcript | RAG (fixed queries) | Agentic RAG (tools) |
|---|---|---|---|
| Personal and payment data | R 92% · P 39% (12 planted) | R 67% · P 38% (12 planted) | R 83% · P 37% (12 planted) |
| Identity verification | R 100% · P 23% (8 planted) | R 100% · P 18% (8 planted) | R 100% · P 21% (8 planted) |
| Commitments and claims | R 75% · P 47% (12 planted) | R 33% · P 40% (12 planted) | R 50% · P 46% (12 planted) |
| Complaints and escalation | R 70% · P 100% (10 planted) | R 40% · P 50% (10 planted) | R 60% · P 67% (10 planted) |
| Honesty and conduct | R 88% · P 47% (8 planted) | R 25% · P 29% (8 planted) | R 62% · P 42% (8 planted) |

## Recall by subtlety and severity

| Planted as | Full transcript | RAG (fixed queries) | Agentic RAG (tools) |
|---|---|---|---|
| obvious | 93% | 56% | 67% |
| subtle | 74% | 48% | 74% |
| minor | 80% | 47% | 73% |
| major | 93% | 57% | 64% |
| critical | 57% | 43% | 86% |

## Benchmark

- Plans: {'clean': 27, 'near_miss': 15, 'violations': 38}
- Planted items: {'near_miss:personal_data': 3, 'near_miss:verification': 3, 'near_miss:conduct': 3, 'near_miss:promises': 3, 'violation:conduct': 8, 'violation:promises': 12, 'violation:escalation': 10, 'violation:verification': 8, 'violation:personal_data': 12, 'near_miss:escalation': 3}
- Violation severities: {'major': 28, 'critical': 7, 'minor': 15}; subtlety: {'obvious': 27, 'subtle': 23}
- Generator: `groq/openai/gpt-oss-20b + qwen/qwen3.8-27b`, independently re-checked: True; generation stats {'generated': 89, 'rejected': 42, 'dropped': 12}

Unmodified chats may contain real policy slips, which count as false positives, so precision is a lower bound.
