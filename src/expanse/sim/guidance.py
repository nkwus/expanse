from __future__ import annotations
from math import atan2

from .vec import Vec2


def torpedo_aim_heading(torpedo, target_track, now_sim: float) -> float:
    """Lead-pursuit: aim at predicted intercept point.

    Uses the sensed track (not ground truth), including estimated acceleration
    for a second-order projection of the target's position, and the torpedo's
    current speed as the projectile speed for the intercept solver.
    """
    age = max(0.0, now_sim - target_track.last_seen_time)
    v_mag = torpedo.vel.length()
    if v_mag < 50.0:
        # Fresh launch: aim where target will be shortly.
        tp = target_track.predict_pos(age + 1.0)
    else:
        aim = target_track.intercept_point(torpedo.pos, v_mag)
        # Add the acceleration-based correction
        dt_est = max(1.0, (Vec2(aim.x - torpedo.pos.x, aim.y - torpedo.pos.y).length()) / v_mag)
        tp = target_track.predict_pos(age + dt_est)
    return atan2(tp.y - torpedo.pos.y, tp.x - torpedo.pos.x)
