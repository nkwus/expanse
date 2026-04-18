from __future__ import annotations
from math import pi, atan2, cos, sin

from .bodies import Ship, Side
from .vec import Vec2
from .integrator import step_kinematics
from .tracks import TrackTable, Classification
from .sensors import signature, detect_range, torpedo_signature
from .events import Event, SimEvent
from .weapons import Torpedo, PDCMode
from .guidance import torpedo_aim_heading
from .damage import apply_damage
from ..config import G0
from ..util.ids import IdGen
from ..util.rng import Rng


TORP_ENTITY_OFFSET = 100_000


class World:
    SENSOR_PERIOD_TICKS = 4  # 20 Hz sim / 4 = 5 Hz sensor update

    def __init__(self, seed: int = 0) -> None:
        self.ships: list[Ship] = []
        self.torpedoes: list[Torpedo] = []
        self.now_sim: float = 0.0
        self.track_tables: dict[Side, TrackTable] = {s: TrackTable() for s in Side}
        self.events: list[Event] = []
        self._tick_n: int = 0
        self._rng = Rng(seed)
        self._torp_id_gen = IdGen(start=1)
        self.ais: list = []
        self.outcome: str | None = None  # 'win' | 'loss' | 'stalemate'
        self._stalemate_ballistic_since: float | None = None
        self._sides_seen: set[Side] = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def add_ship(self, ship: Ship) -> None:
        self.ships.append(ship)
        self._sides_seen.add(ship.side)

    def player_ship(self) -> Ship | None:
        for s in self.ships:
            if s.side == Side.PLAYER and not s.destroyed:
                return s
        return None

    def player_tracks(self) -> TrackTable:
        return self.track_tables[Side.PLAYER]

    def emit(self, kind: SimEvent, message: str, payload: dict | None = None) -> None:
        self.events.append(Event(time=self.now_sim, kind=kind, message=message, payload=payload or {}))

    def fire_torpedo(self, shooter: Ship, target_track_id: int) -> Torpedo | None:
        """Launch a torpedo from `shooter` at the contact with the given track id.

        Returns the Torpedo on success, None if no tube ready, no magazine,
        shooter destroyed, or track unknown to the shooter's side.
        """
        if shooter.destroyed or shooter.magazine is None:
            return None
        mag = shooter.magazine
        if mag.torpedoes_remaining <= 0:
            return None
        tube = mag.ready_tube_index()
        if tube is None:
            return None
        table = self.track_tables[shooter.side]
        track = table.get_by_track_id(target_track_id)
        if track is None:
            return None
        # Muzzle offset ahead of shooter to avoid self-fuse
        ox = cos(shooter.heading) * 30.0
        oy = sin(shooter.heading) * 30.0
        torp = Torpedo(
            id=self._torp_id_gen.next(),
            side=shooter.side,
            pos=Vec2(shooter.pos.x + ox, shooter.pos.y + oy),
            vel=Vec2(shooter.vel.x, shooter.vel.y),
            heading=shooter.heading,
            mass=mag.torp_mass,
            thrust_g=mag.torp_thrust_g,
            fuel_s=mag.torp_fuel_s,
            warhead_yield=mag.torp_warhead,
            prox_fuse_radius=mag.torp_prox_m,
            target_track_id=track.track_id,
            spawn_time=self.now_sim,
        )
        self.torpedoes.append(torp)
        mag.torpedoes_remaining -= 1
        mag.tubes_cooldown_s[tube] = mag.reload_time_s
        self.emit(
            SimEvent.TORPEDO_LAUNCHED,
            f"{shooter.name} launch -> T{track.track_id:03d}",
            {"torp_id": torp.id, "shooter_id": shooter.id, "target_track": track.track_id},
        )
        return torp

    # ------------------------------------------------------------------
    # Main step
    # ------------------------------------------------------------------
    def step(self, dt: float) -> None:
        if self.outcome is not None:
            return
        self._tick_n += 1

        # AI
        for ai in self.ais:
            ai.tick(self)

        # Ships
        for ship in self.ships:
            if ship.destroyed:
                continue
            if ship.autopilot is not None:
                done = ship.autopilot.tick(ship, dt)
                if done:
                    ship.autopilot = None
            ship.drive.update(ship.cmd_thrust_g, dt)
            if ship.cmd_heading is not None:
                ship.heading, ship.ang_vel = _slew_heading(
                    ship.heading, ship.ang_vel, ship.cmd_heading,
                    ship.max_rot_rate, ship.max_rot_accel, dt,
                )
            thrust_a = ship.drive.current_g * G0
            accel = Vec2.from_angle(ship.heading, thrust_a) if thrust_a > 0 else Vec2(0.0, 0.0)
            ship.pos, ship.vel = step_kinematics(ship.pos, ship.vel, accel, dt)
            if ship.magazine is not None:
                ship.magazine.tick(dt)
            for pdc in ship.pdcs:
                if pdc.cooldown_remaining_s > 0.0:
                    pdc.cooldown_remaining_s = max(0.0, pdc.cooldown_remaining_s - dt)

        # Torpedoes
        self._step_torpedoes(dt)

        self.now_sim += dt

        if self._tick_n % self.SENSOR_PERIOD_TICKS == 0:
            self._sensor_tick()
            self._pdc_tick()

        self._check_end_conditions()

    # ------------------------------------------------------------------
    # Torpedoes
    # ------------------------------------------------------------------
    def _step_torpedoes(self, dt: float) -> None:
        still_alive: list[Torpedo] = []
        for torp in self.torpedoes:
            if not torp.alive:
                continue
            # Lifetime
            if self.now_sim - torp.spawn_time >= torp.lifetime_s:
                torp.alive = False
                self.emit(
                    SimEvent.TORPEDO_DETONATED,
                    f"torpedo #{torp.id} fuel/lifetime spent",
                    {"torp_id": torp.id, "reason": "expired"},
                )
                continue

            # Aim at sensed track (from shooter's side)
            table = self.track_tables[torp.side]
            track = table.get_by_track_id(torp.target_track_id) if torp.target_track_id else None
            if track is not None:
                torp.heading = _slew_heading_simple(
                    torp.heading,
                    torpedo_aim_heading(torp, track, self.now_sim),
                    torp.max_rot_rate, dt,
                )

            # Drive: burn while fuel remains
            if torp.fuel_s > 0.0:
                torp.fuel_s = max(0.0, torp.fuel_s - dt)
                thrust_a = torp.thrust_g * G0
                accel = Vec2.from_angle(torp.heading, thrust_a)
            else:
                accel = Vec2(0.0, 0.0)
            torp.pos, torp.vel = step_kinematics(torp.pos, torp.vel, accel, dt)

            # Proximity fuse against enemy ships (ground truth — contact fuse is physical)
            fused = False
            for ship in self.ships:
                if ship.destroyed or ship.side == torp.side:
                    continue
                d = (Vec2(ship.pos.x - torp.pos.x, ship.pos.y - torp.pos.y)).length()
                if d <= torp.prox_fuse_radius:
                    self.emit(
                        SimEvent.TORPEDO_DETONATED,
                        f"torpedo #{torp.id} hit {ship.name}",
                        {"torp_id": torp.id, "target_id": ship.id, "reason": "prox"},
                    )
                    apply_damage(self, ship, torp.warhead_yield, cause=f"torpedo #{torp.id}")
                    torp.alive = False
                    fused = True
                    break
            if fused:
                continue
            still_alive.append(torp)
        self.torpedoes = still_alive

    # ------------------------------------------------------------------
    # Sensors
    # ------------------------------------------------------------------
    def _sensor_tick(self) -> None:
        for side, table in self.track_tables.items():
            observer = self._primary_observer(side)
            if observer is None:
                continue
            # Ships
            for target in self.ships:
                if target is observer or target.destroyed or target.side == side:
                    continue
                self._try_detect_ship(side, table, observer, target)
            # Torpedoes (enemy only)
            for torp in self.torpedoes:
                if not torp.alive or torp.side == side:
                    continue
                self._try_detect_torpedo(side, table, observer, torp)
            dropped = table.decay(self.now_sim)
            if side == Side.PLAYER:
                for t in dropped:
                    self.emit(
                        SimEvent.CONTACT_LOST,
                        f"CTC T{t.track_id:03d}  lost",
                        {"track_id": t.track_id, "entity_id": t.entity_id},
                    )

    def _try_detect_ship(self, side, table, observer, target) -> None:
        sig = signature(target)
        r = detect_range(sig)
        d = (Vec2(target.pos.x - observer.pos.x, target.pos.y - observer.pos.y)).length()
        if d > r:
            return
        pos_noise_sigma = max(50.0, d * 0.005)
        vel_noise_sigma = 3.0
        sensed_pos = Vec2(
            target.pos.x + self._rng.gauss(0.0, pos_noise_sigma),
            target.pos.y + self._rng.gauss(0.0, pos_noise_sigma),
        )
        sensed_vel = Vec2(
            target.vel.x + self._rng.gauss(0.0, vel_noise_sigma),
            target.vel.y + self._rng.gauss(0.0, vel_noise_sigma),
        )
        track, was_new = table.update_from_detection(
            target.id, sensed_pos, sensed_vel, self.now_sim, Classification.SHIP,
        )
        if was_new and side == Side.PLAYER:
            bearing = _compass_bearing_deg(observer.pos, target.pos)
            self.emit(
                SimEvent.CONTACT_ACQUIRED,
                f"CTC T{track.track_id:03d}  brg {bearing:.0f}°  rng {d/1000:.0f} km",
                {"track_id": track.track_id, "entity_id": target.id},
            )

    def _try_detect_torpedo(self, side, table, observer, torp) -> None:
        sig = torpedo_signature(torp)
        r = detect_range(sig)
        d = (Vec2(torp.pos.x - observer.pos.x, torp.pos.y - observer.pos.y)).length()
        if d > r:
            return
        pos_noise_sigma = max(30.0, d * 0.003)
        vel_noise_sigma = 5.0
        sensed_pos = Vec2(
            torp.pos.x + self._rng.gauss(0.0, pos_noise_sigma),
            torp.pos.y + self._rng.gauss(0.0, pos_noise_sigma),
        )
        sensed_vel = Vec2(
            torp.vel.x + self._rng.gauss(0.0, vel_noise_sigma),
            torp.vel.y + self._rng.gauss(0.0, vel_noise_sigma),
        )
        eid = TORP_ENTITY_OFFSET + torp.id
        track, was_new = table.update_from_detection(
            eid, sensed_pos, sensed_vel, self.now_sim, Classification.TORPEDO,
        )
        if was_new and side == Side.PLAYER:
            bearing = _compass_bearing_deg(observer.pos, torp.pos)
            self.emit(
                SimEvent.TORPEDO_INBOUND,
                f"VAMPIRE T{track.track_id:03d}  brg {bearing:.0f}°  rng {d/1000:.0f} km",
                {"track_id": track.track_id, "torp_id": torp.id},
            )

    # ------------------------------------------------------------------
    # PDCs
    # ------------------------------------------------------------------
    def _pdc_tick(self) -> None:
        """AUTO_DEFEND: each ship's PDCs engage the most-threatening inbound torpedo."""
        for ship in self.ships:
            if ship.destroyed or not ship.pdcs:
                continue
            if ship.pdc_mode != PDCMode.AUTO_DEFEND:
                continue
            threat = self._select_pdc_threat(ship)
            if threat is None:
                continue
            for pdc in ship.pdcs:
                if pdc.cooldown_remaining_s > 0.0:
                    continue
                d = (Vec2(threat.pos.x - ship.pos.x, threat.pos.y - ship.pos.y)).length()
                if d > pdc.max_range_m:
                    continue
                p_hit = _pdc_hit_prob(pdc, d)
                if self._rng.random() < p_hit:
                    threat.alive = False
                    self.emit(
                        SimEvent.TORPEDO_DETONATED,
                        f"{ship.name} PDC killed torp #{threat.id}",
                        {"torp_id": threat.id, "shooter_id": ship.id, "reason": "pdc"},
                    )
                pdc.cooldown_remaining_s = pdc.burst_cooldown_s
                break  # one PDC fires per tick per ship; others stay warm

    def _select_pdc_threat(self, ship: Ship) -> Torpedo | None:
        best: Torpedo | None = None
        best_d = float("inf")
        for torp in self.torpedoes:
            if not torp.alive or torp.side == ship.side:
                continue
            d = (Vec2(torp.pos.x - ship.pos.x, torp.pos.y - ship.pos.y)).length()
            if d < best_d:
                best = torp
                best_d = d
        return best

    # ------------------------------------------------------------------
    def _primary_observer(self, side: Side) -> Ship | None:
        for s in self.ships:
            if s.side == side and not s.destroyed:
                return s
        return None

    # ------------------------------------------------------------------
    # Victory / loss / stalemate
    # ------------------------------------------------------------------
    STALEMATE_RANGE_M = 5_000_000.0
    STALEMATE_BALLISTIC_S = 300.0

    def _check_end_conditions(self) -> None:
        # Only scenarios that put BOTH sides on the board can win/lose/stalemate.
        if not ({Side.PLAYER, Side.HOSTILE} <= self._sides_seen):
            return
        player_alive = any(s.side == Side.PLAYER and not s.destroyed for s in self.ships)
        hostile_alive = any(s.side == Side.HOSTILE and not s.destroyed for s in self.ships)
        if not player_alive:
            self._finish("loss", "Ownship destroyed")
            return
        if not hostile_alive:
            self._finish("win", "All hostiles destroyed")
            return
        # Stalemate: far apart AND both ballistic (all drives cold, no torpedoes)
        players = [s for s in self.ships if s.side == Side.PLAYER and not s.destroyed]
        hostiles = [s for s in self.ships if s.side == Side.HOSTILE and not s.destroyed]
        if not players or not hostiles:
            return
        p = players[0]; h = hostiles[0]
        d2 = (p.pos.x - h.pos.x) ** 2 + (p.pos.y - h.pos.y) ** 2
        far = d2 > self.STALEMATE_RANGE_M * self.STALEMATE_RANGE_M
        ballistic = (p.drive.current_g < 0.01 and h.drive.current_g < 0.01 and not self.torpedoes)
        if far and ballistic:
            if self._stalemate_ballistic_since is None:
                self._stalemate_ballistic_since = self.now_sim
            elif self.now_sim - self._stalemate_ballistic_since >= self.STALEMATE_BALLISTIC_S:
                self._finish("stalemate", "Range > 5,000 km, both ballistic")
        else:
            self._stalemate_ballistic_since = None

    def _finish(self, outcome: str, message: str) -> None:
        if self.outcome is not None:
            return
        self.outcome = outcome
        self.emit(SimEvent.SCENARIO_END, f"{outcome.upper()}: {message}", {"outcome": outcome})


