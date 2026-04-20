from __future__ import annotations
from math import sqrt

from ..sim.world import World
from ..sim.bodies import Ship, Side
from ..sim.vec import Vec2
from ..sim.drive import EpsteinDrive
from ..sim.celestial import CelestialBody, SolarSystem
from ..config import AU, MU_SUN


class _CircularOrbitWorld(World):
    def step(self, dt: float) -> None:
        super().step(dt)
        if self._tick_n % 1000 == 0 and self.ships:
            ship = self.ships[0]
            r = ship.pos.length()
            v2 = ship.vel.length_sq()
            E = 0.5 * v2 - MU_SUN / r
            print(
                f"t={self.now_sim:9.0f}s  "
                f"r={r/AU:.6f} AU  "
                f"|v|={v2**0.5:8.1f} m/s  "
                f"E={E: .4e} J/kg"
            )


def build() -> World:
    sun = CelestialBody(name="Sun", mu=MU_SUN, radius_m=6.96e8)
    ss = SolarSystem([sun])
    world = _CircularOrbitWorld(solar_system=ss)
    v_circ = sqrt(MU_SUN / AU)
    ship = Ship(
        id=1,
        side=Side.PLAYER,
        name="Probe",
        pos=Vec2(AU, 0.0),
        vel=Vec2(0.0, v_circ),
        heading=0.0,
        dry_mass=1_000.0,
        drive=EpsteinDrive(max_thrust_g=0.0, crew_safe_g=3.0),
        crew_g_tolerance=3.0,
        hull_hp=1.0,
        hull_hp_max=1.0,
    )
    world.add_ship(ship)
    return world
