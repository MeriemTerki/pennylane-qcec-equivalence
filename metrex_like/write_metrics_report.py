"""Write docs/METRICS_RESULTS_REPORT.md from equiv_metrics summary + JSONL."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", type=str, required=True)
    parser.add_argument("--out", type=str, default="../docs/METRICS_RESULTS_REPORT.md")
    parser.add_argument("--predictions-tag", type=str, default="gpt-4o-mini preds")
    args = parser.parse_args()

    s = json.loads(Path(args.summary).read_text(encoding="utf-8"))
    lines = [
        "# Equivalence results: QCEC + paper metrics (how to read this)",
        "",
        f"**Data:** PennySynth kept corpus, model = {args.predictions_tag}.",
        "",
        "## Where the files are",
        "",
        "| File | What it contains |",
        "|---|---|",
        "| `results/pennysynth_full/loop_openrouter_v2.jsonl` | **QCEC only** (older script); each row: equivalent / not / extract fail |",
        "| `results/pennysynth_full/loop_openrouter_v2_summary.json` | QCEC totals: **150** eq, **227** neq, **67** fail (444 total) |",
        "| `results/pennysynth_full/equiv_metrics_mini.jsonl` | **QCEC + all numeric metrics** per sample (one JSON object per line) |",
        "| `results/pennysynth_full/equiv_metrics_mini_summary.json` | Aggregates: agreement with QCEC, means, breakdown |",
        "| This file | Plain-language interpretation |",
        "",
        "## The pipeline in one sentence",
        "",
        "For each kept sample: extract **gold** circuit and **model** circuit → ask **MQT QCEC** (formal yes/no) → compute **numbers** from paper formulas (fidelity, Pauli residuals) on the same two circuits.",
        "",
        "## QCEC (your main checker)",
        "",
        f"- Rows scored: **{s.get('n_ok')}** / {s.get('n_total')} ({s.get('extract_failed')} failed to extract model or gold)",
        f"- QCEC says **equivalent**: {s.get('qcec_decisions', {}).get('equivalent', '?')}",
        f"- QCEC says **not equivalent**: {s.get('qcec_decisions', {}).get('not_equivalent', '?')}",
        "",
        "This is the result you already had. Metrics do **not** replace QCEC; they sit beside it.",
        "",
        "## What each metric means (and how to read the value)",
        "",
        "| Metric | Bigger or smaller is “more equivalent”? | If value means… |",
        "|---|---|---|",
        "| `process_fidelity` | **Closer to 1** = more alike | 1.0 = same unitary up to global phase; 0 = very different |",
        "| `process_fidelity_manjushri_tol` | Same number as above; **stricter** rule (≥ 1 − 10⁻¹⁵) | Manjushri paper tolerance |",
        "| `pauli_miter_l2_residual` | **Closer to 0** = more alike | Xia paper: miter residual r_M on U₂†U₁ |",
        "| `pauli_generator_max_rG_2n` | **Closer to 0** = more alike | Max r_G over 2n Pauli generators (Xᵢ, Zᵢ) |",
        "| `pauli_generator_l2_residual_X` | **Closer to 0** | Only one generator (X on qubit 0) — weak witness |",
        "| `min_basis_state_fidelity` | **Closer to 1** | Simulation on basis/random states — weaker than QCEC |",
        "| `hilbert_schmidt_residual` | **Closer to 0** | Same information as 1 − process_fidelity |",
        "",
        "In `equiv_metrics_mini.jsonl`, each row has:",
        "",
        "- `qcec.decision` → `equivalent` | `not_equivalent`",
        "- `metrics` → floats",
        "- `metric_labels` → `true` / `false` meaning “this metric would call it equivalent” at the paper threshold",
        "",
        "## Do the paper metrics agree with QCEC?",
        "",
        "(Among pairs where QCEC and the metric both returned equiv or not-equiv.)",
        "",
    ]
    for name, row in s.get("metric_vs_qcec", {}).items():
        pct = row.get("agreement_with_qcec")
        comp = row.get("comparable")
        if pct is not None:
            lines.append(f"- **{name}**: {pct * 100:.1f}% agree with QCEC ({comp} pairs)")
        else:
            lines.append(f"- **{name}**: n/a")
    lines.extend(
        [
            "",
            "**How to interpret agreement:**",
            "",
            "- **High agreement** (e.g. Pauli miter ~99%): the formula track formal equivalence well on this corpus.",
            "- **Lower agreement** on a single-generator witness (`pauli_generator_l2_residual_X`): one Pauli direction is not enough; use `pauli_generator_max_rG_2n` instead.",
            "- On undecided/failed extract rows, only QCEC or partial metrics apply — **trust QCEC** for the formal label when tools disagree.",
            "",
            "## Average metric values when QCEC says equivalent vs not",
            "",
        ]
    )
    for name, row in s.get("metric_by_qcec_group", {}).items():
        lines.append(
            f"- **{name}**: mean = {row.get('when_qcec_equivalent_mean')} when QCEC=eq (n={row.get('n_eq')}); "
            f"mean = {row.get('when_qcec_not_equivalent_mean')} when QCEC=neq (n={row.get('n_neq')})"
        )
    lines.extend(
        [
            "",
            "You should see **high fidelity / low Pauli residual** when QCEC=equivalent, and **lower fidelity / higher residual** when QCEC=not_equivalent.",
            "",
            "## What is *not* in this report",
            "",
            "- Full Manjushri WBDD tool, sparse Pauli engine from Xia’s paper, MPO residual as a separate number, VeriThoughts training metrics.",
            "- Those need extra tools or different data; see `PAPERS_AND_METRICS.md`.",
            "",
            f"*Generated from {Path(args.summary).as_posix()}*",
        ]
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()