def _slew_heading(
    heading: float, ang_vel: float, target: float,
    max_rate: float, max_accel: float, dt: float,
) -> tuple[float, float]:
    diff = (target - heading + pi) % (2 * pi) - pi
    desired_rate = max(-max_rate, min(max_rate, diff / max(dt, 1e-6)))
    rate_diff = desired_rate - ang_vel
    accel_step = max_accel * dt
    if abs(rate_diff) <= accel_step:
        new_ang_vel = desired_rate
    else:
        new_ang_vel = ang_vel + accel_step * (1 if rate_diff > 0 else -1)
    new_heading = heading + new_ang_vel * dt
    new_heading = (new_heading + pi) % (2 * pi) - pi
    return new_heading, new_ang_vel


def _slew_heading_simple(heading: float, target: float, max_rate: float, dt: float) -> float:
    """Rate-limited heading update for torpedoes — no angular-velocity state."""
    diff = (target - heading + pi) % (2 * pi) - pi
    max_step = max_rate * dt
    if diff > max_step:
        diff = max_step
    elif diff < -max_step:
        diff = -max_step
    h = heading + diff
    return (h + pi) % (2 * pi) - pi


def _compass_bearing_deg(a: Vec2, b: Vec2) -> float:
    dx = b.x - a.x
    dy = b.y - a.y
    math_angle_deg = atan2(dy, dx) * 180.0 / pi
    bearing = (90.0 - math_angle_deg) % 360.0
    return bearing


def _pdc_hit_prob(pdc, range_m: float) -> float:
    """Linear falloff from p_hit_at_1km (at 1 km) to 0 (at max_range)."""
    if range_m >= pdc.max_range_m:
        return 0.0
    if range_m <= 1_000.0:
        return pdc.p_hit_at_1km
    span = pdc.max_range_m - 1_000.0
    if span <= 0.0:
        return pdc.p_hit_at_1km
    frac = (pdc.max_range_m - range_m) / span
    return pdc.p_hit_at_1km * max(0.0, min(1.0, frac))
