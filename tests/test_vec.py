from math import pi, isclose

from expanse.sim.vec import Vec2


def test_add_sub():
    a = Vec2(1, 2)
    b = Vec2(3, 5)
    assert a + b == Vec2(4, 7)
    assert b - a == Vec2(2, 3)


def test_scalar_mul():
    a = Vec2(1, 2)
    assert a * 3 == Vec2(3, 6)
    assert 2 * a == Vec2(2, 4)


def test_length_and_normalize():
    a = Vec2(3, 4)
    assert isclose(a.length(), 5.0)
    n = a.normalized()
    assert isclose(n.length(), 1.0)


def test_rotate():
    a = Vec2(1, 0).rotated(pi / 2)
    assert isclose(a.x, 0.0, abs_tol=1e-9)
    assert isclose(a.y, 1.0, abs_tol=1e-9)


def test_from_angle():
    a = Vec2.from_angle(0.0)
    assert isclose(a.x, 1.0) and isclose(a.y, 0.0)
