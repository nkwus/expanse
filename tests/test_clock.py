from expanse.clock import GameClock
from expanse.config import SIM_DT


def test_pause_no_ticks():
    c = GameClock()
    c.set_multiplier_index(0)
    assert c.advance(1.0) == 0
    assert c.now_sim == 0.0


def test_1x_ticks():
    c = GameClock()
    # 0.1s real at 1x should produce 2 ticks of 0.05s
    ticks = c.advance(0.1)
    assert ticks == 2
    assert abs(c.now_sim - 2 * SIM_DT) < 1e-9


def test_100x_ticks():
    c = GameClock()
    c.set_multiplier_index(3)  # 100x
    # 1/60 real s * 100x / 0.05 = 33.33 ticks -> 33
    ticks = c.advance(1.0 / 60.0)
    assert 32 <= ticks <= 34


def test_step_clamp():
    c = GameClock()
    c.set_multiplier_index(1)
    c.step_multiplier(10)  # should clamp to max
    assert c.multiplier == 1000.0
    c.step_multiplier(-10)  # clamp to min (pause)
    assert c.multiplier == 0.0


def test_toggle_pause_restores():
    c = GameClock()
    c.set_multiplier_index(3)  # 100x
    c.toggle_pause()
    assert c.multiplier == 0.0
    c.toggle_pause()
    assert c.multiplier == 100.0
