from expanse.sim.tracks import TrackTable, Classification
from expanse.sim.vec import Vec2


def test_new_track_gets_id():
    tt = TrackTable()
    t, is_new = tt.update_from_detection(42, Vec2(1, 2), Vec2(0, 0), 0.0, Classification.SHIP)
    assert is_new is True
    assert t.track_id == 1
    assert t.entity_id == 42
    assert t.confidence == 1.0


def test_second_update_same_entity_same_track():
    tt = TrackTable()
    t1, _ = tt.update_from_detection(42, Vec2(0, 0), Vec2(10, 0), 0.0, Classification.SHIP)
    t2, is_new = tt.update_from_detection(42, Vec2(10, 0), Vec2(10, 0), 1.0, Classification.SHIP)
    assert is_new is False
    assert t1.track_id == t2.track_id


def test_accel_estimation_from_velocity_change():
    tt = TrackTable()
    tt.update_from_detection(1, Vec2(0, 0), Vec2(0, 0), 0.0, Classification.SHIP)
    # Velocity changed by 10 m/s over 1 s -> accel sample 10 m/s^2
    t, _ = tt.update_from_detection(1, Vec2(0, 0), Vec2(10, 0), 1.0, Classification.SHIP)
    # With alpha=0.3, est_accel.x = 0*0.7 + 10*0.3 = 3.0
    assert abs(t.est_accel.x - 3.0) < 1e-6


def test_confidence_decays_then_drops():
    tt = TrackTable()
    tt.update_from_detection(1, Vec2(0, 0), Vec2(0, 0), 0.0, Classification.SHIP)
    assert tt.decay(5.0) == []  # fresh
    tt.decay(25.0)  # decaying
    t = tt.get_by_entity(1)
    assert t is not None and 0.0 < t.confidence < 1.0
    dropped = tt.decay(100.0)  # stale
    assert len(dropped) == 1 and dropped[0].entity_id == 1
    assert tt.get_by_entity(1) is None


def test_predict_pos_second_order():
    tt = TrackTable()
    tt.update_from_detection(1, Vec2(0, 0), Vec2(0, 0), 0.0, Classification.SHIP)
    t, _ = tt.update_from_detection(1, Vec2(0, 0), Vec2(10, 0), 1.0, Classification.SHIP)
    # est_accel.x ≈ 3 (from alpha)
    # predict forward 2s: x = 0 + 10*2 + 0.5*3*4 = 26
    p = t.predict_pos(2.0)
    assert abs(p.x - 26.0) < 1e-6
