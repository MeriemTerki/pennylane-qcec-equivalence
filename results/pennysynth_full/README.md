# Saved run artifacts (PennySynth, 444 kept)

| File | What it is |
|---|---|
| `kept.jsonl` | Checkable corpus (444 samples) |
| `summary.json` | Keep / reject counts |
| `loop_oracle.jsonl` | Gold vs gold (QCEC self-check of the loop) |
| `preds_openrouter.jsonl` | `openai/gpt-4o-mini` programs |
| `loop_openrouter.jsonl` | Mini scores, first extractor |
| `loop_openrouter_v2.jsonl` | Mini scores, current extractor (**use this**) |
| `preds_openrouter_gpt4o.jsonl` | `openai/gpt-4o` programs |
| `loop_openrouter_gpt4o.jsonl` | gpt-4o scores, current extractor |
| `neq_mini.json` / `neq_gpt4o.json` | Close-mutant vs different-circuit split |

`*_summary.json` files are one-line totals for the matching `loop_*.jsonl`.
