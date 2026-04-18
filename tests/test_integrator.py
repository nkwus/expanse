from expanse.sim.vec import Vec2
from expanse.sim.integrator import step_kinematics


def test_zero_accel_momentum_conservation():
    pos = Vec2(0.0, 0.0)
    vel = Vec2(10.0, -5.0)
    for _ in range(10_000):
        pos, vel = step_kinematics(pos, vel, Vec2(0.0, 0.0), 0.05)
    assert abs(vel.x - 10.0) < 1e-9
    assert abs(vel.y + 5.0) < 1e-9


def test_constant_accel_closed_form():
    # x(t) = 0.5 a t^2; v(t) = a t
    pos = Vec2(0.0, 0.0)
    vel = Vec2(0.0, 0.0)
    a = Vec2(9.80665, 0.0)  # 1 g along +x
    dt = 0.05
    n = 1200  # 60 s
    for _ in range(n):
        pos, vel = step_kinematics(pos, vel, a, dt)
    t = n * dt
    expected_x = 0.5 * a.x * t * t
    expected_vx = a.x * t
    # Semi-implicit Euler is first-order; allow modest relative error.
    assert abs(vel.x - expected_vx) / expected_vx < 1e-3
    # Position accumulates small per-step bias; allow ~0.5% at 60s.
    assert abs(pos.x - expected_x) / expected_x < 5e-3
