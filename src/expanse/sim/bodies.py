from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto

from .vec import Vec2, ZERO
from .drive import EpsteinDrive


class Side(Enum):
    PLAYER = auto()
    HOSTILE = auto()
    NEUTRAL = auto()


@dataclass
class Ship:
    id: int
    side: Side
    name: str
    pos: Vec2 = ZERO
    vel: Vec2 = ZERO
    heading: float = 0.0
    ang_vel: float = 0.0
    dry_mass: float = 500_000.0
    drive: EpsteinDrive = field(default_factory=EpsteinDrive)
    crew_g_tolerance: float = 3.0
    max_rot_rate: float = 0.5
    max_rot_accel: float = 0.5
    cmd_heading: float | None = None
    cmd_thrust_g: float = 0.0
    autopilot: object | None = None  # sim.autopilot.Autopilot; avoid circular import
    hull_hp: float = 1000.0
    hull_hp_max: float = 1000.0
    destroyed: bool = False
    hull_size_sig: float = 1.0
    magazine: object | None = None  # weapons.Magazine
    pdcs: list = field(default_factory=list)  # list[weapons.PDC]
    pdc_mode: str = "AUTO"  # PDCMode.AUTO_DEFEND
