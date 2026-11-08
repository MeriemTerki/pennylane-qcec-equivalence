"""Extract a Qiskit QuantumCircuit from a PennyLane code snippet, when possible."""

from __future__ import annotations

import ast
import contextlib
import inspect
import io
import re
import textwrap
import traceback
from typing import Any

import numpy as np
import pennylane as qml
from pennylane.workflow import construct_tape
from qiskit import QuantumCircuit
from qiskit.qasm2 import loads as qasm2_loads


UNSUPPORTED_DEVICE_HINTS = (
    "strawberryfields",
    "cirq.gaussian",
    "lightning.kokkos",  # may be ok but often unavailable
    "qutrit",
)


def _dummy_for_param(name: str, annotation: Any) -> Any:
    n = (name or "").lower()
    if any(k in n for k in ("wire", "wires", "qubit")):
        return 0
    if any(k in n for k in ("weight", "param", "theta", "angle", "phi", "feature", "input", "x", "data")):
        return np.zeros(4)
    if annotation in (int, "int"):
        return 2
    if annotation in (float, "float"):
        return 0.1
    return np.zeros(4)


def _n_wires(qnode: Any, ns: dict) -> int:
    for key in ("n_qubits", "n_wires", "wires"):
        val = ns.get(key)
        if isinstance(val, int) and val > 0:
            return val
    try:
        return len(qnode.device.wires)
    except Exception:  # noqa: BLE001
        return 2


def _candidate_calls(qnode: Any, ns: dict) -> list[tuple[tuple, dict]]:
    """Build several plausible argument patterns for a QNode."""
    n = _n_wires(qnode, ns)
    fn = getattr(qnode, "func", qnode)
    try:
        params = [
            p
            for name, p in inspect.signature(fn).parameters.items()
            if name not in {"self", "cls"}
            and p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)
            and p.default is inspect.Parameter.empty
        ]
    except Exception:  # noqa: BLE001
        params = []

    attempts: list[tuple[tuple, dict]] = [(tuple(), {})]
    if not params:
        return attempts

    # Non-zero dummies so circuits are not trivially identity (important for mutant checks).
    inputs = np.linspace(0.2, 1.1, n)
    weights_sel = (np.arange(1, 1 + 3 * n, dtype=float).reshape(1, n, 3)) * 0.15
    weights_basic = np.linspace(0.3, 1.0, n)
    weights_2d = np.linspace(0.2, 0.9, n).reshape(1, n)

    names = [p.name.lower() for p in params]

    def _dummy_for(name: str, i: int) -> Any:
        if any(k in name for k in ("filter", "flag", "mode", "kind", "name")):
            return "H"
        if any(k in name for k in ("seq", "gates", "ops", "gate_sequence")):
            return ["H", "X", "CNOT"]
        if any(k in name for k in ("thing", "bit", "msg", "message", "text", "string", "code")):
            return "01001100"
        if any(k in name for k in ("angle", "theta", "phi", "rot", "gamma", "beta", "alpha")):
            return 0.3 + 0.1 * i
        if "weight" in name:
            return weights_basic
        return 0.3 + 0.1 * i

    scalar_tuple = tuple(_dummy_for(nm, i) for i, nm in enumerate(names))
    attempts.append((scalar_tuple, {}))

    if len(params) == 1:
        name = names[0]
        if "weight" in name:
            attempts.extend(
                [
                    ((weights_sel,), {}),
                    ((weights_basic,), {}),
                    ((weights_2d,), {}),
                    ((0.1,), {}),
                ]
            )
        elif any(k in name for k in ("angle", "theta", "phi", "rot")):
            # Scalar rotation parameters must not receive per-wire vectors.
            attempts.extend([((0.5,), {}), ((0.1,), {}), ((float(n),), {})])
        elif any(k in name for k in ("thing", "bit", "msg", "message", "text", "string", "code")):
            # Bitstring / Huffman-style encoders; avoid array dummies that skip i+=2.
            attempts.extend([(("01001100",), {}), (("01",), {}), (("00",), {})])
        else:
            attempts.extend([((0.1,), {}), (("01001100",), {}), ((inputs,), {}), ((n,), {})])
    else:
        attempts.extend(
            [
                ((inputs, weights_sel), {}),
                ((inputs, weights_basic), {}),
                ((inputs, weights_2d), {}),
                ((inputs, 0.1), {}),
            ]
        )
        a, b = params[0].name, params[1].name
        attempts.append((tuple(), {a: inputs, b: weights_sel}))
        attempts.append((tuple(), {p.name: _dummy_for(p.name.lower(), i) for i, p in enumerate(params)}))

    # Torch interface fallback.
    try:
        import torch

        t_in = torch.linspace(0.2, 1.1, n)
        t_w = torch.linspace(0.1, 1.0, 3 * n).reshape(1, n, 3)
        if len(params) >= 2:
            attempts.append(((t_in, t_w), {}))
        elif len(params) == 1:
            attempts.append(((t_in,), {}))
    except Exception:  # noqa: BLE001
        pass

    return attempts


