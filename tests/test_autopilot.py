from expanse.sim.world import World
from expanse.sim.bodies import Ship, Side
from expanse.sim.vec import Vec2
from expanse.sim.drive import EpsteinDrive
from expanse.sim.autopilot import MatchVelocity
from expanse.config import SIM_DT


def _make_ship(vel: Vec2) -> Ship:
    return Ship(
        id=1, side=Side.PLAYER, name="Test",
        pos=Vec2(0, 0), vel=vel, heading=0.0,
        dry_mass=500_000.0,
        drive=EpsteinDrive(max_thrust_g=12.0, crew_safe_g=3.0, spool_rate_g_per_s=10.0),
        crew_g_tolerance=3.0,
    )


def test_match_velocity_zero_converges():
    w = World()
    ship = _make_ship(vel=Vec2(500.0, -300.0))
    w.add_ship(ship)
    ship.autopilot = MatchVelocity(
        target_vel=Vec2(0.0, 0.0),
        thrust_g=3.0,
        epsilon_mps=5.0,
    )
    # Run up to 120 sim seconds
    for _ in range(int(120 / SIM_DT)):
        w.step(SIM_DT)
        if ship.autopilot is None:
            break
    assert ship.autopilot is None, "autopilot did not complete"
    assert ship.vel.length() < 10.0, f"final vel {ship.vel.length()} too high"
    assert ship.cmd_thrust_g == 0.0


def test_heading_slew_reaches_target():
    from math import pi, isclose
    w = World()
    ship = _make_ship(vel=Vec2(0, 0))
    ship.max_rot_rate = 1.0  # rad/s
    ship.max_rot_accel = 2.0
    w.add_ship(ship)
    ship.cmd_heading = pi / 2  # 90°
    for _ in range(int(10 / SIM_DT)):
        w.step(SIM_DT)
    assert isclose(ship.heading, pi / 2, abs_tol=0.02)
