"""
Compute paper-style equivalence metrics + QCEC on the same circuit pairs.

Output per row: QCEC label + numeric metrics (see equivalence_metrics.py formulas).
Summary: agreement between metric-threshold labels and QCEC, plus distribution of metrics.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

from extract_circuit import extract_from_code
from equivalence_metrics import (
    TOL_MANJUSHRI,
    TOL_MPO_PRR,
    TOL_XIA_2611,
    compute_all_metrics,
)
from filter_corpus import is_equivalent, qcec_label


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def qcec_decision(ref_qc, cand_qc, timeout_s: float) -> dict:
    t0 = time.perf_counter()
    try:
        label = qcec_label(ref_qc, cand_qc, timeout_s=timeout_s)
    except Exception as exc:  # noqa: BLE001
        return {"decision": "error", "label": str(exc), "seconds": time.perf_counter() - t0}
    dt = time.perf_counter() - t0
    if label == "timeout":
        return {"decision": "timeout", "label": label, "seconds": dt}
    if is_equivalent(label):
        return {"decision": "equivalent", "label": label, "seconds": dt}
    if "not_equivalent" in label.lower():
        return {"decision": "not_equivalent", "label": label, "seconds": dt}
    return {"decision": "undecided", "label": label, "seconds": dt}


def summarize(rows: list[dict]) -> dict:
    ok = [r for r in rows if r.get("status") == "ok"]
    ref = "qcec"
    metric_names = [
        "process_fidelity",
        "process_fidelity_manjushri_tol",
        "pauli_miter_l2_residual",
        "pauli_generator_l2_residual_X",
        "pauli_generator_max_rG_2n",
        "min_basis_state_fidelity",
        "hilbert_schmidt_residual",
    ]
    out: dict = {
        "n_ok": len(ok),
        "n_total": len(rows),
        "extract_failed": len(rows) - len(ok),
        "thresholds": {
            "xia_pauli_epsilon": TOL_XIA_2611,
            "manjushri_notes": TOL_MANJUSHRI,
            "mpo_prr_notes": TOL_MPO_PRR,
        },
        "qcec_decisions": _counts(ok, ref, "decision"),
        "metric_vs_qcec": {},
        "metric_value_stats": {},
    }
    for m in metric_names:
        agree = tot = 0
        values: list[float] = []
        for r in ok:
            qd = r["qcec"]["decision"]
            if qd not in ("equivalent", "not_equivalent"):
                continue
            labeled = r.get("metric_labels", {}).get(m)
            val = r.get("metrics", {}).get(m)
            if labeled is None or val is None:
                continue
            tot += 1
            q_equiv = qd == "equivalent"
            if labeled == q_equiv:
                agree += 1
            values.append(float(val))
        out["metric_vs_qcec"][m] = {
            "comparable": tot,
            "agreement_with_qcec": (agree / tot) if tot else None,
        }
        if values:
            out["metric_value_stats"][m] = {
                "mean": statistics.fmean(values),
                "min": min(values),
                "max": max(values),
            }
        eq_vals, neq_vals = [], []
        for r in ok:
            if r["qcec"]["decision"] == "equivalent":
                v = r.get("metrics", {}).get(m)
                if v is not None:
                    eq_vals.append(float(v))
            elif r["qcec"]["decision"] == "not_equivalent":
                v = r.get("metrics", {}).get(m)
                if v is not None:
                    neq_vals.append(float(v))
        if eq_vals or neq_vals:
            out.setdefault("metric_by_qcec_group", {})[m] = {
                "when_qcec_equivalent_mean": statistics.fmean(eq_vals) if eq_vals else None,
                "when_qcec_not_equivalent_mean": statistics.fmean(neq_vals) if neq_vals else None,
                "n_eq": len(eq_vals),
                "n_neq": len(neq_vals),
            }
    return out


def _counts(rows: list[dict], key: str, sub: str) -> dict[str, int]:
    c: dict[str, int] = {}
    for r in rows:
        d = r[key][sub]
        c[d] = c.get(d, 0) + 1
    return c


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kept", type=str, required=True)
    parser.add_argument("--predictions", type=str, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--out", type=str, required=True)
    parser.add_argument("--summary-out", type=str, default=None)
    parser.add_argument("--qcec-timeout", type=float, default=15.0)
    args = parser.parse_args()

    kept = load_jsonl(Path(args.kept))
    kept = kept[args.offset : args.offset + args.limit if args.limit else None]
    preds: dict[str, str] = {}
    if args.predictions:
        for row in load_jsonl(Path(args.predictions)):
            if row.get("id") and row.get("code"):
                preds[str(row["id"])] = row["code"]

    results: list[dict] = []
    t0 = time.perf_counter()
    for i, row in enumerate(kept, 1):
        sid = str(row["id"])
        gold = row.get("code") or ""
        cand = preds.get(sid, gold)
        ref_qc, ref_err, ref_meta = extract_from_code(gold)
        if ref_qc is None:
            results.append({"id": sid, "status": "ref_extract_failed", "error": ref_err})
            continue
        cand_qc, cand_err, cand_meta = extract_from_code(cand)
        if cand_qc is None:
            results.append({"id": sid, "status": "cand_extract_failed", "error": cand_err})
            continue
        qcec = qcec_decision(ref_qc, cand_qc, args.qcec_timeout)
        bundle = compute_all_metrics(ref_qc, cand_qc)
        results.append(
            {
                "id": sid,
                "status": "ok",
                "qcec": qcec,
                "metrics": bundle.metrics,
                "metric_labels": bundle.labels_from_metrics,
                "metric_formulas": {d.name: d.formula_ref for d in bundle.details},
                "ref_meta": {k: ref_meta.get(k) for k in ("n_qubits", "n_ops")},
                "cand_meta": {k: cand_meta.get(k) for k in ("n_qubits", "n_ops")},
            }
        )
        if i % 25 == 0 or i == 1:
            print(f"[metrics] {i}/{len(kept)}", flush=True)

    summary = summarize(results)
    summary["wall_seconds"] = time.perf_counter() - t0

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for rec in results:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    summary_path = Path(args.summary_out) if args.summary_out else out.with_name(out.stem + "_summary.json")
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Wrote {out}")
    print(f"Wrote {summary_path}")

    if args.predictions and "preds_openrouter_gpt4o" in (args.predictions or ""):
        tag = "gpt-4o preds"
    elif args.predictions:
        tag = "gpt-4o-mini preds"
    else:
        tag = "oracle gold vs gold"
    report_py = Path(__file__).with_name("write_metrics_report.py")
    if report_py.exists():
        import subprocess
        import sys

        subprocess.check_call(
            [
                sys.executable,
                str(report_py),
                "--summary",
                str(summary_path),
                "--predictions-tag",
                tag,
            ]
        )


if __name__ == "__main__":
    main()