def _has_leading_indent(code: str) -> bool:
    return any(line.startswith((" ", "\t")) for line in code.splitlines() if line.strip())


def repair_flat_indent(code: str) -> str:
    """Best-effort indent repair for corpus rows that stripped all leading whitespace.

    PennyLang's dataset.json responses are often completely dedented. This recovers
    enough structure for many QNode snippets (def/if suites + return-based dedent).
    """
    if not code or _has_leading_indent(code):
        return code

    ind = "    "
    level = 0
    soft_dedent = 0
    in_triple: str | None = None
    out: list[str] = []
    align_left = re.compile(r"^(elif\b|else:|except\b|finally:)")
    force_zero = re.compile(r"^(if __name__\b|import |from )")
    end_suite = re.compile(r"^(return\b|pass\b|raise\b|break\b|continue\b)")

    def _toggle_triple(s: str, state: str | None) -> str | None:
        for marker in ('"""', "'''"):
            count = s.count(marker)
            if count == 0:
                continue
            # Odd count toggles in/out of that marker.
            if state is None and count % 2 == 1:
                return marker
            if state == marker and count % 2 == 1:
                return None
        return state

    for raw in code.splitlines():
        s = raw.strip()
        if not s:
            out.append("")
            continue

        was_in_triple = in_triple is not None
        in_triple = _toggle_triple(s, in_triple)
        # Still inside a docstring/string opened on a previous line.
        still_in_triple = was_in_triple and in_triple is not None
        # Line that both opens and closes a one-line triple string.
        opened_and_closed = (
            not was_in_triple and in_triple is None and ('"""' in s or "'''" in s)
        )
        # Line that opens a triple string (docstring start).
        opens_triple = not was_in_triple and in_triple is not None

        if not was_in_triple:
            if force_zero.match(s):
                level = 0
                soft_dedent = 0
            elif align_left.match(s):
                level = max(0, level - 1)
                soft_dedent = 0
            elif soft_dedent:
                level = max(0, level - soft_dedent)
                soft_dedent = 0

        out.append(ind * level + s)

        if was_in_triple or still_in_triple or opens_triple or opened_and_closed:
            # Ignore structural colons inside docstrings / triple quotes.
            # Closing docstring line: if it was a one-line """...""", treat as statement.
            if not was_in_triple and in_triple is None and opened_and_closed:
                if end_suite.match(s):
                    soft_dedent = 1
            continue

        if s.endswith(":") and not s.startswith("#"):
            level += 1
            soft_dedent = 0
        elif end_suite.match(s):
            # Next sibling should leave this suite (typical for flat QNode bodies).
            soft_dedent = 1

    return "\n".join(out)


def is_probably_truncated(code: str) -> bool:
    """Detect empty blocks after ':' which are common in incomplete dataset snippets."""
    lines = code.splitlines()
    for i, line in enumerate(lines[:-1]):
        if not line.rstrip().endswith(":"):
            continue
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j >= len(lines):
            return True
        nxt = lines[j]
        if not (nxt.startswith(" ") or nxt.startswith("\t")) and not nxt.lstrip().startswith("#"):
            return True
    return False


def _scalarize_tape(tape):
    """Replace array-valued gate params with Python floats so OpenQASM is valid."""
    try:
        from pennylane.tape import QuantumScript
    except Exception:  # noqa: BLE001
        return tape
    new_ops = []
    for op in tape.operations:
        if not getattr(op, "data", None):
            new_ops.append(op)
            continue
        data = []
        for p in op.data:
            if isinstance(p, str):
                data.append(p)
                continue
            try:
                arr = np.asarray(p, dtype=float)
            except (TypeError, ValueError):
                data.append(p)
                continue
            if arr.size == 0:
                data.append(0.1)
            elif arr.ndim == 0 or arr.size == 1:
                data.append(float(np.ravel(arr)[0]))
            else:
                data.append(float(np.ravel(arr)[0]))
        try:
            new_ops.append(op.__class__(*data, wires=op.wires))
        except Exception:  # noqa: BLE001
            new_ops.append(op)
    try:
        return QuantumScript(new_ops, tape.measurements)
    except Exception:  # noqa: BLE001
        return tape


