# thelmic

> An instrument you ride, not configure.

Thelmic is a stateful, intent-driven MIDI generation system for live hard
electronic music. Its current architectural contract is planner-first: musical
meaning is planned before renderers emit events.

This document describes the current implementation and musical contract. Older
kick-first phase notes are historical and are not the active architecture.

---

## Current Status

| Phase | Status | Meaning |
|---|---|---|
| Phase 0 planner foundation | complete | `thelmic/phrase_plan.py` exists and exposes a debuggable `PhrasePlan` |
| Phase 1 planned bass | complete | bass is rendered from `phrase_plan.bass_pattern` |
| Phase 2 hook identity rendering | complete | hook is rendered from `phrase_plan.hook_pattern` |
| Phase 3 phrase syntax compliance | complete | `PhrasePlan` enforces phrase_state, call_slots, response_slots, and silence_mask |
| Phase 4 planner-owned call generation | complete | calls render from `phrase_plan.call_slots` with `role="call"` |
| Phase 5 planner-owned response generation | complete | responses render from `phrase_plan.response_slots` with `role="response"` |
| Phase 6 silence mask compliance | complete | `silence_mask` is a hard constraint across all layers |
| Phase 7 Pression compliance | complete | Pression is audited as control-only and cannot create note events |
| Phase 8 supporting layer compliance | complete | support layers are checked against bass/hook authority and silence |
| Phase 9 drop construction | complete | `DROP_RELOCK` enforces bass/kick/hook relock and pre-drop contrast |
| Phase 10 survivor signal and atomic drop commit | complete | survivor events pass through pre-drop silence and drop commit state guards the relock boundary |
| Phase 11 slider dynamics and structural trajectory | complete | slider dynamics, trajectory, priority, and sparsity shape arrangement without bypassing drop boundaries |

Current rule:

```text
Bass defines meaning.
Hook defines identity.
Everything else behaves relative to those two.
```

---

## Active System Architecture

```text
Intent / controls / landscape position
        |
Transition Engine
        |
Force Engine
        |
BehaviourField
        |
PhrasePlan
        |
Bass truth
        |
Hook identity
        |
Phrase syntax
        |
Call / response
        |
Silence
        |
Pressure / Pression
        |
Supporting renderers
        |
Drop relock
        |
Transport
        |
MIDI out
```

The musical generation order is:

```text
phrase_plan
-> bass_pattern
-> hook_pattern
-> phrase_state
-> call/response
-> silence_mask
-> pressure_curve
-> supporting layers
-> drop_relock
```

Generators consume `PhrasePlan`. They must not invent phrase structure
independently once their planner phase has landed.

`BehaviourField` affects rendering behaviour, intensity, deformation, and CC
movement. It does not have authority over the plan's musical syntax.

---

## Live Control Flow

```text
slider -> target_position
transition_engine -> current_position
force_engine -> force_state(current_position)
behaviour_field -> derived from force_state + transition
phrase_plan -> musical syntax and authored material
modules/renderers -> driven by phrase_plan + behaviour_field
manual overrides -> override per key only
```

Invariants:

- `target_position` represents intent only.
- `current_position` represents live landscape state.
- `force_state` is derived from `current_position`, not `target_position`.
- `BehaviourField` is the module-facing behaviour contract.
- Musical modules consume `BehaviourField`, not raw `ForceState`.
- Musical structure comes from `PhrasePlan`, not individual generators.
- Manual overrides win per key only.

---

## PhrasePlan

Implemented in `thelmic/phrase_plan.py`.

Core structures:

```text
PhrasePlan
PlanNote
SilenceMask
PhraseState
generate_phrase_plan()
```

Planner output:

```text
bass_pattern
hook_pattern
phrase_state
call_slots
response_slots
silence_mask
pressure_curve
```

Phrase states:

```text
RESOLVED_STABLE
CALL_UNRESOLVED
HOLD_SILENCE
RESPONSE_RESOLVED
DROP_RELOCK
```

Current consumption:

