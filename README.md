# Expanse — Tactical Space Combat (MVP)

A single-ship, top-down, real-time tactical combat game inspired by the
ship-to-ship engagements in *The Expanse*. You are the CO of the Rocinante;
one scenario ships with the MVP: `first_contact` — Roci vs a Martian corvette.

This document is the handover. It explains how to run the game, how the
code is laid out, **why** it's laid out that way, and the invariants a new
dev must not violate.

---

## 1. Quick start

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/) (any recent version).

```bash
uv sync                       # install deps into .venv
uv run python main.py         # launch the game
uv run pytest                 # run the 36-test suite
```

If `uv` isn't available, a `python -m venv` + `pip install -e .` flow
works too — the project uses a standard `pyproject.toml` with `hatchling`.

### Controls

| Key              | Action                                              |
|------------------|-----------------------------------------------------|
| `Space`          | Pause / resume                                      |
| `1`–`4`          | Time multiplier (1x / 10x / 100x / 1000x)           |
| `,` / `.`        | Step multiplier down / up                           |
| `H`              | Heading: then click anywhere on scope to aim        |
| `T` then `0`–`9` | Thrust in g (clamped by crew tolerance)             |
| `+` / `-`        | Nudge thrust by 1 g                                 |
| `C`              | Cut drive (zero thrust, clear autopilot)            |
| `B`              | Flip-and-burn to zero velocity (autopilot)          |
| `F`              | Fire torpedo: then click a contact                  |
| `P`              | Cycle PDC mode (AUTO / HOLD / MANUAL)               |
| Wheel, `[`/`]`   | Zoom scope                                          |
| `F1`             | Help overlay                                        |
| `Esc`            | Cancel pending command (or exit after scenario end) |

---

## 2. The 60-second architecture

Three modules, one rule:

```text
sim/        pure physics and game state. No pygame. No I/O. Deterministic.
render/     reads sim state. Never mutates it.
input/      turns pygame events into ship commands. Never touches sim directly.
app.py      the one file that wires all three together.
```

Keeping those boundaries hard-edged is what lets the sim be unit-testable
without a display, lets the renderer be replaced later (web? terminal?),
and lets the multiplayer/AI-opponent future stay open.

---

## 3. The two rules that matter most

### Rule 1 — The stealth invariant

> **The UI reads from `world.player_tracks()`, never from `world.ships`.**

The world has two parallel states:

- **Ground truth** — `World.ships`, `World.torpedoes`. Where things actually are.
- **Per-side sensor picture** — `World.track_tables[side]`, a `TrackTable` of
  `ContactTrack` records populated by passive thermal sensors.

The scope, the contact list, and the torpedo guidance all read from
the TrackTable. If you ever find yourself writing `world.ships[0].pos` in
a renderer or an AI, you are breaking the game's core stealth mechanic:
the player should not know where a cold-running enemy is until the
sensor sees them.

The one deliberate exception: **the player's own ownship** is drawn from
ground truth in `render/scope.py` (you always know where you are), and
**your own torpedoes** are drawn from truth (you know what you launched).
Enemy torpedoes ("VAMPIRE") are detected via the same thermal pipeline
and appear as tracks on the scope with a triangle glyph.

### Rule 2 — The tick is fixed

> **`SIM_DT = 0.05` (20 Hz). It never varies. Time compression works by
> running more ticks per frame, not by scaling `dt`.**

`src/expanse/clock.py` translates `real_dt × multiplier → n whole sim
ticks` with sub-tick remainder carried forward. This means:

- Physics stays stable at 1000x because every step is still `0.05s`.
- The integrator, the autopilot slew, the PDC p_hit — nothing has to
  handle a surprise huge `dt`.
- A hard cap (`MAX_TICKS_PER_FRAME = 2000` in [clock.py](src/expanse/clock.py))
  stops a stalled frame from spiraling the multiplier.

Consequence for new code: **do not** make physics depend on elapsed
wall-clock time; always use `dt`, which will always be `SIM_DT`.

---

## 4. Directory map