def _modernize_pennylane(code: str) -> str:
    """Rewrite a few common stale APIs that models still emit."""
    # qml.T(wires=0).inv()  →  qml.adjoint(qml.T)(wires=0)
    return re.sub(
        r"qml\.([A-Za-z_][A-Za-z0-9_]*)\(([^()\n]*)\)\.inv\(\)",
        r"qml.adjoint(qml.\1)(\2)",
        code,
    )


def _tape_to_qiskit(tape) -> QuantumCircuit:
    tape = _scalarize_tape(tape)
    qasm = qml.to_openqasm(tape, measure_all=False, rotations=False)
    if "qreg " not in qasm:
        n = max(len(getattr(tape, "wires", [])), 1)
        lines = qasm.strip().splitlines()
        insert_at = 1
        for i, line in enumerate(lines):
            if line.startswith("include"):
                insert_at = i + 1
                break
        lines.insert(insert_at, f"qreg q[{n}];")
        qasm = "\n".join(lines) + "\n"
    return qasm2_loads(qasm)


def _find_qnodes(ns: dict) -> list[Any]:
    found = []
    for v in ns.values():
        if isinstance(v, qml.QNode):
            found.append(v)
    return found


def _decorator_mentions_qnode(dec: ast.AST) -> bool:
    return "qnode" in ast.dump(dec)


def _infer_n_wires(fn_src: str, full_src: str) -> int:
    wires = [0]
    # Use \bwires so we do not match the suffix of num_wires / n_wires assignments.
    wire_assign = re.compile(r"\bwires\s*=\s*(\d+)")
    wire_list = re.compile(r"\bwires\s*=\s*\[([^\]]+)\]")
    for src in (fn_src, full_src):
        for m in wire_assign.finditer(src):
            wires.append(int(m.group(1)))
        for m in wire_list.finditer(src):
            for part in m.group(1).split(","):
                part = part.strip()
                if part.isdigit():
                    wires.append(int(part))
    for m in re.finditer(r"device\([^)]*\bwires\s*=\s*(\d+)", full_src):
        return max(int(m.group(1)), max(wires) + 1)
    # Common pattern: num_wires = N / n_qubits = N near a device(...) call.
    for m in re.finditer(r"\b(?:num_wires|n_wires|n_qubits|wires)\s*=\s*(\d+)", full_src):
        wires.append(int(m.group(1)) - 1)  # store as max index candidate via N-1
        return max(int(m.group(1)), max(wires) + 1)
    return max(max(wires) + 1, 1)


