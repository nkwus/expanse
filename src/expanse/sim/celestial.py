from __future__ import annotations
from dataclasses import dataclass
from math import sqrt

from .vec import Vec2


@dataclass
class CelestialBody:
    name: str
    mu: float
    radius_m: float
    pos: Vec2 = Vec2(0.0, 0.0)
    parent: str | None = None
    a: float = 0.0
    e: float = 0.0
    omega: float = 0.0
    M0: float = 0.0
    mean_motion: float = 0.0


class SolarSystem:
    def __init__(self, bodies: list[CelestialBody] | None = None) -> None:
        self.bodies: list[CelestialBody] = list(bodies) if bodies else []

    def add(self, body: CelestialBody) -> None:
        self.bodies.append(body)

    def advance(self, t: float) -> None:
        """No-op while all bodies are static; Phase 2 fills this in."""
        return None

    def gravity_at(self, pos: Vec2) -> Vec2:
        gx = 0.0
        gy = 0.0
        for b in self.bodies:
            dx = b.pos.x - pos.x
            dy = b.pos.y - pos.y
            r2 = dx * dx + dy * dy
            if r2 < 1.0:
                continue
            r = sqrt(r2)
            k = b.mu / (r2 * r)
            gx += dx * k
            gy += dy * k
        return Vec2(gx, gy)