```text
main.py                      entry point (tiny)
pyproject.toml               pygame-ce + pytest; src/ layout
src/expanse/
  app.py                     App.run() — event loop
  clock.py                   GameClock: multiplier + sub-stepping
  config.py                  SIM_DT, window size, palette, range rings
  sim/
    vec.py                   frozen Vec2 with slots — + - * / dot length angle
    integrator.py            semi-implicit Euler
    drive.py                 EpsteinDrive: rate-limited spool to commanded g
    bodies.py                Ship dataclass, Side enum
    weapons.py               Torpedo, PDC, Magazine, PDCMode
    guidance.py              torpedo lead-pursuit against a sensed track
    autopilot.py             standing orders: MatchVelocity, HoldHeading
    sensors.py               signature(ship), detect_range(sig)
    tracks.py                ContactTrack (predict_pos / intercept_point),
                             TrackTable (confidence decay)
    damage.py                apply_damage() — single choke point for HP loss
    events.py                SimEvent enum + Event dataclass
    ai.py                    CorvetteAI (coast/burn/fight/retreat FSM)
    world.py                 World.step() — the tick function
  render/
    renderer.py              panel layout + per-frame draw
    scope.py                 the tactical scope (pan/zoom, ownship, tracks)
    panels.py                top bar, status MFD, contact list, event log,
                             command bar
    draw.py                  primitives: dashed circle, arrow, text align
    theme.py                 palette + fonts
  input/
    controller.py            keyboard / scope-click -> ship commands;
                             mode state for heading-pick, thrust-entry, fire-pick
  scenarios/
    first_contact.py         the MVP encounter
  util/
    ids.py                   monotonic IdGen
    rng.py                   seeded Random wrapper
tests/                       36-case pytest suite
```

---

## 5. Tick anatomy (read once, refer back forever)

`World.step(dt)` in [src/expanse/sim/world.py](src/expanse/sim/world.py)
runs **once per sim tick** at 20 Hz. The order matters:

1. **Outcome short-circuit.** If the scenario has ended, return immediately.
2. **AI tick.** Each registered AI reads the world's sensed state and sets
   its ship's `cmd_heading` / `cmd_thrust_g` / autopilot.
3. **Per-ship update:**
   - Autopilot tick (may clear itself by returning True).
   - Drive spool: `EpsteinDrive.update(cmd_thrust_g, dt)`.
   - Heading slew toward `cmd_heading` with angular-velocity + accel limits.
   - Integrate position/velocity with semi-implicit Euler.
   - Magazine cooldown tick, PDC cooldown tick.
