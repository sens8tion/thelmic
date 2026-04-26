# thelmic

> An instrument you ride, not configure.

A performance instrument for shaping anticipation → tension → release over time.
MIDI out. Python. No DAW dependency at this stage.

---

## What This Is

Thelmic is a stateful, intent-driven MIDI sequencer for live dance music performance
(target: DnB / heavy electronic). The performer rides a landscape of three territories —
Oak, Chaos, Nott — in real time, using a MIDI knob. The engine maintains coherent
force state across generated banks, responding to trajectory and history rather than
executing fixed patterns.

This is not a step sequencer. It does not loop clips. It generates banks of MIDI
(4 phrases × 4 bars) driven by a continuous force state, queues them for playback,
and accepts interrupts from the performer.

---

## Landscape Territories

```
Oak    — stable, archetype-compliant, trust-building
Chaos  — principled corruption; internal logic the audience cannot track
Nott   — off-beam resolution; dark, legible destination, unexpected arrival
```

All transitions between territories are permissible. No fixed sequence.
The `landscape_position` axis (0.0 → 1.0, Oak → Nott via Chaos) is a live
performance control, mapped to a MIDI CC knob.

The engine tracks not just current position but transition history — where it came
from, how fast it moved, what it left unresolved.

---

## System Architecture

```
Intent Input        (axis value + optional text intent)
        ↓
Control Layer       (knobs / parameter constraints)
        ↓
Force Engine        (stateful, history-aware, trajectory-tracking)
        ↓
Bank Generator      (4 phrases × 4 bars of MIDI)
        ↓
Transport           (queue / play / interrupt-replace)
        ↓
MIDI Out            (rtmidi, same pattern as dnb-seq)
```

---

## Layer Specifications

### 1. Force Engine

The heart of the system. Owns state and trajectory — not just what is happening
now, but what needs to happen next.

**Force dimensions** (all 0.0–1.0):
- `anticipation`        — pressure building toward an event
- `release_pressure`    — accumulated need to resolve
- `instability`         — degree of principled corruption active
- `density`             — rhythmic and textural fullness
- `control_vs_chaos`    — position on the Oak–Chaos axis

**Temporal state:**
- `landscape_position`      — current 0.0–1.0 axis value (live, from MIDI CC)
- `bank_history`            — list of BankSnapshot objects (force values + transition event)
- `current_trajectory`      — direction and rate of change (delta per bank)
- `resolution_likelihood`   — 0.0–1.0, forward-looking

**Three temporal scopes:**
1. Phrase scope  — bar-by-bar; what is happening right now
2. Bank scope    — position of this phrase in the 4-phrase arc
3. Cross-bank    — memory and momentum; informs generation of next bank

**Transition events** are recorded explicitly in bank_history:
```python
@dataclass
class TransitionEvent:
    from_territory: str        # 'oak' | 'chaos' | 'nott'
    to_territory: str
    axis_position: float       # where on 0.0–1.0 the transition occurred
    bank_index: int            # which bank this happened at
    left_unresolved: bool      # whether the departing territory was resolved
```

```python
@dataclass
class BankSnapshot:
    bank_index: int
    force_state: ForceState
    transition: TransitionEvent | None
    completed: bool            # False if bank was interrupted
```

### 2. Control Layer

User-defined parameter constraints. Applied as ceilings/floors on force engine output.

```python
@dataclass
class Controls:
    groove_lock: float       # 0.0–1.0; how tightly rhythm aligns to grid
    chaos_limit: float       # 0.0–1.0; ceiling on instability dimension
    density_ceiling: float   # 0.0–1.0
    variation_rate: float    # 0.0–1.0; how fast patterns change within a bank
    kick_dominance: float    # 0.0–1.0; kick vs other elements
```

### 3. Bank Generator

Generates a complete bank (4 phrases × 4 bars) as MIDI events, driven by
force state. Each MIDI event carries semantic role metadata.

**Event roles:**
- `anchor`              — weight-bearing; establishes grid
- `ghost`               — decorative; low emphasis
- `disruption`          — breaks expectation deliberately
- `impact`              — high-energy landing
- `withheld_resolution` — expected impact that doesn't arrive

