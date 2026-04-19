from __future__ import annotations
from dataclasses import dataclass
from math import cos, sin, log10, floor, pi
import pygame

from . import theme as T
from . import draw
from ..sim.vec import Vec2
from ..sim.bodies import Side
from ..sim.tracks import Classification
from ..config import RANGE_RINGS_M


@dataclass
class ScopeView:
    rect: pygame.Rect
    center_world: Vec2 = Vec2(0.0, 0.0)
    scale_px_per_m: float = 1.0 / 3000.0
    follow_ownship: bool = True

    def world_to_screen(self, w: Vec2) -> tuple[float, float]:
        dx = (w.x - self.center_world.x) * self.scale_px_per_m
        dy = (w.y - self.center_world.y) * self.scale_px_per_m
        return (self.rect.centerx + dx, self.rect.centery - dy)

    def screen_to_world(self, s: tuple[int, int]) -> Vec2:
        dx = (s[0] - self.rect.centerx) / self.scale_px_per_m
        dy = -(s[1] - self.rect.centery) / self.scale_px_per_m
        return Vec2(self.center_world.x + dx, self.center_world.y + dy)

    def zoom_by(self, factor: float) -> None:
        self.scale_px_per_m = max(1e-9, min(1.0, self.scale_px_per_m * factor))

    def pan_by(self, dx_m: float, dy_m: float) -> None:
        self.follow_ownship = False
        self.center_world = Vec2(self.center_world.x + dx_m, self.center_world.y + dy_m)

    def center_on_ownship(self) -> None:
        self.follow_ownship = True


def draw_scope(surface, scope: ScopeView, world, font) -> None:
    pygame.draw.rect(surface, T.BG, scope.rect)
    pygame.draw.rect(surface, T.PANEL_BORDER, scope.rect, 1)

    ownship = world.player_ship()
    if scope.follow_ownship and ownship is not None:
        scope.center_world = ownship.pos

    prev_clip = surface.get_clip()
    surface.set_clip(scope.rect)

    center_screen = scope.world_to_screen(scope.center_world)
    for rng_m in RANGE_RINGS_M:
        r_px = rng_m * scope.scale_px_per_m
        if 15 < r_px < 1500:
            draw.draw_dashed_circle(surface, T.RING, center_screen, r_px)
            draw.draw_text(
                surface, font, _format_range(rng_m),
                (center_screen[0] + r_px + 4, center_screen[1] - 10),
                T.RING_LABEL,
            )

    # Scope crosshair
    pygame.draw.aaline(surface, T.GRID, (center_screen[0] - 10, center_screen[1]), (center_screen[0] + 10, center_screen[1]))
    pygame.draw.aaline(surface, T.GRID, (center_screen[0], center_screen[1] - 10), (center_screen[0], center_screen[1] + 10))

    # Ownship from ground truth
    if ownship is not None:
        _draw_ownship(surface, scope, ownship, font)

    # Contacts from player TrackTable — stealth invariant: UI reads only tracks
    ptable = world.player_tracks()
    for track in ptable.all():
        _draw_track(surface, scope, track, world.now_sim, font)

    # Own-side torpedoes are displayed from truth (we know what we launched).
    for torp in getattr(world, "torpedoes", []):
        if torp.alive and ownship is not None and torp.side == ownship.side:
            _draw_own_torpedo(surface, scope, torp)

    _draw_scale_legend(surface, scope, font)
    surface.set_clip(prev_clip)


def _draw_ownship(surface, scope, ship, font):
    color = T.OWNSHIP
    p = scope.world_to_screen(ship.pos)
    pygame.draw.circle(surface, color, (int(p[0]), int(p[1])), 5, 1)
    # Heading tick
    hx = p[0] + cos(ship.heading) * 12
    hy = p[1] - sin(ship.heading) * 12
    pygame.draw.aaline(surface, color, p, (hx, hy))
    # Velocity vector (60 s extrapolation)
    tip_world = Vec2(ship.pos.x + ship.vel.x * 60.0, ship.pos.y + ship.vel.y * 60.0)
    draw.draw_arrow(surface, color, p, scope.world_to_screen(tip_world))
    # Commanded heading (dashed ray)
    if ship.cmd_heading is not None:
        diff = abs((ship.cmd_heading - ship.heading + pi) % (2 * pi) - pi)
        if diff > 0.02:
            cx = p[0] + cos(ship.cmd_heading) * 40
            cy = p[1] - sin(ship.cmd_heading) * 40
            _dashed_line(surface, T.TRACK_PREDICTED, p, (cx, cy))
    # Drive flame
    if ship.drive.current_g > 0.01:
        flen = 10 + min(18, ship.drive.current_g * 2)
        bx = p[0] - cos(ship.heading) * flen
        by = p[1] + sin(ship.heading) * flen
        pygame.draw.aaline(surface, T.WEAPON, p, (bx, by))
    draw.draw_text(surface, font, ship.name, (p[0] + 8, p[1] + 6), color)