4. **Per-torpedo update:** lifetime, guidance (lead-pursuit against its
   own side's TrackTable — **not** ground truth), drive burn, integrate,
   proximity-fuse check against enemy ships → `apply_damage`.
5. `now_sim += dt`.
6. **Every 4 ticks (5 Hz) — sensor tick:** for each side, the primary
   observer scans all enemy ships + torpedoes. Anything inside
   `detect_range(sig)` becomes a detection, with noise added, feeding
   `TrackTable.update_from_detection`. The table's est_accel updates via
   exponential smoothing. Stale tracks decay and get dropped.
7. **Every 4 ticks — PDC tick:** each ship in AUTO_DEFEND finds the
   nearest hostile torpedo inside `max_range_m` and rolls `p_hit`
   (linearly falling from `p_hit_at_1km` to 0 at max range).
8. **End-conditions check:** loss if player destroyed, win if all hostiles
   destroyed, stalemate if range > 5,000 km AND both ballistic for 300s.

---

## 6. The track prediction model (the Expanse feel)

Every `ContactTrack` in a TrackTable stores:

- `last_seen_pos`, `last_seen_vel` — the most recent sensed sample.
- `est_accel` — **exponentially smoothed** from successive velocity samples,
  `α = 0.3`. Smoothing rejects sensor jitter while staying responsive when
  a target suddenly lights its drive.
- `last_seen_time`, `first_seen_time`, `confidence`, `classification`.

From that, three derived methods power the entire UI/weapon loop:

- `predict_pos(dt)` — second-order extrapolation `p + v·dt + ½a·dt²`.
- `predict_vel(dt)` — linear velocity extrapolation.
- `intercept_point(shooter_pos, projectile_speed)` — quadratic solve for
  the lead point, assuming **constant** target velocity (the accel term
  is applied afterwards by the guidance code as a correction).

The predicted-trajectory dashed line you see on the scope, the torpedo
lead solution, and the AI's range-to-target calculation **all come from
these methods**. That's deliberate: when the enemy lights their drive,
the curve on the scope and the torpedo's pursuit both shift
simultaneously — which is what makes the combat feel like the show.

### Why a simple smoothed estimator instead of a Kalman filter?

Because sensor noise is small relative to the accelerations we care
about (a 3g burn is ~29 m/s²; sensor velocity noise σ is 3 m/s), an EMA
is sufficient, readable, and trivially testable. Swapping in a Kalman
filter later is a local change inside `TrackTable.update_from_detection`.

---

## 7. Sensor model

See [src/expanse/sim/sensors.py](src/expanse/sim/sensors.py).

```text
signature(ship)     = max(HULL_FLOOR_SIG, hull_size_sig)
                    + DRIVE_SIG_COEFF * current_g * dry_mass
detect_range(sig)   = BASE_DETECT_RANGE_M * sqrt(sig / MIN_SIG)
```

Concrete numbers for the `first_contact` scenario:

- Ballistic Rocinante: sig ≈ 1, detect range ≈ 50 km.
- Rocinante at 3g: sig ≈ 15,001, detect range ≈ **~6,100 km**.
- 2g Martian corvette: sig ≈ 7,001, detect range ≈ **~4,180 km**.

That gap is the stealth mechanic. A cold ship is essentially invisible
past 50 km. The moment you light the drive, the other side sees you
from across the engagement space. Every maneuver decision in the game
comes out of managing that asymmetry.

Passive thermal is the **only** sensor modality in v1. Active radar,
IFF, EW, and chaff are deferred — see §11.

---

## 8. Commands, autopilot, and standing orders

Input is one-shot commands (set heading, set thrust, cut drive) **or**
standing orders (autopilot). Autopilots are per-tick state machines on
the ship object: while `ship.autopilot` is not None, its `.tick(ship, dt)`
runs before drive/heading update and can set `cmd_heading` / `cmd_thrust_g`.
Autopilots return `True` when satisfied, which clears the standing order.

Currently implemented:

- `MatchVelocity(target_vel, thrust_g)` — the flip-and-burn. Aligns to
  the required delta-v direction, holds thrust until velocity is within
  `epsilon_mps` of target.
- `HoldHeading(heading)` — points at a bearing; no thrust.

To add a new autopilot, subclass `Autopilot` in
[src/expanse/sim/autopilot.py](src/expanse/sim/autopilot.py) and assign
an instance to `ship.autopilot`. The renderer picks up `ship.autopilot.label`
automatically for the status panel's `AUTO` line.

---

## 9. Walk-through: torpedo lifecycle

Because this is the most cross-cutting flow in the codebase:

1. **Player presses `F`** → `Controller.handle_key` checks the magazine
   has rounds and a ready tube, enters `FIRE_PICK` mode.
2. **Player clicks a contact on the scope** → `Controller.on_scope_click`
   picks the nearest track to the click position (within 200 km) and
   calls `World.fire_torpedo(ship, track_id)`.
3. **`World.fire_torpedo`** creates a `Torpedo`, debits the magazine,
   sets the chosen tube's cooldown, emits `TORPEDO_LAUNCHED`.
4. **Each tick, `World._step_torpedoes`:**
   - Refreshes the torpedo's onboard seeker view of the target with
     noise that scales with *torp-to-target* range — so a launched
     torpedo resolves its prey more precisely than the launching ship
     ever did. If the target entity is gone, falls back to the ship's
     track table (and flies blind if that too is stale — a consequence
     of Rule 1).
   - Computes `torpedo_aim_heading(torp, view, now)` — proportional
     navigation against the sensed target, `N = 4`.
   - Rate-limits the heading change by `torp.max_rot_rate`.
   - Burns fuel, integrates kinematics.
   - Proximity fuse: sweeps the line segments torp and ship traced
     over the tick; if the minimum separation falls within
     `prox_fuse_radius`, detonate → `apply_damage` → emit
     `TORPEDO_DETONATED`.
5. **Sensor tick** sees the hot torpedo as a `TORPEDO`-classified track
   on the other side's TrackTable → `TORPEDO_INBOUND` ("VAMPIRE") event.
6. **PDC tick** on the defending ship picks the nearest hostile torpedo
   inside range and rolls `p_hit`. On success, the torpedo is killed
   and a `TORPEDO_DETONATED` (reason: "pdc") event fires.

If you want to trace any bug here, the order of events above is the
order to set breakpoints.

---

## 10. How to add things

### A new scenario

Create `src/expanse/scenarios/<name>.py` with a `build() -> World`
function. Mirror `first_contact.py`. Register the scenario by swapping
the import in [src/expanse/app.py](src/expanse/app.py). (A scenario
selection menu is deferred work — see §11.)

### A new ship class

Today `Ship` is one dataclass. For distinct classes, the cheapest path
is a factory function in the scenario module that returns a `Ship` with
the right `drive`, `hull_hp`, `magazine`, and `pdcs`. If you find
yourself needing per-class behavior (e.g., different PDC layouts),
consider a small `ShipClass` spec struct rather than subclassing `Ship`.

### A new weapon

1. Add a dataclass to [src/expanse/sim/weapons.py](src/expanse/sim/weapons.py).
2. Give `World` a list of instances + an id generator.
3. Add a per-tick update in `World.step`.
4. Wire it into the sensor tick if it should show up on tracks.
5. Wire a fire-control command in `Controller` and a picker mode if
   it needs target designation.

### A new AI behavior

Add a class to [src/expanse/sim/ai.py](src/expanse/sim/ai.py) with a
`tick(world)` method. Append an instance to `world.ais` in the
scenario builder. Keep the AI reading from `world.track_tables[own_side]`,
not `world.ships` — same stealth rule applies to computer opponents.

---

## 11. Explicitly deferred (not in v1)

None of these are "wouldn't work" — they're "chose not to include to keep
the MVP shippable." Hooks are preserved where it mattered.

| Deferred                 | Hook preserved                                        |
|--------------------------|-------------------------------------------------------|
| Light-lag                | `sensors.query(observer, now)` already takes `now`    |
| 3D / z-axis              | Vec2 would become Vec3; scope is top-down only        |
| Multiple ship classes    | Scenario builds Ships directly — swap factories       |
| Active radar, EW, chaff  | Sensors are one function call; add modalities there   |
| Propellant depletion     | Drive has no fuel state yet — add to `EpsteinDrive`   |
| Subsystem damage         | Only hull HP today; `apply_damage` is the choke point |
| Save/load                | World is dataclasses + lists — serialize later        |
| Scenario selection menu  | `app.py` imports one scenario; add a picker state     |
| Audio                    | No audio subsystem wired                              |
| Campaign, multiplayer    | Out of scope                                          |

---

## 12. Testing

36 tests in `tests/`. Run with `uv run pytest`.

- `test_vec.py` — Vec2 algebra identities.
- `test_integrator.py` — momentum conservation, analytic `x(t)=½at²` check.
- `test_clock.py` — multiplier/tick math; pause emits no ticks.
- `test_sensors.py` — monotonic detect range, A-sees-B symmetry.
- `test_tracks.py` — id stability, confidence decay, second-order predict.
- `test_guidance.py` — fresh-launch aim, lead angle on a crossing target.
- `test_weapons.py` — fire gating, full hit on a stationary target,
  PDC intercept at 3 km.
- `test_damage.py` — hull reduction, destroyed path emits event.
- `test_ai.py` — hostile AI enters BURN on detection and launches in FIGHT.
- `test_autopilot.py` — `MatchVelocity` converges to zero velocity.
- `test_scenario_smoke.py` — headless scenario run ends in
  win/loss/stalemate.

Tests never import pygame — sim/ stays renderer-free.

---

## 13. Invariants a new dev must not break

1. **UI/AI read tracks, not ground truth.** (See Rule 1.)
2. **`SIM_DT` is fixed.** No physics call computes or scales by wall time.
3. **`sim/` imports nothing from `render/` or `input/` or `pygame`.**
   If a `sim/` test suddenly needs pygame to run, something has gone sideways.
4. **`apply_damage` is the only place hull HP decreases.** That's where
   the SHIP_DESTROYED event lives; bypassing it means missed events.
5. **Events go through `world.emit()`.** Never mutate `world.events` from outside.
6. **Tube IDs and ship IDs are monotonic (`util.ids.IdGen`).** Don't
   reassign them or reuse them — the TrackTable keys off `entity_id`
   (`TORP_ENTITY_OFFSET + torp.id` for torpedoes) and collisions would
   silently break tracking.
7. **Autopilots mutate `cmd_*`, not `heading` / `vel` / `pos` directly.**
   They run before the normal per-tick integrator; breaking that
   ordering means autopilot commands skip the slew/spool limits.

---

## 14. Why these choices (rationale in one place)

- **Pure-Python physics, no numpy.** The tick has single-digit entities.
  A dependency-free sim is cheaper to reason about, trivial to profile,
  and keeps `sim/` portable.
- **Fixed tick, variable render.** Render at 60 fps for smooth visuals,
  sim at 20 Hz for stable physics. Textbook decoupling; doesn't cost
  us anything and protects the whole simulation from frame-rate
  dependencies.
- **Dataclasses, no ORM / ECS.** 2 ships and a handful of torpedoes
  don't need an ECS. When the entity count grows past 50, reconsider.
- **Events are a flat list, not a bus.** Good enough for the event log
  panel, which is the only consumer. Replace with a dispatcher if
  more than one consumer ever appears.
- **Seeded RNG (`util/rng.py`).** So scenarios are reproducible for
  debugging and tests.
- **Compass bearings in UI (0° = north, clockwise) but math angles
  internally (0 = +x, CCW).** Conversion lives in `world._compass_bearing_deg`
  and `Controller._bearing_str`. Don't mix them.
- **Y-axis flip in the scope.** World +y is "up" (north). Screen +y is
  "down". The flip is applied exactly once, in
  `ScopeView.world_to_screen`. Every drawing function that uses
  `sin(angle)` negates the y term for this reason — watch for this
  when you add new sprites.
