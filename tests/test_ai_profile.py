from pathlib import Path

import pytest

from expanse.sim.ai_profile import Profile, load_profiles, default_profiles_path
from expanse.sim.weapons import PDCMode


def test_default_profiles_file_loads():
    profiles = load_profiles()
    assert "default" in profiles
    d = profiles["default"]
    assert isinstance(d, Profile)
    assert d.burn_g > 0.0
    assert d.salvo_range_m > 0.0
    assert d.salvo_count >= 1
    assert d.pdc_mode in {PDCMode.HOLD, PDCMode.AUTO_DEFEND, PDCMode.MANUAL}


def test_all_shipped_profiles_valid():
    profiles = load_profiles()
    # Personalities shown in the handover doc must all parse.
    for name in ("default", "aggressor", "cagey", "suicidal"):
        assert name in profiles, f"missing profile '{name}' in ai_profiles.toml"


def test_missing_field_raises(tmp_path: Path):
    bad = tmp_path / "bad.toml"
    bad.write_text(
        "[profiles.broken]\n"
        "burn_g = 2.0\n"
        # salvo_range_m intentionally omitted
        "salvo_count = 2\n"
        "salvo_cooldown_s = 30.0\n"
        "retreat_hull_frac = 0.3\n"
        'pdc_mode = "AUTO_DEFEND"\n'
    )
    with pytest.raises(ValueError, match="missing field"):
        load_profiles(bad)


def test_invalid_pdc_mode_raises(tmp_path: Path):
    bad = tmp_path / "bad.toml"
    bad.write_text(
        "[profiles.broken]\n"
        "burn_g = 2.0\n"
        "salvo_range_m = 500_000\n"
        "salvo_count = 2\n"
        "salvo_cooldown_s = 30.0\n"
        "retreat_hull_frac = 0.3\n"
        'pdc_mode = "NOT_A_REAL_MODE"\n'
    )
    with pytest.raises(ValueError):
        load_profiles(bad)


def test_env_var_override(tmp_path: Path, monkeypatch):
    custom = tmp_path / "custom.toml"
    custom.write_text(
        "[profiles.spicy]\n"
        "burn_g = 9.9\n"
        "salvo_range_m = 1_000_000\n"
        "salvo_count = 5\n"
        "salvo_cooldown_s = 10.0\n"
        "retreat_hull_frac = 0.1\n"
        'pdc_mode = "HOLD"\n'
    )
    monkeypatch.setenv("EXPANSE_AI_PROFILES", str(custom))
    assert default_profiles_path() == custom
    profiles = load_profiles()
    assert profiles["spicy"].burn_g == 9.9
    assert profiles["spicy"].pdc_mode == PDCMode.HOLD