- `bass_pattern` is consumed by planned bass rendering.
- `hook_pattern` is consumed by first-class hook identity rendering.
- `call_slots` are consumed by planned call rendering.
- `response_slots` are consumed by planned response rendering.
- `phrase_state` and `silence_mask` are enforced by the syntax and compliance passes.
- `DROP_RELOCK` is enforced by the drop relock pass.
- `pressure_curve` informs macro context but must not own note syntax.

---

## Bass Truth

Bass is now first-class authored truth from `phrase_plan.bass_pattern`.

Implemented contract:

- `generate_planned_bass()` renders `PhrasePlan.bass_pattern`.
- Bass chooses and exposes a tonal centre.
- Bass pitch movement is constrained to root, optional fifth, and optional octave.
- Bass rhythm is locked to the kick grid.
- Bass is not derived from stabs, lead material, hook material, or call/response.
- Bass remains stable truth even when stabs carry a call role.

Required debug state:

```yaml
runtime:
  bass_source: "phrase_plan"
  bass_tonal_centre: 36
```

---

## Hook Identity

Hook is first-class rendered identity from `phrase_plan.hook_pattern`.

Current status:

- `PhrasePlan.hook_pattern` exists.
- `generate_planned_hook()` renders hook events with `layer="hook"` and `role="hook"`.
- Hook is independent of call/response material.
- Hook repeats across rendered bars from the authored plan.

Implemented Phase 2 contract:

- Render a recognisable 2-5 note motif.
- Keep it loopable over 1-2 bars.
- Preserve recognisability across phrase states.
- Ensure it does not mask or redefine bass meaning.
- Keep call/response subordinate to hook identity.

---

## Call / Response

Call and response are planner-owned.

Implemented contract:

- Calls render only from `phrase_plan.call_slots`.
- Calls use `role="call"`.
- Responses render only from `phrase_plan.response_slots`.
- Responses use `role="response"`.
- A response requires a valid preceding planned call.
- No valid call means no response.
- Calls must leave space.
- Responses must fill or resolve that space.
- Bass truth and hook identity must remain legible.

Implemented files:

- `thelmic/calls.py`
- `thelmic/responses.py`

---

## Silence

Silence is punctuation, not absence.

Target contract:

- Silence comes from `phrase_plan.silence_mask`.
- Silence follows calls, occurs during `HOLD_SILENCE`, and precedes drops.
- Silence may thin or omit bass, hook, percussion, and support layers as planned.
- Event generators are filtered by the syntax enforcement pass so masked regions
  suppress event emission.
- Silence is absolute. It overrides call slots, response slots, BehaviourField
  output, deformation output, and generated notes.
- Kick is not currently exempt; it is silenced like every other layer.

Implemented in `thelmic/syntax_enforcer.py`.

---

## Supporting Layers

Supporting layers are compliant consumers of the plan.

Implemented contract:

- Supporting layers may add texture, motion, emphasis, and colour.
- Supporting layers must not invent phrase structure.
- Supporting layers must not carry structural call/response roles outside the
  planned call/response renderers.
- Non-drum supporting layers must not collide with bass or hook authority.
- Supporting layer compliance only suppresses; it never adds events to fill gaps.

Implemented in `thelmic/support_enforcer.py`.

---

## Drop Relock

`DROP_RELOCK` is implemented as a planned structural arrival, not random maximum
activity.

Implemented contract:

- Drop regions are detected from `PhrasePlan.phrase_state == DROP_RELOCK`.
- Bass, kick, and hook are asserted at the first non-muted drop step.
- Bass uses the planned bass tonal authority.
- Hook uses planned hook identity.
- Kick aligns with bass and hook at the drop step.
- Unresolved call/response material is suppressed in the drop bar.
- Echo-style lower-velocity copies of authority material are suppressed.
- Pre-drop contrast is checked from the preceding `HOLD_SILENCE` or low-density
  bar.
- Drop relock may add missing bass/kick/hook authority events, but only as
  reassertions of planned identity at the structurally required arrival.
- It does not add density to fill natural silence.

Implemented in `thelmic/drop_enforcer.py`.

---

## Phase 10-11 Design Specification

Phase 10 and Phase 11 are implemented.

Do not use this section as permission to:

