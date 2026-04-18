from expanse.sim.sensors import signature, detect_range, BASE_DETECT_RANGE_M
from expanse.sim.bodies import Ship, Side
from expanse.sim.drive import EpsteinDrive
from expanse.sim.vec import Vec2


def _ship(current_g: float) -> Ship:
    s = Ship(
        id=1, side=Side.PLAYER, name="T",
        pos=Vec2(0, 0), vel=Vec2(0, 0), heading=0.0,
        dry_mass=500_000.0,
        drive=EpsteinDrive(max_thrust_g=12.0, current_g=current_g),
    )
    return s


def test_signature_increases_with_thrust():
    assert signature(_ship(0.0)) < signature(_ship(0.1))
    assert signature(_ship(0.1)) < signature(_ship(1.0))
    assert signature(_ship(1.0)) < signature(_ship(5.0))


def test_detect_range_monotonic():
    r0 = detect_range(signature(_ship(0.0)))
    r1 = detect_range(signature(_ship(1.0)))
    r5 = detect_range(signature(_ship(5.0)))
    assert r0 < r1 < r5


def test_ballistic_vs_1g_ratio_is_large():
    r_ballistic = detect_range(signature(_ship(0.0)))
    r_1g = detect_range(signature(_ship(1.0)))
    # The stealth mechanic requires orders-of-magnitude advantage for going dark.
    assert r_1g / r_ballistic > 50.0


def test_ballistic_range_matches_base():
    r = detect_range(signature(_ship(0.0)))
    assert abs(r - BASE_DETECT_RANGE_M) < 1.0