```python
@dataclass
class MIDIEvent:
    time: str              # e.g. "7.4.3" (bar.beat.tick)
    note: int
    velocity: int
    duration: float
    layer: str             # e.g. 'kick', 'snare', 'bass'
    role: str              # anchor | ghost | disruption | impact | withheld_resolution
    emphasis: float        # 0.0–1.0
    openness: float        # 0.0–1.0
    expected_weight: float # 0.0–1.0
    should_resolve: bool
```

**Build order for instruments:**
1. Kick only — verify force → pattern mapping
2. Add snare/hat — no interaction
3. Add bass — no interaction
4. Inter-instrument roles: anchor, ghost, call/response
5. Expression layer (CC automation)
6. Voice/sample layer

### 3a. Rhythmic Archetype System

Kick placement is driven by **probability distributions and expectation maps** derived
from dance music genre conventions (`thelmic/archetypes.py`), not uniform random sampling.

**Slot index reference** (0-indexed, 4/4 at 16th-note resolution):

```
0  = beat 1 (downbeat)     8  = beat 3
1  = "1-e"                 9  = "3-e"
2  = "1-and"               10 = "3-and"
3  = "1-ah"                11 = "3-ah"
4  = beat 2                12 = beat 4
5  = "2-e"                 13 = "4-e"
6  = "2-and"               14 = "4-and"
7  = "2-ah"                15 = "4-ah"
```

Beats 2 and 4 (slots 4 and 12) are snare territory in all DnB archetypes — kick
archetypes deliberately avoid or approach these slots as part of their identity.

**The 10 archetypes:**

| Name | Genre | Key slots | Density |
|------|-------|-----------|---------|
| `half_step` | Neurofunk / dark DnB | 0 only | 0.10 |
| `two_step` | DnB signature | 0, 6 | 0.35 |
| `shuffled_two_step` | Jungle | 0, 6 + swing fills | 0.45 |
| `stutter` | DnB / hardcore | 0–1, 8–9 double-hits | 0.50 |
| `rolling` | Liquid / tech-step | 0, 3, 6, 9, 12 (every 3rd) | 0.60 |
| `breakbeat_hardcore` | Early UK rave | 0, 6, 8, 14 complex | 0.55 |
| `four_on_the_floor` | House / hardcore / techno | 0, 4, 8, 12 | 0.75 |
| `happy_hardcore` | Bouncy hardcore | 0, 2, 4, 6, 8, 10, 12, 14 | 0.85 |
| `amen` | Jungle / DnB break | Multi-hit: 0, 2, 4, 6, 8, 10 | 0.70 |
| `gabber` | Industrial hardcore | Near-continuous | 1.00 |

**Archetype selection** (`select_blend(density, instability, landscape_position)`):

```
Oak  (pos < 0.33):  density selects along half_step → two_step → rolling
                    → four_on_the_floor → happy_hardcore
                    Disruption archetype: breakbeat_hardcore

Chaos (0.33–0.67):  blends shuffled_two_step → amen, weighted by (density × chaos_depth)
                    Disruption archetype: gabber (density > 0.65) or stutter

Nott (pos > 0.67):  blends two_step → half_step with increasing nott_depth
                    Disruption archetype: stutter
```

In all territories, `instability` blends the base archetype toward the disruption
archetype (capped at 65% so the base is always audible).

**Role assignment** uses the expectation map of the selected blend:

```
slot expectation ≥ 0.7  →  anchor (or impact if release_pressure > 0.6 on final phrase)
slot expectation < 0.25 + high instability  →  disruption (probabilistic)
slot expectation < 0.25  →  ghost
slot fired on any other mid-expectation slot  →  anchor
unfired slot with expectation ≥ 0.7 (last bar, high anticipation)  →  withheld_resolution
```

`withheld_resolution` events have `velocity=0` and are display-only — they mark expected
hits that were deliberately withheld. They appear in the sequencer grid as blue blocks
but produce no MIDI output.