- Write or modify production code.
- Add new files, modules, or classes.
- Refactor phases 1-9.
- Attempt partial implementation.
- Infer missing behaviour and fill gaps.
- Merge these concepts into existing runtime logic.

### Phase 10: Survivor Signal And Atomic Drop Commit

Phase 10 introduces two coordinated behaviours:

- A continuous timing carrier that survives silence.
- A hard structural boundary at the drop.

The intended result is:

```text
continuity of time + discontinuity of structure
```

### Survivor Signal

Problem:

- Full silence removes anticipation.
- Any clearly audible signal weakens the drop.

The survivor signal solves this by persisting through silence while encoding
timing inevitability. It should become perceptually minimal near the drop.

Characteristics:

- Survives silence suppression.
- Has no low-frequency energy.
- Has no dominant transient.
- Density increases toward the drop.
- Amplitude decreases toward the drop.
- Subdivision tightens toward the drop.

Conceptual model:

```python
survivor_lane = {
    "immune_to_silence": True,
    "max_density": N,
    "low_freq_allowed": False,
    "transient_strength": "minimal",
}
```

Control signal:

```text
tightening_factor in [0, 1]

subdivision = f(tightening_factor)
density     = f(tightening_factor)
amplitude   = inverse_f(tightening_factor)
```

The survivor signal is not a musical layer. It is a timing/phase carrier and
must never compete with kick or bass at the drop. Just before the drop, tension
should be felt, but not clearly heard.

### Atomic Drop Commit

Drop must become a transaction boundary:

```text
pre-drop -> speculative / pending state
drop     -> atomic commit
post-drop -> new active structure
```

At the drop step:

- Structural state switches instantly.
- Kick, bass, hook, and groove re-anchor.
- No residual pre-drop structure remains.

Constraints:

- No structural bleed before drop.
- No lag after drop.
- No continuous morphing of structure.

Foreshadowing may exist only as an extremely low-magnitude hint. It must not
affect timing, structural placement, or identity.

Phase 10 outcome:

- Continuous time perception from the survivor signal.
- Discrete structural reset from the drop commit.

Implemented Phase 10 contract:

- Survivor events use `role="survivor"`, `layer="survivor"`,
  `survives_silence=True`, and `structural_authority=False`.
- Silence enforcement preserves only explicitly marked survivor events.
- Supporting-layer compliance also preserves explicitly marked survivors.
- Survivor ticks are high-register, low-velocity, and generated only before the
  drop step.
- `DropCommitState` tracks `active_state`, `pending_state`, and committed drop
  ids so each drop boundary commits once.
- Drop relock still asserts kick, bass, and hook at `DROP_STEP`.
- Phase 10 diagnostics include `drop_step`, `survivor_events_before_drop`,
  `normal_events_suppressed_before_drop`, `commit_applied`,
  `active_state_before`, `pending_state`, `active_state_after`,
  `kick_at_drop`, and `bass_at_drop`.

### Phase 11: Slider Dynamics And Structural Trajectory

Phase 11 transforms the slider from a static control parameter into a dynamic
system that drives structural evolution over time.

Core principles:

- Slider is not a value. It is a target position within a constraint field
  inside a dynamical system.
- The system evolves even when the slider is static.
- Slider movement defines a structural journey across time.

Two behaviour layers:

- Position as constraint: archetype region, allowable behaviour, and variation
  limits.
- Internal motion as continuous behaviour: micro-variation, phrase evolution,
  and energy cycles.

Each position defines a basin of valid musical states. The system may move
inside the basin, but must not escape it.

Internal motion layers:

- Micro, fast: timing variation, velocity modulation, ghosting.
- Phrase, medium: call/response reshaping, motif evolution, density changes.
- Energy, slow: pressure cycles, anticipation waves, pseudo build/release.

These layers must not alter archetype, break structural rules, or drift
identity.

### Slider Inertia

Slider movement should feel physical:

- It does not snap instantly.
- It may glide, lag, or overshoot.
- It responds to gesture speed.

User input becomes force applied to the system, not command.

### Trajectory Model

Slider movement defines a structural journey across time.

Inputs:

- Start position.
- End position.
- Distance.
- Movement speed.

Outputs:

