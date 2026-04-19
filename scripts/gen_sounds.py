"""Synthesize placeholder WAV clips for the two short sound effects.

Runtime deps: standard library only. Run once to refresh the bundled WAVs;
commit the output. Replace the resulting files with better-sourced clips
whenever — the audio engine just loads whatever is at the same paths.
"""
from __future__ import annotations
import math
import random
import struct
import wave
from pathlib import Path

SR = 44_100  # sample rate
OUT_DIR = Path(__file__).resolve().parent.parent / "assets" / "audio"


def _write_wav(path: Path, samples: list[float], target_peak: float = 0.95) -> None:
    """Write mono 16-bit PCM WAV from float samples in [-1, 1]. Peak-normalizes to target_peak."""
    peak = max(1e-9, max(abs(s) for s in samples))
    scale = target_peak / peak
    data = b"".join(struct.pack("<h", int(max(-32768, min(32767, s * scale * 32767)))) for s in samples)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data)


def _one_pole_lp(xs: list[float], cutoff_hz: float) -> list[float]:
    """Single-pole low-pass."""
    rc = 1.0 / (2 * math.pi * cutoff_hz)
    dt = 1.0 / SR
    a = dt / (rc + dt)
    ys: list[float] = []
    y = 0.0
    for x in xs:
        y += a * (x - y)
        ys.append(y)
    return ys


def _one_pole_hp(xs: list[float], cutoff_hz: float) -> list[float]:
    rc = 1.0 / (2 * math.pi * cutoff_hz)
    dt = 1.0 / SR
    a = rc / (rc + dt)
    ys: list[float] = []
    y_prev_in = 0.0
    y = 0.0
    for x in xs:
        y = a * (y + x - y_prev_in)
        y_prev_in = x
        ys.append(y)
    return ys


def gen_torpedo_launch(duration_s: float = 2.0) -> list[float]:
    """Two-part launch: a sequence of metal-on-metal mechanical events
    (hydraulic release -> tube door -> cradle separation -> bay slam),
    then a deep whoosh as the rocket exhaust grazes the hull and recedes."""
    rng = random.Random(0xC1A7)
    n = int(duration_s * SR)
    out = [0.0] * n

    def _impact(start_t: float, strength: float,
                freqs: list[float], decays: list[float]) -> None:
        """Metal-on-metal strike: broadband transient plus inharmonic damped sines."""
        start_i = int(start_t * SR)
        # Broadband attack — the actual contact, not a pure tone.
        trans_n = int(0.012 * SR)
        for j in range(trans_n):
            if start_i + j >= n:
                break
            env = math.exp(-j / (trans_n * 0.3))
            out[start_i + j] += strength * 1.3 * rng.gauss(0, 1) * env
        # Inharmonic metallic ring — each mode decays at its own rate.
        tail_n = min(int(1.0 * SR), n - start_i)
        for k, (f, d) in enumerate(zip(freqs, decays)):
            amp = strength * 0.55 / (1.0 + 0.25 * k)
            for j in range(tail_n):
                t = j / SR
                out[start_i + j] += amp * math.sin(2 * math.pi * f * t) * math.exp(-d * t)

    # --- Sequence of mechanical events (~1 s of metal moving) ---
    # 1) Hydraulic actuator release — deepest, heaviest.
    _impact(0.00, 1.7, [42, 97, 168, 262], [3.8, 6.0, 10.0, 16.0])
    # 2) Outer tube door opens — brighter mid clang.
    _impact(0.17, 1.0, [78, 145, 240, 380], [5.0, 8.0, 13.0, 20.0])
    # 3) Torp separates from cradle — low thud with rattle.
    _impact(0.40, 1.4, [32, 73, 128, 215], [3.2, 5.0, 8.0, 14.0])
    # 4) Bay slams shut behind it.
    _impact(0.68, 1.1, [58, 115, 198, 310], [4.5, 7.0, 11.0, 17.0])

    # --- Metal friction / sliding: torp body dragging through the tube ---
    friction_start = int(0.05 * SR)
    friction_n = int(0.55 * SR)
    f_noise = [rng.gauss(0, 1) for _ in range(friction_n)]
    friction = _one_pole_lp(_one_pole_hp(f_noise, 180), 1300)
    for i in range(friction_n):
        t = i / SR
        # Arc envelope: rise -> plateau -> release (a slide, not an impact).
        if t < 0.08:
            env = t / 0.08
        elif t < 0.35:
            env = 1.0
        else:
            env = max(0.0, 1.0 - (t - 0.35) / 0.15)
        # Irregular mechanical roughness — makes it sound like metal, not pink noise.
        mod = 0.55 + 0.45 * math.sin(2 * math.pi * 11 * t + 0.4 * math.sin(2 * math.pi * 3.5 * t))
        out[friction_start + i] += 0.75 * friction[i] * env * mod

    # --- Part B: deep whoosh — rocket exhaust through the hull, fading to vacuum ---
    whoosh_start = int(0.82 * SR)  # after the mechanical sequence finishes
    whoosh_n = n - whoosh_start
    w_noise = [rng.gauss(0, 1) for _ in range(whoosh_n)]
    whoosh = _one_pole_lp(_one_pole_hp(w_noise, 40), 280)
    r_noise = [rng.gauss(0, 1) for _ in range(whoosh_n)]
    rumble = _one_pole_lp(r_noise, 90)
    s_noise = [rng.gauss(0, 1) for _ in range(whoosh_n)]
    sub = _one_pole_lp(s_noise, 45)
    for i in range(whoosh_n):
        t = i / SR
        if t < 0.05:
            env = t / 0.05
        elif t < 0.18:
            env = 1.0 - 0.15 * (t - 0.05) / 0.13
        else:
            env = 0.85 * math.exp(-1.9 * (t - 0.18))
        out[whoosh_start + i] += 1.25 * whoosh[i] * env
        out[whoosh_start + i] += 1.00 * rumble[i] * env
        out[whoosh_start + i] += 0.85 * sub[i] * env

    # Global LPF — dark for hull-transmitted feel, but passes enough to keep metal character.
    out = _one_pole_lp(out, 1500)
    out = [math.tanh(1.0 * x) for x in out]
    fade_n = int(0.04 * SR)
    for i in range(n - fade_n, n):
        out[i] *= (n - i) / fade_n
    return out


