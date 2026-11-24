# How programs are filtered

Goal: keep PennySynth programs that can be compared as circuits.

The keep rule is in [KEEP_RULE.md](KEEP_RULE.md).

```text
raw PennySynth row
        │
        ▼
normalize instruction and code
        │
        ▼
lift a QNode and build a tape ──fail──► rejected
        │
        ▼
export OpenQASM / Qiskit ──fail──► rejected
        │
        ▼
size ≤ 12 qubits and ≤ 200 ops ──fail──► rejected
        │
        ▼
QCEC: circuit equals itself ──fail──► rejected
        │
        ▼
optional mutant flag (does not reject)
        │
        ▼
kept
```

## What the PennySynth run produced

Input: QNode-looking rows from `pennylane_rag_enhanced.jsonl` (a QNode decorator and `default.qubit` or `lightning.qubit`).

| | Count |
|---|---:|
| Candidates | 3416 |
| Kept | 444 |
| Rejected | 2972 |
| Checkable fraction | 13% |

Reject reasons:

| Reason | Count |
|---|---:|
| Tape or export failed | 1732 |
| No QNode after the lift | 890 |
| Truncated snippet | 261 |
| `while` loop (skipped; it can hang) | 66 |
| Unsupported device | 23 |

Counts are in `results/pennysynth_full/summary.json`.

## What a kept row contains

```json
{
  "id": "pennysynth_130",
  "source": "pennysynth",
  "instruction": "...",
  "code": "..."
}
```

`code` is the gold program. Later steps compare a model program with this gold circuit.

## What this filter is for

Every later number in this repository (QCEC model scores, numerical metrics, close-versus-different splits) uses **only** `kept.jsonl`. Programs that never become a circuit are not given an equivalence label.
