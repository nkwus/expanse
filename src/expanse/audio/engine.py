from __future__ import annotations
import math
from pathlib import Path

import pygame

from ..sim.events import SimEvent


_AUDIO_DIR = Path(__file__).resolve().parents[3] / "assets" / "audio"


class AudioEngine:
    """Ownship SFX: continuous drive rumble + torpedo / PDC one-shots.

    Consumes `world.events` via a monotonically advancing cursor and
    filters on `payload["shooter_id"] == ownship.id` so enemy fire is silent.
    Rumble volume tracks live thrust as a fraction of max.
    """

    RUMBLE_K = 0.35              # exp-saturation rate: bigger = quicker rise, earlier asymptote
    RUMBLE_SMOOTHING = 0.15      # per-frame lerp toward target volume
    TORP_VOL = 0.8
    PDC_VOL = 1.0

    def __init__(self) -> None:
        self._available = False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44_100, size=-16, channels=2, buffer=512)
        except pygame.error:
            return
        try:
            self._torp = pygame.mixer.Sound(str(_AUDIO_DIR / "torpedo_launch.wav"))
            self._pdc = pygame.mixer.Sound(str(_AUDIO_DIR / "pdc_burst.wav"))
            self._rumble = pygame.mixer.Sound(str(_AUDIO_DIR / "drive_rumble.wav"))
        except (pygame.error, FileNotFoundError):
            return
        self._torp.set_volume(self.TORP_VOL)
        self._pdc.set_volume(self.PDC_VOL)
        # Reserve channel 0 for the looping rumble so one-shots never steal it.
        pygame.mixer.set_reserved(1)
        self._rumble_channel = pygame.mixer.Channel(0)
        self._rumble_channel.set_volume(0.0)
        self._rumble_channel.play(self._rumble, loops=-1)
        self._event_cursor = 0
        self._available = True

    def tick(self, world) -> None:
        if not self._available:
            return
        ownship = world.player_ship()
        ownship_id = ownship.id if ownship is not None else None
        events = world.events
        while self._event_cursor < len(events):
            ev = events[self._event_cursor]
            self._event_cursor += 1
            if ownship_id is None or ev.payload.get("shooter_id") != ownship_id:
                continue
            if ev.kind is SimEvent.TORPEDO_LAUNCHED:
                self._torp.play()
            elif ev.kind is SimEvent.PDC_FIRED:
                self._pdc.play()
        if ownship is None or ownship.destroyed or ownship.drive.current_g <= 0.0:
            target = 0.0
        else:
            # Exponential saturation: sharp rise through cruise thrust (1-3 g),
            # asymptoting toward 1.0 as g climbs to combat burns. Absolute g so
            # identical g sounds identical across ships regardless of max_thrust.
            target = 1.0 - math.exp(-self.RUMBLE_K * ownship.drive.current_g)
        cur = self._rumble_channel.get_volume()
        self._rumble_channel.set_volume(cur + (target - cur) * self.RUMBLE_SMOOTHING)

    def shutdown(self) -> None:
        if not self._available:
            return
        self._rumble_channel.stop()
        pygame.mixer.quit()
        self._available = False
