from __future__ import annotations

from .vec import Vec2


def step_kinematics(pos: Vec2, vel: Vec2, accel: Vec2, dt: float) -> tuple[Vec2, Vec2]:
    """Semi-implicit Euler: v_next = v + a*dt; x_next = x + v_next*dt."""
    new_vel = vel + accel * dt
    new_pos = pos + new_vel * dt
    return new_pos, new_vel
