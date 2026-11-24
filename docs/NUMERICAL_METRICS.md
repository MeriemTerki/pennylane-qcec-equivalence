# Numerical metrics

These metrics score the same two circuits that QCEC compares: the gold circuit and the model circuit, after both have been exported to Qiskit.

Each metric is a number. A fixed cutoff turns that number into **equivalent** or **not equivalent**, so the decision can sit next to the QCEC decision.

Definitions and cutoffs are implemented in `metrex_like/equivalence_metrics.py`.

## The numbers

Let \(U_1\) and \(U_2\) be the two unitaries, and \(d = 2^n\).

| Name in the JSON | What is computed | Equivalent when | Direction |
|---|---|---|---|
| `process_fidelity` | \(F = \lvert \mathrm{Tr}(U_1^\dagger U_2) \rvert^2 / d^2\) | \(F \ge 1 - 10^{-8}\) | closer to **1** means more alike |
| `process_fidelity_strict` (stored as `process_fidelity_manjushri_tol`) | the same \(F\) | \(F \ge 1 - 10^{-15}\) | same number, stricter cutoff |
| `hilbert_schmidt_residual` | \(1 - F\) | value \(\le 10^{-8}\) | closer to **0** means more alike |
| `pauli_miter_l2_residual` | Write \(U_2^\dagger U_1\) in the Pauli basis. The residual is the Euclidean size of every coefficient except the identity | residual \(\le 10^{-10}\) | closer to **0** |
| `pauli_generator_max_rG_2n` | For every one-qubit \(X\) and \(Z\), compare how the two circuits conjugate that operator. Report the **largest** difference | largest \(\le 10^{-10}\) | closer to **0** |
| `pauli_generator_l2_residual_X` | The same difference for **only** \(X\) on qubit 0 | value \(\le 10^{-10}\) | closer to **0**, but a small value is not enough |
| `min_basis_state_fidelity` | Fidelity of the two output states, worst case over computational-basis inputs (or 32 random states if the circuit is wide) | value \(\ge 1 - 10^{-8}\) | closer to **1** |

Global phase is ignored for process fidelity: two circuits that differ only by a global phase still have \(F = 1\).

## Which decisions are trustworthy here

On the 302 gpt-4o-mini pairs where every formula ran:

- process fidelity, \(1-F\), the Pauli miter, the **largest** generator residual, and basis-state fidelity agree with QCEC on 99.7–100% of pairs
- the single \(X\) on qubit 0 agrees only about 83% of the time, and it labels extra pairs as equivalent

Use the full set of generators, or the fidelity / miter residual. Do not use one generator as the equivalence test.

## Where a metric returns no decision

The JSON field is `null` when the circuits have different widths, the unitary cannot be built, or the circuit is too wide for a dense Pauli expansion (miter residual stops above 14 qubits; the generator sweep stops above 12). The kept corpus is capped at 12 qubits, so the usual cause of a skip is a failed unitary build, not the cap.

QCEC does not have that skip. That is why QCEC has a decision on all 377 extracted pairs and the numerical columns have 75 gaps.

## Output files

`results/pennysynth_full/equiv_metrics_mini.jsonl` — one sample per line:

- `qcec.decision`: `equivalent` or `not_equivalent`
- `metrics`: the floats
- `metric_labels`: `true` if that cutoff says equivalent, `false` if not, `null` if not computed

`equiv_metrics_mini_summary.json` — counts, agreement with QCEC, and mean values split by the QCEC label.

Side-by-side counts: [SIDE_BY_SIDE_EQUIVALENCE.md](SIDE_BY_SIDE_EQUIVALENCE.md).
