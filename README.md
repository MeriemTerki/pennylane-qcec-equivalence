# PennyLane circuit equivalence

This repository checks whether two PennyLane programs implement the same quantum circuit.

The check has two layers:

1. **MQT QCEC**, a formal equivalence checker. It returns equivalent or not equivalent.
2. **Numerical metrics** computed from the two extracted unitaries (fidelity and Pauli residuals). Each metric is turned into the same kind of yes/no decision, so it can be compared with QCEC on the same pairs.

The data are lab PennySynth programs. A model is asked to rewrite each instruction in PennyLane. Gold code and model code are both turned into circuits, then compared.

---

## What was done

```text
PennySynth programs
        │
        ▼
Keep only programs we can turn into a small circuit
and that QCEC accepts as equivalent to themselves
        │
        ▼
444 kept programs
        │
        ├── Gold vs gold (pipeline check)          → QCEC
        ├── Model vs gold (gpt-4o-mini, gpt-4o)    → QCEC
        ├── Look at why extracts fail
        ├── Look at how far the non-equivalent circuits are
        └── Same model-vs-gold pairs               → numerical metrics
```

### 1. Build a checkable set

PennySynth has many programs that are not a single runnable circuit (training loops, missing QNodes, devices we cannot export).

A program is **kept** only if all of this works:

- a QNode can be lifted from the code
- the circuit exports to OpenQASM and Qiskit
- it has at most 12 qubits and 200 operations
- QCEC reports the circuit equivalent to itself

Details: [docs/KEEP_RULE.md](docs/KEEP_RULE.md), [docs/FILTER_PIPELINE.md](docs/FILTER_PIPELINE.md).

From 3416 QNode-looking PennySynth rows, **444 (13%)** were kept. The kept rows are `results/pennysynth_full/kept.jsonl`.

### 2. Check the pipeline on gold code

Each kept program is extracted twice and compared with QCEC (gold versus gold).

**441 / 444 (about 99%)** are equivalent. The extractor and QCEC agree on this filtered set. Three rows are not equivalent under this second pass; they are recorded in `loop_oracle.jsonl`.

### 3. Score model programs with QCEC

For each kept instruction, an OpenRouter model writes PennyLane. That code is extracted and compared with the gold circuit.

| Model | Equivalent | Not equivalent | Extract failed | Equivalent / 444 |
|---|---:|---:|---:|---:|
| gpt-4o-mini | 150 | 227 | 67 | **34%** |
| gpt-4o | 162 | 187 | 95 | **37%** |

Among pairs that both extract: mini **40%** equivalent (150/377), gpt-4o **46%** (162/349).

gpt-4o is only a small gain. It writes slightly more circuits that match gold, and more code that does not extract.

The current mini scores are `loop_openrouter_v2.jsonl`. An earlier extractor left 124 extract failures and 124 equivalents (28%). Fixes in `extract_circuit.py` (scalar parameters, `.inv()` rewritten to `qml.adjoint`) recovered circuits and moved the mini result to the table above. See [docs/FAIL_ANALYSIS.md](docs/FAIL_ANALYSIS.md).

### 4. What the non-equivalent circuits look like

On pairs QCEC calls not equivalent, gate lists were compared (names and wires, not a second checker).

| | gpt-4o-mini (227) | gpt-4o (187) |
|---|---:|---:|
| Same gates, different angles | 23% | 30% |
| About one extra, missing, or reordered gate | 35% | 35% |
| **Close to gold (those two)** | **59%** | **65%** |
| Same width, clearly different skeleton | 13% | 13% |
| Different number of qubits | 28% | 22% |

Most wrong answers are near the gold circuit: a wrong angle, one extra gate, or the wrong width. They are not a different algorithm. See [docs/NEQ_ANALYSIS.md](docs/NEQ_ANALYSIS.md).

### 5. Assess the same pairs with numerical metrics

On the **gpt-4o-mini** predictions, each extracted pair is scored again with numerical tests. QCEC is still computed on that run, so every row has both answers.

Full table and how to read a row: [docs/SIDE_BY_SIDE_EQUIVALENCE.md](docs/SIDE_BY_SIDE_EQUIVALENCE.md).  
What each number means: [docs/NUMERICAL_METRICS.md](docs/NUMERICAL_METRICS.md).

On **377** extracted pairs:

| Method | Equivalent | Not equivalent | No decision |
|---|---:|---:|---:|
| **QCEC** | **150** | **227** | 0 |
| Process fidelity | 139 | 163 | 75 |
| Process fidelity, stricter cutoff \(10^{-15}\) | 138 | 164 | 75 |
| Hilbert–Schmidt residual \(1 - F\) | 139 | 163 | 75 |
| Pauli miter residual | 139 | 163 | 75 |
| Largest Pauli-generator residual (all generators) | 138 | 164 | 75 |
| Minimum basis-state fidelity | 139 | 163 | 75 |
| Residual of a single \(X\) on qubit 0 | 188 | 114 | 75 |

The 75 “no decision” rows are pairs where the dense unitary or Pauli expansion did not run (width mismatch, or the circuit was too large for that calculation). QCEC still labeled them.

On the **302** pairs where every metric ran, process fidelity, the Pauli miter, the full generator residual, and basis-state fidelity agree with QCEC on **99.7–100%** of pairs.

