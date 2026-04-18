from __future__ import annotations
from math import atan2, asin

from ..config import G0


# Proportional navigation constant. N=3..5 is standard for real-world missiles.
_PN_N = 4.0


def torpedo_aim_heading(torpedo, target_track, now_sim: float) -> float:
    """Proportional navigation against the sensed track.

    Classic PN: commanded lateral acceleration = N · closing_speed · LOS_rate.
    The torp's thrust has fixed magnitude, so we translate the lateral command
    into an angular offset from the line-of-sight:
        sin(offset) = a_lat_cmd / a_thrust
    The returned heading is `LOS + offset`. When the LOS stops rotating (zero
    LOS rate), offset → 0 and the torp flies straight at the target — a
    constant-bearing-decreasing-range intercept.

    Uses the sensed track (not ground truth). `predict_pos`/`predict_vel` give
    us the target's "right now" state extrapolated from the last sensor sample.
    """
    age = max(0.0, now_sim - target_track.last_seen_time)
    target_pos = target_track.predict_pos(age)
    target_vel = target_track.predict_vel(age)

    rx = target_pos.x - torpedo.pos.x
    ry = target_pos.y - torpedo.pos.y
    r_sq = rx * rx + ry * ry
    if r_sq < 1.0:
        return torpedo.heading
    r_mag = r_sq ** 0.5
    los_angle = atan2(ry, rx)

    vrx = target_vel.x - torpedo.vel.x
    vry = target_vel.y - torpedo.vel.y

    # Closing speed: positive when the range is shrinking.
    closing = -(rx * vrx + ry * vry) / r_mag
    if closing <= 0.0:
        # Not closing — point straight at the target and let thrust fix it.
        return los_angle

    # Line-of-sight rotation rate (rad/s, scalar; 2D cross of r and v_rel).
    los_rate = (rx * vry - ry * vrx) / r_sq

    a_thrust = torpedo.thrust_g * G0 if torpedo.fuel_s > 0 else 0.0
    if a_thrust < 1e-6:
        # Out of fuel: coast toward current LOS, nothing to steer with.
        return los_angle

    a_lat_cmd = _PN_N * closing * los_rate
    ratio = a_lat_cmd / a_thrust
    if ratio > 0.99:
        ratio = 0.99
    elif ratio < -0.99:
        ratio = -0.99
    return los_angle + asin(ratio)
