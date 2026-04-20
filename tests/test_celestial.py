from math import sqrt

from expanse.config import AU, MU_SUN, SIM_DT
from expanse.sim.celestial import CelestialBody, SolarSystem
from expanse.sim.vec import Vec2
from expanse.scenarios import circular_orbit, free_fall


def test_celestial_body_instantiable():
    sun = CelestialBody("Sun", mu=MU_SUN, radius_m=6.96e8)
    assert sun.name == "Sun"
    assert sun.parent is None
    assert sun.pos.x == 0.0 and sun.pos.y == 0.0


def test_gravity_at_1au_points_toward_sun():
    ss = SolarSystem([CelestialBody("Sun", mu=MU_SUN, radius_m=6.96e8)])
    g = ss.gravity_at(Vec2(AU, 0.0))
    expected = MU_SUN / (AU * AU)
    assert abs(g.length() - expected) / expected < 1e-9
    # Points toward origin (−x).
    assert g.x < 0.0
    assert abs(g.y) < 1e-20


def test_gravity_ignores_self_at_origin():
    # Probe inside a 1 m radius is skipped (div-by-zero guard).
    ss = SolarSystem([CelestialBody("Sun", mu=MU_SUN, radius_m=6.96e8)])
    g = ss.gravity_at(Vec2(0.0, 0.0))
    assert g.x == 0.0 and g.y == 0.0


def test_world_without_solar_system_has_zero_gravity():
    from expanse.sim.world import World
    w = World()
    g = w.gravity_at(Vec2(AU, 0.0))
    assert g.x == 0.0 and g.y == 0.0


def test_free_fall_scenario_monotonic_infall(capsys):
    world = free_fall.build()
    r0 = world.ships[0].pos.length()
    # ~1 sim-hour: enough for measurable infall at 1 AU (a ≈ 5.93e-3 m/s²)
    for _ in range(int(3600 / SIM_DT)):
        world.step(SIM_DT)
    capsys.readouterr()  # discard debug prints
    r1 = world.ships[0].pos.length()
    # 0.5 * a * t² over 3600 s ≈ 3.84e4 m
    assert r1 < r0
    assert (r0 - r1) > 1e4


def test_circular_orbit_stays_within_1pct(capsys):
    """Integrate ~1/100th of an Earth year (~3.7 days) and verify radius holds."""
    world = circular_orbit.build()
    # 3.156e7 s / 100 ≈ 3.156e5 s. At SIM_DT=0.05 that's 6.31e6 steps —
    # too slow for CI. Use a larger internal dt on step_kinematics by
    # stepping the world with a bigger effective dt via repeated calls.
    # Alternative: run fewer real sim-seconds but enough to see an arc.
    #
    # 3 sim-days: ~0.8% of orbit (~3° sweep). Radius should hold to <0.1%.
    dt = 10.0  # 10 s per step; circular orbit is well-resolved
    duration = 3 * 86400.0
    n = int(duration / dt)
    ship = world.ships[0]
    for _ in range(n):
        world.step(dt)
    r_final = ship.pos.length()
    assert abs(r_final - AU) / AU < 0.01
    # Sanity: something moved in +y direction (initial tangential velocity)
    assert ship.pos.y > 1e7


def test_circular_orbit_energy_bounded(capsys):
    """Semi-implicit Euler is symplectic — specific energy should stay bounded."""
    world = circular_orbit.build()
    ship = world.ships[0]
    dt = 10.0

    def specific_energy() -> float:
        r = ship.pos.length()
        return 0.5 * ship.vel.length_sq() - MU_SUN / r

    E0 = specific_energy()
    # 10 sim-days (~1/36 of year)
    for _ in range(int(10 * 86400.0 / dt)):
        world.step(dt)
    E_final = specific_energy()
    assert abs((E_final - E0) / E0) < 0.01
