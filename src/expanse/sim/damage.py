from __future__ import annotations

from .bodies import Ship
from .events import SimEvent


def apply_damage(world, ship: Ship, amount: float, cause: str = "impact") -> bool:
    """Reduce a ship's hull and mark destroyed/emit event on zero. Returns True if destroyed."""
    if ship.destroyed:
        return True
    ship.hull_hp = max(0.0, ship.hull_hp - amount)
    if ship.hull_hp <= 0.0:
        ship.destroyed = True
        ship.cmd_thrust_g = 0.0
        ship.cmd_heading = None
        ship.autopilot = None
        ship.drive.current_g = 0.0
        world.emit(
            SimEvent.SHIP_DESTROYED,
            f"{ship.name} destroyed ({cause})",
            {"entity_id": ship.id, "cause": cause},
        )
        return True
    return False
