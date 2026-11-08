"""
MetRex-like starter circuits for QCEC probing.

Each entry is a small Qiskit program that *returns a QuantumCircuit*.
That is the right analogue of a synthesizable Verilog module in VeriThoughts.

For every base circuit we also provide:
  - an equivalent rewrite (should be QCEC-equivalent)
  - a mutant (should be QCEC-not-equivalent)
"""

from __future__ import annotations

from qiskit import QuantumCircuit


def bell() -> QuantumCircuit:
    qc = QuantumCircuit(2)
    qc.h(0)
    qc.cx(0, 1)
    return qc


def bell_rewrite() -> QuantumCircuit:
    # Same Bell unitary: CX(0,1) rewritten as H-CZ-H on the target.
    qc = QuantumCircuit(2)
    qc.h(0)
    qc.h(1)
    qc.cz(0, 1)
    qc.h(1)
    return qc


def bell_mutant() -> QuantumCircuit:
    qc = QuantumCircuit(2)
    qc.h(0)
    # Missing CX: not a Bell pair.
    return qc


def ghz(n: int = 3) -> QuantumCircuit:
    qc = QuantumCircuit(n)
    qc.h(0)
    for i in range(n - 1):
        qc.cx(i, i + 1)
    return qc


def ghz_rewrite(n: int = 3) -> QuantumCircuit:
    # Same GHZ unitary: each CX rewritten as H-CZ-H on the target.
    qc = QuantumCircuit(n)
    qc.h(0)
    for i in range(n - 1):
        qc.h(i + 1)
        qc.cz(i, i + 1)
        qc.h(i + 1)
    return qc


def ghz_mutant(n: int = 3) -> QuantumCircuit:
    qc = QuantumCircuit(n)
    qc.h(0)
    for i in range(n - 1):
        qc.cx(i, i + 1)
    qc.x(n - 1)  # flips the state: not GHZ
    return qc


def swap_via_cx() -> QuantumCircuit:
    qc = QuantumCircuit(2)
    qc.cx(0, 1)
    qc.cx(1, 0)
    qc.cx(0, 1)
    return qc


def swap_native() -> QuantumCircuit:
    qc = QuantumCircuit(2)
    qc.swap(0, 1)
    return qc


def swap_mutant() -> QuantumCircuit:
    qc = QuantumCircuit(2)
    qc.cx(0, 1)
    qc.cx(1, 0)
    # Missing third CX: not a full SWAP
    return qc


def qft2() -> QuantumCircuit:
    qc = QuantumCircuit(2)
    qc.h(0)
    qc.cp(3.141592653589793 / 2, 1, 0)
    qc.h(1)
    qc.swap(0, 1)
    return qc


def qft2_rewrite() -> QuantumCircuit:
    # Same 2-qubit QFT, written with CU1-style angle via crz-equivalent cp.
    qc = QuantumCircuit(2)
    qc.h(0)
    qc.cp(1.5707963267948966, 1, 0)
    qc.h(1)
    qc.cx(0, 1)
    qc.cx(1, 0)
    qc.cx(0, 1)  # SWAP via 3 CXs
    return qc


def qft2_mutant() -> QuantumCircuit:
    qc = QuantumCircuit(2)
    qc.h(0)
    qc.cp(3.141592653589793 / 2, 1, 0)
    qc.h(1)
    # Missing final SWAP
    return qc


def rx_cascade() -> QuantumCircuit:
    qc = QuantumCircuit(1)
    qc.rx(0.3, 0)
    qc.rx(0.4, 0)
    return qc


def rx_cascade_rewrite() -> QuantumCircuit:
    qc = QuantumCircuit(1)
    qc.rx(0.7, 0)  # 0.3 + 0.4
    return qc


def rx_cascade_mutant() -> QuantumCircuit:
    qc = QuantumCircuit(1)
    qc.rx(0.3, 0)
    qc.rx(-0.4, 0)
    return qc


# Catalog used by the runner.
# Each item: id, base builder, equivalent builder, mutant builder, kwargs
CATALOG: list[dict] = [
    {
        "id": "bell",
        "base": bell,
        "equiv": bell_rewrite,
        "mutant": bell_mutant,
        "kwargs": {},
    },
    {
        "id": "ghz3",
        "base": ghz,
        "equiv": ghz_rewrite,
        "mutant": ghz_mutant,
        "kwargs": {"n": 3},
    },
    {
        "id": "ghz4",
        "base": ghz,
        "equiv": ghz_rewrite,
        "mutant": ghz_mutant,
        "kwargs": {"n": 4},
    },
    {
        "id": "swap",
        "base": swap_via_cx,
        "equiv": swap_native,
        "mutant": swap_mutant,
        "kwargs": {},
    },
    {
        "id": "qft2",
        "base": qft2,
        "equiv": qft2_rewrite,
        "mutant": qft2_mutant,
        "kwargs": {},
    },
    {
        "id": "rx_cascade",
        "base": rx_cascade,
        "equiv": rx_cascade_rewrite,
        "mutant": rx_cascade_mutant,
        "kwargs": {},
    },
]