def gen_pdc_burst(duration_s: float = 0.32, rpm: int = 1800) -> list[float]:
    """Heavy autocannon brrrrt — .50+ caliber rounds: noise crack plus bass thump per shot."""
    rng = random.Random(0x9D)
    n = int(duration_s * SR)
    out = [0.0] * n
    period = SR * 60 // rpm  # samples per round
    crack_len = int(0.008 * SR)    # 8 ms noise attack per round
    thump_len = int(0.030 * SR)    # 30 ms low-frequency body per round
    for start in range(0, n, period):
        amp = 0.85 + 0.3 * rng.random()  # slight per-round variance
        # Crack: broadband noise burst (muzzle transient).
        for j in range(crack_len):
            i = start + j
            if i >= n:
                break
            env = math.exp(-j / (crack_len * 0.45))
            out[i] += rng.gauss(0, 1) * env * amp
        # Thump: deep sine + harmonic, fast decay — the caliber-heavy body.
        for j in range(thump_len):
            i = start + j
            if i >= n:
                break
            t = j / SR
            body = math.sin(2 * math.pi * 55 * t) * math.exp(-40.0 * t)
            body += 0.5 * math.sin(2 * math.pi * 110 * t) * math.exp(-55.0 * t)
            out[i] += 0.8 * body * amp
    # Bandpass dropped way down: no top-end sparkle, all throat.
    out = _one_pole_lp(_one_pole_hp(out, 70), 2000)
    # Gentler saturation than before so the thump has dynamic range instead of
    # squaring off into a constant wall.
    out = [math.tanh(1.8 * x) for x in out]
    # Fade the last 20 ms so the brrrt tails off rather than clipping.
    fade_n = int(0.02 * SR)
    for i in range(n - fade_n, n):
        out[i] *= (n - i) / fade_n
    return out


def _brown_noise(n: int, seed: int) -> list[float]:
    """Leaky-integrator brown noise, peak-normalized to [-1, 1]."""
    rng = random.Random(seed)
    out = [0.0] * n
    y = 0.0
    for i in range(n):
        y = 0.995 * y + rng.gauss(0, 0.05)
        out[i] = y
    peak = max(1e-9, max(abs(x) for x in out))
    return [x / peak for x in out]


