# Frozen keep rule (do not change without noting it)

A sample is **kept** iff all of the following succeed:

1. **Extract** a PennyLane QNode / tape from the code snippet (AST-lifted QNode; no full-file exec)  
2. **Export** to OpenQASM → Qiskit `QuantumCircuit`  
3. **Size gate** (corpus default): ≤ 12 qubits and ≤ 200 ops (configurable; not a QCEC failure)  
4. **QCEC self-check**: `qcec.verify(C, C)` is equivalent  

A sample is **rejected** if any of those fail (no QNode, empty tape, export error, too large, QCEC self-fail).

## Explicitly soft (flag only, never hard-reject)

- **Mutant check** (`C` vs `C` with an X on qubit 0): store `mutant_detected` as `true` / `false` / `null`  
- Dynamic-circuit / measurement quirks may make the mutant check error; that does **not** reject the sample

## Corpus policy

| Use | Dataset |
|---|---|
| Main MetRex-like corpus | PennySynth `kept.jsonl` after this rule |
| Secondary / footnote | PennyLang filtered kept only |
| Evaluation later | QHack / QTestBench (not this filter) |

CLI that produces the frozen corpus:

```bash
cd Implementation
python equivalence_probe/metrex_like/filter_corpus.py \
  --input pennylane_rag_enhanced.jsonl \
  --source pennysynth \
  --prefer-qnode \
  --skip-mutant \
  --out-dir equivalence_probe/metrex_like/filter_out/pennysynth_full
```

`--skip-mutant` only omits the soft flag (faster). It does **not** change keep/reject.
