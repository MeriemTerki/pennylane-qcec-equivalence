"""
Classify QCEC not-equivalent model circuits: close mutant vs different program.

Does not touch extract failures. Uses extract_from_code + gate lists only.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from extract_circuit import extract_from_code


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def ops_from_qc(qc) -> list[tuple[str, tuple[int, ...], tuple[float, ...]]]:
    out = []
    for inst in qc.data:
        name = inst.operation.name
        if name in {"barrier", "measure"}:
            continue
        qubits = tuple(qc.find_bit(q).index for q in inst.qubits)
        params = []
        for p in inst.operation.params:
            try:
                params.append(round(float(p), 5))
            except (TypeError, ValueError):
                continue
        out.append((name, qubits, tuple(params)))
    return out


def lcs_len(a: list, b: list) -> int:
    n, m = len(a), len(b)
    if n == 0 or m == 0:
        return 0
    prev = [0] * (m + 1)
    for i in range(1, n + 1):
        cur = [0] * (m + 1)
        ai = a[i - 1]
        for j in range(1, m + 1):
            if ai == b[j - 1]:
                cur[j] = prev[j - 1] + 1
            else:
                cur[j] = cur[j - 1] if cur[j - 1] >= prev[j] else prev[j]
        prev = cur
    return prev[m]


def classify(ref_ops, cand_ops, nq_ref: int, nq_cand: int) -> str:
    struct_r = [(n, q) for n, q, _ in ref_ops]
    struct_c = [(n, q) for n, q, _ in cand_ops]
    names_r = [n for n, _, _ in ref_ops]
    names_c = [n for n, _, _ in cand_ops]

    if nq_ref != nq_cand:
        return "different_width"

    if struct_r == struct_c:
        if ref_ops == cand_ops:
            return "same_ops_qcec_disagree"
        return "param_only"

    n_ref, n_cand = len(ref_ops), len(cand_ops)
    delta = abs(n_ref - n_cand)
    lcs = lcs_len(struct_r, struct_c)
    denom = max(n_ref, n_cand, 1)
    overlap = lcs / denom
    bag_r, bag_c = Counter(names_r), Counter(names_c)
    inter = sum((bag_r & bag_c).values())
    union = sum((bag_r | bag_c).values()) or 1
    jaccard = inter / union

    # Close: same width, extra/missing/swap of ~1 gate (percent overlap is harsh on 1–3 gate circuits).
    if delta <= 1:
        return "near_mutant"
    if delta <= 2 and (overlap >= 0.6 or jaccard >= 0.6):
        return "near_mutant"
    return "different_program"


def analyze_one(kept_by_id: dict, preds_by_id: dict, loop_rows: list[dict]) -> dict:
    cache: dict[str, tuple] = {}

    def get_ops(sid: str, code: str):
        key = (sid, hash(code))
        if key not in cache:
            qc, err, meta = extract_from_code(code)
            cache[key] = (qc, err, meta)
        return cache[key]

    buckets: dict[str, list[dict]] = {
        "param_only": [],
        "near_mutant": [],
        "different_program": [],
        "different_width": [],
        "same_ops_qcec_disagree": [],
        "reextract_failed": [],
    }

    neq = [
        r
        for r in loop_rows
        if r.get("status") == "ok" and r.get("equivalent") is False
    ]

    for i, row in enumerate(neq, 1):
        sid = str(row["id"])
        gold = kept_by_id.get(sid, {})
        gold_code = gold.get("code") or ""
        cand_code = preds_by_id.get(sid, "")
        ref_qc, ref_err, _ = get_ops(f"g:{sid}", gold_code)
        cand_qc, cand_err, _ = get_ops(f"c:{sid}", cand_code)
        if ref_qc is None or cand_qc is None:
            buckets["reextract_failed"].append(
                {"id": sid, "ref_err": ref_err, "cand_err": cand_err}
            )
            continue
        ref_ops = ops_from_qc(ref_qc)
        cand_ops = ops_from_qc(cand_qc)
        label = classify(ref_ops, cand_ops, ref_qc.num_qubits, cand_qc.num_qubits)
        rec = {
            "id": sid,
            "instruction": (row.get("instruction") or gold.get("instruction") or "")[:180],
            "n_qubits_ref": ref_qc.num_qubits,
            "n_qubits_cand": cand_qc.num_qubits,
            "n_ops_ref": len(ref_ops),
            "n_ops_cand": len(cand_ops),
            "ref_gates": [n for n, _, _ in ref_ops][:12],
            "cand_gates": [n for n, _, _ in cand_ops][:12],
            "bucket": label,
        }
        buckets[label].append(rec)
        if i % 50 == 0 or i == 1:
            print(f"  [{i}/{len(neq)}]", flush=True)

    counts = {k: len(v) for k, v in buckets.items()}
    n = sum(counts.values()) or 1
    return {"n_not_equivalent": len(neq), "counts": counts, "frac": {k: v / n for k, v in counts.items()}, "buckets": buckets}


def examples(rows: list[dict], k: int = 3) -> list[dict]:
    return rows[:k]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kept", type=str, required=True)
    parser.add_argument("--predictions", type=str, required=True)
    parser.add_argument("--loop", type=str, required=True)
    parser.add_argument("--out", type=str, required=True)
    parser.add_argument("--tag", type=str, default="")
    args = parser.parse_args()

    kept = {str(r["id"]): r for r in load_jsonl(Path(args.kept))}
    preds = {str(r["id"]): r.get("code") or "" for r in load_jsonl(Path(args.predictions))}
    loop = load_jsonl(Path(args.loop))

    print(f"Analyzing not-equivalent for {args.tag or args.predictions}", flush=True)
    result = analyze_one(kept, preds, loop)
    slim = {
        "tag": args.tag,
        "n_not_equivalent": result["n_not_equivalent"],
        "counts": result["counts"],
        "frac": result["frac"],
        "examples": {k: examples(v) for k, v in result["buckets"].items() if k != "reextract_failed"},
    }
    out = Path(args.out)
    out.write_text(json.dumps(slim, indent=2), encoding="utf-8")
    print(json.dumps({"tag": args.tag, "counts": result["counts"]}, indent=2))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
