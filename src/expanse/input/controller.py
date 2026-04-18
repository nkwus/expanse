from __future__ import annotations
from enum import Enum, auto
from math import atan2, pi
import pygame

from ..clock import GameClock
from ..sim.world import World
from ..sim.vec import Vec2
from ..sim.autopilot import MatchVelocity
from ..sim.weapons import PDCMode


class InputMode(Enum):
    IDLE = auto()
    HEADING_PICK = auto()
    THRUST_ENTRY = auto()
    FIRE_PICK = auto()  # placeholder for M4


class Controller:
    """Keyboard/mouse -> time controls + ownship commands.

    M2 scope: SET_HEADING (H then scope-click), SET_THRUST (T + digit),
    CUT_DRIVE (C), FLIP_AND_BURN (B), thrust +/- (`+`/`-`).
    """

    def __init__(self, clock: GameClock, world: World) -> None:
        self.clock = clock
        self.world = world
        self.mode: InputMode = InputMode.IDLE
        self._last_event_msg: str | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def prompt(self) -> str | None:
        if self.mode == InputMode.HEADING_PICK:
            return "HEADING: click scope to aim, Esc to cancel"
        if self.mode == InputMode.THRUST_ENTRY:
            return "THRUST: press 0-9 to set g (current capped by crew tolerance), Esc to cancel"
        if self.mode == InputMode.FIRE_PICK:
            return "FIRE: click a contact to launch a torpedo, Esc to cancel"
        return self._last_event_msg

    def handle_key(self, event: pygame.event.Event) -> bool:
        if event.type != pygame.KEYDOWN:
            return False
        k = event.key

        # Esc cancels any pending mode first
        if k == pygame.K_ESCAPE:
            if self.mode != InputMode.IDLE:
                self.mode = InputMode.IDLE
                self._flash("canceled")
                return True
            return False

        # THRUST_ENTRY: consume a digit, then return to IDLE
        ship = self.world.player_ship()
        if self.mode == InputMode.THRUST_ENTRY:
            digit = _digit_from_key(k)
            if digit is not None and ship is not None:
                ship.cmd_thrust_g = min(float(digit), ship.drive.max_thrust_g, ship.crew_g_tolerance)
                ship.autopilot = None
                self._flash(f"thrust {ship.cmd_thrust_g:.1f}g")
                self.mode = InputMode.IDLE
                return True
            # Any other key exits the mode silently
            self.mode = InputMode.IDLE
            return True

        # Time controls (only in IDLE to avoid stealing digits from entry modes)
        if k == pygame.K_SPACE:
            self.clock.toggle_pause(); return True
        if k in (pygame.K_1, pygame.K_KP_1): self.clock.set_multiplier_index(1); return True
        if k in (pygame.K_2, pygame.K_KP_2): self.clock.set_multiplier_index(2); return True
        if k in (pygame.K_3, pygame.K_KP_3): self.clock.set_multiplier_index(3); return True
        if k in (pygame.K_4, pygame.K_KP_4): self.clock.set_multiplier_index(4); return True
        if k == pygame.K_COMMA: self.clock.step_multiplier(-1); return True
        if k == pygame.K_PERIOD: self.clock.step_multiplier(+1); return True

        if ship is None:
            return False

        if k == pygame.K_h:
            self.mode = InputMode.HEADING_PICK
            return True
        if k == pygame.K_t:
            self.mode = InputMode.THRUST_ENTRY
            return True
        if k == pygame.K_c:
            ship.cmd_thrust_g = 0.0
            ship.autopilot = None
            self._flash("drive cut")
            return True
        if k == pygame.K_b:
            ship.autopilot = MatchVelocity(
                target_vel=Vec2(0.0, 0.0),
                thrust_g=ship.drive.crew_safe_g,
            )
            self._flash("flip-and-burn to zero velocity")
            return True
        if k == pygame.K_f:
            if ship.magazine is None or ship.magazine.torpedoes_remaining <= 0:
                self._flash("no torpedoes")
                return True
            if ship.magazine.ready_tube_index() is None:
                self._flash("all tubes reloading")
                return True
            self.mode = InputMode.FIRE_PICK
            return True
        if k == pygame.K_p:
            ship.pdc_mode = _cycle_pdc(ship.pdc_mode)
            self._flash(f"PDC {ship.pdc_mode}")
            return True
        if k in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
            new_g = min(ship.cmd_thrust_g + 1.0, ship.drive.max_thrust_g, ship.crew_g_tolerance)
            ship.cmd_thrust_g = new_g
            ship.autopilot = None
            self._flash(f"thrust {new_g:.1f}g")
            return True
        if k in (pygame.K_MINUS, pygame.K_KP_MINUS):
            ship.cmd_thrust_g = max(0.0, ship.cmd_thrust_g - 1.0)
            ship.autopilot = None
            self._flash(f"thrust {ship.cmd_thrust_g:.1f}g")
            return True

        return False

    def on_scope_click(self, button: int, world_pt: Vec2) -> None:
        ship = self.world.player_ship()
        if ship is None:
            return
        if self.mode == InputMode.HEADING_PICK and button == 1:
            dx = world_pt.x - ship.pos.x
            dy = world_pt.y - ship.pos.y
            if dx * dx + dy * dy < 1.0:
                return
            ship.cmd_heading = atan2(dy, dx)
            ship.autopilot = None
            self._flash(f"heading {self._bearing_str(ship.cmd_heading)}")
            self.mode = InputMode.IDLE
            return
        if self.mode == InputMode.FIRE_PICK and button == 1:
            track = self._nearest_track(world_pt)
            if track is None:
                self._flash("no contact near cursor")
                self.mode = InputMode.IDLE
                return
            torp = self.world.fire_torpedo(ship, track.track_id)
            if torp is None:
                self._flash("fire refused")
            else:
                self._flash(f"torpedo away -> T{track.track_id:03d}")
            self.mode = InputMode.IDLE

    def _nearest_track(self, world_pt: Vec2, max_range_m: float = 200_000.0):
        best = None
        best_d2 = max_range_m * max_range_m
        now = self.world.now_sim
        for t in self.world.player_tracks().all():
            p = t.predict_pos(max(0.0, now - t.last_seen_time))
            dx = p.x - world_pt.x
            dy = p.y - world_pt.y
            d2 = dx * dx + dy * dy
            if d2 < best_d2:
                best = t
                best_d2 = d2
        return best

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _flash(self, msg: str) -> None:
        self._last_event_msg = msg

    @staticmethod
    def _bearing_str(rad: float) -> str:
        bearing = (90.0 - (rad * 180.0 / pi)) % 360.0
        return f"{bearing:.0f}° bearing"


def _cycle_pdc(mode: str) -> str:
    order = [PDCMode.AUTO_DEFEND, PDCMode.HOLD, PDCMode.MANUAL]
    try:
        i = order.index(mode)
    except ValueError:
        return PDCMode.AUTO_DEFEND
    return order[(i + 1) % len(order)]


def _digit_from_key(k: int) -> int | None:
    mapping = {
        pygame.K_0: 0, pygame.K_KP_0: 0,
        pygame.K_1: 1, pygame.K_KP_1: 1,
        pygame.K_2: 2, pygame.K_KP_2: 2,
        pygame.K_3: 3, pygame.K_KP_3: 3,
        pygame.K_4: 4, pygame.K_KP_4: 4,
        pygame.K_5: 5, pygame.K_KP_5: 5,
        pygame.K_6: 6, pygame.K_KP_6: 6,
        pygame.K_7: 7, pygame.K_KP_7: 7,
        pygame.K_8: 8, pygame.K_KP_8: 8,
        pygame.K_9: 9, pygame.K_KP_9: 9,
    }
    return mapping.get(k)
