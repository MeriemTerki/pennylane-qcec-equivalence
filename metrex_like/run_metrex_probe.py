"""
Run QCEC on the MetRex-like starter circuits.

For each circuit id we check:
  base vs equivalent rewrite  -> expect equivalent (or equivalent_up_to_global_phase)
  base vs mutant              -> expect not_equivalent
"""

from __future__ import annotations

import json
from pathlib import Path

from mqt import qcec

from circuits_lib import CATALOG

OUT = Path(__file__).resolve().parent / "results"
OUT.mkdir(parents=True, exist_ok=True)


def check(qc_a, qc_b) -> str:
    return str(qcec.verify(qc_a, qc_b).equivalence)


def is_equiv(label: str) -> bool:
    s = label.lower()
    return "not_equivalent" not in s and "equivalent" in s


def main() -> None:
    rows = []
    print("id,comparison,verdict,expected_ok")
    for item in CATALOG:
        cid = item["id"]
        kw = item["kwargs"]
        base = item["base"](**kw)
        equiv = item["equiv"](**kw)
        mutant = item["mutant"](**kw)

        for name, other, should_equiv in [
            ("base_vs_equiv", equiv, True),
            ("base_vs_mutant", mutant, False),
        ]:
            try:
                verdict = check(base, other)
                ok = is_equiv(verdict) if should_equiv else (not is_equiv(verdict))
                status = "ok"
                err = None
            except Exception as exc:  # noqa: BLE001
                verdict = None
                ok = False
                status = "qcec_failed"
                err = str(exc)

            row = {
                "id": cid,
                "comparison": name,
                "status": status,
                "equivalence": verdict,
                "expected_equivalent": should_equiv,
                "pass": ok,
                "n_qubits": base.num_qubits,
                "base_depth": base.depth(),
                "other_depth": other.depth(),
                "error": err,
            }
            rows.append(row)
            print(f"{cid},{name},{verdict},{ok}", flush=True)

    out_json = OUT / "metrex_like_qcec.json"
    out_csv = OUT / "metrex_like_qcec.csv"
    out_json.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    lines = ["id,comparison,status,equivalence,expected_equivalent,pass,n_qubits"]
    for r in rows:
        lines.append(
            f"{r['id']},{r['comparison']},{r['status']},{r['equivalence']},"
            f"{r['expected_equivalent']},{r['pass']},{r['n_qubits']}"
        )
    out_csv.write_text("\n".join(lines) + "\n", encoding="utf-8")

    n_pass = sum(1 for r in rows if r["pass"])
    print(f"\nPassed {n_pass}/{len(rows)}")
    print(f"Wrote {out_json}")
    print(f"Wrote {out_csv}")


if __name__ == "__main__":
    main()
