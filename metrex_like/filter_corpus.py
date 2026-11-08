"""
Filter PennyLang / PennySynth-style samples into a MetRex-like kept set.

Frozen keep rule (see KEEP_RULE.md):
  normalize → extract → OpenQASM/Qiskit export → QCEC self-check
  mutant check is flag-only (never a hard reject)

Demo mode (no external dataset needed):
  python filter_corpus.py --demo

On a real dataset:
  python filter_corpus.py --input path/to/dataset.json --limit 100
  python filter_corpus.py --input path/to/file.jsonl --source pennysynth --prefer-qnode
"""

from __future__ import annotations

import argparse
import json
import traceback
from pathlib import Path
from typing import Any

from mqt import qcec
from qiskit import QuantumCircuit

from circuits_lib import CATALOG
from extract_circuit import extract_from_code

DEFAULT_OUT = Path(__file__).resolve().parent / "filter_out"


def load_raw_rows(path: Path) -> list[Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    data = json.loads(text)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("data", "samples", "dataset", "items"):
            if key in data and isinstance(data[key], list):
                return data[key]
        return [data]
    raise ValueError(f"Unsupported JSON root type: {type(data)}")


def looks_promising(code: str) -> bool:
    if not code or "@qml.qnode" not in code:
        return False
    if "default.qubit" not in code and "lightning.qubit" not in code:
        return False
    if "strawberryfields" in code.lower():
        return False
    if "from catalyst" in code or "qjit" in code:
        return False
    return True


def load_records(
    path: Path,
    source: str,
    limit: int | None,
    prefer_qnode: bool = False,
) -> list[dict]:
    rows = load_raw_rows(path)
    out = []
    for i, row in enumerate(rows):
        rec = normalize_row(row, source=source, idx=i)
        if prefer_qnode and not looks_promising(rec.get("code", "")):
            continue
        out.append(rec)
        if limit is not None and len(out) >= limit:
            break
    return out


def normalize_row(row: dict, source: str, idx: int) -> dict:
    instruction = (
        row.get("instruction")
        or row.get("input")
        or row.get("query")
        or row.get("prompt")
        or row.get("description")
        or ""
    )
    code = (
        row.get("code")
        or row.get("response")
        or row.get("output")
        or row.get("completion")
        or row.get("answer")
        or ""
    )
    # Some datasets nest fields.
    if not code and isinstance(row.get("messages"), list):
        for msg in reversed(row["messages"]):
            if msg.get("role") in {"assistant", "output"} and msg.get("content"):
                code = msg["content"]
                break
    return {
        "id": str(row.get("id", f"{source}_{idx}")),
        "source": source,
        "instruction": instruction if isinstance(instruction, str) else str(instruction),
        "code": code if isinstance(code, str) else str(code),
        "raw_keys": sorted(row.keys()),
    }


def _strip_measures(qc: QuantumCircuit) -> QuantumCircuit:
    """Drop measure/barrier/reset so QCEC sees a unitary gate list when possible."""
    clean = QuantumCircuit(qc.num_qubits)
    for inst in qc.data:
        if inst.operation.name in {"measure", "barrier", "reset"}:
            continue
        clean.append(inst)
    return clean if clean.size() > 0 else qc


def qcec_label(a: QuantumCircuit, b: QuantumCircuit, timeout_s: float = 15.0) -> str:
    """QCEC with a hard deadline so a single sample cannot hang the corpus filter."""
    a2, b2 = _strip_measures(a), _strip_measures(b)
    try:
        # Forced process kill after deadline (MQT QCEC API).
        result = qcec.verify_with_hard_timeout(
            a2,
            b2,
            timeout_s,
            transform_dynamic_circuit=True,
        )
        if isinstance(result, dict):
            return str(result.get("equivalence", result))
        return str(getattr(result, "equivalence", result))
    except TimeoutError:
        return "timeout"
    except TypeError:
        try:
            result = qcec.verify_with_hard_timeout(a2, b2, timeout_s)
            if isinstance(result, dict):
                return str(result.get("equivalence", result))
            return str(getattr(result, "equivalence", result))
        except TimeoutError:
            return "timeout"
    except Exception:
        # Fall back to in-process verify with cooperative timeout.
        try:
            return str(
                qcec.verify(a2, b2, transform_dynamic_circuit=True, timeout=timeout_s).equivalence
            )
        except TypeError:
            return str(qcec.verify(a2, b2, timeout=timeout_s).equivalence)


def is_equivalent(label: str) -> bool:
    s = label.lower()
    return "not_equivalent" not in s and "equivalent" in s


def mutate_circuit(qc: QuantumCircuit) -> QuantumCircuit | None:
    """Simple semantic mutant: flip/add an X on qubit 0, or drop last gate."""
    if qc.num_qubits == 0:
        return None
    mut = qc.copy()
    try:
        mut.x(0)
        return mut
    except Exception:  # noqa: BLE001
        pass
    if qc.size() == 0:
        return None
    mut = QuantumCircuit(qc.num_qubits, qc.num_clbits)
    for inst in list(qc.data)[:-1]:
        mut.append(inst)
    return mut


def filter_qiskit_circuit(
    sample_id: str,
    qc: QuantumCircuit,
    *,
    run_mutant: bool = True,
) -> dict:
    """Core filter used by both demo circuits and future extractors."""
    try:
        self_label = qcec_label(qc, qc)
    except Exception as exc:  # noqa: BLE001
        return {
            "id": sample_id,
            "status": "rejected",
            "reason": "qcec_self_fail",
            "error": str(exc),
        }
    if self_label == "timeout":
        return {
            "id": sample_id,
            "status": "rejected",
            "reason": "qcec_timeout",
            "equivalence": self_label,
        }
    if not is_equivalent(self_label):
        return {
            "id": sample_id,
            "status": "rejected",
            "reason": "qcec_self_not_equivalent",
            "equivalence": self_label,
        }

    # Mutant check is informative, not a hard reject.
    mutant_label = None
    mutant_ok = None
    if run_mutant:
        mut = mutate_circuit(qc)
        if mut is not None:
            try:
                mutant_label = qcec_label(qc, mut)
                mutant_ok = not is_equivalent(mutant_label)
            except Exception as exc:  # noqa: BLE001
                mutant_label = f"error: {exc}"
                mutant_ok = None

    return {
        "id": sample_id,
        "status": "kept",
        "reason": None,
        "equivalence_self": self_label,
        "equivalence_mutant": mutant_label,
        "mutant_detected": mutant_ok,
        "n_qubits": qc.num_qubits,
        "n_ops": qc.size(),
        "depth": qc.depth(),
    }


def try_filter_code_sample(
    rec: dict,
    *,
    run_mutant: bool = True,
    max_qubits: int | None = 12,
    max_ops: int | None = 200,
) -> dict:
    """Extract a circuit from a code string, then apply QCEC keep/reject rules."""
    code = (rec.get("code") or "").strip()
    qc, err, meta = extract_from_code(code, allow_full_exec=False)
    if qc is None:
        return {
            **rec,
            "status": "rejected",
            "reason": err or "no_circuit",
            "extract_meta": meta,
        }

    if max_qubits is not None and qc.num_qubits > max_qubits:
        return {
            **rec,
            "status": "rejected",
            "reason": f"too_many_qubits:{qc.num_qubits}>{max_qubits}",
            "extract_meta": meta,
            "n_qubits": qc.num_qubits,
            "n_ops": qc.size(),
        }
    if max_ops is not None and qc.size() > max_ops:
        return {
            **rec,
            "status": "rejected",
            "reason": f"too_many_ops:{qc.size()}>{max_ops}",
            "extract_meta": meta,
            "n_qubits": qc.num_qubits,
            "n_ops": qc.size(),
        }

    result = filter_qiskit_circuit(rec["id"], qc, run_mutant=run_mutant)
    return {**rec, **result, "extract_meta": meta}


def run_demo() -> tuple[list[dict], list[dict]]:
    kept, rejected = [], []
    for item in CATALOG:
        qc = item["base"](**item["kwargs"])
        result = filter_qiskit_circuit(item["id"], qc)
        row = {
            "id": item["id"],
            "source": "metrex_like_seed",
            "instruction": f"Build the {item['id']} circuit.",
            "code": f"<circuits_lib.{item['id']}>",
            **result,
        }
        (kept if result["status"] == "kept" else rejected).append(row)
    return kept, rejected


def _reason_bucket(reason: str | None) -> str:
    if not reason:
        return "unknown"
    if reason.startswith("import_or_exec:IndentationError"):
        return "truncated_or_indent_error"
    if reason.startswith("import_or_exec:"):
        return "import_or_exec"
    if reason.startswith("unsupported_device:"):
        return "unsupported_device"
    if reason.startswith("unsupported_control_flow:"):
        return "unsupported_control_flow"
    if reason.startswith("tape_or_export_failed:"):
        return "tape_or_export_failed"
    if reason.startswith("too_many_qubits:") or reason.startswith("too_many_ops:"):
        return reason.split(":", 1)[0]
    return reason


def summarize(kept: list[dict], rejected: list[dict], pending: list[dict]) -> dict:
    reasons: dict[str, int] = {}
    for row in rejected:
        key = _reason_bucket(row.get("reason"))
        reasons[key] = reasons.get(key, 0) + 1
    total = len(kept) + len(rejected) + len(pending)
    return {
        "total": total,
        "kept": len(kept),
        "rejected": len(rejected),
        "pending_extraction": len(pending),
        "checkable_fraction_among_decided": (
            len(kept) / (len(kept) + len(rejected)) if (kept or rejected) else None
        ),
        "reject_reasons": reasons,
    }


def write_outputs(
    kept: list[dict],
    rejected: list[dict],
    pending: list[dict],
    out_dir: Path,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    def dump_jsonl(path: Path, rows: list[dict]) -> None:
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    dump_jsonl(out_dir / "kept.jsonl", kept)
    dump_jsonl(out_dir / "rejected.jsonl", rejected)
    dump_jsonl(out_dir / "pending_extraction.jsonl", pending)
    summary = summarize(kept, rejected, pending)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Wrote outputs in {out_dir}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="Filter the local seed circuits")
    parser.add_argument("--input", type=str, help="Path to PennyLang/PennySynth json/jsonl")
    parser.add_argument("--source", type=str, default="corpus", help="Label for source field")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--out-dir", type=str, default=str(DEFAULT_OUT))
    parser.add_argument(
        "--prefer-qnode",
        action="store_true",
        help="Only process snippets that already look like qubit QNodes",
    )
    parser.add_argument(
        "--skip-mutant",
        action="store_true",
        help="Skip soft mutant flag (faster full corpus builds; keep rule unchanged)",
    )
    parser.add_argument(
        "--max-qubits",
        type=int,
        default=12,
        help="Reject circuits larger than this (QCEC cost); 0 disables",
    )
    parser.add_argument(
        "--max-ops",
        type=int,
        default=200,
        help="Reject circuits with more ops than this; 0 disables",
    )
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    run_mutant = not args.skip_mutant
    max_qubits = None if args.max_qubits == 0 else args.max_qubits
    max_ops = None if args.max_ops == 0 else args.max_ops

    if args.demo:
        kept, rejected = run_demo()
        write_outputs(kept, rejected, pending=[], out_dir=out_dir)
        return

    if not args.input:
        raise SystemExit("Provide --demo or --input path/to/dataset.json[.l]")

    path = Path(args.input)
    if not path.exists():
        raise SystemExit(f"Missing input file: {path}")

    records = load_records(
        path,
        source=args.source,
        limit=args.limit,
        prefer_qnode=args.prefer_qnode,
    )
    print(
        f"Loaded {len(records)} records from {path} (mutant={'on' if run_mutant else 'off'})",
        flush=True,
    )
    kept, rejected, pending = [], [], []
    for i, rec in enumerate(records, 1):
        if i % 25 == 0 or i == 1:
            print(f"[{args.source}] {i}/{len(records)} kept={len(kept)} rejected={len(rejected)}", flush=True)
        try:
            result = try_filter_code_sample(
                rec,
                run_mutant=run_mutant,
                max_qubits=max_qubits,
                max_ops=max_ops,
            )
        except Exception as exc:  # noqa: BLE001
            result = {
                **rec,
                "status": "rejected",
                "reason": "import_or_exec",
                "error": f"{exc}\n{traceback.format_exc()}",
            }
        status = result.get("status")
        if status == "kept":
            kept.append(result)
        elif status == "pending_extraction":
            pending.append(result)
        else:
            rejected.append(result)

    write_outputs(kept, rejected, pending, out_dir=out_dir)


if __name__ == "__main__":
    main()
