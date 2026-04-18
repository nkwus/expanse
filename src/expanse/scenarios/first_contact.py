from __future__ import annotations
from math import pi

from ..sim.world import World
from ..sim.bodies import Ship, Side
from ..sim.vec import Vec2
from ..sim.drive import EpsteinDrive
from ..sim.weapons import Magazine, PDC, PDCMode
from ..sim.ai import CorvetteAI


def _make_pdcs(base_id: int) -> list[PDC]:
    return [
        PDC(id=base_id, mount="fore"),
        PDC(id=base_id + 1, mount="aft"),
    ]


def build() -> World:
    world = World()
    player = Ship(
        id=1,
        side=Side.PLAYER,
        name="Rocinante",
        pos=Vec2(0.0, 0.0),
        vel=Vec2(0.0, 0.0),
        heading=0.0,
        dry_mass=500_000.0,
        drive=EpsteinDrive(max_thrust_g=12.0, crew_safe_g=3.0),
        crew_g_tolerance=3.0,
        hull_hp=1000.0,
        hull_hp_max=1000.0,
        magazine=Magazine(torpedoes_remaining=20),
        pdcs=_make_pdcs(1),
        pdc_mode=PDCMode.AUTO_DEFEND,
    )
    world.add_ship(player)
    hostile = Ship(
        id=2,
        side=Side.HOSTILE,
        name="MCRN Harbinger",
        pos=Vec2(1_200_000.0, 100_000.0),
        vel=Vec2(-3000.0, 0.0),
        heading=pi,
        dry_mass=350_000.0,
        drive=EpsteinDrive(max_thrust_g=10.0, crew_safe_g=3.0),
        crew_g_tolerance=3.0,
        hull_hp=700.0,
        hull_hp_max=700.0,
        magazine=Magazine(torpedoes_remaining=12),
        pdcs=_make_pdcs(101),
        pdc_mode=PDCMode.AUTO_DEFEND,
    )
    world.add_ship(hostile)
    world.ais.append(CorvetteAI(ship_id=hostile.id))
    return world
