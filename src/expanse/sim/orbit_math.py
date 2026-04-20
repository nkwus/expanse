from __future__ import annotations
from math import cos, sin, sqrt

from .vec import Vec2


def solve_kepler(M: float, e: float, tol: float = 1e-10) -> float:
    """Solve Kepler's equation M = E - e·sin(E) for eccentric anomaly E.

    Newton-Raphson, initial guess E = M + e·sin(M), capped at 10 iterations.
    """
    E = M + e * sin(M)
    for _ in range(10):
        f = E - e * sin(E) - M
        if abs(f) < tol:
            break
        fp = 1.0 - e * cos(E)
        E -= f / fp
    return E


def elements_to_pos(a: float, e: float, omega: float, M: float, mu: float) -> Vec2:
    """2D position from Keplerian elements (perifocal frame rotated by omega).

    mu kept in the signature so the future elements_to_state variant (with
    velocity) doesn't force callers to reorder args.
    """
    _ = mu
    E = solve_kepler(M, e)
    x_pf = a * (cos(E) - e)
    y_pf = a * sqrt(1.0 - e * e) * sin(E)
    c, s = cos(omega), sin(omega)
    return Vec2(x_pf * c - y_pf * s, x_pf * s + y_pf * c)
