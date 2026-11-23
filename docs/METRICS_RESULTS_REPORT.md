# Equivalence results: QCEC + paper metrics (how to read this)

**Data:** PennySynth kept corpus, model = gpt-4o-mini preds.

## Where the files are

| File | What it contains |
|---|---|
| `results/pennysynth_full/loop_openrouter_v2.jsonl` | **QCEC only** (older script); each row: equivalent / not / extract fail |
| `results/pennysynth_full/loop_openrouter_v2_summary.json` | QCEC totals: **150** eq, **227** neq, **67** fail (444 total) |
| `results/pennysynth_full/equiv_metrics_mini.jsonl` | **QCEC + all numeric metrics** per sample (one JSON object per line) |
| `results/pennysynth_full/equiv_metrics_mini_summary.json` | Aggregates: agreement with QCEC, means, breakdown |
| This file | Plain-language interpretation |

## The pipeline in one sentence

For each kept sample: extract **gold** circuit and **model** circuit → ask **MQT QCEC** (formal yes/no) → compute **numbers** from paper formulas (fidelity, Pauli residuals) on the same two circuits.

## QCEC (your main checker)

- Rows scored: **377** / 444 (67 failed to extract model or gold)
- QCEC says **equivalent**: 150
- QCEC says **not equivalent**: 227

This is the result you already had. Metrics do **not** replace QCEC; they sit beside it.

## What each metric means (and how to read the value)

| Metric | Bigger or smaller is “more equivalent”? | If value means… |
|---|---|---|
| `process_fidelity` | **Closer to 1** = more alike | 1.0 = same unitary up to global phase; 0 = very different |
| `process_fidelity_manjushri_tol` | Same number as above; **stricter** rule (≥ 1 − 10⁻¹⁵) | Manjushri paper tolerance |
| `pauli_miter_l2_residual` | **Closer to 0** = more alike | Xia paper: miter residual r_M on U₂†U₁ |
| `pauli_generator_max_rG_2n` | **Closer to 0** = more alike | Max r_G over 2n Pauli generators (Xᵢ, Zᵢ) |
| `pauli_generator_l2_residual_X` | **Closer to 0** | Only one generator (X on qubit 0) — weak witness |
| `min_basis_state_fidelity` | **Closer to 1** | Simulation on basis/random states — weaker than QCEC |
| `hilbert_schmidt_residual` | **Closer to 0** | Same information as 1 − process_fidelity |

In `equiv_metrics_mini.jsonl`, each row has:

- `qcec.decision` → `equivalent` | `not_equivalent`
- `metrics` → floats
- `metric_labels` → `true` / `false` meaning “this metric would call it equivalent” at the paper threshold

## Do the paper metrics agree with QCEC?

(Among pairs where QCEC and the metric both returned equiv or not-equiv.)

- **process_fidelity**: 99.7% agree with QCEC (302 pairs)
- **process_fidelity_manjushri_tol**: 100.0% agree with QCEC (302 pairs)
- **pauli_miter_l2_residual**: 99.7% agree with QCEC (302 pairs)
- **pauli_generator_l2_residual_X**: 83.4% agree with QCEC (302 pairs)
- **pauli_generator_max_rG_2n**: 100.0% agree with QCEC (302 pairs)
- **min_basis_state_fidelity**: 99.7% agree with QCEC (302 pairs)
- **hilbert_schmidt_residual**: 99.7% agree with QCEC (302 pairs)

**How to interpret agreement:**

- **High agreement** (e.g. Pauli miter ~99%): the formula track formal equivalence well on this corpus.
- **Lower agreement** on `pauli_generator_l2_residual_X` only (~83%): one Pauli generator is a weak witness; **`pauli_generator_max_rG_2n` matches QCEC 100%** on comparable pairs.

## Average metric values when QCEC says equivalent vs not

- **process_fidelity**: mean = 0.9999999999999996 when QCEC=eq (n=138); mean = 0.47001387544627893 when QCEC=neq (n=164)
- **process_fidelity_manjushri_tol**: mean = 0.9999999999999996 when QCEC=eq (n=138); mean = 0.47001387544627893 when QCEC=neq (n=164)
- **pauli_miter_l2_residual**: mean = 0.0 when QCEC=eq (n=138); mean = 0.6437429224220703 when QCEC=neq (n=164)
- **pauli_generator_l2_residual_X**: mean = 0.0 when QCEC=eq (n=138); mean = 0.6039210973765075 when QCEC=neq (n=164)
- **pauli_generator_max_rG_2n**: mean = 0.0 when QCEC=eq (n=138); mean = 1.1137175939608315 when QCEC=neq (n=164)
- **min_basis_state_fidelity**: mean = 0.9999999999999996 when QCEC=eq (n=138); mean = 0.5067468802286909 when QCEC=neq (n=164)
- **hilbert_schmidt_residual**: mean = 3.314578885112786e-16 when QCEC=eq (n=138); mean = 0.5299861245537211 when QCEC=neq (n=164)

You should see **high fidelity / low Pauli residual** when QCEC=equivalent, and **lower fidelity / higher residual** when QCEC=not_equivalent.

## What is *not* in this report

- Full Manjushri WBDD tool, sparse Pauli engine from Xia’s paper, MPO residual as a separate number, VeriThoughts training metrics.
- Those need extra tools or different data; see `PAPERS_AND_METRICS.md`.

*Generated from ../results/pennysynth_full/equiv_metrics_mini_summary.json*