"""
Pluggable equivalence decisions on Qiskit circuits.

Reference oracle in this repo: MQT QCEC (see filter_corpus.qcec_label).

Additional checkers support comparison with paper-style metrics
(completion rate, reference-consistent decisions, runtime).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator, Statevector, process_fidelity

from filter_corpus import _strip_measures, is_equivalent, qcec_label

Decision = Literal["equivalent", "not_equivalent", "undecided", "error", "timeout"]


@dataclass
class CheckerResult:
    checker: str
    decision: Decision
    detail: str
    seconds: float


def _to_decision(equivalent: bool | None, *, undecided_reason: str = "") -> tuple[Decision, str]:
    if equivalent is None:
        return "undecided", undecided_reason or "undecided"
    return ("equivalent", "") if equivalent else ("not_equivalent", "")


def check_qcec(
    a: QuantumCircuit,
    b: QuantumCircuit,
    *,
    timeout_s: float = 15.0,
) -> CheckerResult:
    t0 = time.perf_counter()
    try:
        label = qcec_label(a, b, timeout_s=timeout_s)
    except Exception as exc:  # noqa: BLE001
        return CheckerResult("qcec", "error", str(exc), time.perf_counter() - t0)
    dt = time.perf_counter() - t0
    if label == "timeout":
        return CheckerResult("qcec", "timeout", label, dt)
    if is_equivalent(label):
        return CheckerResult("qcec", "equivalent", label, dt)
    if "not_equivalent" in label.lower():
        return CheckerResult("qcec", "not_equivalent", label, dt)
    return CheckerResult("qcec", "undecided", label, dt)


def check_unitary_fidelity(
    a: QuantumCircuit,
    b: QuantumCircuit,
    *,
    fidelity_tol: float = 1e-8,
) -> CheckerResult:
    """Unitary equivalence up to global phase via process_fidelity (Qiskit)."""
    t0 = time.perf_counter()
    a2, b2 = _strip_measures(a), _strip_measures(b)
    if a2.num_qubits != b2.num_qubits:
        return CheckerResult(
            "unitary_fidelity",
            "not_equivalent",
            f"width_mismatch:{a2.num_qubits}!={b2.num_qubits}",
            time.perf_counter() - t0,
        )
    try:
        op_a = Operator(a2)
        op_b = Operator(b2)
        fid = float(process_fidelity(op_a, op_b))
    except Exception as exc:  # noqa: BLE001
        return CheckerResult("unitary_fidelity", "undecided", f"not_unitary_or_bind:{exc}", time.perf_counter() - t0)
    dt = time.perf_counter() - t0
    if fid >= 1.0 - fidelity_tol:
        return CheckerResult("unitary_fidelity", "equivalent", f"process_fidelity={fid:.12g}", dt)
    return CheckerResult("unitary_fidelity", "not_equivalent", f"process_fidelity={fid:.12g}", dt)


def check_basis_statevector(
    a: QuantumCircuit,
    b: QuantumCircuit,
    *,
    max_qubits_full: int = 10,
    random_samples: int = 32,
    fidelity_tol: float = 1e-8,
    rng: np.random.Generator | None = None,
) -> CheckerResult:
    """
    Compare circuits by input–output fidelity on |0..0> and either all basis states
    (n <= max_qubits_full) or random pure states. Weaker than QCEC; cheap simulation metric.
    """
    t0 = time.perf_counter()
    a2, b2 = _strip_measures(a), _strip_measures(b)
    n = a2.num_qubits
    if n != b2.num_qubits:
        return CheckerResult(
            "basis_statevector",
            "not_equivalent",
            "width_mismatch",
            time.perf_counter() - t0,
        )
    rng = rng or np.random.default_rng(0)
    try:
        Ua = Operator(a2)
        Ub = Operator(b2)
    except Exception as exc:  # noqa: BLE001
        return CheckerResult("basis_statevector", "undecided", str(exc), time.perf_counter() - t0)

    def min_fid(psi: np.ndarray) -> float:
        out_a = psi @ Ua.data
        out_b = psi @ Ub.data
        denom = float(np.linalg.norm(out_a) * np.linalg.norm(out_b))
        if denom == 0.0:
            return 1.0
        return float(np.abs(np.vdot(out_a, out_b)) / denom)

    fids: list[float] = []
    z = np.zeros(2**n, dtype=complex)
    z[0] = 1.0
    fids.append(min_fid(z))

    if n <= max_qubits_full:
        for i in range(1, 2**n):
            psi = np.zeros(2**n, dtype=complex)
            psi[i] = 1.0
            fids.append(min_fid(psi))
    else:
        for _ in range(random_samples):
            psi = rng.standard_normal(2**n) + 1j * rng.standard_normal(2**n)
            psi /= np.linalg.norm(psi)
            fids.append(min_fid(psi))

    worst = min(fids)
    dt = time.perf_counter() - t0
    if worst >= 1.0 - fidelity_tol:
        return CheckerResult(
            "basis_statevector",
            "equivalent",
            f"min_output_fidelity={worst:.12g}",
            dt,
        )
    return CheckerResult(
        "basis_statevector",
        "not_equivalent",
        f"min_output_fidelity={worst:.12g}",
        dt,
    )


def run_all(
    a: QuantumCircuit,
    b: QuantumCircuit,
    *,
    qcec_timeout_s: float = 15.0,
) -> list[CheckerResult]:
    return [
        check_qcec(a, b, timeout_s=qcec_timeout_s),
        check_unitary_fidelity(a, b),
        check_basis_statevector(a, b),
    ]