# Side-by-side equivalence: QCEC vs paper metrics

This is the comparison your supervisor asked for.

**Same pairs, same method as QCEC:** gold circuit vs model circuit (gpt-4o-mini, 444 kept samples).  
**QCEC** returns equivalent / not equivalent.  
**Each metric** uses a formula from the papers and a threshold, then returns the **same kind of answer**: equivalent or not equivalent.

Per-sample file (both answers on one line):

`results/pennysynth_full/equiv_metrics_mini.jsonl`

Look at:

- `qcec.decision` — MQT QCEC
- `metric_labels.<name>` — `true` means that metric says **equivalent**, `false` means **not equivalent**, `null` means **could not decide** (formula did not run)

---

## Headline counts (377 circuits both extracted)

| Method | Says equivalent | Says not equivalent | Could not decide | Usable as an equivalence checker? |
|---|---:|---:|---:|---|
| **MQT QCEC** | **150** | **227** | 0 | Yes — this is the reference |
| Process fidelity (threshold \(1-10^{-8}\)) | 139 | 163 | 75 | **Yes** — almost the same calls as QCEC |
| Manjushri tolerance (\(1-10^{-15}\)) | 138 | 164 | 75 | **Yes** — same story, slightly stricter |
| Hilbert–Schmidt residual \(1-F\) | 139 | 163 | 75 | **Yes** — same information as process fidelity |
| Pauli miter residual \(r_M\) (Xia, \(\varepsilon=10^{-10}\)) | 139 | 163 | 75 | **Yes** — tracks QCEC |
| Max generator residual over \(2n\) Paulis | 138 | 164 | 75 | **Yes** — tracks QCEC |
| **Only** \(X\) on qubit 0 | 188 | 114 | 75 | **No** — calls too many pairs equivalent |
| Min basis-state fidelity | 139 | 163 | 75 | **Yes on these small circuits** — same pattern as fidelity |

67 more rows never reached this table: the model code could not be turned into a circuit. That failure is the same for every method.

The **75 “could not decide”** rows are pairs where the formula code failed or skipped (for example width mismatch, or a circuit too wide for a dense Pauli expansion). QCEC still labeled those 75. So on the full 377, QCEC covers more pairs than the numeric formulas.

On the **302 pairs where every formula ran**, the usable metrics agree with QCEC about **99.7–100%** of the time (see `equiv_metrics_mini_summary.json`).

---

## How to read one sample

Example idea (real row `pennysynth_130`):

- QCEC: **not equivalent**
- Process fidelity / miter / max \(r_G\) / state fidelity: **not equivalent**
- Single \(X_0\) generator: **equivalent** ← this metric is wrong here

That is why the single-generator column is marked **not usable alone**.

---

## What “using the paper formula” means here

| Metric | Formula used as the equivalence test |
|---|---|
| Process fidelity | \(F=\lvert\mathrm{Tr}(U_1^\dagger U_2)\rvert^2/d^2\). Equivalent if \(F\) is essentially 1. |
| Manjushri column | Same \(F\), cutoff \(10^{-15}\) (paper 2601.22372). |
| Pauli miter \(r_M\) | Expand \(U_2^\dagger U_1\) in the Pauli basis; \(r_M\) is the size of every coefficient except identity. Equivalent if \(r_M\le 10^{-10}\) (paper 2611.15080). |
| Max \(r_G\) | For each generator \(X_i,Z_i\), compare how the two circuits conjugate it. Equivalent only if **every** generator matches within \(10^{-10}\). |
| Single \(X_0\) | Same formula on **one** generator only. A match does **not** prove the circuits are the same. |
| Basis fidelity | Compare output states on computational-basis inputs. Equivalent if the worst fidelity is essentially 1. |

These are **equivalence decisions**, not a second training score and not “how much the metric agrees” as the main result. Agreement is only how you **compare** those decisions to QCEC.

---

## What from the Papers folder is still not a column

| Paper | Why there is no extra column |
|---|---|
| VeriThoughts `2505.20302` | Verilog / pass@k, not a quantum circuit formula |
| Manjushri tool itself | We used their **tolerance on fidelity**, not their WBDD program |
| MPO paper `3q71-y8cf` | That method is the QCEC/MPO family; QCEC is already the column |
| Shallow circuits `2504.01558` | Needs constant-depth local projections, not these general circuits |
| Parameterized automata `2511.19897` | For infinite families of circuits, not one fixed pair |

---

## Practical conclusion

On your PennySynth pairs, **process fidelity, Pauli miter \(r_M\), and max \(r_G\) over all generators** can be used to assess equivalence the same way you used QCEC: they mostly give the same yes/no.

**One Pauli generator cannot.**

QCEC remains the one that finishes on more pairs (no 75 skips) and is the formal tool you already reported.

Numbers above were counted from `equiv_metrics_mini.jsonl` (377 extracted pairs).