### 4. Transport

```
Generate → Queue → Playing
               ↓
         [interrupt] → Generate new → replaces queue
```

- **Queue**: bank generates ahead, drops in at next bank boundary (bar 1, beat 1)
- **Interrupt**: performer blows away queued bank; new bank generates immediately
- **Force continuity**: if a bank is interrupted, the snapshot records `completed=False`
  and trajectory updates from the actual exit point, not the intended destination

```python
class Transport:
    def queue_bank(self, bank: Bank) -> None: ...
    def interrupt_and_replace(self, bank: Bank) -> None: ...
    def on_bank_boundary(self) -> None: ...   # called by clock at bar 1 beat 1
    def current_position(self) -> str: ...    # bar.beat.tick
```

### 5. MIDI Out

- Library: `rtmidi` (python-rtmidi)
- Virtual MIDI port, named `thelmic`
- Ableton (or any DAW) receives it as a standard MIDI input
- No DAW API calls; no tight integration

### 6. Web UI

- Server: FastAPI + uvicorn (`thelmic/server.py`)
- Frontend: single-page HTML/JS, no framework (`thelmic/static/index.html`)
- Real-time: WebSocket at `/ws` — bidirectional state sync
- Start: `python -m thelmic.server` or `thelmic` (after `pip install -e .`)
- Open: `http://localhost:8000`

**UI controls:**
- Axis slider (Oak → Chaos → Nott) — sends `{ type: "axis", value: 0.0–1.0 }`
- Force state bars — live readout of all five dimensions + resolution_likelihood
- Play / Stop — starts/stops the MIDI playback loop in a background thread
- BPM input — updates playback speed
- Controls section — all five `Controls` fields as sliders

**WebSocket message protocol:**

Client → Server:
```json
{ "type": "axis",    "value": 0.5 }
{ "type": "play" }
{ "type": "stop" }
{ "type": "bpm",     "value": 174 }
{ "type": "control", "key": "groove_lock", "value": 0.8 }
```

Server → Client:
```json
{ "type": "state", "landscape_position": 0.5, "territory": "chaos",
  "anticipation": 0.7, "release_pressure": 0.6, "instability": 0.8,
  "density": 0.75, "control_vs_chaos": 0.8, "resolution_likelihood": 0.3,
  "bank_count": 4, "playing": true, "bpm": 174,
  "archetype": "amen+disruption", "midi_port": "poodle 0",
  "bank_events": [{ "time": "1.1.0", "layer": "kick", "role": "anchor",
                    "velocity": 100, "emphasis": 0.8 }, ...] }
```

`midi_port` is `null` until a port is selected. `bank_events` is the full event list
for the current bank (including velocity-0 `withheld_resolution` display events).

**MIDI port selection** (WebSocket):
```json
{ "type": "midi_port", "value": "poodle" }
```
Server opens the named loopMIDI port (case-insensitive substring match). REST endpoint
`GET /api/midi-ports` returns the current list of available output ports.

---

## Repository Structure

```
thelmic/
├── README.md
├── ARCHITECTURE.md          ← this file
├── pyproject.toml
├── requirements.txt
│
├── thelmic/
│   ├── __init__.py
│   ├── force_engine.py      ← ForceState, ForceEngine, BankSnapshot, TransitionEvent
│   ├── controls.py          ← Controls dataclass
│   ├── archetypes.py        ← 10 rhythm archetypes, select_blend(), archetype_name_at()
│   ├── bank_generator.py    ← Bank, Phrase, MIDIEvent, BankGenerator
│   ├── transport.py         ← Transport, clock integration
│   ├── midi_out.py          ← rtmidi wrapper, virtual port management
│   ├── intent.py            ← axis input, optional text intent parsing (stub)
│   ├── landscape.py         ← territory definitions, axis → force mappings
│   ├── server.py            ← FastAPI app, WebSocket, playback loop
│   └── static/
│       └── index.html       ← single-page web UI
│
├── tests/
│   ├── test_force_engine.py
│   ├── test_bank_generator.py
│   └── test_transport.py
│
├── examples/
│   └── kick_only.py         ← first working example: single instrument
│
└── docs/
    ├── tension-vocabulary.md
    └── mode-topology.md
```

