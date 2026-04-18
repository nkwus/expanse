from __future__ import annotations
from math import sqrt

from .bodies import Ship


DRIVE_SIG_COEFF = 0.01  # sig contribution per g per kg of mass
HULL_FLOOR_SIG = 1.0
BASE_DETECT_RANGE_M = 50_000.0  # detection range of a ballistic hull
MIN_SIG = 1.0


def signature(ship: Ship) -> float:
    """Thermal signature of a ship. Drive plume dominates; hull has a floor."""
    drive = DRIVE_SIG_COEFF * ship.drive.current_g * ship.dry_mass
    return max(HULL_FLOOR_SIG, ship.hull_size_sig) + drive


def detect_range(sig: float) -> float:
    """How far away a signature of `sig` is detectable by a baseline passive sensor."""
    return BASE_DETECT_RANGE_M * sqrt(max(sig, MIN_SIG) / MIN_SIG)


def torpedo_signature(torpedo) -> float:
    """Drive-burning torpedoes emit proportional to their thrust * mass (M4)."""
    return DRIVE_SIG_COEFF * getattr(torpedo, "thrust_g", 0.0) * getattr(torpedo, "mass", 500.0) + 5.0
