# Quantum circuit equivalence for a VeriThoughts-style study

This repository is the **first stage** of adapting [VeriThoughts](https://arxiv.org/abs/2505.20302) (formal verification + LLMs for Verilog) to **PennyLane quantum programs**.

It answers the question: *can [MQT QCEC](https://github.com/cda-tum/qcec) play the role of Yosys, and can we build a MetRex-like set of checkable circuits from lab data?*

It does **not** reproduce the full VeriThoughts data-generation and training pipeline. That distinction is important if you are comparing numbers to the paper.

| VeriThoughts | This repo |
|---|---|
| MetRex (synthesizable Verilog) | Filtered PennyLane QNodes (`results/pennysynth_full/kept.jsonl`, **444** samples) |
| Yosys equivalence | **MQT QCEC** on extracted Qiskit circuits |
| Generate question \(Q\) from gold \(V\) | **Not done** — we reused existing PennySynth instructions |
| Reasoning trace \(R\) + new code \(V^*\) | Off-the-shelf OpenRouter models; **no CoT stored** |
| Label \(L_C = E(V, V^*)\) | Yes: QCEC(gold circuit, model circuit) |
| Train on \(\{V, Q, R, V^*, L_C\}\) | **Not done** |

**Affiliation:** eBRAIN Lab, NYU Abu Dhabi.

---

## What we implemented

```text
PennySynth JSONL
        │
        ▼
  extract QNode → OpenQASM / Qiskit → QCEC self-check (C ≡ C)
        │
        ├── reject  (not checkable)
        └── keep    (444 programs)     ← MetRex analogue
                │
                ├── oracle:  QCEC(gold, gold)     ~99% equivalent
                └── models:  QCEC(gold, model)    labeled equivalent / not / failed
```

1. **Keep rule (frozen).** A sample is kept only if we can extract a circuit, export it, stay within size limits (≤12 qubits, ≤200 ops), and QCEC reports the circuit equivalent to itself. Mutant checks are flags only; they never reject a sample. Details: [`docs/KEEP_RULE.md`](docs/KEEP_RULE.md).
2. **Oracle loop.** On the kept set, gold code is compared to itself through extract → QCEC. This tests the pipeline, not a model.
3. **Model scoring (optional eval, not the paper).** An LLM writes PennyLane from the **existing** instruction; we extract its circuit and compare it to the gold circuit with QCEC.
4. **Error analysis.** Failed extracts vs not-equivalent circuits; among not-equivalent, close mutants vs different programs.

QHack / QTestBench is **out of this repo**. It is a later evaluation set, not the training-style corpus.

---

## Main results

### Checkable fraction (PennySynth)

Source: lab [PennySynth](https://github.com/eBrain4Everyone/PennySynth) (`pennylane_rag_enhanced.jsonl`). We first keep QNode-looking rows (`@qml.qnode` + `default.qubit` / `lightning.qubit`).

| | Count |
|---|---:|
| QNode-looking candidates | 3416 |
| **Kept (QCEC-checkable)** | **444** |
| **Checkable fraction** | **13%** |

Reject reasons (among 2972): tape/export failed 1732, no QNode after lift 890, truncated 261, `while` 66, unsupported device 23. Full counts: `results/pennysynth_full/summary.json`.

PennyLang was only a 100-sample pilot (~7% kept) and is **not** the main corpus.

### Oracle (gold vs gold)

On all 444 kept samples: **441 / 444 equivalent (~99%)**. Extract + QCEC works on this filtered set.

### Off-the-shelf models vs gold (same 444, current extractor)

These are **not** VeriThoughts scores. Questions were not generated from gold; traces were not saved; no model was trained.

| Candidate | Equivalent | Not equivalent | Extract failed | Rate |
|---|---:|---:|---:|---:|
| `openai/gpt-4o-mini` | 150 | 227 | 67 | **34%** |
| `openai/gpt-4o` | 162 | 187 | 95 | **37%** |

Among circuits we could extract: mini 40% equivalent (150/377), gpt-4o 46% (162/349).

**Not-equivalent split** (extract failures ignored). Most wrong programs are close to gold, not a different algorithm:

| | mini (227) | gpt-4o (187) |
|---|---:|---:|
| Same skeleton, different angles | 23% | 30% |
| ±1 gate / small reorder | 35% | 35% |
| **Close (those two)** | **59%** | **65%** |
| Same width, far skeleton | 13% | 13% |
| Wrong qubit count | 28% | 22% |

Write-ups: [`docs/FAIL_ANALYSIS.md`](docs/FAIL_ANALYSIS.md), [`docs/NEQ_ANALYSIS.md`](docs/NEQ_ANALYSIS.md). Meeting note: [`docs/STATUS.md`](docs/STATUS.md).

---

## Repository layout

```text
pennylane-qcec-equivalence/
  README.md
  requirements.txt
  .env.example                 # copy to metrex_like/.env; never commit .env
  metrex_like/                 # runnable code
    extract_circuit.py         # PennyLane snippet → Qiskit circuit
    filter_corpus.py           # keep / reject (MetRex analogue)
    run_verithoughts_loop.py   # QCEC labels on kept samples
    generate_openrouter.py     # optional LLM generation
    analyze_neq.py             # close-mutant vs different-circuit
    circuits_lib.py            # tiny hand-written QCEC demo circuits
    run_metrex_probe.py        # demo: rewrite ≡ , mutant ≢
  docs/                        # keep rule, pipeline, analyses
  results/pennysynth_full/     # kept corpus + scores (no API keys)
```

**Intentionally not in this repo**

- API keys (`.env`)
- Raw PennySynth / PennyLang dumps (large, lab-owned; we ship the **444 kept** rows)
- Rejected JSONL (~25k leftover programs)
- Pilot filter runs (100-sample slices)
- QHack notebook extraction and pairwise probes
- `__pycache__`

---

## Setup

Python 3.11 recommended.

```powershell
git clone <this-repo-url>
cd pennylane-qcec-equivalence
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Linux / macOS: `source .venv/bin/activate`.

Optional, only for model generation: copy `.env.example` to `metrex_like/.env` and set `OPENROUTER_API_KEY`. Do not commit `.env`.

---

## How to run

All commands below assume you are in `metrex_like/`.

### 1. Sanity check (no dataset)

Hand-written Bell / GHZ-style circuits: equivalent rewrite vs mutant.

```powershell
python run_metrex_probe.py
```

### 2. Rebuild the kept corpus from PennySynth

Point `--input` at your local copy of `pennylane_rag_enhanced.jsonl` (not in this repo).

```powershell
python filter_corpus.py `
  --input path\to\pennylane_rag_enhanced.jsonl `
  --source pennysynth `
  --prefer-qnode `
  --skip-mutant `
  --out-dir ..\results\pennysynth_full
```

`--skip-mutant` only skips the soft flag; it does not change keep/reject. Expected: **444** kept, ~13% of QNode-like rows. Pipeline notes: [`docs/FILTER_PIPELINE.md`](docs/FILTER_PIPELINE.md).

### 3. Oracle loop (gold vs gold)

```powershell
python run_verithoughts_loop.py `
  --kept ..\results\pennysynth_full\kept.jsonl `
  --out ..\results\pennysynth_full\loop_oracle.jsonl
```

### 4. Score saved model programs (no API)

```powershell
python run_verithoughts_loop.py `
  --kept ..\results\pennysynth_full\kept.jsonl `
  --predictions ..\results\pennysynth_full\preds_openrouter.jsonl `
  --out ..\results\pennysynth_full\loop_openrouter_v2.jsonl

python run_verithoughts_loop.py `
  --kept ..\results\pennysynth_full\kept.jsonl `
  --predictions ..\results\pennysynth_full\preds_openrouter_gpt4o.jsonl `
  --out ..\results\pennysynth_full\loop_openrouter_gpt4o.jsonl
```

### 5. Generate new predictions (needs OpenRouter key)

Writes a **new** file. Do not overwrite `preds_openrouter.jsonl` if you still want the mini baseline.

```powershell
python generate_openrouter.py `
  --kept ..\results\pennysynth_full\kept.jsonl `
  --out ..\results\pennysynth_full\preds_openrouter_NEW.jsonl `
  --limit 444 `
  --model openai/gpt-4o-mini `
  --resume
```

Default `--limit` is 10. Pass `--limit 444` for the full kept set.

### 6. Classify not-equivalent circuits

```powershell
python analyze_neq.py `
  --kept ..\results\pennysynth_full\kept.jsonl `
  --predictions ..\results\pennysynth_full\preds_openrouter.jsonl `
  --loop ..\results\pennysynth_full\loop_openrouter_v2.jsonl `
  --out ..\results\pennysynth_full\neq_mini.json `
  --tag gpt-4o-mini
```

---

## Data

| Field | Meaning |
|---|---|
| `id` | e.g. `pennysynth_130` |
| `instruction` | Natural-language task (from PennySynth, not regenerated) |
| `code` | Gold PennyLane program |
| Predictions JSONL | `{id, model, instruction, code}` |

Upstream data (not shipped here):

- [PennySynth](https://github.com/eBrain4Everyone/PennySynth)
- [PennyLang](https://github.com/eBrain4Everyone/Pennylang) (secondary)

---

## What a fair next step looks like (not in this repo yet)

To follow VeriThoughts **the same way** (and only then compare *methods*, not raw percentages):

1. Gold circuit \(V\) = a kept sample (already here).
2. Generate a new question \(Q\) **from** \(V\) (do not reuse the dataset instruction as if it were that \(Q\)).
3. A reasoning model produces \(R\) and new PennyLane \(V^*\).
4. \(L_C \leftarrow\) QCEC\((V, V^*)\).
5. Store \(\{V, Q, R, V^*, L_C\}\). Training / hold-out eval come after that.

Even then, numbers will differ from the paper (PennyLane vs Verilog, 444 vs ~20k, QCEC vs Yosys). The comparable object is the **pipeline shape**, not 34% vs their pass@k.

---

## References

- Pinckney, N. et al. *VeriThoughts: Enabling Automated Verilog Code Generation using Reasoning and Formal Verification.* arXiv:2505.20302.
- Abdelatty, M. et al. *MetRex* (synthesizable Verilog corpus used by VeriThoughts).
- Burgholzer, L. & Wille, R. *MQT QCEC* — quantum circuit equivalence checking.
- PennySynth / PennyLang — eBRAIN Lab, NYUAD.
