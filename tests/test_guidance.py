from math import pi

from expanse.sim.guidance import torpedo_aim_heading
from expanse.sim.weapons import Torpedo
from expanse.sim.tracks import ContactTrack, Classification
from expanse.sim.vec import Vec2
from expanse.sim.bodies import Side


def _torp(pos=Vec2(0, 0), vel=Vec2(0, 0), heading=0.0) -> Torpedo:
    return Torpedo(id=1, side=Side.PLAYER, pos=pos, vel=vel, heading=heading)


def _track(pos, vel=Vec2(0, 0), a=Vec2(0, 0), t=0.0) -> ContactTrack:
    return ContactTrack(
        track_id=1, entity_id=1,
        last_seen_pos=pos, last_seen_vel=vel, est_accel=a,
        last_seen_time=t, first_seen_time=t,
        confidence=1.0, classification=Classification.SHIP,
    )


def test_fresh_launch_aims_roughly_at_target():
    t = _track(Vec2(1000.0, 0.0))
    torp = _torp(vel=Vec2(0, 0))  # slow -> fresh-launch branch
    h = torpedo_aim_heading(torp, t, now_sim=0.0)
    # Should point to +x
    assert abs(h) < 0.05


def test_lead_on_crossing_target():
    # Target moving +y at 500 m/s, torpedo fast enough to intercept
    t = _track(Vec2(1000.0, 0.0), vel=Vec2(0.0, 500.0))
    torp = _torp(vel=Vec2(1000.0, 0.0))  # moving along +x at 1 km/s
    h = torpedo_aim_heading(torp, t, now_sim=0.0)
    # Intercept should lead above +x-axis: heading above 0
    assert h > 0.05, f"expected positive lead angle, got {h}"
    # And not more than pi/2 (not firing backwards)
    assert h < pi / 2
