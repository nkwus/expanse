from __future__ import annotations
from dataclasses import dataclass

from .config import SIM_DT, MAX_TICKS_PER_FRAME, MULTIPLIERS


@dataclass
class GameClock:
    now_real: float = 0.0
    now_sim: float = 0.0
    multiplier: float = 1.0
    _sim_accum: float = 0.0
    _mult_idx: int = 1
    _saved_mult_idx: int = 1

    def advance(self, real_dt: float) -> int:
        self.now_real += real_dt
        if self.multiplier <= 0.0:
            return 0
        self._sim_accum += real_dt * self.multiplier
        ticks = int(self._sim_accum / SIM_DT)
        if ticks > MAX_TICKS_PER_FRAME:
            ticks = MAX_TICKS_PER_FRAME
            self._sim_accum = 0.0
        else:
            self._sim_accum -= ticks * SIM_DT
        self.now_sim += ticks * SIM_DT
        return ticks

    def set_multiplier_index(self, idx: int) -> None:
        idx = max(0, min(len(MULTIPLIERS) - 1, idx))
        self._mult_idx = idx
        self.multiplier = MULTIPLIERS[idx]

    def step_multiplier(self, delta: int) -> None:
        self.set_multiplier_index(self._mult_idx + delta)

    def toggle_pause(self) -> None:
        if self.multiplier > 0.0:
            self._saved_mult_idx = self._mult_idx if self._mult_idx > 0 else 1
            self.set_multiplier_index(0)
        else:
            self.set_multiplier_index(self._saved_mult_idx if self._saved_mult_idx > 0 else 1)

    @property
    def is_paused(self) -> bool:
        return self.multiplier <= 0.0

    @property
    def multiplier_label(self) -> str:
        if self.is_paused:
            return "PAUSED"
        m = self.multiplier
        if m >= 1.0:
            return f"{m:g}x"
        return f"{m:g}x"