def _crackle(n: int, rate_hz: float, seed: int) -> list[float]:
    """Sparse exponentially-decaying noise pops — the SRB plume-shock crackle."""
    rng = random.Random(seed)
    out = [0.0] * n
    avg_gap = SR / rate_hz
    t = int(rng.expovariate(1.0 / avg_gap))
    while t < n:
        pop_len = int(rng.uniform(0.0015, 0.006) * SR)  # longer pops = more prominent
        amp = rng.uniform(0.7, 1.0)
        for j in range(pop_len):
            i = t + j
            if i >= n:
                break
            env = math.exp(-j / (pop_len * 0.4))
            out[i] += rng.gauss(0, 1) * env * amp
        t += int(rng.expovariate(1.0 / avg_gap))
    return _one_pole_hp(out, 1500)  # keep some body, not just tinny fizz


def gen_drive_rumble(duration_s: float = 4.0) -> list[float]:
    """Solid-rocket-booster rumble: chamber rumble + roar + plume crackle, looped."""
    rng = random.Random(0xD21E)
    fade_n = int(0.12 * SR)                  # crossfade at loop join
    total_n = int(duration_s * SR) + fade_n  # generate extra, trim after fade

    def _pk(xs: list[float]) -> list[float]:
        pk = max(1e-9, max(abs(x) for x in xs))
        return [x / pk for x in xs]

    # Sub-bass layer: two low sines give consistent bottom-end weight.
    sub = [math.sin(2*math.pi*38*t/SR) + 0.7*math.sin(2*math.pi*72*t/SR) for t in range(total_n)]
    sub = _pk(sub)
    # Brown noise low rumble (stacked LPF for steep roll-off).
    low = _pk(_one_pole_lp(_one_pole_lp(_brown_noise(total_n, seed=0xDEEF), 110), 110))
    mid_src = [rng.gauss(0, 1) for _ in range(total_n)]
    mid = _pk(_one_pole_lp(_one_pole_hp(mid_src, 140), 900))
    # Saturate the crackle layer before peak-norm so its RMS climbs toward the peaks —
    # perceptually turns sparse pops into a constant rough crackling texture.
    crack_raw = _crackle(total_n, rate_hz=600.0, seed=0xC2AC)
    crack = _pk([math.tanh(3.5 * x) for x in crack_raw])
    hiss_src = [rng.gauss(0, 1) for _ in range(total_n)]
    hiss = _pk(_one_pole_hp(hiss_src, 5000))

    # Slow "combustion breathing" LFO — integer cycles per loop so it seams cleanly.
    lfo_hz = 1.0 / duration_s * 3  # 3 full cycles per loop
    lfo = [1.0 + 0.09 * math.sin(2 * math.pi * lfo_hz * t / SR) for t in range(total_n)]

    out = [0.0] * total_n
    for i in range(total_n):
        # Layers are peak-normalized (crack is also pre-saturated) so these gains
        # directly control the mix balance.
        sig = (
            0.70 * sub[i]    # constant sub-bass weight
            + 0.55 * low[i]  # chaotic low rumble
            + 0.18 * mid[i]  # a touch of mid body
            + 1.10 * crack[i]  # front-and-center SRB plume crackle
            + 0.02 * hiss[i]  # barely there
        )
        out[i] = sig * lfo[i]
    # Very light tanh — lets crackle transients pop through.
    out = [math.tanh(0.55 * x) for x in out]

    # Crossfade: blend tail into head so the loop seam is inaudible.
    duration_n = total_n - fade_n
    for i in range(fade_n):
        a = i / fade_n
        out[i] = out[i] * a + out[duration_n + i] * (1.0 - a)
    return out[:duration_n]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    torp = gen_torpedo_launch()
    burst = gen_pdc_burst()
    rumble = gen_drive_rumble()
    _write_wav(OUT_DIR / "torpedo_launch.wav", torp)
    _write_wav(OUT_DIR / "pdc_burst.wav", burst)
    # Peak target 0.5 — keeps RMS ~-14 dB so the rumble doesn't swamp the PDC at 3 g.
    _write_wav(OUT_DIR / "drive_rumble.wav", rumble, target_peak=0.5)
    print(f"wrote {OUT_DIR / 'torpedo_launch.wav'} ({len(torp)} samples)")
    print(f"wrote {OUT_DIR / 'pdc_burst.wav'} ({len(burst)} samples)")
    print(f"wrote {OUT_DIR / 'drive_rumble.wav'} ({len(rumble)} samples)")


if __name__ == "__main__":
    main()
