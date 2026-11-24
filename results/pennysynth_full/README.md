# Saved results (PennySynth, 444 kept programs)

All later scores use `kept.jsonl`.

## Corpus and QCEC

| File | Content |
|---|---|
| `kept.jsonl` | 444 programs that passed the keep rule |
| `summary.json` | 3416 candidates, 444 kept, 2972 rejected, reject reasons |
| `loop_oracle.jsonl` | gold versus gold, one row per program |
| `loop_oracle_summary.json` | 441 equivalent, 3 not equivalent, 0 failed |
| `preds_openrouter.jsonl` | gpt-4o-mini programs |
| `loop_openrouter.jsonl` | mini scores **before** the extractor fix (124 equivalent, 124 failed) |
| `loop_openrouter_v2.jsonl` | mini scores **after** the fix — use this for QCEC |
| `loop_openrouter_v2_summary.json` | 150 equivalent, 227 not equivalent, 67 failed |
| `preds_openrouter_gpt4o.jsonl` | gpt-4o programs |
| `loop_openrouter_gpt4o.jsonl` | gpt-4o QCEC scores |
| `loop_openrouter_gpt4o_summary.json` | 162 equivalent, 187 not equivalent, 95 failed |
| `neq_mini.json`, `neq_gpt4o.json` | how far non-equivalent circuits are from gold |

## Numerical metrics (gpt-4o-mini only)

| File | Content |
|---|---|
| `equiv_metrics_mini.jsonl` | QCEC decision, metric values, and metric yes/no for each sample |
| `equiv_metrics_mini_summary.json` | agreement with QCEC and mean values |
| `equiv_metrics_test.jsonl` | five-row trial run; ignore for reported numbers |
| `checker_compare_mini.jsonl` | earlier three-checker timing run; the metric files above are the ones to cite |
| `loop_openrouter_v2_rerun_summary.json` | partial rerun summary; do not cite |

`*_summary.json` next to a `loop_*.jsonl` is the totals for that file.
