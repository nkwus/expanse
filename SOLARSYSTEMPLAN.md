# Solar System + Newtonian Gravity — Step-by-Step Plan

## Context

Expanse is currently a closed 2D combat sandbox: ships and torpedoes move in free space with only thrust, on meter-scale coordinates, with a semi-implicit Euler integrator at 20 Hz. There are no celestial bodies and no gravity. This plan turns it into a real solar system simulator where ships travel under Newtonian gravitation, with enough fidelity that combat, sensing, and guidance still work near or between planets.

**Fidelity chosen:** Keplerian orbits, real AU distances, major moons (Luna, Galileans, Titan, Triton), plus three downstream upgrades (track prediction, torpedo guidance, transfer-orbit autopilot).

**Strategy:** each step below is small, ends with a runnable verification, and can be committed independently. You can stop after any phase and have a working game.

---

## Overall Architecture (reference for all steps)

- **Coordinate frame:** single heliocentric 2D inertial frame, raw SI meters. No origin-shifting initially.
- **Planet motion:** analytic Keplerian (no integration state). Each body has fixed elements at J2000; position at time `t` computed by Kepler's equation.
- **Ship motion:** integrated via existing [step_kinematics](src/expanse/sim/integrator.py#L6) with `a = a_thrust + a_gravity`.
- **2D projection:** flatten to ecliptic plane (ignore inclination).
- **Time warp:** unchanged — existing clock already delivers fixed 0.05s ticks at up to 1000×.

---

## Phase 1 — Gravity Foundation

**Goal:** a single ship in free space, a single fixed gravitating body, circular orbit closes within 1%.

### Step 1.1 — Add physics constants
- **File:** [src/expanse/config.py](src/expanse/config.py)
- Add: `G_NEWTON = 6.67430e-11`, `AU = 1.495978707e11`, `MU_SUN = 1.32712440018e20`.
- **Test:** module imports clean (`python -c "from expanse import config; print(config.AU)"`).

### Step 1.2 — Create Kepler equation solver
- **New file:** `src/expanse/sim/orbit_math.py`
- Implement `solve_kepler(M: float, e: float, tol: float = 1e-10) -> float` — Newton-Raphson, 10 iter cap, starting guess `E = M + e*sin(M)`.
- **Test:** new file `tests/sim/test_orbit_math.py` — verify `solve_kepler(0.0, 0.0) == 0.0`, `solve_kepler(pi/2, 0.5)` matches a known value (hand-compute or reference).

### Step 1.3 — Elements → 2D state vector
- Same file `orbit_math.py`. Add `elements_to_pos(a, e, omega, M, mu) -> Vec2` returning position only (velocity later when needed).
- Formula: solve for E, then `x = a*(cos(E) - e)`, `y = a*sqrt(1-e²)*sin(E)`, rotate by `omega`.
- **Test:** extend `test_orbit_math.py` — at `M=0, omega=0`, position is at perihelion `(a(1-e), 0)`. At `M=pi`, aphelion `(-a(1+e), 0)`.

### Step 1.4 — CelestialBody dataclass
- **New file:** `src/expanse/sim/celestial.py`
- `@dataclass class CelestialBody: name: str; mu: float; radius_m: float; pos: Vec2 = Vec2(0,0); parent: str | None = None; a: float = 0; e: float = 0; omega: float = 0; M0: float = 0; mean_motion: float = 0`.
- **Test:** instantiable; `CelestialBody("Sun", mu=MU_SUN, radius_m=6.96e8)` works.

### Step 1.5 — SolarSystem container
- Same file `celestial.py`. `class SolarSystem` with `bodies: list[CelestialBody]`, methods `add(body)`, `advance(t: float)` (no-op for static-position bodies in this phase — leave stub for Phase 2), `gravity_at(pos: Vec2) -> Vec2`.
- `gravity_at`: sum `mu * (body.pos - pos) / |body.pos - pos|³` over bodies (skip if distance < 1 m to avoid div-by-zero).
- **Test:** new `tests/sim/test_celestial.py` — SolarSystem with only the Sun at origin, `gravity_at(Vec2(AU, 0))` has magnitude ≈ `MU_SUN / AU²` ≈ 5.93e-3 m/s² pointing toward origin.

### Step 1.6 — Plumb SolarSystem through World
- **File:** [src/expanse/sim/world.py](src/expanse/sim/world.py)
- `World.__init__` accepts `solar_system: SolarSystem | None = None`; store as `self.solar_system`.
- Add `World.gravity_at(pos: Vec2) -> Vec2` — delegates, or returns `Vec2(0, 0)` if None.
- **Test:** existing scenarios still run unchanged (no SolarSystem passed → zero gravity → identical behavior). Run `first_contact` and confirm outcome matches pre-change.

### Step 1.7 — Apply gravity to ship integration
- **File:** [src/expanse/sim/world.py](src/expanse/sim/world.py), around line 131.
- Change:
  ```python
  thrust_accel = Vec2.from_angle(ship.heading, thrust_a) if thrust_a > 0 else Vec2(0.0, 0.0)
  accel = thrust_accel + self.gravity_at(ship.pos)
  ```
- **Test:** `first_contact` still passes (no solar system → gravity is zero → no change).

### Step 1.8 — Apply gravity to torpedo integration
- **File:** [src/expanse/sim/world.py](src/expanse/sim/world.py), around line 192.
- Same pattern: add `self.gravity_at(torp.pos)` to `accel` before `step_kinematics`.
- **Test:** `first_contact` outcome unchanged.

### Step 1.9 — Free-fall sanity scenario
- **New file:** `src/expanse/scenarios/free_fall.py`
- Sun at origin (`CelestialBody("Sun", mu=MU_SUN, pos=Vec2(0,0))`). One ship at `Vec2(AU, 0)` with `vel = Vec2(0, 0)`, no thrust.
- **Test:** run at 1000× for 30 s wall-time (~8 hours sim). Ship should fall measurably toward Sun. Add a print of `ship.pos.length()` each 100 ticks; verify it decreases monotonically.

### Step 1.10 — Circular orbit scenario
- **New file:** `src/expanse/scenarios/circular_orbit.py`
- Ship at `Vec2(AU, 0)`, velocity `Vec2(0, sqrt(MU_SUN / AU))` (≈ 29,784 m/s, tangential).
- **Test:** run at 1000× for ~6 min wall-time = ~100 days sim. Ship trace should arc; log ship distance from Sun — should stay within 1% of AU. Half-period check: at ~182 sim-days, ship should be near `(-AU, 0)`.

### Step 1.11 — Energy conservation check
- Add a debug log: every 1000 ticks print `E = 0.5·v² − μ/r`. Over 10 sim-years, |ΔE/E| should stay < 1%.
- **Test:** if drift > 1%, upgrade `step_kinematics` to leapfrog (kick-drift-kick); otherwise leave Euler.

**Phase 1 commit point:** "Add Newtonian gravity with static Sun; ship orbits correctly."

---

## Phase 2 — Keplerian Solar System + Rendering

**Goal:** full solar system of moving bodies, visible on scope, orbital periods match reality.

### Step 2.1 — Mean motion and elements table shape
- **File:** `src/expanse/sim/celestial.py`. `CelestialBody.__post_init__` computes `mean_motion = sqrt(mu_parent / a³)` when `a > 0`; store.
- Add method `position_at(t: float, parent_pos: Vec2) -> Vec2` using `M = M0 + mean_motion * t`, then `elements_to_pos`, then translate by `parent_pos`.
- **Test:** unit test — body with `a=AU, e=0, M0=0, omega=0` parented to Sun at origin, `position_at(0)` ≈ `(AU, 0)`; `position_at(quarter_period)` ≈ `(0, AU)`.

### Step 2.2 — SolarSystem.advance implementation
- **File:** `src/expanse/sim/celestial.py`. `advance(t)` updates each body's `pos` in parent-first order. Maintain an internal `_order` list built at construction (topological sort on `parent` names).
- **Test:** SolarSystem with Sun + one planet at 1 AU, advance by `period/4`, planet should be at `(0, AU)`.

### Step 2.3 — Wire advance into World.step
- **File:** [src/expanse/sim/world.py](src/expanse/sim/world.py). At the top of `step()`, call `if self.solar_system: self.solar_system.advance(self.now_sim)`.
- **Test:** existing scenarios unaffected; new scenario confirms planet moves.

### Step 2.4 — J2000 planet data (8 planets only)
- **New file:** `src/expanse/sim/solar_system_data.py`
- Hardcode `(name, mu, radius, a, e, omega_plus_M0_at_j2000, parent="Sun")` for Mercury through Neptune from NASA fact sheets. Keep comments citing source.
- Expose `build_solar_system() -> SolarSystem` returning Sun + 8 planets, no moons yet.
- **Test:** load, call `advance(0)`, print each planet's distance from Sun — matches semi-major axis within 5% (eccentricity spread).

### Step 2.5 — Tour scenario
- **New file:** `src/expanse/scenarios/tour_system.py` — builds the full solar system, no ships, no combat.
- **Test:** run at 1000× for 60 s wall ≈ 17 days sim; log Earth pos periodically. Run longer (2 min ≈ 33 days) to see noticeable Earth motion relative to the grid.

### Step 2.6 — Render solar bodies on scope
- **New file:** `src/expanse/render/solar_system.py`. Function `draw_bodies(surface, solar_system, camera)` iterating `solar_system.bodies`:
  - World→screen via existing camera transform
  - Radius: `max(body.radius_m * scale_px_per_m, 3)` pixels
  - Fill color keyed by name (Sun yellow, Earth blue, Mars red, etc.)
  - Label below body
- Call from [scope.py](src/expanse/render/scope.py) render function, BEFORE ships (so ships render on top).
- **Test:** run `tour_system` — zoom out; planets visible as dots. Zoom all the way out: see full Sun–Neptune span.

### Step 2.7 — Extend zoom range
- **File:** [src/expanse/config.py](src/expanse/config.py). Add to `RANGE_RINGS_M`: `100_000_000, 1_000_000_000, 1e10, 1e11, 1e12`.
- **File:** [render/scope.py](src/expanse/render/scope.py). Increase max zoom out so 1 pixel = 1 Gm is reachable.
- **Test:** `tour_system` at max zoom-out — whole solar system visible on one screen.

### Step 2.8 — Follow-body camera mode
- **File:** [render/scope.py](src/expanse/render/scope.py). Add optional `follow_body: str | None` to scope state; when set, camera centers on that body's current pos instead of ownship.
- Bind key (e.g. `F`) cycling through `ownship → Sun → Earth → Mars → Jupiter → ownship`.
- **Test:** in `tour_system`, press F to lock to Earth — Moon (added next) visibly orbits it.

### Step 2.9 — Add major moons
- **File:** `src/expanse/sim/solar_system_data.py`. Add Luna (parent=Earth), Phobos, Deimos, Io, Europa, Ganymede, Callisto, Titan, Triton — each with `parent` set to their primary.
- **Test:** re-run `tour_system`; at Jupiter zoom, Galileans orbit visibly over 2 minutes wall (≈ 33 days sim, Ganymede period ~7 days).

### Step 2.10 — Period-matching sanity test
- Run `tour_system` at 1000×; measure real-time wall seconds for one Earth orbit (should be ~365.25 days sim / 1000 = ~8.8 minutes). Within ±1% is a pass.
- Write a dev-only test `tests/sim/test_orbit_periods.py` that advances the SolarSystem and asserts each planet's period matches its published value within 0.1%.

### Step 2.11 — Update first_contact to live in Earth's neighborhood
- **File:** [src/expanse/scenarios/first_contact.py](src/expanse/scenarios/first_contact.py). Place Earth at its real J2000 position; offset ships by current first_contact positions relative to Earth.
- **Test:** run `first_contact` — Earth's gravity pulls both ships uniformly over combat duration (~10 min); relative dynamics mostly unchanged. Outcome statistics across ~10 runs should be similar to pre-Earth baseline.

**Phase 2 commit point:** "Planets and moons on Keplerian orbits with real-scale rendering."

---

## Phase 3 — Track Prediction Under Gravity

**Goal:** sensor tracks curve correctly when the tracked ship is in a gravity well.

### Step 3.1 — Add gravity snapshot to ContactTrack
- **File:** [src/expanse/sim/tracks.py](src/expanse/sim/tracks.py). Add field `gravity_at_last_seen: Vec2 = field(default_factory=lambda: Vec2(0,0))`.
- Populate in `TrackTable.update_from_detection` — needs SolarSystem access. Option: pass `world` or gravity function into `update_from_detection`. Simpler: add a parameter `gravity_accel: Vec2 = Vec2(0,0)` and have callers in world.py pass `self.gravity_at(sensed_pos)`.
- **File:** [world.py](src/expanse/sim/world.py) — update `_try_detect_ship` and `_try_detect_torpedo` call sites.
- **Test:** existing `first_contact` runs unchanged (behaviorally — gravity now small additional accel on tracks, predict_pos still constant-accel formula).

### Step 3.2 — Strip gravity from est_accel sampling
- **File:** [tracks.py:111–121](src/expanse/sim/tracks.py#L111). When computing `sampled_a`, subtract `gravity_at_last_seen` so `est_accel` represents the target's *thrust*, not total accel.
- **Test:** in `first_contact`, `est_accel` readings on a thrusting enemy should match its drive g's ±10% (sensor noise) — unchanged from before because the baseline scenario has zero gravity. Run the new gravity-enabled `first_contact`: a coasting ship has `est_accel ≈ 0` even though it's actually falling.

### Step 3.3 — Short-horizon predict_pos unchanged
- `predict_pos(dt)` currently uses `est_accel` (now thrust-only). Add `gravity_at_last_seen` back as a constant-accel term:
  ```python
  a_total = self.est_accel + self.gravity_at_last_seen
  return p + v*dt + 0.5*a_total*dt²
  ```
- **Test:** predicted path of a coasting ship near Earth in the scope should curve toward Earth within seconds.

### Step 3.4 — Long-horizon predict_pos_gravity
- Add new method `predict_pos_gravity(self, dt: float, solar_system) -> Vec2`:
  ```python
  steps = max(1, int(dt / 5.0))
  sub = dt / steps
  p, v = self.last_seen_pos, self.last_seen_vel
  for _ in range(steps):
      a = self.est_accel + solar_system.gravity_at(p)
      v = v + a * sub
      p = p + v * sub
  return p
  ```
- **Test:** unit test in `tests/sim/test_tracks.py` — predict position 300 s into a circular orbit; result should be near true orbit position (within a few km) instead of tangent line (which diverges by thousands of km).

### Step 3.5 — Use gravity-aware prediction for scope trajectory overlay
- **File:** [render/scope.py](src/expanse/render/scope.py) — the dashed predicted-trajectory renderer. Use `predict_pos_gravity` at 10-second intervals when a SolarSystem is present.
- **Test:** visual — put a coasting enemy near Earth, observe its dashed trajectory curves instead of extending straight.

### Step 3.6 — Iterative intercept_point
- **File:** [tracks.py:45–74](src/expanse/sim/tracks.py#L45). Current closed-form quadratic assumes straight-line target. Replace with iterative solve using `predict_pos_gravity`:
  - Initial `t = |rel| / projectile_speed`
  - Iterate 5×: `p_target = predict_pos_gravity(t); t = |p_target − shooter_pos| / projectile_speed`
  - Return `predict_pos_gravity(t)`.
- Keep SolarSystem as optional arg; if None, fall back to existing closed-form.
- **Test:** in `first_contact` near Earth, first-shot torpedo hit rate against a ballistic enemy at 1 Mm range unchanged from pre-gravity baseline (since both lead point and target experience same gravity).

**Phase 3 commit point:** "Track prediction and intercept solutions respect gravity."

---

## Phase 4 — Torpedo Guidance Under Gravity

**Goal:** torpedoes converge on gravitating targets; PN doesn't waste delta-v fighting background gravity.

### Step 4.1 — Strip gravity from torp seeker's est_accel
- **File:** [world.py:292–299](src/expanse/sim/world.py#L292) — `_update_torp_seeker`. Subtract `self.gravity_at(target.pos)` from `sampled_ax/ay` so seeker's est_accel is target thrust only.
- **Test:** launch torp at a ballistic enemy falling toward Earth — seeker's `est_accel` stays near zero (target is coasting under gravity).

### Step 4.2 — PN gravity-compensation term
- **File:** [src/expanse/sim/guidance.py](src/expanse/sim/guidance.py). In `torpedo_aim_heading`, accept optional SolarSystem. Compute:
  ```python
  a_comp = solar_system.gravity_at(target_pos) - solar_system.gravity_at(torp.pos)
  ```
  Add `a_comp` (projected onto lateral direction) to the lateral-accel command before converting to heading.
- **File:** [world.py:178–182](src/expanse/sim/world.py#L178) — update caller to pass `self.solar_system`.
- **Test:** unit test in `tests/sim/test_guidance.py` — torp and target in same gravity well, `a_comp` near zero, heading command unchanged. Torp at low altitude, target at high altitude, `a_comp` nonzero.

### Step 4.3 — Gravity-well combat scenario
- **New file:** `src/expanse/scenarios/earth_duel.py` — two ships in low Earth orbit (altitude ~400 km, ISS-like), engaging.
- **Test:** run scenario; torpedoes should converge successfully (miss distance ≤ prox_fuse_radius at intercept). Compare hit rate to control case of same ships in deep space.

### Step 4.4 — Long-range cross-planet engagement
- Scenario: ship near Mars firing at ship near Earth, 0.5 AU apart. Torp flight time ~hours.
- **Test:** torp must curve around the Sun's gravity correctly; intercept point uses `predict_pos_gravity`. Expect fuel starvation before convergence — this test is to confirm *failure modes are physical*, not numerical.

**Phase 4 commit point:** "Torpedo guidance compensates for gravity differentials."

---

## Phase 5 — Transfer-Orbit Autopilot

**Goal:** player selects a destination body, autopilot plans and executes a burn schedule.

### Step 5.1 — Extend Autopilot base class
- **File:** [src/expanse/sim/autopilot.py](src/expanse/sim/autopilot.py). Ensure base class supports multi-phase state machines (if not already). Add a simple `state: str` field.

### Step 5.2 — Burn-to-intercept planner (simplest useful)
- **New file:** `src/expanse/sim/autopilot/transfer.py` (create package if needed).
- Class `InterceptAP(Autopilot)` taking `target_body: str, max_thrust_g: float, time_of_flight_s: float`.
- `plan()`:
  - Predict target position at arrival time (walk forward with `SolarSystem.advance_copy`).
  - Solve for burn duration `t_burn` such that starting from current pos/vel, burning at `max_g` toward some heading, then coasting for `TOF − t_burn`, arrives at target.
  - Use bisection on `t_burn` with gravity-aware forward integration.
  - Returns `(heading, t_burn)` or None if infeasible.
- **Test:** unit test — Sun-only system, ship at 1 AU at rest, target a second body at 1.5 AU at rest 90° away, TOF = 1 year. Expected burn duration within 10% of analytical estimate.

### Step 5.3 — InterceptAP execute state machine
- States: `ORIENT_BURN → BURN → COAST → DONE`.
- `ORIENT_BURN`: command heading; transition when aligned within 1°.
- `BURN`: command max thrust; transition when `t_burn` elapsed.
- `COAST`: set thrust to 0; transition when within prox_radius of target or TOF exceeded.
- **Test:** run scenario "Earth to Mars direct": ship in Earth orbit engages InterceptAP with target Mars. Arrives within 10,000 km of Mars.

### Step 5.4 — UI: transfer plot command
- **File:** [src/expanse/input/controller.py](src/expanse/input/controller.py) — add keybinding to open a "target body" selector.
- **File:** [render/panels.py](src/expanse/render/panels.py) — on selection, display Δv estimate, TOF, fuel cost, "CONFIRM" button.
- On confirm, construct `InterceptAP` and assign to `ship.autopilot`.
- **Test:** in-game: press `T`, select "Mars", confirm, watch ship execute.

### Step 5.5 — Hohmann transfer planner (bonus, cleaner dynamics)
- In `transfer.py`, add `HohmannTransferAP` with proper 2-burn solution.
- Computes Δv₁, Δv₂, TOF from origin/target orbital radii. Phase-angle check: warn if launch window is wrong.
- **Test:** "Earth to Mars Hohmann" scenario; final parking orbit within 50,000 km of Mars. (Less precise than brachistochrone but more fuel-efficient.)

### Step 5.6 — Autopilot cancellation and error paths
- Ensure assigning a new autopilot cancels the old; player can abort mid-burn.
- If a burn would exceed `crew_g_tolerance`, cap thrust and extend burn time.
- **Test:** abort mid-transfer scenario — ship stops burning immediately, coasts.

**Phase 5 commit point:** "Transfer-orbit autopilot; full solar-system navigation playable."

---

## Critical Files to Modify

- [src/expanse/config.py](src/expanse/config.py) — constants, range rings
- [src/expanse/sim/world.py](src/expanse/sim/world.py) — SolarSystem wiring, gravity in ship/torp integrate, sensor gravity pass-through
- [src/expanse/sim/tracks.py](src/expanse/sim/tracks.py) — gravity-aware predict, iterative intercept
- [src/expanse/sim/guidance.py](src/expanse/sim/guidance.py) — PN gravity compensation
- [src/expanse/render/scope.py](src/expanse/render/scope.py) — zoom range, follow-body, gravity-aware trajectory overlay
- [src/expanse/sim/autopilot.py](src/expanse/sim/autopilot.py) — base class touch-up
- [src/expanse/scenarios/first_contact.py](src/expanse/scenarios/first_contact.py) — relocate to near Earth

## Critical Files to Create

- `src/expanse/sim/celestial.py`
- `src/expanse/sim/orbit_math.py`
- `src/expanse/sim/solar_system_data.py`
- `src/expanse/sim/autopilot/transfer.py`
- `src/expanse/render/solar_system.py`
- `src/expanse/scenarios/free_fall.py`
- `src/expanse/scenarios/circular_orbit.py`
- `src/expanse/scenarios/tour_system.py`
- `src/expanse/scenarios/earth_duel.py`
- `tests/sim/test_orbit_math.py`
- `tests/sim/test_celestial.py`
- `tests/sim/test_tracks.py` (extend if exists)
- `tests/sim/test_guidance.py` (extend if exists)
- `tests/sim/test_orbit_periods.py`

## Existing Code to Reuse

- [step_kinematics](src/expanse/sim/integrator.py#L6) — integrator unchanged; feed combined accel
- [Vec2.from_angle](src/expanse/sim/vec.py) — unchanged
- [clock.py](src/expanse/clock.py) — time-warp unchanged
- [Autopilot](src/expanse/sim/autopilot.py) base class — extended
- [ContactTrack](src/expanse/sim/tracks.py#L16) — fields extended, semantics of `est_accel` clarified

---

## End-to-End Verification

After each phase, the scenarios that gate the commit:

| Phase | Scenario                   | Pass criteria                                                               |
| ----- | -------------------------- | --------------------------------------------------------------------------- |
| 1     | `circular_orbit`           | 1 AU orbit closes within 1% after 1 year sim                                |
| 2     | `tour_system`              | Earth period 365±1 days, Jupiter period ~12 yr at 1000×                     |
| 3     | `first_contact` near Earth | Scope shows curved predicted path; intercept hit rate ≥ pre-change baseline |
| 4     | `earth_duel`               | Torpedo hit rate in LEO ≥ 80% of deep-space baseline                        |
| 5     | Earth→Mars transfer        | Ship arrives within 10,000 km of Mars at TOF                                |

**Invocation:**
```
PYTHONPATH=src python -m expanse.app --scenario circular_orbit
PYTHONPATH=src python -m expanse.app --scenario tour_system
PYTHONPATH=src python -m expanse.app --scenario first_contact
PYTHONPATH=src python -m expanse.app --scenario earth_duel
PYTHONPATH=src python -m pytest tests/
```
