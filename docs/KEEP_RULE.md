# Keep rule

A PennySynth program is **kept** only when every step below succeeds. This rule is fixed for the results in this repository.

1. **Extract** a PennyLane QNode from the snippet. The extractor lifts the QNode from the syntax tree. It does not execute the whole file.
2. **Export** the circuit to OpenQASM, then to a Qiskit `QuantumCircuit`.
3. **Size.** At most 12 qubits and 200 operations.
4. **QCEC self-check.** `qcec.verify(C, C)` returns equivalent.

If any step fails, the program is **rejected**. Typical reasons: no QNode, empty tape, export error, too large, or the self-check fails.

## Recorded, but never used to reject

- **Mutant check.** Compare `C` with the same circuit plus an `X` on qubit 0. The flag `mutant_detected` may be true, false, or null.
- Errors on dynamic circuits or measurements during that mutant check do not reject the sample.

## Which data this rule was applied to

| Role | Data |
|---|---|
| Main corpus | PennySynth, output `results/pennysynth_full/kept.jsonl` (444 programs) |
| Not used in the reported scores | PennyLang pilot, QHack / QTestBench |

Rebuild from a local PennySynth file:

```powershell
cd metrex_like
python filter_corpus.py `
  --input path\to\pennylane_rag_enhanced.jsonl `
  --source pennysynth `
  --prefer-qnode `
  --skip-mutant `
  --out-dir ..\results\pennysynth_full
```

`--skip-mutant` only skips the optional flag. It does not change which programs are kept.