---

## Build Order

### Phase UI — Web interface (complete)
- FastAPI server with WebSocket at `/ws`
- Single-page HTML/JS UI: axis slider, force state bars, transport, controls
- Playback runs in background thread; axis updates are live
- Run: `python -m thelmic.server` → open `http://localhost:8000`

### Phase 1 — Force engine + kick (complete)
- Implement `ForceState`, `ForceEngine` with landscape_position input
- Implement `Controls` with defaults
- Implement `BankGenerator` for kick only
- Implement `MIDIOut` with virtual port
- Wire together in `examples/kick_only.py`
- Tests: assert that force values produce expected density ranges,
  role distribution, and resolution_likelihood

### Phase 2 — Transport
- Implement `Transport` with queue and interrupt
- Clock: simple tick loop, fires `on_bank_boundary` at bar 1 beat 1
- Test: queue → play → interrupt → replace

### Phase 3 — Second instrument (snare/hat)
- Extend BankGenerator; no inter-instrument logic yet
- Test: two instruments generate independently without conflict

### Phase 4 — Inter-instrument roles
- Anchor/ghost/call-response relationships between layers
- Force engine coordinates roles across instruments

### Phase 5 — Pressure Curves

A **pressure curve** is a time-varying 0→1 function spanning a defined number of bars.
Curves are chainable in sequence and serve two roles:

1. **Deformation modulator** — replaces or scales the direct force→intensity mapping
   for a specific deformation (e.g. ghost inject intensity follows a decelerating curve
   into Chaos rather than tracking instability linearly)

2. **MIDI CC output** — drives a CC value directly (brightness, filter, reverb send etc.)
   to a DAW controller, independent of any deformation

**Curve shapes** (defined by behaviour of the first differential):
- `linear`       — constant 1st differential; steady ramp up or down
- `accelerating` — increasing 1st differential; slow start, fast finish
- `decelerating` — decreasing 1st differential; fast start, slow finish
- `sinusoidal`   — smooth oscillation; full or partial cycle over N bars
- `step`         — holds then jumps; constant until final bar

Each curve has:
- `shape: str`
- `bars: int`          — duration in bars
- `from_value: float`  — starting value (0.0–1.0)
- `to_value: float`    — ending value (0.0–1.0)
- `target: str`        — deformation name (e.g. `"ghost_inject"`) or `"cc:<n>"` for MIDI CC

Curves chain by linking `to_value` of one to `from_value` of the next.
The chain loops or holds at end unless explicitly stopped.

**UI representation:** each active curve is depicted as a small sparkline next to
its associated deformation strip row (if targeting a deformation) or in a dedicated
CC lane (if targeting MIDI CC output).

### Phase 5a — Expression layer (CC automation)
- CC automation output driven by force state and/or pressure curves
- Brightness, saturation, spatial width etc. as MIDI CC

### Phase 6 — Intent text parsing
- Simple keyword → force bias mapping
- "hold it back", "push harder", "let it go"

### Phase 7 — Voice/sample layer
- Intelligibility axis
- Sample triggering driven by force state

---

## Key Principles

1. Intent does not directly generate output
2. Control constrains; force engine decides
3. Force layer owns time and direction
4. MIDI defines structure; expression defines impact
5. Transition history matters as much as current state
6. Generate at bank resolution; force state is continuous
7. Interrupted banks update trajectory from where they actually left off
8. Perception is ground truth — Oak listens and labels

---

## Territory Force Profiles (starting defaults)

```python
OAK_PROFILE = ForceState(
    anticipation=0.2,
    release_pressure=0.1,
    instability=0.05,
    density=0.6,
    control_vs_chaos=0.1,
)

CHAOS_PROFILE = ForceState(
    anticipation=0.7,
    release_pressure=0.6,
    instability=0.8,
    density=0.75,
    control_vs_chaos=0.8,
)

NOTT_PROFILE = ForceState(
    anticipation=0.1,
    release_pressure=0.0,
    instability=0.2,
    density=0.5,
    control_vs_chaos=0.3,
)
```

