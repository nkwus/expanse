# Solar System, Newtonian Gravity, and LLM Hailing — Step-by-Step Plan

## Context

Expanse is currently a closed 2D combat sandbox: ships and torpedoes move in free space with only thrust, on meter-scale coordinates, with a semi-implicit Euler integrator at 20 Hz. There are no celestial bodies, no gravity, and no comms. This plan turns it into a real solar system simulator where ships travel under Newtonian gravitation (Phases 1–5) and can hail one another via a local LLM subject to speed-of-light round-trip delay (Phase 6).

**Fidelity chosen:** Keplerian orbits, real AU distances, major moons (Luna, Galileans, Titan, Triton), plus three gravity downstream upgrades (track prediction, torpedo guidance, transfer-orbit autopilot), plus hailing with local-LLM + RAG personas and a tabbed comms panel with persistent conversation history.

**Strategy:** each step below is small, ends with a runnable verification, and can be committed independently. You can stop after any phase and have a working game.

---

## Overall Architecture (reference for all steps)

- **Coordinate frame:** single heliocentric 2D inertial frame, raw SI meters. No origin-shifting initially.
- **Planet motion:** analytic Keplerian (no integration state). Each body has fixed elements at J2000; position at time `t` computed by Kepler's equation.
- **Ship motion:** integrated via existing [step_kinematics](src/expanse/sim/integrator.py#L6) with `a = a_thrust + a_gravity`.
- **2D projection:** flatten to ecliptic plane (ignore inclination).
- **Time warp:** unchanged — existing clock already delivers fixed 0.05s ticks at up to 1000×.
- **Comms:** messages queued with `deliver_at = now + distance / C_LIGHT`; conversations persisted across tab close/reopen; LLM responses generated on delivery.

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

## Phase 6 — Ship Hailing with Local LLM

**Goal:** player hails a contact; a local LLM responds in-persona subject to speed-of-light round-trip delay; outcomes can update track classification, fire scenario events, and drive enemy captain reactions. Fallback to canned responses when LLM is unavailable.

**Estimate:** ~1 week. Light-delay + queue plumbing is a day; LLM backend + RAG is 2–3 days; UI and integrations are 2–3 days.

### Step 6.1 — LLM backend abstraction

- **New file:** `src/expanse/llm/backend.py`
- Protocol `LLMBackend` with `generate(system: str, messages: list[dict]) -> str`.
- Implementations: `OllamaBackend` (HTTP to `http://localhost:11434`), `LlamaCppBackend` (subprocess or python bindings), `CannedBackend` (deterministic fallback for tests/offline).
- Config in [config.py](src/expanse/config.py): `LLM_BACKEND = "ollama"`, `LLM_MODEL = "llama3.1:8b"`, `LLM_ENDPOINT`.
- **Test:** `tests/llm/test_backend.py` — `CannedBackend` round-trips; `OllamaBackend` skipped unless env var set.

### Step 6.2 — RAG corpus loader

- **New file:** `src/expanse/llm/rag.py`
- In-memory vector store over short Markdown docs in `src/expanse/llm/corpus/` (faction lore, ship classes, cargo manifests).
- Use `sentence-transformers` (small model) or a simple TF-IDF fallback if dep weight matters. `retrieve(query, k=3) -> list[str]`.
- **Test:** `tests/llm/test_rag.py` — seed 5 corpus docs, query "pirate" returns pirate-themed doc first.

### Step 6.3 — ShipPersona dataclass

- **New file:** `src/expanse/sim/persona.py`
- `@dataclass ShipPersona: role: str; disposition: str; hidden_intent: str; cargo: str | None; name: str; captain_name: str; traits: list[str]`
- Method `system_prompt() -> str` assembles a setting-grounded system prompt.
- **Test:** `tests/sim/test_persona.py` — persona renders all fields into prompt.

### Step 6.4 — Persona templates (class-level)

- **New file:** `src/expanse/sim/persona_templates.py`
- Generators: `cargo_hauler(rng)`, `pirate(rng)`, `patrol(rng)`, `civilian(rng)`, `military(rng)` — return `ShipPersona` with randomized but on-theme fields.
- **Test:** each generator produces valid Persona from seeded RNG, reproducible.

### Step 6.5 — Ship gets optional persona

- **File:** [src/expanse/sim/bodies.py](src/expanse/sim/bodies.py) — add `persona: ShipPersona | None = None` to `Ship`.
- Scenarios may assign directly (scenario-level override); if left None and ship is NPC, world auto-assigns from template at world init based on ship class/side.
- **Test:** `first_contact` auto-assigns personas; scenario can override. Confirm attribute access works.

### Step 6.6 — Physical constants for comms

- **File:** [src/expanse/config.py](src/expanse/config.py) — add `C_LIGHT = 299_792_458.0`.

### Step 6.7 — CommsMessage + CommsQueue

- **New file:** `src/expanse/sim/comms.py`
- `@dataclass CommsMessage: id: int; sender_id: int; recipient_id: int; text: str; sent_at: float; deliver_at: float; is_reply: bool; conversation_id: int; estimated_round_trip_at_send: float`
- `class CommsQueue`: `enqueue(msg)`, `deliver_ready(now) -> list[CommsMessage]`, `active_conversations() -> set[int]`. Sorted list or heap by `deliver_at`.
- Helper `light_delay(sender_pos, recipient_pos) -> float = distance / C_LIGHT`.
- **Test:** `tests/sim/test_comms.py` — enqueue with 1 AU gap, `deliver_ready` at t=498s returns nothing, at t=500s returns the message.

### Step 6.8 — Wire CommsQueue into World

- **File:** [src/expanse/sim/world.py](src/expanse/sim/world.py) — `World` holds a `CommsQueue`. In `step()`, pull `deliver_ready(now_sim)` and emit `MESSAGE_DELIVERED` events.
- New `SimEvent.MESSAGE_SENT`, `MESSAGE_DELIVERED`, `HAIL_OPENED`, `HAIL_CLOSED` in [events.py](src/expanse/sim/events.py).
- **Test:** synthetic scenario `comms_pingpong`: two ships 1 AU apart exchange three messages. Verify delivery times match `distance / C_LIGHT` at 1000× warp.

### Step 6.9 — Hail command + input

- **File:** [src/expanse/input/controller.py](src/expanse/input/controller.py) — keybind `H` to "hail selected contact". Opens a text-entry overlay.
- Text editor state on the controller (cursor, buffer); `Enter` sends, `Esc` cancels.
- **Test:** manual — press H with a selected track, type, send; message appears in outgoing queue.

### Step 6.10 — Conversation store (persistent history)

- **New file:** `src/expanse/sim/conversation.py`
- `@dataclass Conversation: id: int; entity_id: int; ship_name: str; turns: list[CommsMessage]; opened_at: float; last_activity: float`
- `class ConversationStore`: keyed by `entity_id` (the NPC ship), NOT by tab state. `get_or_create(entity_id)`, `append(entity_id, msg)`, `all() -> list[Conversation]`.
- Conversations persist for the lifetime of the `World` regardless of whether their tab is open or closed in the UI. Closing a tab is a UI-only action.
- **Test:** `tests/sim/test_conversation.py` — append messages to a conversation, close/reopen (simulated) the tab, verify full turn history returns.

### Step 6.11 — Comms panel with tabs

- **File:** [src/expanse/render/panels.py](src/expanse/render/panels.py) — new `CommsPanel` on the right side (or as a bottom strip; scope-dependent).
- **Tab bar** at the top of the panel: one tab per *currently open* conversation, labeled with the ship's display name (from `ConversationTrack` or track-id if persona not yet revealed). Active tab highlighted.
- Each tab has an **X close affordance**. Closing a tab removes it from the visible tab list but does **not** delete the underlying `Conversation` in the store.
- **Header strip (inside active tab):** shows the current link status as *estimates*, recomputed each render frame from live positions:
  - `Range: 4.2 Mm` (current distance to the contact)
  - `One-way delay: ~14 s` (= `range / C_LIGHT`)
  - `Est. round-trip: ~28 s` (= `2 × one-way`)
  - All values prefixed with "~" and labeled "est." to make clear they will drift as ships maneuver between send and receipt.
- **Tab body:** scrolling message log for the active conversation. Outgoing messages right-aligned, incoming left-aligned, each with sim-time stamp.
- **Pending-reply indicator:** when the most recent turn is an outgoing message with no reply yet, render a ghost entry showing:
  - `Elapsed since send: T+18 s` — a live counter driven by `now_sim − msg.sent_at`. Counts up from zero, no fixed endpoint.
  - `Expected reply in: ~X s` where X = `estimated_round_trip_at_send − elapsed`, clamped at 0. Display turns to `overdue by N s` once it passes zero. This is purely informational — actual arrival still comes from the CommsQueue.
- **UI state:** `CommsPanelState.open_tabs: list[int]` (ordered entity_ids); `active_tab: int | None`. Held on the render-side controller, not the sim.
- **Sim-side hook:** `CommsMessage` gains an `estimated_round_trip_at_send: float` field (snapshot of `2 × range / C_LIGHT` at send time), used by the UI for the expected-reply estimate. The real `deliver_at` on the reply remains computed at generation time from then-current positions and is authoritative.
- **Test:** manual — open three hails, close the middle tab with its X, verify the other two remain and active_tab shifts sensibly. Send a hail from a ship closing fast on the target; verify the header "one-way delay" decreases frame by frame, while the "expected reply in" counter (based on send-time snapshot) does not — confirming the estimate is a snapshot, not a live prediction.

### Step 6.12 — Re-hail restores full history

- When the player hails a ship whose `entity_id` already has a `Conversation` in the store:
  - If tab is already open: focus it; append the new message.
  - If tab was closed: re-open the tab (append `entity_id` to `open_tabs`), load the full prior turn log from the store, append the new message as a fresh turn.
- The NPC's responder also sees the full prior history (via the same store) so the persona behaves as if resuming, not starting fresh.
- **Test:** hail cargo ship → exchange 3 turns → close tab → hail the same ship again → tab reappears with all 3 prior turns visible, new turn appends beneath.

### Step 6.13 — Auto-slow during active hail

- **File:** [src/expanse/clock.py](src/expanse/clock.py) or [world.py](src/expanse/sim/world.py) — expose `active_hails_for_player() -> bool`. Clock checks this each frame; if true, clamp `time_multiplier` to `1.0`.
- Clear when the player closes the conversation AND no pending deliveries remain.
- **Test:** set warp to 1000×, send hail → warp drops to 1×. Close → returns to previous setting.

### Step 6.14 — Responder subsystem (LLM call on delivery)

- **New file:** `src/expanse/llm/responder.py`
- On `MESSAGE_DELIVERED` to an NPC with a persona: build prompt (persona system + RAG context + last N conversation turns + incoming text) and submit to backend in a thread pool.
- When result returns: enqueue reply with `deliver_at = now + light_delay(recipient_pos, sender_pos)`.
- **Test:** `tests/llm/test_responder.py` with `CannedBackend`; hail triggers expected canned reply routed back through queue.

### Step 6.15 — Structured output for classification

- Prompt instructs LLM to end each reply with `<classification>CARGO|PIRATE|PATROL|CIVILIAN|MILITARY_FRIENDLY|MILITARY_HOSTILE|AMBIGUOUS</classification>`.
- **File:** [src/expanse/sim/tracks.py](src/expanse/sim/tracks.py) — extend `Classification` enum with new values.
- Responder parses tag, updates the player's ContactTrack classification for that entity. Classification is "sticky" — once set from dialogue, only further dialogue can change it.
- **Test:** `test_responder.py` — CannedBackend emits `<classification>CARGO</classification>`, player's track gets updated.

### Step 6.16 — Scenario event tags

- Prompt also permits optional `<event>SURRENDER|DISTRESS|AMBUSH|HOSTILE_INTENT</event>` tag.
- Responder emits corresponding `SimEvent` when parsed. Scenario code subscribes via the existing events bus.
- New sample scenario `src/expanse/scenarios/customs_inspection.py` — player must hail and classify 3 contacts; surrendering pirates count as wins, shooting cargo loses.
- **Test:** scripted CannedBackend yields SURRENDER → scenario logic marks encounter resolved.

### Step 6.17 — Captain AI may initiate hails

- **File:** [src/expanse/sim/ai.py](src/expanse/sim/ai.py) — Captain layer gets a `should_hail()` decision based on ROE (e.g., patrol hails unknowns at detection; pirate hails cargo pre-ambush).
- When triggered, AI enqueues a message from its own persona to the player's ship.
- **Test:** scenario with patrol ship — within 30s of detection, player receives a hail with light-delayed arrival.

### Step 6.18 — Per-ship conversation memory + RAG refresh

- Each `Ship.persona` carries a rolling window of the last N=10 turns in memory.
- Older turns summarized by a cheap LLM call and folded back into the persona's RAG context. (This is where RAG earns its keep — long conversations stay coherent without ballooning the prompt.)
- **Test:** extended 20-turn conversation stays on-persona in the final exchanges.

### Step 6.19 — Offline / canned fallback wiring

- On LLM backend error or missing endpoint, fall back to `CannedBackend` with a library of ~8 canned responses per role, keyed by message hash for variety.
- Emit a `SimEvent.COMMS_DEGRADED` warning once per session.
- **Test:** stop local Ollama; hail still returns a response.

**Phase 6 commit point:** "Hail contacts with light-delayed LLM dialogue; classification and scenario events driven by conversation."

---

## Critical Files to Modify

- [src/expanse/config.py](src/expanse/config.py) — physics constants, range rings, LLM config, `C_LIGHT`
- [src/expanse/sim/world.py](src/expanse/sim/world.py) — SolarSystem wiring, gravity in ship/torp integrate, sensor gravity pass-through, CommsQueue integration
- [src/expanse/sim/tracks.py](src/expanse/sim/tracks.py) — gravity-aware predict, iterative intercept, extended Classification enum
- [src/expanse/sim/guidance.py](src/expanse/sim/guidance.py) — PN gravity compensation
- [src/expanse/sim/bodies.py](src/expanse/sim/bodies.py) — `persona` field on Ship
- [src/expanse/sim/ai.py](src/expanse/sim/ai.py) — Captain ROE for initiating hails
- [src/expanse/sim/events.py](src/expanse/sim/events.py) — new comms events
- [src/expanse/sim/autopilot.py](src/expanse/sim/autopilot.py) — base class touch-up
- [src/expanse/render/scope.py](src/expanse/render/scope.py) — zoom range, follow-body, gravity-aware trajectory overlay
- [src/expanse/render/panels.py](src/expanse/render/panels.py) — transfer-plot UI, CommsPanel with tabs
- [src/expanse/input/controller.py](src/expanse/input/controller.py) — transfer keybind, hail keybind + text entry
- [src/expanse/clock.py](src/expanse/clock.py) — auto-slow during hail
- [src/expanse/scenarios/first_contact.py](src/expanse/scenarios/first_contact.py) — relocate to near Earth

## Critical Files to Create

### Gravity (Phases 1–5)

- `src/expanse/sim/celestial.py`
- `src/expanse/sim/orbit_math.py`
- `src/expanse/sim/solar_system_data.py`
- `src/expanse/sim/autopilot/transfer.py`
- `src/expanse/render/solar_system.py`
- `src/expanse/scenarios/free_fall.py`
- `src/expanse/scenarios/circular_orbit.py`
- `src/expanse/scenarios/tour_system.py`
- `src/expanse/scenarios/earth_duel.py`

### Hailing + LLM (Phase 6)

- `src/expanse/sim/comms.py`
- `src/expanse/sim/conversation.py`
- `src/expanse/sim/persona.py`
- `src/expanse/sim/persona_templates.py`
- `src/expanse/llm/backend.py`
- `src/expanse/llm/rag.py`
- `src/expanse/llm/responder.py`
- `src/expanse/llm/corpus/*.md` (faction lore, ship classes)
- `src/expanse/scenarios/comms_pingpong.py`
- `src/expanse/scenarios/customs_inspection.py`

### Tests

- `tests/sim/test_orbit_math.py`
- `tests/sim/test_celestial.py`
- `tests/sim/test_tracks.py` (extend if exists)
- `tests/sim/test_guidance.py` (extend if exists)
- `tests/sim/test_orbit_periods.py`
- `tests/sim/test_comms.py`
- `tests/sim/test_conversation.py`
- `tests/sim/test_persona.py`
- `tests/llm/test_backend.py`
- `tests/llm/test_rag.py`
- `tests/llm/test_responder.py`

## Existing Code to Reuse

- [step_kinematics](src/expanse/sim/integrator.py#L6) — integrator unchanged; feed combined accel
- [Vec2.from_angle](src/expanse/sim/vec.py) — unchanged
- [clock.py](src/expanse/clock.py) — time-warp unchanged apart from auto-slow hook
- [Autopilot](src/expanse/sim/autopilot.py) base class — extended
- [ContactTrack](src/expanse/sim/tracks.py#L16) — fields extended, semantics of `est_accel` clarified
- [events.py](src/expanse/sim/events.py) event bus — reused for comms and scenario tags

---

## End-to-End Verification

After each phase, the scenarios that gate the commit:

| Phase | Scenario | Pass criteria |
|---|---|---|
| 1 | `circular_orbit` | 1 AU orbit closes within 1% after 1 year sim |
| 2 | `tour_system` | Earth period 365±1 days, Jupiter period ~12 yr at 1000× |
| 3 | `first_contact` near Earth | Scope shows curved predicted path; intercept hit rate ≥ pre-change baseline |
| 4 | `earth_duel` | Torpedo hit rate in LEO ≥ 80% of deep-space baseline |
| 5 | Earth→Mars transfer | Ship arrives within 10,000 km of Mars at TOF |
| 6 | `customs_inspection` | Hail delivers with correct light delay, reply returns in-persona, classification tag updates ContactTrack |

**Invocation:**

```
PYTHONPATH=src python -m expanse.app --scenario circular_orbit
PYTHONPATH=src python -m expanse.app --scenario tour_system
PYTHONPATH=src python -m expanse.app --scenario first_contact
PYTHONPATH=src python -m expanse.app --scenario earth_duel
PYTHONPATH=src python -m expanse.app --scenario customs_inspection
PYTHONPATH=src python -m pytest tests/
```
