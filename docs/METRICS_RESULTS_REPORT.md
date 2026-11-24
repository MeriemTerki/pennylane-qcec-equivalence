# How to read the metric results

This page is the short version of [SIDE_BY_SIDE_EQUIVALENCE.md](SIDE_BY_SIDE_EQUIVALENCE.md) and [NUMERICAL_METRICS.md](NUMERICAL_METRICS.md).

**Data:** 444 kept PennySynth programs, gpt-4o-mini model code.

## Files

| File | What it is |
|---|---|
| `results/pennysynth_full/loop_openrouter_v2.jsonl` | QCEC only, current extractor |
| `results/pennysynth_full/loop_openrouter_v2_summary.json` | 150 equivalent, 227 not equivalent, 67 extract failures |
| `results/pennysynth_full/equiv_metrics_mini.jsonl` | QCEC decision and every numerical metric, one sample per line |
| `results/pennysynth_full/equiv_metrics_mini_summary.json` | agreement with QCEC, and mean values split by the QCEC label |

## Pipeline

For each kept sample the gold program and the model program are turned into circuits. QCEC compares them. The same two circuits are then scored with fidelity and Pauli residuals. A cutoff on each number produces a second equivalent / not equivalent label.

## QCEC

- 377 / 444 pairs extracted
- **150** equivalent, **227** not equivalent
- 67 model programs did not become a circuit

## Metric labels versus QCEC

Among pairs where both QCEC and that metric returned a yes or no (302 pairs for the metrics that all ran):

| Metric | Same decision as QCEC |
|---|---:|
| Process fidelity | 99.7% |
| Process fidelity, cutoff \(10^{-15}\) | 100% |
| Pauli miter residual | 99.7% |
| Largest generator residual | 100% |
| Minimum basis-state fidelity | 99.7% |
| Hilbert–Schmidt residual | 99.7% |
| \(X\) on qubit 0 only | 83.4% |

## Means by QCEC label

| Metric | Mean when QCEC equivalent | Mean when QCEC not equivalent |
|---|---:|---:|
| Process fidelity | 1.00 | 0.47 |
| Pauli miter residual | 0.00 | 0.64 |
| Largest generator residual | 0.00 | 1.11 |
| Minimum basis-state fidelity | 1.00 | 0.51 |
| Hilbert–Schmidt residual | ~0 | 0.53 |

Fidelity near 1 and residual near 0 means the circuits match. The drop in fidelity and the rise in residual, when QCEC says not equivalent, is the numerical picture of a mismatch.

The \(X\)-on-qubit-0 residual is the exception: a value near 0 does not mean the circuits are equivalent.
