# When QCEC says not equivalent, how different is the circuit?

This note covers only pairs that **both extracted** and that QCEC labeled **not equivalent**. Extract failures are excluded.

Gold and model circuits are compared by gate name and qubit index. Parameters are rounded. Script: `metrex_like/analyze_neq.py`.

| Bucket | Meaning |
|---|---|
| Same skeleton, different angles | Same gates on the same wires; numbers differ |
| Near change | Same width; about one extra, missing, or reordered gate |
| Different program | Same width, gate pattern not close |
| Different width | Different number of qubits |

Angle differences can include cases where the extractor filled a parameter with a fixed dummy value. The gate skeleton still matches.

## Counts

| | gpt-4o-mini (227) | gpt-4o (187) |
|---|---:|---:|
| Same skeleton, different angles | 53 (23%) | 56 (30%) |
| Near change | 80 (35%) | 65 (35%) |
| **Close (those two together)** | **133 (59%)** | **121 (65%)** |
| Different program | 30 (13%) | 25 (13%) |
| Different width | 63 (28%) | 41 (22%) |
| Same operations, QCEC still disagrees | 1 | 0 |

## Examples (gpt-4o-mini)

- **Angles.** `pennysynth_228`: both circuits are `H`, `CX`, `U3` on 3 qubits. The `U3` angles differ.
- **Near change.** `pennysynth_253`: four `RY` gates versus those four plus an `H`.
- **Near change.** `pennysynth_1208`: `CX–RY–RX` versus `RY–RX–CX`.
- **Different program.** `pennysynth_750`: gold has 16 operations; the model wrote `H`, `CX`, `X` once.
- **Different width.** `pennysynth_733`: gold uses 1 qubit; the model uses 2.

## Interpretation

When the model is wrong but the code still runs, it is usually **close to the gold circuit**. The largest “different task” group is the wrong number of qubits.

QCEC is separating those cases correctly. The gap is in the generated program (angle, one gate, or width), not in the checker failing to notice a match.
