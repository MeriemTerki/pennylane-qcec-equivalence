# Project status

This note matches the repository README. Use the README for commands and file paths.

## Done

1. Filtered PennySynth to programs that export to a circuit and pass a QCEC self-check: **444 / 3416 (13%)**.
2. Checked gold versus gold: **441 / 444** equivalent.
3. Scored gpt-4o-mini and gpt-4o against gold with QCEC: **34%** and **37%** equivalent.
4. Separated extract failures from real mismatches. After extractor fixes, mini extract failures fell from 124 to 67.
5. Classified mismatches: about **60%** are close to gold (angle, one gate, or order); the rest are a different skeleton or a different width.
6. Scored the same mini pairs with numerical metrics (fidelity and Pauli residuals) and compared each yes/no with QCEC.

## Result in one paragraph

The checker works on the kept set. Models match the gold circuit about one third of the time. When they miss, they are often close. On circuits the numerical formulas can expand, those formulas agree with QCEC, except a test that looks at only one Pauli generator.

## Not done

- Generating a new instruction from the gold circuit, then training a model on the equivalence labels.
- Running the numerical expansions on the gpt-4o predictions (QCEC scores for gpt-4o are already saved).

## Main files

| Question | File |
|---|---|
| What was run, and what did it show? | `README.md` |
| Which programs were kept? | `docs/KEEP_RULE.md`, `docs/FILTER_PIPELINE.md` |
| Why did model code fail to extract? | `docs/FAIL_ANALYSIS.md` |
| How wrong are the non-equivalent circuits? | `docs/NEQ_ANALYSIS.md` |
| What do the numbers mean? | `docs/NUMERICAL_METRICS.md` |
| QCEC next to each metric | `docs/SIDE_BY_SIDE_EQUIVALENCE.md` |
