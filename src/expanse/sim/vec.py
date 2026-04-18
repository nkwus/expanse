from __future__ import annotations
from dataclasses import dataclass
from math import cos, sin, atan2, hypot


@dataclass(frozen=True, slots=True)
class Vec2:
    x: float = 0.0
    y: float = 0.0

    def __add__(self, o: "Vec2") -> "Vec2":
        return Vec2(self.x + o.x, self.y + o.y)

    def __sub__(self, o: "Vec2") -> "Vec2":
        return Vec2(self.x - o.x, self.y - o.y)

    def __mul__(self, s: float) -> "Vec2":
        return Vec2(self.x * s, self.y * s)

    __rmul__ = __mul__

    def __truediv__(self, s: float) -> "Vec2":
        return Vec2(self.x / s, self.y / s)

    def __neg__(self) -> "Vec2":
        return Vec2(-self.x, -self.y)

    def dot(self, o: "Vec2") -> float:
        return self.x * o.x + self.y * o.y

    def length(self) -> float:
        return hypot(self.x, self.y)

    def length_sq(self) -> float:
        return self.x * self.x + self.y * self.y

    def normalized(self) -> "Vec2":
        L = self.length()
        if L <= 1e-12:
            return Vec2(0.0, 0.0)
        return Vec2(self.x / L, self.y / L)

    def rotated(self, rad: float) -> "Vec2":
        c, s = cos(rad), sin(rad)
        return Vec2(self.x * c - self.y * s, self.x * s + self.y * c)

    def angle(self) -> float:
        return atan2(self.y, self.x)

    @staticmethod
    def from_angle(rad: float, length: float = 1.0) -> "Vec2":
        return Vec2(cos(rad) * length, sin(rad) * length)


ZERO = Vec2(0.0, 0.0)
