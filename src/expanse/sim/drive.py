from __future__ import annotations
from dataclasses import dataclass


@dataclass
class EpsteinDrive:
    max_thrust_g: float = 12.0
    crew_safe_g: float = 3.0
    spool_rate_g_per_s: float = 2.0
    current_g: float = 0.0

    def update(self, commanded_g: float, dt: float) -> None:
        commanded_g = max(0.0, min(self.max_thrust_g, commanded_g))
        diff = commanded_g - self.current_g
        step = self.spool_rate_g_per_s * dt
        if abs(diff) <= step:
            self.current_g = commanded_g
        else:
            self.current_g += step if diff > 0 else -step
