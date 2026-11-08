"""
VeriThoughts-style loop on *kept* samples only (not raw JSONL).

Round-trip shape (quantum analogue):
  Q  = instruction
  R  = code response (gold today; model later)
  C  = extracted reference circuit from gold code
  C* = extracted circuit from candidate code
  label = QCEC.verify(C, C*)

Usage (sanity / oracle baseline — candidate = gold code):
  python run_verithoughts_loop.py \\
    --kept filter_out/pennysynth_full/kept.jsonl \\
    --limit 20

Usage (score a predictions file):
  python run_verithoughts_loop.py \\
    --kept filter_out/pennysynth_full/kept.jsonl \\
    --predictions path/to/preds.jsonl

predictions.jsonl rows: {"id": "...", "code": "..."} matching kept ids.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from extract_circuit import extract_from_code
from filter_corpus import is_equivalent, qcec_label


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def circuit_from_code(code: str):
    qc, err, meta = extract_from_code(code)
    return qc, err, meta


def score_pair(ref_qc, cand_qc) -> dict:
    try:
        label = qcec_label(ref_qc, cand_qc)
    except Exception as exc:  # noqa: BLE001
        return {"status": "qcec_failed", "error": str(exc)}
    return {
        "status": "ok",
        "equivalence": label,
        "equivalent": is_equivalent(label),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kept", type=str, required=True, help="Path to kept.jsonl")
    parser.add_argument(
        "--predictions",
        type=str,
        default=None,
        help="Optional jsonl of {id, code}; default = oracle (gold code)",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Output jsonl (default: alongside kept as loop_results.jsonl)",
    )
    args = parser.parse_args()

    kept_path = Path(args.kept)
    kept = load_jsonl(kept_path)
    if args.limit is not None:
        kept = kept[: args.limit]

    preds: dict[str, str] = {}
    mode = "oracle_gold"
    if args.predictions:
        mode = "predictions"
        for row in load_jsonl(Path(args.predictions)):
            if row.get("id") is not None and row.get("code"):
                preds[str(row["id"])] = row["code"]

    out_path = Path(args.out) if args.out else kept_path.parent / "loop_results.jsonl"
    results = []
    n_eq = n_neq = n_fail = 0

    for i, row in enumerate(kept, 1):
        sid = str(row["id"])
        instruction = row.get("instruction") or ""
        gold_code = row.get("code") or ""
        cand_code = preds.get(sid, gold_code) if mode == "predictions" else gold_code

        ref_qc, ref_err, ref_meta = circuit_from_code(gold_code)
        if ref_qc is None:
            rec = {
                "id": sid,
                "status": "ref_extract_failed",
                "error": ref_err,
                "mode": mode,
            }
            n_fail += 1
            results.append(rec)
            continue

        cand_qc, cand_err, cand_meta = circuit_from_code(cand_code)
        if cand_qc is None:
            rec = {
                "id": sid,
                "status": "cand_extract_failed",
                "error": cand_err,
                "mode": mode,
                "instruction": instruction[:200],
            }
            n_fail += 1
            results.append(rec)
            continue

        verdict = score_pair(ref_qc, cand_qc)
        if verdict.get("status") != "ok":
            n_fail += 1
        elif verdict.get("equivalent"):
            n_eq += 1
        else:
            n_neq += 1

        results.append(
            {
                "id": sid,
                "mode": mode,
                "instruction": instruction[:300],
                "ref_meta": {k: ref_meta.get(k) for k in ("n_qubits", "n_ops", "stage")},
                "cand_meta": {k: cand_meta.get(k) for k in ("n_qubits", "n_ops", "stage")},
                **verdict,
            }
        )
        if i % 25 == 0 or i == 1:
            print(f"[loop] {i}/{len(kept)} eq={n_eq} neq={n_neq} fail={n_fail}", flush=True)

    summary = {
        "mode": mode,
        "total": len(results),
        "equivalent": n_eq,
        "not_equivalent": n_neq,
        "failed": n_fail,
        "oracle_equivalent_fraction": (n_eq / len(results) if results else None),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for rec in results:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    summary_path = out_path.with_name(out_path.stem + "_summary.json")
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
