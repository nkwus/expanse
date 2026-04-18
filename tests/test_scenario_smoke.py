from expanse.scenarios import first_contact
from expanse.config import SIM_DT
from expanse.sim.events import SimEvent


def test_scenario_builds():
    world = first_contact.build()
    assert len(world.ships) == 2
    player = world.player_ship()
    assert player is not None
    assert player.name == "Rocinante"


def test_scenario_runs_headless_briefly():
    world = first_contact.build()
    # 60 sim seconds (20 Hz * 60 = 1200 ticks)
    for _ in range(1200):
        world.step(SIM_DT)
    # Hostile should have closed ~180 km (3 km/s * 60s)
    hostile = world.ships[1]
    # Its x position went from 1_200_000 toward origin at -3 km/s
    assert 1_000_000 < hostile.pos.x < 1_100_000


def test_scenario_reaches_outcome():
    """Autonomous run should produce a terminal outcome.

    Player sits silent; hostile AI coasts (passes wide of a cold-running
    Rocinante without detecting it) and eventually separates past the
    stalemate range. Ample sim-time budget because the ships are slow.
    """
    world = first_contact.build()
    # 3000 sim seconds is well past stalemate_range / hostile_speed + stalemate_ballistic_s
    for _ in range(int(3000 / SIM_DT)):
        world.step(SIM_DT)
        if world.outcome is not None:
            break
    assert world.outcome in ("win", "loss", "stalemate")
    assert any(e.kind == SimEvent.SCENARIO_END for e in world.events)
