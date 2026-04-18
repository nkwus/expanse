from __future__ import annotations
from dataclasses import dataclass, field

from .vec import Vec2, ZERO
from .bodies import Side


@dataclass
class PDC:
    id: int
    mount: str  # 'fore' | 'aft'
    arc_deg: float = 180.0
    max_range_m: float = 5_000.0
    rounds_per_burst: int = 30
    burst_cooldown_s: float = 0.3
    p_hit_at_1km: float = 0.65
    cooldown_remaining_s: float = 0.0


class PDCMode:
    HOLD = "HOLD"
    AUTO_DEFEND = "AUTO"
    MANUAL = "MANUAL"


@dataclass
class Magazine:
    torpedoes_remaining: int = 20
    tube_count: int = 2
    tubes_cooldown_s: list[float] = field(default_factory=lambda: [0.0, 0.0])
    reload_time_s: float = 3.0
    torp_thrust_g: float = 15.0
    torp_fuel_s: float = 180.0
    torp_warhead: float = 400.0
    torp_prox_m: float = 50.0
    torp_mass: float = 500.0

    def ready_tube_index(self) -> int | None:
        for i, c in enumerate(self.tubes_cooldown_s):
            if c <= 0.0:
                return i
        return None

    def tick(self, dt: float) -> None:
        for i, c in enumerate(self.tubes_cooldown_s):
            if c > 0.0:
                self.tubes_cooldown_s[i] = max(0.0, c - dt)


@dataclass
class Torpedo:
    id: int
    side: Side
    pos: Vec2
    vel: Vec2
    heading: float
    ang_vel: float = 0.0
    mass: float = 500.0
    thrust_g: float = 15.0
    fuel_s: float = 180.0
    max_rot_rate: float = 3.0
    max_rot_accel: float = 6.0
    warhead_yield: float = 400.0
    prox_fuse_radius: float = 50.0
    target_track_id: int | None = None
    spawn_time: float = 0.0
    lifetime_s: float = 600.0
    alive: bool = True

    @property
    def current_g(self) -> float:
        return self.thrust_g if self.fuel_s > 0 else 0.0
