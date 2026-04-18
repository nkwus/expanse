from __future__ import annotations
from dataclasses import dataclass, field
from math import atan2, pi

from .bodies import Ship, Side
from .vec import Vec2
from .autopilot import MatchVelocity, Autopilot
from .tracks import Classification
from .weapons import PDCMode


class CorvetteAI:
    """Scripted hostile captain.

    Phases:
      COAST  - ballistic until it sees the player
      BURN   - 2 g intercept burn toward last-known player position
      FIGHT  - launch salvos when inside range, PDCs AUTO_DEFEND
      RETREAT - hull below threshold -> flip-and-burn away from player
    """

    SALVO_RANGE_M = 600_000.0
    SALVO_COUNT = 2
    SALVO_COOLDOWN_S = 35.0
    RETREAT_HULL_FRAC = 0.3
    BURN_G = 2.0

    def __init__(self, ship_id: int) -> None:
        self.ship_id = ship_id
        self.phase: str = "COAST"
        self._last_salvo_at: float = -1e9
        self._salvo_remaining: int = 0
        self._salvo_target_track: int | None = None

    # ------------------------------------------------------------------
    def tick(self, world) -> None:
        ship = _find(world, self.ship_id)
        if ship is None or ship.destroyed:
            return
        ship.pdc_mode = PDCMode.AUTO_DEFEND

        # Retreat check
        if self.phase != "RETREAT" and ship.hull_hp_max > 0 and ship.hull_hp / ship.hull_hp_max < self.RETREAT_HULL_FRAC:
            self.phase = "RETREAT"
            self._enter_retreat(ship, world)
            return

        table = world.track_tables[Side.HOSTILE]
        tgt = _pick_ship_track(table)

        if self.phase == "COAST":
            if tgt is not None:
                self.phase = "BURN"
                self._enter_burn(ship, tgt)
            return

        if self.phase == "BURN":
            if tgt is None:
                return
            self._update_burn(ship, tgt)
            rng = _range_to(ship, tgt, world.now_sim)
            if rng <= self.SALVO_RANGE_M:
                self.phase = "FIGHT"
                self._salvo_remaining = self.SALVO_COUNT
                self._salvo_target_track = tgt.track_id
            return

        if self.phase == "FIGHT":
            if tgt is None:
                self.phase = "BURN"  # lost contact — press the burn
                return
            self._update_burn(ship, tgt)  # keep closing while in FIGHT
            self._fire_salvos(ship, tgt, world)
            return

        if self.phase == "RETREAT":
            # Autopilot set in _enter_retreat; nothing per-tick
            return

    # ------------------------------------------------------------------
    def _enter_burn(self, ship: Ship, track) -> None:
        ship.autopilot = None
        ship.cmd_heading = _bearing_to(ship.pos, track.last_seen_pos)
        ship.cmd_thrust_g = min(self.BURN_G, ship.drive.max_thrust_g, ship.crew_g_tolerance)

    def _update_burn(self, ship: Ship, track) -> None:
        if ship.autopilot is not None:
            return  # let standing orders run uninterrupted
        ship.cmd_heading = _bearing_to(ship.pos, track.last_seen_pos)
        ship.cmd_thrust_g = min(self.BURN_G, ship.drive.max_thrust_g, ship.crew_g_tolerance)

    def _fire_salvos(self, ship: Ship, track, world) -> None:
        now = world.now_sim
        if self._salvo_remaining <= 0:
            if now - self._last_salvo_at > self.SALVO_COOLDOWN_S:
                self._salvo_remaining = self.SALVO_COUNT
                self._salvo_target_track = track.track_id
            else:
                return
        mag = ship.magazine
        if mag is None or mag.torpedoes_remaining <= 0 or mag.ready_tube_index() is None:
            return
        torp = world.fire_torpedo(ship, self._salvo_target_track or track.track_id)
        if torp is not None:
            self._salvo_remaining -= 1
            self._last_salvo_at = now

    def _enter_retreat(self, ship: Ship, world) -> None:
        table = world.track_tables[Side.HOSTILE]
        tgt = _pick_ship_track(table)
        if tgt is not None:
            away = Vec2(ship.pos.x - tgt.last_seen_pos.x, ship.pos.y - tgt.last_seen_pos.y)
            if away.length() > 1.0:
                escape_vel = Vec2(
                    away.x / away.length() * 8000.0,
                    away.y / away.length() * 8000.0,
                )
                ship.autopilot = MatchVelocity(
                    target_vel=escape_vel,
                    thrust_g=min(ship.drive.crew_safe_g, ship.drive.max_thrust_g),
                )
                return
        # Fallback: just cut drive
        ship.cmd_thrust_g = 0.0


# ----------------------------------------------------------------------
def _find(world, ship_id: int) -> Ship | None:
    for s in world.ships:
        if s.id == ship_id:
            return s
    return None


def _pick_ship_track(table):
    best = None
    best_conf = -1.0
    for t in table.all():
        if t.classification != Classification.SHIP:
            continue
        if t.confidence > best_conf:
            best = t
            best_conf = t.confidence
    return best


def _bearing_to(a: Vec2, b: Vec2) -> float:
    return atan2(b.y - a.y, b.x - a.x)


def _range_to(ship: Ship, track, now: float) -> float:
    age = max(0.0, now - track.last_seen_time)
    p = track.predict_pos(age)
    dx = p.x - ship.pos.x
    dy = p.y - ship.pos.y
    return (dx * dx + dy * dy) ** 0.5
