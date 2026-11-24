# Extract failures on model code

First full QCEC run of **gpt-4o-mini** on the 444 kept programs (`loop_openrouter.jsonl`):

| | Count |
|---|---:|
| Equivalent | 124 (28%) |
| Not equivalent | 196 |
| Extract or export failed | 124 |

## Why those 124 failed

| Cause | About | Where the fault was |
|---|---:|---|
| OpenQASM saw a numpy array (`[0.2 0.4]`) | 45 | Extractor dummy inputs |
| No QNode after the lift (class wrappers, helpers only) | 14 | Often the model |
| Names used but not defined | ~15 | Model, incomplete code |
| Old PennyLane calls (`.inv()`, bad kwargs) | ~10 | Model; `.inv()` is now rewritten |
| Other signature or empty-tape errors | rest | Mostly the model |

## Extractor changes

In `extract_circuit.py`:

- dummy arguments are scalars or strings (`phi=0.5`, `filter="H"`), not arrays
- gate parameters are forced to floats before OpenQASM export
- `qml.T(...).inv()` is rewritten to `qml.adjoint(qml.T)(...)`

The same 124 programs were extracted again: **57 / 124** then exported.

## Rescore of all 444 (same mini predictions)

| | Before | After |
|---|---:|---:|
| Equivalent | 124 | **150 (34%)** |
| Not equivalent | 196 | 227 |
| Failed | 124 | **67** |

File after the fix: `results/pennysynth_full/loop_openrouter_v2.jsonl`.

Most of the 57 recovered programs became **not equivalent**. The model had written a different circuit; the checker could finally see it. **26** became equivalent.

The remaining 67 failures are mostly code that still has no QNode, missing names, or a PennyLane call the extractor does not run. They are not a QCEC timeout.
