from __future__ import annotations
from dataclasses import dataclass
from math import pi

from .vec import Vec2


class Autopilot:
    """Standing order that mutates ship.cmd_heading / cmd_thrust_g per tick.
    tick() returns True when the behavior is complete and should be cleared.
    """

    label: str = "auto"

    def tick(self, ship, dt: float) -> bool:  # pragma: no cover - overridden
        return True


@dataclass
class MatchVelocity(Autopilot):
    """Flip-and-burn to reach target velocity (default = zero)."""

    target_vel: Vec2 = Vec2(0.0, 0.0)
    thrust_g: float = 3.0
    epsilon_mps: float = 5.0
    align_tolerance_rad: float = 0.1
    label: str = "FLIP-AND-BURN"

    def tick(self, ship, dt: float) -> bool:
        delta = self.target_vel - ship.vel
        if delta.length() < self.epsilon_mps:
            ship.cmd_thrust_g = 0.0
            ship.cmd_heading = None
            return True
        desired_heading = delta.angle()
        ship.cmd_heading = desired_heading
        diff = (desired_heading - ship.heading + pi) % (2 * pi) - pi
        if abs(diff) < self.align_tolerance_rad:
            target_g = min(self.thrust_g, ship.crew_g_tolerance, ship.drive.max_thrust_g)
            ship.cmd_thrust_g = target_g
        else:
            ship.cmd_thrust_g = 0.0
        return False


@dataclass
class HoldHeading(Autopilot):
    """Keep pointing at a fixed bearing; no thrust."""

    heading: float = 0.0
    label: str = "HOLD HDG"

    def tick(self, ship, dt: float) -> bool:
        ship.cmd_heading = self.heading
        return False