- Number of drops.
- Spacing of drops.
- Magnitude of structural changes.
- Energy progression.

Distance carries meaning:

- Short distance means subtle evolution, fine-grained changes, and multiple
  small adjustments.
- Long distance means major transformation, multiple structural stages, and
  clear identity shifts.

Multi-drop planning is conceptual only at this stage. Future drop roles may
include transition, intensify, peak, and resolve, but these are not implemented.

Structural knee rule:

```text
Between drops:
  structural change may happen progressively

At drop:
  structural change may happen instantaneously
```

The drop is the only valid instantaneous structural knee. Between drops,
motif mutation, density evolution, sparsity shifts, call/response intensity
changes, groove-feel modulation, and priority emphasis changes may happen when
they are continuous and bounded by the current constraint basin.

Velocity influence:

- Fast movement means fewer, larger changes and aggressive transitions.
- Slow movement means more, smaller changes and smoother evolution.

Trajectory feeds pressure, anticipation, and drop triggering. The intended
experience is:

```text
I set something in motion that is unfolding.
```

### Phase 10-11 Combined Model

```text
USER INPUT (slider gesture)
        |
TRAJECTORY (distance + velocity)
        |
CONSTRAINT FIELD (position basin)
        |
DYNAMIC SYSTEM (multi-timescale motion)
        |
SURVIVOR SIGNAL (continuous timing)
        |
DROP EVENTS (atomic commits)
        |
STRUCTURAL EVOLUTION (multi-stage)
```

Key insight:

```text
The system is a bounded dynamical system that emits structured musical events.
```

Future implementation constraints:

- Survivor signal must be isolated from musical layers.
- Drop commit must override all prior phases.
- Trajectory must not bypass drop boundaries for instantaneous structural
  commits.
- Slider inertia must not break the constraint basin.

Implemented Phase 11 contract:

- `thelmic/phase11.py` owns `SliderDynamics`, `TrajectoryPlan`, `Phase11State`,
  instrument priority, and sparsity enforcement.
- Slider input updates a target position; playback advances an inertial actual
  position that drives `ForceEngine.set_landscape_position()`.
- Static internal motion is periodic and bounded by the current constraint
  basin; it is not a random walk and does not author archetype changes.
- Trajectory planning derives drop roles from gesture distance and velocity.
- Priority and sparsity run as an arrangement-shaping pass before Phase 10
  relock, so mandatory drop kick/bass/hook authority can still be reasserted.
- Diagnostics expose slider target, actual position, slider velocity,
  trajectory state, drop plan, current drop index, drop role, dominant
  instrument, sparsity mode/level, and priority/sparsity counters.
- Structural mutation diagnostics distinguish `progressive` from
  `instantaneous` changes. Progressive bounded deltas are allowed between
  drops; instantaneous structural deltas are accepted only at the drop step.

---

## Pression / Pressure

Pression is CC, control, and intensity only. It is not musical syntax.

Implemented Pression lanes include:

```text
pressure
impact
density
silence
riser
leadership
call_intensity
response_intensity
landing_strength
pre_warning
bass_intensity
stab_intensity
```

Allowed:

- CC output.
- Ableton mapping isolation via per-lane Map toggles.
- Phrase-level control/intensity movement.
- Tension, anticipation, release proximity, thinning, riser, impact, landing,
  bass intensity, and stab intensity as control signals.
- `silence` as a control signal for thinning/muting.
- Intra-bar motion and event spikes as smaller additions to phrase-level values.
- Lookahead preview that does not mutate live state.
- Compliance audit proving Pression does not create notes, does not mutate banks,
  does not override `silence_mask`, and does not own phrase syntax.

Not allowed:

- Generating notes.
- Choosing bass truth.
- Choosing hook identity.
- Inventing call/response syntax.
- Owning or replacing `phrase_plan.silence_mask`.
- Replacing `PhrasePlan.phrase_state` with pressure-curve shape labels.

Impact reduction rule:

- Do not reduce impact by repeating motif material at lower velocity. That reads
  as accidental echo/delay, not musical restraint.
- Prefer thinning, omission, shorter articulation, density reduction, or timbral
  softening.