def _lift_nested_qnode_snippets(code: str) -> list[str]:
    """If QNodes are nested inside functions, lift each to a tiny standalone module."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    lines = code.splitlines()
    snippets: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not any(_decorator_mentions_qnode(d) for d in node.decorator_list):
            continue
        # Skip module-level qnodes; those are already visible after exec.
        # We still allow lifting them as a fallback rebuild.
        start = getattr(node, "lineno", None)
        end = getattr(node, "end_lineno", None)
        if start is None or end is None:
            continue
        # Include decorator lines above the def.
        dec_start = start
        if node.decorator_list:
            dec_start = min(getattr(d, "lineno", start) for d in node.decorator_list)
        fn_src = textwrap.dedent("\n".join(lines[dec_start - 1 : end]))
        n_wires = _infer_n_wires(fn_src, code)
        # Ensure the decorator can resolve `dev` when it references it.
        snippet = (
            "import pennylane as qml\n"
            "import numpy as np\n"
            f"dev = qml.device('default.qubit', wires={n_wires})\n"
            f"{fn_src}\n"
        )
        snippets.append(snippet)
    return snippets


def _try_build_from_qnodes(
    qnodes: list[Any],
    ns: dict,
    meta: dict,
    *,
    max_qubits: int | None = 12,
) -> tuple[QuantumCircuit | None, str | None, dict]:
    last_err = None
    for qnode in qnodes:
        try:
            n_dev = _n_wires(qnode, ns)
            if max_qubits is not None and n_dev > max_qubits:
                last_err = f"too_many_qubits:{n_dev}>{max_qubits}"
                continue
            attempts = _candidate_calls(qnode, ns)
            tape = None
            for a, kw in attempts:
                try:
                    tape = construct_tape(qnode)(*a, **kw)
                    meta["call_args"] = {
                        "args": [str(type(x).__name__) for x in a],
                        "kwargs": list(kw),
                    }
                    break
                except Exception as exc:  # noqa: BLE001
                    last_err = f"{type(exc).__name__}: {exc}"
                    continue
            if tape is None:
                continue
            if len(getattr(tape, "operations", [])) == 0:
                last_err = "empty_tape"
                continue
            meta["stage"] = "export"
            meta["n_ops"] = len(tape.operations)
            qc = _tape_to_qiskit(tape)
            meta["stage"] = "done"
            meta["n_qubits"] = qc.num_qubits
            return qc, None, meta
        except Exception as exc:  # noqa: BLE001
            last_err = f"{type(exc).__name__}: {exc}"
            continue
    return None, last_err, meta


def extract_from_code(
    code: str,
    *,
    allow_full_exec: bool = False,
) -> tuple[QuantumCircuit | None, str | None, dict]:
    """
    Returns (circuit, error_reason, meta).
    error_reason is None on success.

    By default only AST-lifted QNode snippets are executed (safe for corpus
    filtering). Set allow_full_exec=True to fall back to exec'ing the whole file.
    """
    meta: dict = {"stage": "start"}
    if not code or not code.strip():
        return None, "empty_code", meta

    lower = code.lower()
    for hint in UNSUPPORTED_DEVICE_HINTS:
        if hint in lower:
            return None, f"unsupported_device:{hint}", meta

    if "pennylane" not in lower and "qml." not in code:
        return None, "no_pennylane_hint", meta

    # Skip obvious non-circuit utilities early.
    if "@qml.qnode" not in code and "qml.device" not in code and "QuantumCircuit" not in code:
        # still may define ops in a function; keep trying lightly
        if "qml." not in code:
            return None, "no_circuit_hint", meta

    ns: dict[str, Any] = {
        "qml": qml,
        "pennylane": qml,
        "np": np,
        "numpy": np,
        "__name__": "snippet",
    }

    repaired = repair_flat_indent(code)
    if repaired != code:
        meta["repaired_indent"] = True
        code = repaired
    modern = _modernize_pennylane(code)
    if modern != code:
        meta["modernized_api"] = True
        code = modern

    if is_probably_truncated(code):
        return None, "truncated_snippet", meta

    # Unbounded while-loops in QNode bodies can hang construct_tape on bad dummies.
    if re.search(r"^\s*while\b", code, flags=re.MULTILINE):
        return None, "unsupported_control_flow:while", meta

    # Prefer AST-lifted QNode snippets first so we do not exec full training loops.
    meta["stage"] = "lift_qnode"
    lift_last_err = None
    for snippet in _lift_nested_qnode_snippets(code):
        lift_ns: dict[str, Any] = {
            "qml": qml,
            "pennylane": qml,
            "np": np,
            "numpy": np,
            "__name__": "snippet_lifted",
        }
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                exec(snippet, lift_ns, lift_ns)  # noqa: S102
        except Exception:  # noqa: BLE001
            continue
        qnodes = _find_qnodes(lift_ns)
        if not qnodes:
            continue
        meta["n_qnodes"] = len(qnodes)
        meta["lifted_qnode"] = True
        meta["stage"] = "construct_tape"
        qc, last_err, meta = _try_build_from_qnodes(
            qnodes, lift_ns, meta, max_qubits=12
        )
        if qc is not None:
            return qc, None, meta
        lift_last_err = last_err

    if not allow_full_exec:
        if meta.get("n_qnodes"):
            return None, f"tape_or_export_failed:{lift_last_err}", meta
        return None, "no_qnode_found", meta

    # Fallback: exec the full snippet (may run side-effect training code).
    meta["stage"] = "exec"
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            exec(code, ns, ns)  # noqa: S102
    except Exception as exc:  # noqa: BLE001
        return None, f"import_or_exec:{type(exc).__name__}: {exc}", {
            **meta,
            "traceback": traceback.format_exc()[-800:],
        }

    qnodes = _find_qnodes(ns)
    meta["n_qnodes"] = len(qnodes)
    if not qnodes:
        return None, "no_qnode_found", meta

    meta["stage"] = "construct_tape"
    qc, last_err, meta = _try_build_from_qnodes(qnodes, ns, meta, max_qubits=12)
    if qc is not None:
        return qc, None, meta
    return None, f"tape_or_export_failed:{last_err}", meta