Averages on those 302 pairs:

| | QCEC equivalent (138) | QCEC not equivalent (164) |
|---|---:|---:|
| Process fidelity (1 = same) | 1.00 | 0.47 |
| Pauli miter residual (0 = same) | 0.00 | 0.64 |
| Largest generator residual (0 = same) | 0.00 | 1.11 |

When QCEC says the circuits match, the numbers sit at a perfect match. When QCEC says they differ, fidelity drops to about one half and the residuals are clearly above zero.

**The single-generator residual cannot be used alone.** It calls 188 pairs equivalent, including pairs QCEC rejects, because one Pauli direction can match while the rest of the circuit does not.

---

## How to read the results

- **13% kept** means most PennySynth programs are not in a form this checker can use. The 444 are the working set.
- **99% gold versus gold** means the checker is reliable on that set. Low model scores are not a broken checker.
- **34–37% model equivalent** is the share of instructions whose model program matches the gold circuit under QCEC.
- **About 60% of the mismatches are close.** The model often has the right shape and misses an angle, a gate, or the qubit count.
- **Numerical metrics** are a second way to say equivalent or not. On circuits small enough to expand, they match QCEC, except the single-generator test.

---

## Repository layout

```text
README.md
requirements.txt
.env.example
metrex_like/                 code
  extract_circuit.py         PennyLane text → Qiskit circuit
  filter_corpus.py           keep / reject
  run_verithoughts_loop.py   QCEC on kept samples
  generate_openrouter.py     ask a model for PennyLane
  analyze_neq.py             close vs different circuits
  equivalence_metrics.py     numerical metrics
  run_equivalence_metrics.py QCEC + metrics on the same pairs
  circuits_lib.py            small hand-written demo circuits
  run_metrex_probe.py        demo: rewrite matches, mutant does not
docs/                        rules, analyses, metric definitions
results/pennysynth_full/     kept data and saved scores
```

Not included: API keys, the raw PennySynth dump, rejected programs, and earlier 100-row pilots.

---

## Setup

Python 3.11.

```powershell
git clone https://github.com/MeriemTerki/pennylane-qcec-equivalence.git
cd pennylane-qcec-equivalence
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

To generate new model code, copy `.env.example` to `metrex_like/.env` and set `OPENROUTER_API_KEY`. Do not commit `.env`.

Commands below are run from `metrex_like/`.

### Demo circuits

```powershell
python run_metrex_probe.py
```

### Rebuild the kept set

Requires a local copy of PennySynth `pennylane_rag_enhanced.jsonl`.

```powershell
python filter_corpus.py `
  --input path\to\pennylane_rag_enhanced.jsonl `
  --source pennysynth `
  --prefer-qnode `
  --skip-mutant `
  --out-dir ..\results\pennysynth_full
```

Expected: 444 kept.

### QCEC: gold versus gold

```powershell
python run_verithoughts_loop.py `
  --kept ..\results\pennysynth_full\kept.jsonl `
  --out ..\results\pennysynth_full\loop_oracle.jsonl
```

### QCEC: saved model programs

```powershell
python run_verithoughts_loop.py `
  --kept ..\results\pennysynth_full\kept.jsonl `
  --predictions ..\results\pennysynth_full\preds_openrouter.jsonl `
  --out ..\results\pennysynth_full\loop_openrouter_v2.jsonl
```

### QCEC and numerical metrics together

```powershell
python run_equivalence_metrics.py `
  --kept ..\results\pennysynth_full\kept.jsonl `
  --predictions ..\results\pennysynth_full\preds_openrouter.jsonl `
  --out ..\results\pennysynth_full\equiv_metrics_mini.jsonl
```

### New model programs

```powershell
python generate_openrouter.py `
  --kept ..\results\pennysynth_full\kept.jsonl `
  --out ..\results\pennysynth_full\preds_openrouter_NEW.jsonl `
  --limit 444 `
  --model openai/gpt-4o-mini `
  --resume
```

`--limit` defaults to 10.

---

## Saved outputs

Described in [results/pennysynth_full/README.md](results/pennysynth_full/README.md).

| File | Content |
|---|---|
| `kept.jsonl` | 444 checkable programs |
| `summary.json` | keep / reject counts |
| `loop_oracle_summary.json` | gold versus gold |
| `loop_openrouter_v2_summary.json` | gpt-4o-mini, current extractor |
| `loop_openrouter_gpt4o_summary.json` | gpt-4o |
| `equiv_metrics_mini.jsonl` | one row per sample: QCEC decision, metric values, metric decisions |
| `equiv_metrics_mini_summary.json` | agreement and averages |

---

## Data fields

| Field | Meaning |
|---|---|
| `id` | sample id, for example `pennysynth_130` |
| `instruction` | task text from PennySynth |
| `code` | gold PennyLane program |
| prediction row | `{id, model, instruction, code}` for the model program |

Upstream corpus: [PennySynth](https://github.com/eBrain4Everyone/PennySynth) (eBRAIN Lab, NYU Abu Dhabi). PennyLang was only a small pilot and is not part of these results.

Equivalence checking uses [MQT QCEC](https://github.com/cda-tum/qcec).
