"""
Compare equivalence checkers on the same (gold, candidate) circuit pairs.

Paper-style aggregates (see docs/PAPERS_AND_METRICS.md):
  - completion_rate: decision not in {error, timeout, undecided} for unitary/sim methods
  - reference_consistent_rate: agreement with QCEC on equivalent / not_equivalent
  - mean_runtime_seconds per checker
  - disagreement counts (checker says equiv but QCEC says not, etc.)

QCEC is the reference oracle (like 'reference-consistent' in Xia et al. 2611.15080).
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from extract_circuit import extract_from_code
from equivalence_checkers import CheckerResult, run_all

DECIDED = frozenset({"equivalent", "not_equivalent"})


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def aggregate(rows: list[dict], checkers: list[str]) -> dict:
    ref = "qcec"
    out: dict = {"n_pairs": len(rows), "checkers": {}}
    for ch in checkers:
        decided = sum(1 for r in rows if r["checkers"].get(ch, {}).get("decision") in DECIDED)
        times = [r["checkers"][ch]["seconds"] for r in rows if ch in r["checkers"]]
        consist = 0
        comparable = 0
        for r in rows:
            qc = r["checkers"].get(ref, {})
            oc = r["checkers"].get(ch, {})
            if qc.get("decision") not in DECIDED or oc.get("decision") not in DECIDED:
                continue
            comparable += 1
            if qc["decision"] == oc["decision"]:
                consist += 1
        out["checkers"][ch] = {
            "completion_rate": (decided / len(rows)) if rows else None,
            "reference_consistent_rate_vs_qcec": (consist / comparable) if comparable else None,
            "comparable_to_qcec": comparable,
            "mean_runtime_seconds": (sum(times) / len(times)) if times else None,
            "decisions": _count_decisions(rows, ch),
        }
    # Explicit cross-check: unitary vs qcec false positives/negatives
    fp = fn = 0
    agree = disagree = 0
    for r in rows:
        q = r["checkers"].get("qcec", {}).get("decision")
        u = r["checkers"].get("unitary_fidelity", {}).get("decision")
        if q not in DECIDED or u not in DECIDED:
            continue
        if q == u:
            agree += 1
        else:
            disagree += 1
            if u == "equivalent" and q == "not_equivalent":
                fp += 1
            if u == "not_equivalent" and q == "equivalent":
                fn += 1
    out["qcec_vs_unitary_fidelity"] = {
        "agree": agree,
        "disagree": disagree,
        "unitary_equiv_but_qcec_not": fp,
        "unitary_not_but_qcec_equiv": fn,
    }
    return out


def _count_decisions(rows: list[dict], ch: str) -> dict[str, int]:
    c: dict[str, int] = {}
    for r in rows:
        d = r["checkers"].get(ch, {}).get("decision", "missing")
        c[d] = c.get(d, 0) + 1
    return c


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kept", type=str, required=True)
    parser.add_argument(
        "--predictions",
        type=str,
        default=None,
        help="Optional; default oracle (candidate = gold)",
    )
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
    t_start = time.perf_counter()
    checkers = ["qcec", "unitary_fidelity", "basis_statevector"]

    for i, row in enumerate(kept, 1):
        sid = str(row["id"])
        gold_code = row.get("code") or ""
        cand_code = preds.get(sid, gold_code)

        ref_qc, ref_err, ref_meta = extract_from_code(gold_code)
        if ref_qc is None:
            results.append({"id": sid, "status": "ref_extract_failed", "error": ref_err})
            continue
        cand_qc, cand_err, cand_meta = extract_from_code(cand_code)
        if cand_qc is None:
            results.append({"id": sid, "status": "cand_extract_failed", "error": cand_err})
            continue

        checks: dict[str, dict] = {}
        for cr in run_all(ref_qc, cand_qc, qcec_timeout_s=args.qcec_timeout):
            checks[cr.checker] = {
                "decision": cr.decision,
                "detail": cr.detail,
                "seconds": cr.seconds,
            }
        results.append(
            {
                "id": sid,
                "status": "ok",
                "ref_meta": {k: ref_meta.get(k) for k in ("n_qubits", "n_ops")},
                "cand_meta": {k: cand_meta.get(k) for k in ("n_qubits", "n_ops")},
                "checkers": checks,
            }
        )
        if i % 25 == 0 or i == 1:
            print(f"[compare] {i}/{len(kept)}", flush=True)

    scored = [r for r in results if r.get("status") == "ok"]
    summary = aggregate(scored, checkers)
    summary["total_rows"] = len(results)
    summary["extract_failed"] = len(results) - len(scored)
    summary["wall_seconds"] = time.perf_counter() - t_start

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


if __name__ == "__main__":
    main()