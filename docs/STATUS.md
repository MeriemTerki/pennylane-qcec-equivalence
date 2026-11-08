# Meeting note (corpus + checker status)

Informal update for the eBRAIN / NYUAD discussion. The canonical explanation of what is (and is not) implemented is the repository `README.md`.

# Update for supervisor — quantum circuit equivalence setup

## Goal

Following your suggestion to explore **quantum circuit equivalence** first (Yosys analogue): I am adapting the VeriThoughts shape to quantum code.

| VeriThoughts | What I am using |
|---|---|
| MetRex (checkable Verilog) | Filtered PennyLane circuit programs |
| Yosys equivalence | **MQT QCEC** |
| Later: model writes code, checker labels it | Same plan, once the corpus + checker work |

QHack is **not** the main corpus here (better as later evaluation). Main source = lab **PennySynth** data; **PennyLang** is secondary.

---

## What I did

1. Took PennySynth (`pennylane_rag_enhanced.jsonl`) and kept only QNode-looking samples.
2. For each sample, tried to:
   - extract a circuit from the code  
   - export it (OpenQASM / Qiskit)  
   - run QCEC self-check: does the circuit equal itself?
3. **Kept** only samples where that full path works.  
   (Mutant checks are optional flags only — they do not decide keep/reject.)
4. Started a VeriThoughts-style loop on the kept set only (not on raw JSONL).

**Keep rule is frozen** in `KEEP_RULE.md`.

---

## Main result (PennySynth)

| | Number |
|---|---:|
| QNode-looking candidates | 3416 |
| **Kept (QCEC-checkable)** | **444** |
| **Checkable fraction** | **13%** |

Outputs: `filter_out/pennysynth_full/kept.jsonl`, `rejected.jsonl`, `summary.json`.

Most rejects are expected: cannot extract/export a circuit, missing QNode after cleanup, truncated code, etc.

**PennyLang footnote:** same idea on a 100-sample pilot → about **7%** kept (code is often fully dedented). Treating it as secondary, not the main corpus.

---

## Concrete example of a kept sample

Instruction: *apply an RY on one qubit and return the state.*

Gold code builds a 1-qubit QNode with `qml.RY(...)`.  
We extract that circuit, export it, and QCEC self-check returns **equivalent** → sample is kept.

That is the unit of data I will use as a reference (MetRex-like entry).

---

## Loop check (oracle baseline)

On all **444** kept samples, I compared gold code vs itself through the loop:

`instruction → code → circuit → QCEC`

Result: **441 / 444 equivalent (~99%)**.  
So the extract + QCEC pipeline is working on the filtered corpus.

Script: `run_verithoughts_loop.py`.

---

## Model run (OpenRouter `gpt-4o-mini` vs kept gold circuits)

Same loop, candidate = model code (not gold).

| Set | Equivalent | Not equivalent | Failed extract/export | Equivalent rate |
|---|---:|---:|---:|---:|
| 10 (pilot, mini) | 1 | 5 | 4 | 10% |
| 50 (mini) | 20 | 19 | 11 | 40% |
| 444 mini (first extractor) | 124 | 196 | 124 | 28% |
| **444 mini (after extractor fixes)** | **150** | **227** | **67** | **34%** |
| **444 `openai/gpt-4o` (same extractor)** | **162** | **187** | **95** | **37%** |

Same OpenRouter mini predictions; only `extract_circuit.py` changed between 28% and 34%. Failures dropped 124 → 67. Extra extracts mostly became **not equivalent** (model still wrote a different circuit), plus **+26 equivalent**.

`gpt-4o` on the same 444: slightly higher equivalence (**162 vs 150**), fewer wrong-but-extractable circuits (187 vs 227), but **more extract failures** (95 vs 67). Among circuits we could actually extract: mini **40%** equivalent (150/377), gpt-4o **46%** (162/349). Gold-vs-gold on the same 444 was ~99%. Details: `FAIL_ANALYSIS.md`.

**Not-equivalent split** (gate lists; extract fails ignored). Most wrong circuits are **close mutants**, not a different algorithm:

| | mini (227 neq) | gpt-4o (187 neq) |
|---|---:|---:|
| Same skeleton, wrong angles | 53 (23%) | 56 (30%) |
| ±1 gate / small reorder | 80 (35%) | 65 (35%) |
| **close (those two)** | **59%** | **65%** |
| Same width, far skeleton | 13% | 13% |
| Wrong qubit count | 28% | 22% |

Examples: `H–CX–U3` with different U3 angles; four `RY` plus an extra `H`; gold 1 qubit vs model 2. Write-up: `NEQ_ANALYSIS.md`.

Outputs: `preds_openrouter.jsonl` + `loop_openrouter_v2.jsonl` (mini); `preds_openrouter_gpt4o.jsonl` + `loop_openrouter_gpt4o.jsonl` (gpt-4o). Mini v1 scores still in `loop_openrouter.jsonl`.

## Proposed next step

Checker is fine. Models often write the **right shape** with a wrong angle, an extra gate, or the wrong width — so the natural next step is **training / a tighter spec on the kept 444**, not more OpenRouter models or extractor work. Decision for the meeting.

## OpenRouter path (local testing)

```powershell
# Put the key in Implementation/equivalence_probe/metrex_like/.env
# OPENROUTER_API_KEY=sk-or-...

cd Implementation
python equivalence_probe/metrex_like/generate_openrouter.py `
  --kept equivalence_probe/metrex_like/filter_out/pennysynth_full/kept.jsonl `
  --limit 10 --model openai/gpt-4o-mini --score
```

This writes model predictions, then scores them with QCEC vs the kept gold circuits.