- Echo/delay must be explicit FX only.

---

## BehaviourField

Implemented in `thelmic/behaviour_field.py`.

`BehaviourField` is derived from `ForceState` and `Transition` and is the only
behaviour input modules should consume.

Current fields:

```text
ghost_intensity
ghost_clustering
anchor_drop_prob
filter_target
gate_tightness
energy_level
accent_strength
ghost_velocity
anchor_velocity
anticipation
instability
release_pressure
```

Current module use:

- ghost injection uses `ghost_intensity`, `ghost_clustering`, and `ghost_velocity`.
- anchor withholding uses `anchor_drop_prob`.
- dynamics uses `ghost_velocity` and `anchor_velocity`.
- filter CC output uses `filter_target`.

Manual merge rule:

```python
result = dict(behaviour_overrides)
result.update(manual_overrides)
```

Manual overrides win only for the keys they explicitly control.

---

## Bank Generator

The bank generator renders the current plan and supporting layers into MIDI
events. It does not define the musical build order.

BankGenerator is a renderer/composer, not a planner.

Current implemented responsibilities:

- create base drum/archetype events.
- render planned bass from `phrase_plan.bass_pattern`.
- render planned hook from `phrase_plan.hook_pattern`.
- render planned calls from `phrase_plan.call_slots`.
- render planned responses from `phrase_plan.response_slots`.
- apply ghost injection.
- apply anchor withholding.
- apply behaviour-driven dynamics.
- append bass and stab events where current implementation supports them.
- enforce `PhrasePlan` syntax with `thelmic/syntax_enforcer.py`.
- enforce supporting-layer compliance with `thelmic/support_enforcer.py`.
- enforce drop construction with `thelmic/drop_enforcer.py`.
- compute and audit Pression after event enforcement.
- expose debug/runtime counters.

Current non-responsibilities:

- It must not decide bass truth independently.
- It must not invent hook identity.
- It must not invent phrase syntax once planner compliance exists for that layer.
- It must not let Pression decide note structure.

---

## Debug State

State exposed for inspection must include:

```yaml
force:
  anticipation:
  instability:
  release_pressure:

behaviour:
  ghost_intensity:
  ghost_clustering:
  anchor_drop_prob:
  filter_target:
  gate_tightness:
  energy_level:
  ghost_velocity:
  anchor_velocity:

transition:
  progress:
  velocity:

phrase_plan:
  bass_pattern:
  hook_pattern:
  phrase_state:
  call_slots:
  response_slots:
  silence_mask:
  pressure_curve:

runtime:
  bass_source: "phrase_plan"
  hook_source: "phrase_plan"
  bass_tonal_centre:
  anchors_dropped_per_bar:
  bass_events_per_bar:
  stab_events_per_bar:
  events_blocked_by_silence:
  events_outside_call_slots:
  events_outside_response_slots:
  syntax_filtered_events_total:
  planned_call_slots:
  call_events_rendered:
  call_events_suppressed:
  call_events_outside_slots:
  planned_response_slots:
  response_events_rendered:
  response_events_suppressed:
  response_events_outside_slots:
  response_events_without_call:
  silence_regions_active:
  events_blocked_by_silence_by_layer:
  support_events_checked:
  support_events_suppressed:
  support_events_suppressed_by_silence:
  support_events_suppressed_by_role:
  support_events_suppressed_by_authority:
  drop_regions_detected:
  drop_relock_events_added:
  drop_relock_events_adjusted:
  drop_missing_contrast:
  drop_illegal_events_suppressed:
  pression_created_note_events:
  pression_mutated_bank_events:
  pression_overrode_silence_mask:
  pression_authored_phrase_syntax:
  pression_modulated_events_count:
  boundary_timing:
```

---

## Repository Structure

