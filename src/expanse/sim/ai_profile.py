from __future__ import annotations
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .weapons import PDCMode


_PDC_MODE_NAMES = {"HOLD", "AUTO_DEFEND", "MANUAL"}


@dataclass(frozen=True)
class Profile:
    name: str
    burn_g: float
    salvo_range_m: float
    salvo_count: int
    salvo_cooldown_s: float
    retreat_hull_frac: float
    pdc_mode: str  # underlying value from PDCMode (e.g. "AUTO")


def load_profiles(path: str | os.PathLike | None = None) -> dict[str, Profile]:
    resolved = Path(path) if path is not None else default_profiles_path()
    with open(resolved, "rb") as f:
        raw = tomllib.load(f)
    profiles_raw = raw.get("profiles") or {}
    if not profiles_raw:
        raise ValueError(f"no [profiles.*] entries found in {resolved}")
    out: dict[str, Profile] = {}
    for name, body in profiles_raw.items():
        try:
            mode_name = body["pdc_mode"]
            if mode_name not in _PDC_MODE_NAMES:
                raise ValueError(
                    f"pdc_mode must be one of {sorted(_PDC_MODE_NAMES)}, got {mode_name!r}"
                )
            out[name] = Profile(
                name=name,
                burn_g=float(body["burn_g"]),
                salvo_range_m=float(body["salvo_range_m"]),
                salvo_count=int(body["salvo_count"]),
                salvo_cooldown_s=float(body["salvo_cooldown_s"]),
                retreat_hull_frac=float(body["retreat_hull_frac"]),
                pdc_mode=getattr(PDCMode, mode_name),
            )
        except KeyError as e:
            raise ValueError(f"profile '{name}' missing field {e}") from None
        except (TypeError, ValueError) as e:
            raise ValueError(f"profile '{name}' has invalid field: {e}") from None
    return out


def default_profiles_path() -> Path:
    env = os.environ.get("EXPANSE_AI_PROFILES")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "data" / "ai_profiles.toml"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "could not locate data/ai_profiles.toml; set EXPANSE_AI_PROFILES to override"
    )
