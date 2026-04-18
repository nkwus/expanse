from math import pi

from expanse.sim.world import World
from expanse.sim.bodies import Ship, Side
from expanse.sim.vec import Vec2
from expanse.sim.drive import EpsteinDrive
from expanse.sim.weapons import Magazine, PDC, PDCMode
from expanse.sim.tracks import Classification
from expanse.sim.events import SimEvent


def _mk_ship(id_, side, pos=Vec2(0, 0), vel=Vec2(0, 0), heading=0.0, **kw):
    return Ship(
        id=id_,
        side=side,
        name=f"ship-{id_}",
        pos=pos,
        vel=vel,
        heading=heading,
        dry_mass=400_000.0,
        drive=EpsteinDrive(),
        hull_hp=kw.pop("hull_hp", 1000.0),
        hull_hp_max=1000.0,
        magazine=kw.pop("magazine", None),
        pdcs=kw.pop("pdcs", []),
        pdc_mode=kw.pop("pdc_mode", PDCMode.HOLD),
    )


def test_fire_torpedo_requires_known_track():
    w = World()
    shooter = _mk_ship(1, Side.PLAYER, magazine=Magazine(torpedoes_remaining=5))
    w.add_ship(shooter)
    torp = w.fire_torpedo(shooter, target_track_id=999)
    assert torp is None
    assert shooter.magazine.torpedoes_remaining == 5  # not consumed


def test_fire_torpedo_consumes_tube_and_round():
    w = World()
    shooter = _mk_ship(1, Side.PLAYER, magazine=Magazine(torpedoes_remaining=5))
    enemy = _mk_ship(2, Side.HOSTILE, pos=Vec2(300_000.0, 0.0))
    w.add_ship(shooter)
    w.add_ship(enemy)
    # Seed a track manually so fire_torpedo has a target
    t, _ = w.track_tables[Side.PLAYER].update_from_detection(
        enemy.id, enemy.pos, enemy.vel, w.now_sim, Classification.SHIP,
    )
    torp = w.fire_torpedo(shooter, target_track_id=t.track_id)
    assert torp is not None
    assert shooter.magazine.torpedoes_remaining == 4
    # Exactly one tube on cooldown now
    on_cd = [c for c in shooter.magazine.tubes_cooldown_s if c > 0.0]
    assert len(on_cd) == 1
    # Launch event emitted
    assert any(e.kind == SimEvent.TORPEDO_LAUNCHED for e in w.events)


def test_torpedo_hits_stationary_target():
    w = World()
    shooter = _mk_ship(1, Side.PLAYER, magazine=Magazine(torpedoes_remaining=1))
    enemy = _mk_ship(2, Side.HOSTILE, pos=Vec2(20_000.0, 0.0), hull_hp=100.0)
    w.add_ship(shooter)
    w.add_ship(enemy)
    w.track_tables[Side.PLAYER].update_from_detection(
        enemy.id, enemy.pos, enemy.vel, w.now_sim, Classification.SHIP,
    )
    track = w.track_tables[Side.PLAYER].get_by_entity(enemy.id)
    w.fire_torpedo(shooter, target_track_id=track.track_id)
    # Step forward: 20 km with 15 g thrust should arrive well under 60 s
    for _ in range(int(120 / 0.05)):
        w.step(0.05)
        if enemy.destroyed:
            break
    assert enemy.destroyed, "torpedo should reach and destroy a 20 km stationary target"


def test_pdc_intercepts_close_torpedo():
    w = World(seed=42)
    shooter = _mk_ship(1, Side.HOSTILE, pos=Vec2(3_000.0, 0.0), magazine=Magazine(torpedoes_remaining=1))
    defender = _mk_ship(
        2, Side.PLAYER,
        pos=Vec2(0.0, 0.0),
        pdcs=[PDC(id=10, mount="fore", p_hit_at_1km=0.95, max_range_m=5_000.0, burst_cooldown_s=0.05)],
        pdc_mode=PDCMode.AUTO_DEFEND,
        hull_hp=500.0,
    )
    w.add_ship(defender)
    w.add_ship(shooter)
    # Give the shooter a track on the defender so it can aim
    w.track_tables[Side.HOSTILE].update_from_detection(
        defender.id, defender.pos, defender.vel, w.now_sim, Classification.SHIP,
    )
    tr = w.track_tables[Side.HOSTILE].get_by_entity(defender.id)
    w.fire_torpedo(shooter, target_track_id=tr.track_id)
    # Run until the torp is gone (killed or fused) or timeout
    for _ in range(int(15 / 0.05)):
        w.step(0.05)
        if not w.torpedoes:
            break
    assert not defender.destroyed, "PDC should have intercepted before impact"
    assert any(
        e.kind == SimEvent.TORPEDO_DETONATED and e.payload.get("reason") == "pdc"
        for e in w.events
    )
