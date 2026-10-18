# Evaluation results

`gpt-5-mini` audits of the benchmark: 70 conversations, every mode scored on the same ones. Ground truth is the planted violations in `results/subsets/unseen.json`.

## Overall

| Method | Recall | 95% CI | Precision | 95% CI | F1 | Clean chats flagged | Near-miss false alarms | Finding cites the planted turn | Severity exact | Weighted κ | Quotes found in cited turn | Mean tool calls | Cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Full transcript | **80%** | 68%–91% | **38%** | 28%–48% | 0.52 | 60% of 25 | 0% of 13 | 97% | 91% | 0.46 | 100% of 110 | 0.0 | $0.31 |
| RAG (fixed queries) | **49%** | 33%–64% | **26%** | 16%–36% | 0.34 | 68% of 25 | 15% of 13 | 95% | 85% | 0.26 | 100% of 90 | 0.0 | $0.28 |
| Agentic RAG (tools) | **71%** | 57%–84% | **35%** | 25%–43% | 0.46 | 60% of 25 | 8% of 13 | 97% | 90% | 0.41 | 98% of 104 | 1.5 | $0.47 |

A baseline that never flags anything has 0% recall, no false alarms and κ 0.

## Recall and precision by category

| Category | Full transcript | RAG (fixed queries) | Agentic RAG (tools) |
|---|---|---|---|
| Personal and payment data | R 90% · P 38% (10 planted) | R 70% · P 37% (10 planted) | R 90% · P 36% (10 planted) |
| Identity verification | R 100% · P 21% (6 planted) | R 100% · P 16% (6 planted) | R 100% · P 19% (6 planted) |
| Commitments and claims | R 70% · P 47% (10 planted) | R 30% · P 33% (10 planted) | R 50% · P 45% (10 planted) |
| Complaints and escalation | R 57% · P 100% (7 planted) | R 29% · P 40% (7 planted) | R 57% · P 67% (7 planted) |
| Honesty and conduct | R 88% · P 47% (8 planted) | R 25% · P 33% (8 planted) | R 62% · P 45% (8 planted) |

## Recall by subtlety and severity

| Planted as | Full transcript | RAG (fixed queries) | Agentic RAG (tools) |
|---|---|---|---|
| obvious | 92% | 54% | 67% |
| subtle | 65% | 41% | 76% |
| minor | 77% | 46% | 77% |
| major | 91% | 55% | 64% |
| critical | 50% | 33% | 83% |

## Benchmark

- Plans: {'clean': 25, 'near_miss': 13, 'violations': 32}
- Planted items: {'near_miss:personal_data': 3, 'near_miss:verification': 3, 'near_miss:promises': 3, 'violation:conduct': 8, 'violation:promises': 10, 'violation:escalation': 7, 'violation:personal_data': 10, 'near_miss:escalation': 3, 'violation:verification': 6, 'near_miss:conduct': 1}
- Violation severities: {'major': 22, 'critical': 6, 'minor': 13}; subtlety: {'obvious': 24, 'subtle': 17}
- Generator: `groq/openai/gpt-oss-20b + qwen/qwen3.8-27b`, independently re-checked: True; generation stats {'generated': 89, 'rejected': 42, 'dropped': 12}

Unmodified chats may contain real policy slips, which count as false positives, so precision is a lower bound.
