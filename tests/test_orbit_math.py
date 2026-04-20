from math import pi, sin

from expanse.sim.orbit_math import solve_kepler, elements_to_pos


def test_solve_kepler_zero():
    assert solve_kepler(0.0, 0.0) == 0.0


def test_solve_kepler_satisfies_equation():
    M = pi / 2
    e = 0.5
    E = solve_kepler(M, e)
    # By definition: M = E - e·sin(E)
    assert abs((E - e * sin(E)) - M) < 1e-10


def test_solve_kepler_circular_passes_through():
    # For e=0, Kepler's equation reduces to M = E.
    for M in (0.1, 1.0, 3.0, -2.0):
        assert abs(solve_kepler(M, 0.0) - M) < 1e-12


def test_elements_to_pos_perihelion():
    a, e = 1.0, 0.2
    p = elements_to_pos(a, e, omega=0.0, M=0.0, mu=1.0)
    assert abs(p.x - a * (1 - e)) < 1e-12
    assert abs(p.y) < 1e-12


def test_elements_to_pos_aphelion():
    a, e = 1.0, 0.2
    p = elements_to_pos(a, e, omega=0.0, M=pi, mu=1.0)
    assert abs(p.x - (-a * (1 + e))) < 1e-12
    assert abs(p.y) < 1e-12


def test_elements_to_pos_omega_rotation():
    # omega=pi/2 rotates perifocal frame by 90°: perihelion should be at +y axis
    a, e = 1.0, 0.1
    p = elements_to_pos(a, e, omega=pi / 2, M=0.0, mu=1.0)
    assert abs(p.x) < 1e-12
    assert abs(p.y - a * (1 - e)) < 1e-12
