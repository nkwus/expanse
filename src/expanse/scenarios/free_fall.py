from __future__ import annotations

from ..sim.world import World
from ..sim.bodies import Ship, Side
from ..sim.vec import Vec2
from ..sim.drive import EpsteinDrive
from ..sim.celestial import CelestialBody, SolarSystem
from ..config import AU, MU_SUN


class _FreeFallWorld(World):
    def step(self, dt: float) -> None:
        super().step(dt)
        if self._tick_n % 100 == 0 and self.ships:
            r = self.ships[0].pos.length()
            print(f"t={self.now_sim:8.0f}s  r={r:.4e} m  ({r/AU:.4f} AU)")


def build() -> World:
    sun = CelestialBody(name="Sun", mu=MU_SUN, radius_m=6.96e8)
    ss = SolarSystem([sun])
    world = _FreeFallWorld(solar_system=ss)
    ship = Ship(
        id=1,
        side=Side.PLAYER,
        name="Probe",
        pos=Vec2(AU, 0.0),
        vel=Vec2(0.0, 0.0),
        heading=0.0,
        dry_mass=1_000.0,
        drive=EpsteinDrive(max_thrust_g=0.0, crew_safe_g=3.0),
        crew_g_tolerance=3.0,
        hull_hp=1.0,
        hull_hp_max=1.0,
    )
    world.add_ship(ship)
    return world
