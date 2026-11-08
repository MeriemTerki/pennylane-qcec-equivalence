# Why 124 model samples failed extract/export

Source: `filter_out/pennysynth_full/loop_openrouter.jsonl` (gpt-4o-mini vs kept gold).

## Split (before extractor fixes)

| Bucket | N | Whose problem? |
|---|---:|---|
| OpenQASM got an array param (`needed an expression, but instead saw [`) | 45 | **Extractor** — dummy args were numpy vectors; QASM cannot print `[0.2 0.4]` |
| No QNode after lift (class methods, helper-only snippets) | 14 | Mixed — often model wrapped QNode in `nn.Module` |
| Missing names (`circuit` / helpers not defined) | ~15 | **Model** — incomplete code |
| Stale APIs (`.inv()`, `.condition`, wrong kwargs) | ~10 | **Model** (we now rewrite `.inv()` → `qml.adjoint`) |
| Wrong PennyLane signatures / empty tape / other | rest | Mostly **model** |

## What we changed in `extract_circuit.py`

- Dummy arguments: prefer scalars / strings (`phi=0.5`, `filter="H"`) instead of arrays
- `_scalarize_tape`: force gate params to floats before `to_openqasm`
- `_modernize_pennylane`: `qml.T(...).inv()` → `qml.adjoint(qml.T)(...)`

Re-extract on the same 124 model programs recovered **57/124** at extract time.

Full QCEC rescore on all 444 (`loop_openrouter_v2.jsonl`, same predictions):

| | v1 | v2 (fixed extractor) |
|---|---:|---:|
| Equivalent | 124 | **150** (34%) |
| Not equivalent | 196 | 227 |
| Failed | 124 | **67** |
