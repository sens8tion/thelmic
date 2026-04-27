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
| Phase 2 hook consumption | pending | `phrase_plan.hook_pattern` exists but is not yet rendered as first-class hook identity |

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
```

Generators consume `PhrasePlan`. They must not invent phrase structure
independently once their planner phase has landed.

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
- `hook_pattern` is planned and exposed, but not yet consumed as rendered hook identity.
- `phrase_state`, `call_slots`, `response_slots`, and `silence_mask` exist but are
  not yet the sole authority for every generator.
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

Hook is planned but not yet consumed as first-class rendered identity.

Current status:

- `PhrasePlan.hook_pattern` exists.
- The plan exposes hook material for inspection.
- No renderer currently treats hook as the persistent identity layer.

Pending Phase 2 contract:

- Render a recognisable 2-5 note motif.
- Keep it loopable over 1-2 bars.
- Preserve recognisability across phrase states.
- Ensure it does not mask or redefine bass meaning.
- Keep call/response subordinate to hook identity.

---

## Call / Response

Current call/response exists but is not yet fully planner-owned.

Target contract:

- Calls occur only in planned call slots.
- Responses occur only in planned response slots.
- A response must be caused by a call.
- No call means no response.
- Calls must leave space.
- Responses must fill or resolve that space.
- Bass truth and hook identity must remain legible.

---

## Silence

Silence is punctuation, not absence.

Target contract:

- Silence comes from `phrase_plan.silence_mask`.
- Silence follows calls, occurs during `HOLD_SILENCE`, and precedes drops.
- Silence may thin or omit bass, hook, percussion, and support layers as planned.
- Event generators do not yet fully obey silence mask; this is pending compliance work.

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
- Intra-bar motion and event spikes as smaller additions to phrase-level values.
- Lookahead preview that does not mutate live state.

Not allowed:

- Generating notes.
- Choosing bass truth.
- Choosing hook identity.
- Inventing call/response syntax.
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

Current implemented responsibilities:

- create base drum/archetype events.
- render planned bass from `phrase_plan.bass_pattern`.
- apply ghost injection.
- apply anchor withholding.
- apply behaviour-driven dynamics.
- append bass and stab events where current implementation supports them.
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
  bass_tonal_centre:
  anchors_dropped_per_bar:
  bass_events_per_bar:
  stab_events_per_bar:
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
|   |-- stabs.py                    # stab/call-response support
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
| 2 | Hook identity rendering - next |
| 3 | Phrase syntax compliance |
| 4 | Planner-owned call generation |
| 5 | Planner-owned response generation |
| 6 | Silence mask compliance |
| 7 | Pressure integration as CC/control only |
| 8 | Supporting layer compliance |
| 9 | Drop construction aligned to bass, hook, and silence |
| 10 | Validation and enforcement |

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
- Do not refactor and extend in the same session.
- Commit before ending a completed session.