These are starting points. They will be refined through perceptual iteration.

---

## Session Guide (Token Efficiency)

This project is designed to be worked on in narrow, focused Claude Code sessions.
Each session should have one target. Do not let sessions sprawl.

### Opening a session

Start every session with:

```
Read ARCHITECTURE.md. Current phase is [N]. Current target is [one sentence].
Do not read other files unless necessary for the target.
```

Then state only what you need done. Do not ask for a plan, a summary, or a
tour of the codebase. Go straight to the work.

### Session targets by phase

Each of these is one session, possibly two if something is genuinely complex:

| Phase | Target |
|-------|--------|
| UI | ~~FastAPI server + HTML/JS UI~~ **done** |
| 1a | ~~ForceState, ForceEngine, Controls, landscape.py~~ **done** |
| 1b | ~~BankGenerator (kick only) + MIDIEvent~~ **done** |
| 1c | ~~Archetype system (10 archetypes, expectation maps, role assignment)~~ **done** |
| 1d | ~~Write `test_force_engine.py` and `test_bank_generator.py`~~ **done** |
| 1e | Verify MIDI output sounds correct; tune force profiles by ear |
| 2  | Implement `Transport` with queue and interrupt |
| 3  | Extend `BankGenerator` for snare/hat, no inter-instrument logic |
| 4  | Inter-instrument roles in force engine and generator |
| 5  | Pressure curves — chainable 0→1 time functions; deformation modulator + MIDI CC output |
| 5a | Expression layer (CC automation via pressure curves) |
| 6  | Intent text parsing |
| 7  | Voice/sample layer |

### Rules for Claude Code sessions

- Read `ARCHITECTURE.md` first, nothing else unless required
- Work on one file or one interface at a time
- Do not refactor and extend in the same session
- Commit before ending a session — clean git state is cheap context
- If a session produces something that needs perceptual verification,
  stop and let Oak listen before continuing
- Do not scaffold Phase N+1 during Phase N

### What NOT to ask Claude Code

- "Build the sequencer" — too broad
- "Refactor everything to be cleaner" — expensive, low value early
- "What does this codebase do?" — read ARCHITECTURE.md yourself first
- "Plan the next few phases" — the plan is already here

---

## Notes for Claude Code

- Start with Phase 1 only. Do not scaffold beyond what is needed.
- `kick_only.py` should produce audible MIDI output to a virtual port within
  Phase 1. That is the acceptance criterion.
- Tests assert structural intent (density counts, role distribution,
  resolution_likelihood range). Perceptual correctness is verified by Oak listening.
- Use dataclasses throughout. Keep force engine and bank generator strictly separated.
- No LLM calls at runtime. The intent layer at this stage is just axis position.
- Python 3.11+. Use `pyproject.toml` with `[project]` table.
- rtmidi via `python-rtmidi`. Virtual port name: `thelmic`.

## Behaviour-First Development Direction

The current system has working pressure curves, deformation modulation, MIDI CC output, and a live Oak → Chaos → Nott slider. The next phase should not simplify the UI yet, and should not add more pressure curve shapes for their own sake.

The priority is to stabilise the behavioural core so the system can be observed, debugged, and heard as it changes over time.

### Current Problem

The system can currently:

- move through the Thelmic landscape using the slider
- trigger pressure curves
- affect beat structure through deformation modules
- affect filters/gates/effects through outbound MIDI CC

But pressure curves are still mostly user-triggered behaviours.

What is missing is an internal transition system where movement through the landscape automatically creates appropriate pressure behaviour.

### Core Concept: Transition / Intent Vector

A slider movement should not directly set the live landscape position.

Instead, dragging from one point to another should create an active transition object:

```yaml
transition:
  start_position: 0.32
  target_position: 0.78
  current_position: 0.41
  remaining_distance: 0.37
  duration_bars: 8
  elapsed_bars: 2
  direction: toward_nott
  active: true
```

