from expanse.sim.world import World
from expanse.sim.bodies import Ship, Side
from expanse.sim.vec import Vec2
from expanse.sim.drive import EpsteinDrive
from expanse.sim.ai import CorvetteAI
from expanse.sim.weapons import Magazine, PDC, PDCMode
from expanse.sim.events import SimEvent
from expanse.config import SIM_DT


def test_hostile_ai_burns_on_detection():
    w = World()
    # Place player burning 3 g so hostile detects it quickly at short range
    player = Ship(
        id=1, side=Side.PLAYER, name="Roci",
        pos=Vec2(0, 0), vel=Vec2(0, 0), heading=0.0,
        dry_mass=500_000.0, drive=EpsteinDrive(max_thrust_g=12.0, crew_safe_g=3.0),
        hull_hp=1000.0, hull_hp_max=1000.0,
        cmd_thrust_g=3.0,
    )
    hostile = Ship(
        id=2, side=Side.HOSTILE, name="MCRN",
        pos=Vec2(100_000.0, 0.0), vel=Vec2(0.0, 0.0), heading=3.14159,
        dry_mass=350_000.0, drive=EpsteinDrive(max_thrust_g=10.0, crew_safe_g=3.0),
        hull_hp=700.0, hull_hp_max=700.0,
        magazine=Magazine(torpedoes_remaining=4),
        pdcs=[PDC(id=10, mount="fore"), PDC(id=11, mount="aft")],
        pdc_mode=PDCMode.HOLD,
    )
    w.add_ship(player)
    w.add_ship(hostile)
    ai = CorvetteAI(ship_id=hostile.id)
    w.ais.append(ai)
    # Run until hostile transitions out of COAST (with a generous budget)
    for _ in range(int(60 / SIM_DT)):
        w.step(SIM_DT)
        if ai.phase != "COAST":
            break
    assert ai.phase in ("BURN", "FIGHT"), f"expected AI to engage, still in {ai.phase}"
    assert hostile.pdc_mode == PDCMode.AUTO_DEFEND, "AI should enable PDC AUTO_DEFEND"


def test_hostile_ai_fires_when_in_range():
    w = World()
    # Start them close so the AI enters FIGHT immediately after first detection.
    player = Ship(
        id=1, side=Side.PLAYER, name="Roci",
        pos=Vec2(0, 0), vel=Vec2(0, 0), heading=0.0,
        dry_mass=500_000.0, drive=EpsteinDrive(max_thrust_g=12.0, crew_safe_g=3.0),
        hull_hp=1000.0, hull_hp_max=1000.0,
        cmd_thrust_g=3.0,
        pdcs=[PDC(id=10, mount="fore", burst_cooldown_s=0.05, p_hit_at_1km=0.01, max_range_m=100.0)],
        pdc_mode=PDCMode.HOLD,  # don't intercept the torp in this test
    )
    hostile = Ship(
        id=2, side=Side.HOSTILE, name="MCRN",
        pos=Vec2(50_000.0, 0.0), vel=Vec2(0.0, 0.0), heading=3.14159,
        dry_mass=350_000.0, drive=EpsteinDrive(max_thrust_g=10.0, crew_safe_g=3.0),
        hull_hp=700.0, hull_hp_max=700.0,
        magazine=Magazine(torpedoes_remaining=4),
        pdc_mode=PDCMode.HOLD,
    )
    w.add_ship(player)
    w.add_ship(hostile)
    w.ais.append(CorvetteAI(ship_id=hostile.id))
    for _ in range(int(30 / SIM_DT)):
        w.step(SIM_DT)
        if any(e.kind == SimEvent.TORPEDO_LAUNCHED for e in w.events):
            break
    assert any(e.kind == SimEvent.TORPEDO_LAUNCHED for e in w.events), "hostile AI should launch a torpedo in range"
