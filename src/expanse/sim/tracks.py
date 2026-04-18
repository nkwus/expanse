from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto

from .vec import Vec2
from ..util.ids import IdGen


class Classification(Enum):
    UNKNOWN = auto()
    SHIP = auto()
    TORPEDO = auto()


@dataclass
class ContactTrack:
    track_id: int
    entity_id: int
    last_seen_pos: Vec2
    last_seen_vel: Vec2
    est_accel: Vec2
    last_seen_time: float
    first_seen_time: float
    confidence: float
    classification: Classification

    def predict_pos(self, dt: float) -> Vec2:
        p = self.last_seen_pos
        v = self.last_seen_vel
        a = self.est_accel
        return Vec2(
            p.x + v.x * dt + 0.5 * a.x * dt * dt,
            p.y + v.y * dt + 0.5 * a.y * dt * dt,
        )

    def predict_vel(self, dt: float) -> Vec2:
        return Vec2(
            self.last_seen_vel.x + self.est_accel.x * dt,
            self.last_seen_vel.y + self.est_accel.y * dt,
        )

    def age(self, now: float) -> float:
        return now - self.last_seen_time

    def intercept_point(self, shooter_pos: Vec2, projectile_speed: float, age: float = 0.0) -> Vec2:
        """Solve for predicted intercept assuming constant-velocity target.

        `age` is the time since `last_seen_time`; the target's state is advanced
        forward by `age` before solving so the shooter aims from where the target
        is *now*, not from where it was last observed. est_accel is used for
        this advance (not for the solver itself, which stays linear).
        """
        start_pos = self.predict_pos(age) if age > 0.0 else self.last_seen_pos
        v = self.predict_vel(age) if age > 0.0 else self.last_seen_vel
        rel = Vec2(start_pos.x - shooter_pos.x, start_pos.y - shooter_pos.y)
        a = v.x * v.x + v.y * v.y - projectile_speed * projectile_speed
        b = 2.0 * (rel.x * v.x + rel.y * v.y)
        c = rel.x * rel.x + rel.y * rel.y
        if abs(a) < 1e-9:
            if abs(b) < 1e-9:
                return start_pos
            t = -c / b
        else:
            disc = b * b - 4 * a * c
            if disc < 0:
                return start_pos
            sq = disc ** 0.5
            t1 = (-b - sq) / (2 * a)
            t2 = (-b + sq) / (2 * a)
            candidates = [t for t in (t1, t2) if t > 0]
            if not candidates:
                return start_pos
            t = min(candidates)
        return self.predict_pos(age + t)


class TrackTable:
    FRESH_WINDOW_S = 10.0
    STALE_AFTER_S = 40.0
    ACCEL_ALPHA = 0.3

    def __init__(self) -> None:
        self._tracks: dict[int, ContactTrack] = {}
        self._ids = IdGen(start=1)

    def update_from_detection(
        self,
        entity_id: int,
        pos: Vec2,
        vel: Vec2,
        now: float,
        classification: Classification,
    ) -> tuple[ContactTrack, bool]:
        t = self._tracks.get(entity_id)
        if t is None:
            tid = self._ids.next()
            t = ContactTrack(
                track_id=tid,
                entity_id=entity_id,
                last_seen_pos=pos,
                last_seen_vel=vel,
                est_accel=Vec2(0.0, 0.0),
                last_seen_time=now,
                first_seen_time=now,
                confidence=1.0,
                classification=classification,
            )
            self._tracks[entity_id] = t
            return t, True

        dt = now - t.last_seen_time
        if dt > 1e-6:
            sampled_a = Vec2(
                (vel.x - t.last_seen_vel.x) / dt,
                (vel.y - t.last_seen_vel.y) / dt,
            )
            a = self.ACCEL_ALPHA
            t.est_accel = Vec2(
                t.est_accel.x * (1 - a) + sampled_a.x * a,
                t.est_accel.y * (1 - a) + sampled_a.y * a,
            )
        t.last_seen_pos = pos
        t.last_seen_vel = vel
        t.last_seen_time = now
        t.classification = classification
        t.confidence = 1.0
        return t, False

    def decay(self, now: float) -> list[ContactTrack]:
        dropped: list[ContactTrack] = []
        for eid in list(self._tracks.keys()):
            t = self._tracks[eid]
            age = now - t.last_seen_time
            if age <= self.FRESH_WINDOW_S:
                t.confidence = 1.0
            elif age >= self.STALE_AFTER_S:
                dropped.append(self._tracks.pop(eid))
            else:
                span = self.STALE_AFTER_S - self.FRESH_WINDOW_S
                t.confidence = max(0.0, 1.0 - (age - self.FRESH_WINDOW_S) / span)
        return dropped

    def all(self) -> list[ContactTrack]:
        return list(self._tracks.values())

    def get_by_entity(self, entity_id: int) -> ContactTrack | None:
        return self._tracks.get(entity_id)

    def get_by_track_id(self, track_id: int) -> ContactTrack | None:
        for t in self._tracks.values():
            if t.track_id == track_id:
                return t
        return None