```text
thelmic/
|-- README.md
|-- ARCHITECTURE.md
|-- pyproject.toml
|-- requirements.txt
|
|-- thelmic/
|   |-- __init__.py
|   |-- force_engine.py             # ForceState and force mapping
|   |-- transition_engine.py        # Transition and TransitionEngine
|   |-- behaviour_field.py          # BehaviourField module-facing contract
|   |-- behaviour_hooks.py          # Behaviour/manual override merge helpers
|   |-- phrase_plan.py              # PhrasePlan, PlanNote, SilenceMask, PhraseState, generate_phrase_plan
|   |-- controls.py                 # Controls dataclass
|   |-- archetypes.py               # rhythm archetypes and expectation maps
|   |-- bank_generator.py           # Bank, Phrase, MIDIEvent, BankGenerator
|   |-- bass.py                     # planned bass rendering from bass_pattern
|   |-- hook.py                     # planned hook rendering from hook_pattern
|   |-- calls.py                    # planned call rendering from call_slots
|   |-- responses.py                # planned response rendering from response_slots
|   |-- stabs.py                    # stab/call-response support
|   |-- syntax_enforcer.py          # PhrasePlan syntax filtering pass
|   |-- support_enforcer.py         # supporting-layer compliance pass
|   |-- drop_enforcer.py            # DROP_RELOCK construction/enforcement pass
|   |-- rhythm.py                   # rhythm conformance helpers
|   |-- deformations.py             # legacy deformation map pipeline
|   |-- deformations_anchor.py      # anchor withholding
|   |-- deformations_dynamics.py    # behaviour-driven velocity scaling
|   |-- pression.py                 # Pression CC/control/intensity timelines
|   |-- midi_out.py                 # rtmidi wrapper and CC output
|   |-- intent.py                   # axis input / text intent stub
|   |-- landscape.py                # territory definitions
|   |-- server.py                   # FastAPI app, WebSocket, playback loop
|   `-- static/
|       `-- index.html              # single-page web UI
|
|-- tests/
|   |-- test_bass.py
|   |-- test_behaviour_field.py
|   |-- test_behaviour_hooks.py
|   |-- test_deformations.py
|   |-- test_deformations_anchor.py
|   |-- test_deformations_dynamics.py
|   |-- test_phrase_plan.py
|   |-- test_pression.py
|   |-- test_pression_compliance.py
|   |-- test_responses.py
|   |-- test_silence.py
|   |-- test_support_compliance.py
|   |-- test_drop_enforcer.py
|   `-- test_pressure_curves.py
|
|-- examples/
`-- docs/
```

---

## Active Development Backlog

| Phase | Target |
|---|---|
| 0 | Planner foundation - done |
| 1 | Planned bass truth - done |
| 2 | Hook identity rendering - done |
| 3 | Phrase syntax compliance - done |
| 4 | Planner-owned call generation - done |
| 5 | Planner-owned response generation - done |
| 6 | Silence mask compliance - done |
| 7 | Pressure integration as CC/control only - done |
| 8 | Supporting layer compliance - done |
| 9 | Drop construction aligned to bass, hook, and silence - done |
| 10 | Survivor signal and atomic drop commit - done |
| 11 | Slider dynamics, structural trajectory, priority, and sparsity - done |

---

## Future / Parallel Transition-Intent Work

Transition-engine work is preserved as future/parallel behavioural infrastructure.
It is not the current implemented musical generation order.

The transition model:

```python
@dataclass
class Transition:
    start_position: float
    target_position: float
    current_position: float
    duration_bars: float
    elapsed_bars: float
    active: bool
```

Derived values:

```text
progress
remaining
direction
velocity
```

Separation rule:

```text
TransitionEngine -> ForceEngine -> BehaviourField -> modules/renderers
```

Transition state represents traversal/intent. Force state represents landscape
state. PhrasePlan represents musical syntax.

Transition and pressure behaviours may influence `BehaviourField` and Pression
control lanes, but they must not override the planner's ownership of bass, hook,
phrase syntax, call/response, silence, or drop structure.

---

## Session Rules

- Read `ARCHITECTURE.md` first.
- Preserve planner-first ordering.
- Do not change runtime behaviour when asked for documentation only.
- Do not let generators invent syntax that belongs in `PhrasePlan`.
- Do not let Pression become a note generator.
- Search for stale phrases like `kick-first`, `add bass`, or `no interaction`
  before finishing architecture edits.
- Do not refactor and extend in the same session.
- Commit before ending a completed session.
