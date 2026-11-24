# QCEC and numerical metrics, side by side

Both columns answer the same question: **is the model circuit the same as the gold circuit?**

- QCEC answers with a formal check.
- Each numerical metric answers with a formula and a cutoff, defined in [NUMERICAL_METRICS.md](NUMERICAL_METRICS.md).

Data: the 444 kept PennySynth programs, model code from **gpt-4o-mini** (`preds_openrouter.jsonl`).

Per-sample file: `results/pennysynth_full/equiv_metrics_mini.jsonl`.

- `qcec.decision` — QCEC
- `metric_labels.<name>` — `true` = equivalent, `false` = not equivalent, `null` = not computed

## Counts on the 377 extracted pairs

| Method | Equivalent | Not equivalent | No decision | Use it as the equivalence test? |
|---|---:|---:|---:|---|
| **MQT QCEC** | **150** | **227** | 0 | Yes. This is the reference result |
| Process fidelity | 139 | 163 | 75 | Yes |
| Process fidelity, cutoff \(10^{-15}\) | 138 | 164 | 75 | Yes |
| Hilbert–Schmidt residual \(1-F\) | 139 | 163 | 75 | Yes. Same information as process fidelity |
| Pauli miter residual | 139 | 163 | 75 | Yes |
| Largest generator residual | 138 | 164 | 75 | Yes |
| Minimum basis-state fidelity | 139 | 163 | 75 | Yes, on these circuit sizes |
| Residual of \(X\) on qubit 0 only | 188 | 114 | 75 | No |

67 of the 444 rows never appear here: the model program did not become a circuit. Every method fails those rows the same way.

The 75 gaps are pairs QCEC still decided, but the dense calculation did not. On the **302** pairs where every metric exists, the usable metrics agree with QCEC on **99.7–100%** of pairs. The single \(X\) agrees on about **83%**.

## What the averages say

Restricted to those 302 pairs:

| | When QCEC says equivalent (138) | When QCEC says not equivalent (164) |
|---|---:|---:|
| Process fidelity | 1.00 | 0.47 |
| Pauli miter residual | 0.00 | 0.64 |
| Largest generator residual | 0.00 | 1.11 |
| Minimum basis-state fidelity | 1.00 | 0.51 |

A match under QCEC shows up as fidelity 1 and residual 0. A mismatch shows up as fidelity near 0.5 and a residual well above the cutoff \(10^{-10}\).

## One row, as an example

`pennysynth_130`:

- QCEC: **not equivalent**
- fidelity, miter, largest generator residual, basis fidelity: **not equivalent**
- \(X\) on qubit 0 only: **equivalent**

That last label is why one generator is not an equivalence test. The circuits can agree on a single Pauli and still differ.

## Interpretation

For this corpus, process fidelity, the Pauli miter, and the largest generator residual can be used **beside** QCEC. They make almost the same calls when they run.

They do not replace QCEC on the 75 pairs they skip.

The single-generator number should be reported only as a diagnostic, not as an equivalence result.