This transition is the engine's current intent.

The UI should render this as a horizontal bar from the current position to the target position on the Oak → Chaos → Nott axis. As the system travels, the bar shortens until the destination is reached.

### Transition Behaviour

The transition should:

1. Capture the current landscape position as `start_position`
2. Capture the user's selected destination as `target_position`
3. Move the actual landscape state toward the target over musical time
4. Expose transition progress, remaining distance, direction, velocity, and phase
5. Trigger or modulate internal pressure behaviours automatically
6. Update visual state so the performer can see where the system is going

The key idea:

```text
user sets destination
system performs the journey
```

not:

```text
user manually triggers every pressure curve
```

### Pressure Curves Become Internal Behaviour

Pressure curves should remain available, but they should increasingly behave as internal modulation timelines attached to transitions.

They should not be thought of primarily as user-facing controls.

Example:

```yaml
on_transition:
  from: oak
  to: chaos
  behaviours:
    - increase ghost injection
    - tighten gate
    - reduce stability
    - avoid full release

on_transition:
  from: chaos
  to: nott
  behaviours:
    - decay ghost pressure
    - open filter or collapse it
    - increase impact behaviour
    - resolve or discharge accumulated tension
```

### Required State to Expose

Add a visible/debuggable state model that includes:

```yaml
thelmic_state:
  position: 0.0-1.0
  target_position: 0.0-1.0
  direction: left | right | none
  transition_active: true/false
  transition_progress: 0.0-1.0
  transition_remaining: 0.0-1.0
  unresolved_tension: 0.0-1.0
  phrase_phase: 0.0-1.0
  last_impact_time: bar.beat
  recent_intensity: 0.0-1.0
```

This state should be inspectable in the UI/log/debug output so we can verify whether the engine's internal state matches what we hear.

### Why This Matters

The current system can make pressure happen, but the performer still has to manually coordinate too much of it.

The next goal is for the system to understand:

```text
where we are
where we are going
how far remains
what pressure has been built
what has not yet resolved
```

Then deformation modules and CC outputs can respond musically to the journey.

### Behaviour Before UI Simplification

Do not collapse the interface into the final "tension trackpad" yet.

First, the behaviour model must prove itself using the existing UI/debug visibility.

The correct order is:

1. Add transition/intention state
2. Make pressure curves respond to transitions
3. Expose state visually and in logs
4. Confirm the audible result
5. Only then simplify the UI into a tension trackpad

### Future UI Direction: 2D Tension Trackpad

Eventually the main control may become a 2D gesture surface.

Horizontal movement:

```text
Oak → Chaos → Nott
```

Vertical movement:

```text
up   = intensify / strain / lift / accelerate
down = drain / hollow / restrain / collapse
```

But this should be implemented only after transition behaviour is musically convincing.

### Development Plan

#### Phase 1: Transition State

Implement a `Transition` model:

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

Add derived values:

```python
progress
remaining
direction
velocity
```

#### Phase 2: Transition Engine

Add a transition engine that updates current landscape position over musical time.

The slider should set a target, not instantly overwrite the live position.

#### Phase 3: Pressure Behaviour Hooks

Allow pressure curves and deformation modules to respond to transition state.

Example inputs to modules:

```python
transition_progress
transition_remaining
transition_direction
unresolved_tension
phrase_phase
```

#### Phase 4: Debug/Visual State

Render:

- current position on Oak → Chaos → Nott axis
- target position
- shrinking transition bar
- transition direction
- active pressure behaviours
- current deformation intensities
- current outbound CC values

#### Phase 5: Auditory Validation

Test whether movement through the landscape now creates audible, expected pressure changes without manually launching curves.

Expected result:

```text
Moving toward Chaos should create structured tension.
Moving toward Nott should discharge, collapse, or impact.
Returning toward Oak should stabilise without becoming dead.
```

### Design Principle

Pressure curves and deformations should not be extra controls the performer must manually operate.

They should become embedded musical behaviours driven by transition intent.

The performer should ride the system at the level of intent.

The engine should handle the pressure mechanics.
