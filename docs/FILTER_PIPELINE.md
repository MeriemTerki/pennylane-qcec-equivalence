# Filter pipeline: PennyLang / PennySynth → MetRex-like corpus

Goal: keep only samples that can play the role of MetRex + Yosys in a VeriThoughts-style study.

**Keep rule is frozen** in [`KEEP_RULE.md`](KEEP_RULE.md): extract → export → QCEC self-check; mutant = flag only.

```text
raw sample
   │
   ▼
1. normalize fields (instruction / code)
   │
   ▼
2. execute / analyze code  ──fail──► rejected: import_or_exec
   │
   ▼
3. extract a circuit / tape ──fail──► rejected: no_circuit
   │
   ▼
4. export OpenQASM / Qiskit ──fail──► rejected: export_failed
   │
   ▼
5. QCEC self-check (C ≡ C) ──fail──► rejected: qcec_self_fail
   │
   ▼
6. optional mutant check   ──flag──► keep, record mutant_detected true/false/null
   ▼
kept: formally checkable sample
```

Mutant check is **informative only** (soft). Hard reject is reserved for extract/export/QCEC self-check failures.

## Step-by-step (what each step means)

### Step 0 — Get the data
Local copies in this project:
```text
Implementation/dataset.json                 # PennyLang (instruction, response)
Implementation/pennylane_rag_enhanced.jsonl # PennySynth-13K (instruction, output)
```

Upstream repos:
- PennyLang: https://github.com/eBrain4Everyone/Pennylang
- PennySynth: https://github.com/eBrain4Everyone/PennySynth

### Step 1 — Normalize
Each raw row becomes:
```json
{
  "id": "...",
  "source": "pennylang|pennysynth",
  "instruction": "...",
  "code": "..."
}
```
Field names differ across releases (`instruction`/`input`/`query`, `code`/`response`/`output`). The filter script maps them.

### Step 2 — Run / parse
- Prefer AST parse + safe exec of the code snippet in a sandbox namespace with `pennylane` imported as `qml`.
- If the snippet is not a full script (only a function body), wrap it.

### Step 3 — Extract a circuit
Try, in order:
1. find a returned `QuantumTape` / QNode tape
2. find `qml.prod` / explicit ops and build a tape
3. export with `qml.to_openqasm(...)`

If nothing circuit-like is found → **reject** (`no_circuit`).  
These rejects are expected and useful for the paper.

### Step 4 — Export
- PennyLane tape → OpenQASM (`measure_all=False`, `rotations=False`) when possible
- or convert to Qiskit `QuantumCircuit`

### Step 5 — QCEC self-check (required)
```text
qcec.verify(circuit, circuit)  → must be equivalent
```
This is the Yosys analogue of “this design is well-formed enough to check.”

### Step 6 — Mutant check (soft)
Apply one simple mutant (insert X on qubit 0), then record whether
`qcec.verify(circuit, mutant)` is `not_equivalent`. Do **not** hard-reject on
mutant failure (dynamic-circuit / measurement edge cases are common).

### Dataset quirks handled by the extractor
- **PennyLang (`dataset.json`)**: every `response` has **zero leading indentation**.
  The extractor runs a best-effort indent repair, then lifts nested `@qml.qnode`
  functions to module scope when needed.
- **PennySynth (`pennylane_rag_enhanced.jsonl`)**: usually well-formed scripts;
  main failures are empty/non-exportable tapes and missing QNodes.

## Outputs to save

| File | Content |
|---|---|
| `kept.jsonl` | samples that passed |
| `rejected.jsonl` | samples that failed + reason |
| `summary.json` | counts per reason, checkable fraction |

### Full PennySynth result (`--prefer-qnode`, no limit)

`filter_out/pennysynth_full/summary.json`:
```json
{
  "total": 3416,
  "kept": 444,
  "checkable_fraction_among_decided": 0.13,
  "reject_reasons": {
    "tape_or_export_failed": 1732,
    "no_qnode_found": 890,
    "truncated_snippet": 261,
    "unsupported_control_flow": 66,
    "unsupported_device": 23
  }
}
```

PennyLang pilot (100 QNode-like): **7%** kept — secondary only.

**Takeaway:** PennySynth QNode slice → **444 kept (13%)** is the working MetRex-like corpus.

## How this connects to VeriThoughts

| VeriThoughts | After this filter |
|---|---|
| MetRex synthesizable Verilog | `kept.jsonl` circuit programs |
| Yosys equivalence | QCEC on extracted circuits |
| Later: Q → R → V* | Later: Q → R → C* on kept samples only |

## What not to do

- Do not use unfiltered PennySynth/PennyLang as if every sample were QCEC-ready.
- Do not use QHack as the main training corpus (keep it for evaluation).
- Do not skip the reject log: the fail modes are part of the research story.
