from expanse.sim.world import World
from expanse.sim.bodies import Ship, Side
from expanse.sim.vec import Vec2
from expanse.sim.drive import EpsteinDrive
from expanse.sim.damage import apply_damage
from expanse.sim.events import SimEvent


def _mk(id_, hp=200.0):
    return Ship(
        id=id_, side=Side.PLAYER, name=f"s{id_}",
        pos=Vec2(0, 0), vel=Vec2(0, 0), heading=0.0,
        dry_mass=100_000.0, drive=EpsteinDrive(),
        hull_hp=hp, hull_hp_max=hp,
    )


def test_damage_reduces_hull_no_destroy():
    w = World()
    s = _mk(1, hp=500)
    w.add_ship(s)
    destroyed = apply_damage(w, s, 200, cause="test")
    assert not destroyed
    assert s.hull_hp == 300
    assert s.destroyed is False
    assert not any(e.kind == SimEvent.SHIP_DESTROYED for e in w.events)


def test_damage_destroys_and_emits():
    w = World()
    s = _mk(1, hp=100)
    w.add_ship(s)
    destroyed = apply_damage(w, s, 400, cause="torpedo")
    assert destroyed
    assert s.destroyed is True
    assert s.hull_hp == 0.0
    assert any(e.kind == SimEvent.SHIP_DESTROYED for e in w.events)