def _draw_track(surface, scope, track, now: float, font):
    base = T.HOSTILE if track.classification == Classification.TORPEDO or True else T.UNKNOWN
    # For now treat all contacts as potentially hostile (orange). Later: classify.
    base = T.HOSTILE
    conf = track.confidence
    color = _fade(base, T.STALE, conf)

    # Use predicted position to account for sample age, then draw current track symbol
    dt_since = max(0.0, now - track.last_seen_time)
    cur_pos = track.predict_pos(dt_since)
    p = scope.world_to_screen(cur_pos)

    # Symbol by classification
    if track.classification == Classification.TORPEDO:
        _draw_triangle(surface, color, p, 5)
    elif track.classification == Classification.SHIP:
        pygame.draw.circle(surface, color, (int(p[0]), int(p[1])), 5, 1)
    else:
        pygame.draw.rect(surface, color, pygame.Rect(int(p[0]) - 4, int(p[1]) - 4, 8, 8), 1)

    # Velocity vector (60 s)
    v = track.predict_vel(dt_since)
    vtip_world = Vec2(cur_pos.x + v.x * 60.0, cur_pos.y + v.y * 60.0)
    draw.draw_arrow(surface, color, p, scope.world_to_screen(vtip_world))

    # Predicted trajectory (dashed) — 5 minutes forward w/ accel estimate
    _draw_predicted_track(surface, scope, track, dt_since, color)

    # Label
    label = f"T{track.track_id:03d}"
    draw.draw_text(surface, font, label, (p[0] + 8, p[1] - 14), color)
    # Confidence hint
    if conf < 0.99:
        draw.draw_text(surface, font, f"{int(conf*100)}%", (p[0] + 8, p[1] + 4), T.STALE)


def _draw_predicted_track(surface, scope, track, dt_since, color):
    # Constant-velocity projection: accel excluded so the tail doesn't wibble.
    # est_accel is sensor-differentiated noise amplified by t^2 over 5 min.
    horizon_s = 300.0
    steps = 12
    cur_pos = track.predict_pos(dt_since)
    v = track.last_seen_vel
    prev = scope.world_to_screen(cur_pos)
    for i in range(1, steps + 1):
        t = horizon_s * (i / steps)
        nxt_world = Vec2(cur_pos.x + v.x * t, cur_pos.y + v.y * t)
        nxt = scope.world_to_screen(nxt_world)
        if i % 2 == 1:  # dashed
            pygame.draw.aaline(surface, T.TRACK_PREDICTED, prev, nxt)
        prev = nxt


def _draw_own_torpedo(surface, scope, torp):
    p = scope.world_to_screen(torp.pos)
    _draw_triangle(surface, T.WEAPON, p, 4)
    tip_world = Vec2(torp.pos.x + torp.vel.x * 30.0, torp.pos.y + torp.vel.y * 30.0)
    pygame.draw.aaline(surface, T.WEAPON, p, scope.world_to_screen(tip_world))
    if torp.fuel_s > 0:
        # Drive flame behind heading vector
        flen = 6
        bx = p[0] - cos(torp.heading) * flen
        by = p[1] + sin(torp.heading) * flen
        pygame.draw.aaline(surface, T.WEAPON, p, (bx, by))


def _draw_triangle(surface, color, center, size):
    cx, cy = center
    pts = [(cx, cy - size), (cx - size, cy + size * 0.8), (cx + size, cy + size * 0.8)]
    pygame.draw.polygon(surface, color, pts, 1)


def _fade(base, stale, t):
    t = max(0.0, min(1.0, t))
    return (
        int(base[0] * t + stale[0] * (1 - t)),
        int(base[1] * t + stale[1] * (1 - t)),
        int(base[2] * t + stale[2] * (1 - t)),
    )


def _dashed_line(surface, color, a, b, dash=6):
    dx = b[0] - a[0]; dy = b[1] - a[1]
    L = (dx * dx + dy * dy) ** 0.5
    if L < 1:
        return
    ux, uy = dx / L, dy / L
    d = 0.0
    on = True
    while d < L:
        e = min(d + dash, L)
        if on:
            pygame.draw.aaline(surface, color, (a[0] + ux * d, a[1] + uy * d), (a[0] + ux * e, a[1] + uy * e))
        on = not on
        d = e


def _format_range(m: float) -> str:
    if m >= 1e9:
        return f"{m / 1e9:g} Gm"
    if m >= 1e6:
        return f"{m / 1e6:g} Mm"
    if m >= 1000:
        return f"{m / 1000:g} km"
    return f"{m:.0f} m"


def _draw_scale_legend(surface, scope, font):
    target_px = 120
    world_m = target_px / scope.scale_px_per_m
    if world_m <= 0:
        return
    exp = floor(log10(world_m))
    mantissa = world_m / (10 ** exp)
    if mantissa < 1.5:
        nice = 1
    elif mantissa < 3.5:
        nice = 2
    elif mantissa < 7.5:
        nice = 5
    else:
        nice = 10
    nice_m = nice * (10 ** exp)
    bar_px = nice_m * scope.scale_px_per_m
    x0 = scope.rect.left + 12
    y0 = scope.rect.bottom - 18
    pygame.draw.aaline(surface, T.TEXT_DIM, (x0, y0), (x0 + bar_px, y0))
    pygame.draw.aaline(surface, T.TEXT_DIM, (x0, y0 - 4), (x0, y0 + 4))
    pygame.draw.aaline(surface, T.TEXT_DIM, (x0 + bar_px, y0 - 4), (x0 + bar_px, y0 + 4))
    draw.draw_text(surface, font, _format_range(nice_m), (x0 + bar_px + 6, y0 - 6), T.TEXT_DIM)
