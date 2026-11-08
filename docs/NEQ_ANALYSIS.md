# Not-equivalent cases: close mutant vs different circuit

QCEC-failed extracts only (`not_equivalent`). Extract failures ignored.

Compared gold vs model **gate lists** (name + wires; params rounded). Script: `analyze_neq.py`.

| Bucket | Meaning |
|---|---|
| **param_only** | Same gates on the same wires; angles differ |
| **near_mutant** | Same width; extra/missing/swap of about one gate, or a short reorder |
| **different_program** | Same width, skeleton not close |
| **different_width** | Different number of qubits |

`param_only` can mix true wrong angles with dummy-input artifacts (extractor feeds fixed numbers). Still the **skeleton matches**.

## Counts

| | mini (227) | gpt-4o (187) |
|---|---:|---:|
| param_only | 53 (23%) | 56 (30%) |
| near_mutant | 80 (35%) | 65 (35%) |
| **close (those two)** | **133 (59%)** | **121 (65%)** |
| different_program | 30 (13%) | 25 (13%) |
| different_width | 63 (28%) | 41 (22%) |
| same ops, QCEC disagree | 1 | 0 |

## Examples (mini)

- **param_only** `pennysynth_228`: both `H–CX–U3` on 3 qubits, U3 angles differ.
- **near_mutant** `pennysynth_253`: four `RY` vs four `RY` + extra `H`.
- **near_mutant** `pennysynth_1208`: `CX–RY–RX` vs `RY–RX–CX` (same gates, different order).
- **different_program** `pennysynth_750`: gold 16 ops vs model `H–CX–X` (model wrote the named gates once; gold is a longer program).
- **different_width** `pennysynth_733`: gold 1 qubit vs model 2 qubits + a layer.

## What this means

Most wrong-but-extractable answers are **almost the gold circuit**, not a different algorithm. Wrong **qubit count** is the main “different task” bucket.

So the next research step is **training / a tighter spec** (angles, width, don’t drop adjoints), not a harder checker. QCEC is already doing its job.
