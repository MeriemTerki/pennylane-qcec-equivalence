"""
Paper-style equivalence *metrics* (numeric) on Qiskit unitaries.

These are simplified implementations of quantities discussed in the supervisor papers,
so results can sit next to MQT QCEC labels on the same (gold, candidate) pair.

References (local PDFs in Papers/):
  - Xia et al. 2611.15080: miter Pauli residual r_M, generator ℓ2 residual r_G, tolerance ε=10^-10
  - Manjushri 2601.22372: same semantic equiv up to global phase; tolerance 10^-15 in their experiments
  - Sander et al. PRR 2025 (3q71-y8cf): MPO contraction with tolerance ε=10^-13
  - Yu & Reps 2504.01558: exact equiv on all input states (we approximate via unitary metrics)

QCEC binary label remains the primary formal checker in this project.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import (
    Operator,
    Pauli,
    SparsePauliOp,
    Statevector,
    process_fidelity,
    state_fidelity,
)

from filter_corpus import _strip_measures

# Paper default tolerances
TOL_XIA_2611 = 1e-10
TOL_MANJUSHRI = 1e-15
TOL_MPO_PRR = 1e-13
TOL_PROCESS = 1e-8


@dataclass
class MetricValue:
    name: str
    value: float | None
    formula_ref: str
    threshold: float | None = None
    equivalent_if: str | None = None
    error: str | None = None


@dataclass
class MetricBundle:
    metrics: dict[str, float | None] = field(default_factory=dict)
    labels_from_metrics: dict[str, bool | None] = field(default_factory=dict)
    details: list[MetricValue] = field(default_factory=list)


def _align_global_phase(U1: np.ndarray, U2: np.ndarray) -> np.ndarray:
    """Return U1' = e^{iφ} U1 so Tr(U2† U1') is maximized (single global phase)."""
    M = U2.conj().T @ U1
    tr = np.trace(M)
    if abs(tr) < 1e-30:
        return U1
    phase = np.angle(tr)
    return U1 * np.exp(-1j * phase)


def process_fidelity_metric(a: QuantumCircuit, b: QuantumCircuit) -> MetricValue:
    """
    F_proc(U1, U2) = |Tr(U1† U2)|² / d²  (Qiskit process_fidelity; unitary channels).
    Equivalent up to global phase when F_proc ≈ 1 (Manjushri / standard unitary equiv).
    """
    try:
        op_a = Operator(_strip_measures(a))
        op_b = Operator(_strip_measures(b))
        fid = float(process_fidelity(op_a, op_b))
        return MetricValue(
            name="process_fidelity",
            value=fid,
            formula_ref="|Tr(U1†U2)|²/d² (global phase ignored; Manjushri Def.1 / Qiskit)",
            threshold=1.0 - TOL_PROCESS,
            equivalent_if=f"value >= {1.0 - TOL_PROCESS}",
        )
    except Exception as exc:  # noqa: BLE001
        return MetricValue("process_fidelity", None, "", error=str(exc))


def pauli_miter_l2_residual(a: QuantumCircuit, b: QuantumCircuit) -> MetricValue:
    r"""
    Miter unitary M = U2† U1 (after global-phase alignment on U1).
    Expand M = \sum_P β_P P. Xia et al. §3.2:
      r_M = sqrt(\sum_{P ≠ I} |β_P|²).

    Decide Equivalent if r_M ≤ ε (ε = 10^-10 in Xia et al. experiments).
    """
    try:
        a2, b2 = _strip_measures(a), _strip_measures(b)
        if a2.num_qubits != b2.num_qubits:
            return MetricValue("pauli_miter_l2_residual", None, "", error="width_mismatch")
        n = a2.num_qubits
        if n > 14:
            return MetricValue(
                "pauli_miter_l2_residual",
                None,
                "r_M from Pauli coeffs of U2†U1",
                error=f"n_qubits={n}>14 (Pauli expansion too large)",
            )
        U1 = _align_global_phase(Operator(a2).data, Operator(b2).data)
        U2 = Operator(b2).data
        M = U2.conj().T @ U1
        spo = SparsePauliOp.from_operator(M)
        r2 = 0.0
        for coeff, pauli in zip(spo.coeffs, spo.paulis):
            if pauli == Pauli("I" * n):
                continue
            r2 += float(np.abs(coeff) ** 2)
        r_m = float(np.sqrt(r2))
        return MetricValue(
            name="pauli_miter_l2_residual",
            value=r_m,
            formula_ref="2611.15080 Eq. miter residual r_M = ||β_{≠I}||_2",
            threshold=TOL_XIA_2611,
            equivalent_if=f"value <= {TOL_XIA_2611}",
        )
    except Exception as exc:  # noqa: BLE001
        return MetricValue("pauli_miter_l2_residual", None, "", error=str(exc))


def _pauli_generator_l2_residual_for_label(
    U1: np.ndarray,
    U2: np.ndarray,
    pauli_label: str,
) -> float:
    Gop = Pauli(pauli_label).to_matrix()
    H1 = U1 @ Gop @ U1.conj().T
    H2 = U2 @ Gop @ U2.conj().T
    diff = SparsePauliOp.from_operator(H1) - SparsePauliOp.from_operator(H2)
    return float(np.linalg.norm(diff.simplify().coeffs))


def pauli_generator_l2_residual_x(
    a: QuantumCircuit,
    b: QuantumCircuit,
    *,
    wire: int = 0,
) -> MetricValue:
    r"""
    Single-generator witness (Xia et al. Eq. 12) for one Pauli X on `wire`:
      r_G = ||α_{1,G} - α_{2,G}||_2
    where α_{i,G} are Pauli coefficients of H_i(G) = U_i G U_i†.

    Any r_G > 0 witnesses not equivalent in exact arithmetic.
    """
    try:
        a2, b2 = _strip_measures(a), _strip_measures(b)
        n = a2.num_qubits
        if n != b2.num_qubits:
            return MetricValue("pauli_generator_l2_residual_X", None, "", error="width_mismatch")
        labels = ["I"] * n
        labels[wire] = "X"
        pauli_label = "".join(labels)
        U1 = Operator(a2).data
        U2 = Operator(b2).data
        r_g = _pauli_generator_l2_residual_for_label(U1, U2, pauli_label)
        return MetricValue(
            name="pauli_generator_l2_residual_X",
            value=r_g,
            formula_ref="2611.15080 Eq. (12) r_G for G=X on wire 0 (one generator)",
            threshold=TOL_XIA_2611,
            equivalent_if=f"value <= {TOL_XIA_2611}",
        )
    except Exception as exc:  # noqa: BLE001
        return MetricValue("pauli_generator_l2_residual_X", None, "", error=str(exc))


def pauli_generator_max_rG_2n(a: QuantumCircuit, b: QuantumCircuit) -> MetricValue:
    """
    Xia et al.: propagate all 2n single-qubit Pauli generators (X_i and Z_i per wire).
    Report max_G r_G and use max for threshold test (any large r_G witnesses NEQ).
    """
    try:
        a2, b2 = _strip_measures(a), _strip_measures(b)
        n = a2.num_qubits
        if n != b2.num_qubits:
            return MetricValue("pauli_generator_max_rG_2n", None, "", error="width_mismatch")
        if n > 12:
            return MetricValue(
                "pauli_generator_max_rG_2n",
                None,
                "max r_G over 2n generators",
                error=f"n_qubits={n}>12",
            )
        U1 = Operator(a2).data
        U2 = Operator(b2).data
        r_list: list[float] = []
        for i in range(n):
            for axis in ("X", "Z"):
                labels = ["I"] * n
                labels[i] = axis
                r_list.append(_pauli_generator_l2_residual_for_label(U1, U2, "".join(labels)))
        r_max = float(max(r_list)) if r_list else 0.0
        return MetricValue(
            name="pauli_generator_max_rG_2n",
            value=r_max,
            formula_ref="2611.15080 Eq. (12); max over 2n generators X_i, Z_i",
            threshold=TOL_XIA_2611,
            equivalent_if=f"max_G r_G <= {TOL_XIA_2611}",
        )
    except Exception as exc:  # noqa: BLE001
        return MetricValue("pauli_generator_max_rG_2n", None, "", error=str(exc))


def manjushri_process_fidelity_equiv(a: QuantumCircuit, b: QuantumCircuit) -> MetricValue:
    """Same F_proc as above; Manjushri 2601.22372 experiments use tolerance 10^-15."""
    pf = process_fidelity_metric(a, b)
    if pf.value is None:
        return MetricValue("process_fidelity_manjushri_tol", None, "", error=pf.error or "no_fidelity")
    thresh = 1.0 - TOL_MANJUSHRI
    return MetricValue(
        name="process_fidelity_manjushri_tol",
        value=pf.value,
        formula_ref="2601.22372: equiv if |Tr(U1†U2)|²/d² ≥ 1 − 10⁻¹⁵",
        threshold=thresh,
        equivalent_if=f"value >= {thresh}",
    )


def min_basis_state_fidelity(a: QuantumCircuit, b: QuantumCircuit, *, max_full_n: int = 10) -> MetricValue:
    """
    min_{|ψ⟩ in basis or sample} |⟨ψ|U2†U1|ψ⟩|  — simulation-style; weak vs formal verification.
  VeriThoughts contrasts formal methods with testbench simulation.
    """
    try:
        a2, b2 = _strip_measures(a), _strip_measures(b)
        n = a2.num_qubits
        if n != b2.num_qubits:
            return MetricValue("min_basis_state_fidelity", None, "", error="width_mismatch")
        U1 = Operator(a2)
        U2 = Operator(b2)
        dim = 2**n
        worst = 1.0
        if n <= max_full_n:
            for i in range(dim):
                psi = np.zeros(dim, dtype=complex)
                psi[i] = 1.0
                sv1 = Statevector(psi).evolve(U1).data
                sv2 = Statevector(psi).evolve(U2).data
                worst = min(worst, float(state_fidelity(sv1, sv2)))
        else:
            rng = np.random.default_rng(0)
            for _ in range(32):
                psi = rng.standard_normal(dim) + 1j * rng.standard_normal(dim)
                psi /= np.linalg.norm(psi)
                sv1 = Statevector(psi).evolve(U1).data
                sv2 = Statevector(psi).evolve(U2).data
                worst = min(worst, float(state_fidelity(sv1, sv2)))
        return MetricValue(
            name="min_basis_state_fidelity",
            value=worst,
            formula_ref="min |⟨ψ|U1|ψ⟩−⟨ψ|U2|ψ⟩| via state_fidelity (simulation benchmark)",
            threshold=1.0 - TOL_PROCESS,
            equivalent_if=f"value >= {1.0 - TOL_PROCESS}",
        )
    except Exception as exc:  # noqa: BLE001
        return MetricValue("min_basis_state_fidelity", None, "", error=str(exc))


def hilbert_schmidt_residual(a: QuantumCircuit, b: QuantumCircuit) -> MetricValue:
    """1 - process_fidelity; algebraically same witness as small miter for unitaries."""
    pf = process_fidelity_metric(a, b)
    if pf.value is None:
        return MetricValue("hilbert_schmidt_residual", None, "1 - F_proc", error=pf.error)
    return MetricValue(
        name="hilbert_schmidt_residual",
        value=1.0 - pf.value,
        formula_ref="1 − F_proc (unitary; related to Xia miter distance d in Eq. 20)",
        threshold=TOL_PROCESS,
        equivalent_if=f"value <= {TOL_PROCESS}",
    )


def compute_all_metrics(a: QuantumCircuit, b: QuantumCircuit) -> MetricBundle:
    vals = [
        process_fidelity_metric(a, b),
        manjushri_process_fidelity_equiv(a, b),
        hilbert_schmidt_residual(a, b),
        pauli_miter_l2_residual(a, b),
        pauli_generator_l2_residual_x(a, b),
        pauli_generator_max_rG_2n(a, b),
        min_basis_state_fidelity(a, b),
    ]
    bundle = MetricBundle()
    for mv in vals:
        bundle.details.append(mv)
        bundle.metrics[mv.name] = mv.value
        if mv.error or mv.value is None or mv.threshold is None:
            bundle.labels_from_metrics[mv.name] = None
        elif mv.name in (
            "process_fidelity",
            "process_fidelity_manjushri_tol",
            "min_basis_state_fidelity",
        ):
            bundle.labels_from_metrics[mv.name] = mv.value >= mv.threshold
        else:
            bundle.labels_from_metrics[mv.name] = mv.value <= mv.threshold
    return bundle