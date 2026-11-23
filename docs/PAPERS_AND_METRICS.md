# Supervisor papers → equivalence metrics (formulas)

Your pipeline stays: **PennyLane → extract circuit → QCEC label** (MQT, your Yosys analogue).

Your supervisor’s new ask: on the **same pairs**, also compute the **numeric metrics** from the quantum equivalence papers and report results **next to QCEC** — not replace QCEC with another tool yet.

VeriThoughts (`2505.20302`) is the **Verilog / training** paper you started from; the other PDFs define **how to measure circuit equivalence**.

## Metric table (implemented in `equivalence_metrics.py`)

| Metric | Formula (short) | Paper | Threshold used | Equivalent when |
|---|---|---|---|---|
| **QCEC label** | MQT formal verify | QCEC / MPO line (`3q71-y8cf`) | tool verdict | `equivalent` |
| **process_fidelity** | \(\| \mathrm{Tr}(U_1^\dagger U_2) \|^2 / d^2\) | Unitary equiv (Manjushri Def.1; Qiskit) | \(1 - 10^{-8}\) | value ≥ threshold |
| **hilbert_schmidt_residual** | \(1 - F_{\mathrm{proc}}\) | Related to Xia miter distance | \(10^{-8}\) | value ≤ threshold |
| **pauli_miter_l2_residual** | \(r_M = \|\boldsymbol{\beta}_{\neq I}\|_2\) for \(M=U_2^\dagger U_1\) | **2611.15080** §3.2 | \(\varepsilon = 10^{-10}\) | \(r_M \le \varepsilon\) |
| **pauli_generator_l2_residual_X** | one \(r_G\) for \(G=X_0\) | **2611.15080** Eq. (12) | \(10^{-10}\) | \(r_G \le \varepsilon\) |
| **pauli_generator_max_rG_2n** | \(\max_{G \in \{X_i,Z_i\}} r_G\) | **2611.15080** (all \(2n\) generators) | \(10^{-10}\) | max \(r_G \le \varepsilon\) |
| **process_fidelity_manjushri_tol** | same \(F_{\mathrm{proc}}\), threshold \(1-10^{-15}\) | **2601.22372** | \(10^{-15}\) | value ≥ \(1-10^{-15}\) |
| **min_basis_state_fidelity** | \(\min_\psi F(|\psi\rangle, U_1, U_2)\) | Simulation-style (contrast to formal) | \(1 - 10^{-8}\) | value ≥ threshold |

**Not implemented as full engines** (need external tools or shallow-circuit assumptions):

- Manjushri WBDD local projections (`2601.22372`) — full \(r_G\) over all \(2n\) generators + 100s runs in Quasimodo  
- MPO contraction residual (`3q71-y8cf`, \(\varepsilon=10^{-13}\)) — same family as QCEC, different backend  
- Shallow local-projection constraints (`2504.01558`) — constant depth only  
- SWTAs (`2511.19897`) — parameterized families, not single fixed circuits  

Our **Pauli miter / generator metrics** are faithful **formula snapshots** on extracted unitaries, not a reimplementation of Xia’s sparse propagation engine.

## Latest full run (`equiv_metrics_mini_summary.json`, gpt-4o-mini preds)

| QCEC (377 extracted) | Count |
|---|---:|
| Equivalent | 150 |
| Not equivalent | 227 |

67 extract failures (same as before). **302** pairs had all metric thresholds computable.

| Metric (threshold label vs QCEC) | Agreement with QCEC |
|---|---:|
| **pauli_miter_l2_residual** (\(\le 10^{-10}\)) | **99.7%** |
| hilbert_schmidt_residual | **99.7%** |
| pauli_generator_l2_residual_X (one generator) | 83.4% |
| process_fidelity | 55.6% |
| min_basis_state_fidelity | 56.6% |

Mean **process_fidelity** over all 302: **0.71**. Pauli miter mean **0.35** (high residual ⇒ mostly QCEC-not-equiv pairs). Wall time ~5 min.

## How to run (same 444 as before)

From `metrex_like/`:

```powershell
python run_equivalence_metrics.py `
  --kept ..\results\pennysynth_full\kept.jsonl `
  --predictions ..\results\pennysynth_full\preds_openrouter.jsonl `
  --out ..\results\pennysynth_full\equiv_metrics_mini.jsonl
```

Outputs:

- **`equiv_metrics_mini.jsonl`** — per sample: `qcec`, `metrics` (floats), `metric_labels` (bool from thresholds), `metric_formulas`  
- **`equiv_metrics_mini_summary.json`** — QCEC counts + **agreement each metric vs QCEC** + mean/min/max of metrics  

Re-run QCEC-only loop (unchanged):

```powershell
python run_verithoughts_loop.py `
  --kept ..\results\pennysynth_full\kept.jsonl `
  --predictions ..\results\pennysynth_full\preds_openrouter.jsonl `
  --out ..\results\pennysynth_full\loop_openrouter_v2_rerun.jsonl
```

Should match `loop_openrouter_v2_summary.json` (150 eq / 227 neq / 67 fail).

## What to show your supervisor

One slide or table:

1. **QCEC** — equivalent / not / failed (your existing result).  
2. **Numeric columns** — e.g. mean `process_fidelity` on QCEC-equivalent vs not-equivalent pairs; fraction where `pauli_miter_l2_residual ≤ 10^{-10}` matches QCEC.  
3. **Honest scope** — Pauli metrics use dense Pauli expansion (works on kept corpus ≤12 qubits); Manjushri / full sparse checker = future if Quasimodo is built.

## Prior checker-comparison run (optional)

`run_checker_comparison.py` reports **completion rate** and **reference-consistent rate** (Pauli/Manjushri paper *evaluation* language).  
`run_equivalence_metrics.py` reports the **formula values** your supervisor asked for.