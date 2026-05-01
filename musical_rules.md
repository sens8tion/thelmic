# Thelmic Music Rules v1.2

**© sens8tion. All rights reserved.**

> **NOT FOR COMMERCIAL USE** without an application licence from sens8tion.
> Personal, educational, and non-commercial research use is permitted.
> To apply for a commercial licence: contact sens8tion directly.

Status: Active v1.2 contract
Supersedes: v1.1
Historical baseline: docs/music_rules_v0.9.md

---

## Purpose

This document defines the complete musical behaviour contract for the thelmic sequencer.

The system is a **deterministic musical stream processor**.

> The performer sets destination. The system performs the journey.

---

## Version Alignment

```text
thelmic: v1.2.0
music_rules: v1.2
note_generation_chain: v1.0
motif_engine: v1.0
stream_engine: v1.0
pression_engine: v1.1-planned
test_contract: v1.2
```

Mixed-version execution is not permitted.

---

## Behaviour Boundary

Only these components may produce musical behaviour:

```text
music_rules
note_generation_chain
motif_engine
stream_engine
pression_engine
test_contract
dimension_engine      — derives v1.2 dimensions from landscape trajectory
phrase_engine         — derives phrase state and archetype from dimensions
landscape_trajectory  — derives trajectory state from performer input
archetypes            — defines archetype patterns and selection logic
```

All other components are behaviour-transparent.

Behaviour-transparent infrastructure includes UI, visualisation, MIDI output,
clock, transport, config, logging, diagnostics, and test harness plumbing.

These must not add or remove events, change timing, alter motif identity,
affect phrase/drop structure, apply rules, or compensate for invalid generation.

If they do, they must become a versioned behaviour component.

Hard rule:

```text
No hidden behaviour.
No post-fix systems.
No rule bypasses.
No hidden corrections.
```

---

## Core Model

The system operates as a deterministic pipeline:

```text
rules -> landscape_trajectory -> musical_dimensions -> phrase_state -> sub_phrase_state -> motif_state -> render -> event_stream
```

Renderers do not invent behaviour.

```text
Renderers are not composers.
```

---

## Parametric Identity

The system produces musical territories addressable by three parameters:

```text
seed : feature : heat
```

- **seed** defines the world — terrain topology, feature positions, signature rhythms
- **feature** selects a location within that world — Oak, Nott, or a named Chaos peak (C1–C5)
- **heat** defines energy expression at that location

The same address always produces the same musical territory. This is a design invariant, not a feature.

People will develop vocabulary around specific addresses. The system must support this by making addresses readable, shareable, and enterable.

Rules:
- feature names are stable for a given seed
- the number of Chaos peaks (3–5) is stable for a given seed
- navigating to a feature by name must produce deterministic behaviour
- address format is: `seed/feature/heat` (example: `1103/C3/0.7`)

---

## Determinism Contract

Given identical:

```text
music_rules
landscape_trajectory
musical_dimensions
phrase_state
sub_phrase_state
motif_state
clock_position
seed (if used)
```

The output must be identical.

Randomness is only allowed if:

- seeded
- declared
- reproducible
- inside an authorised behaviour component

No component may infer musical intent from generated output.

---

## Core Invariants

```text
1. Percussive drive never collapses
2. Drop-prep is grid reminder
3. Timing anchor always survives
4. Motif persists at least one phrase
5. Motif mutation <= one event or <= 20 percent
6. Structural change only at drop
7. Only one structural change per phrase
8. All instruments obey rules
9. Intent comes only from landscape trajectory
10. Anticipation mechanisms preserve anchors
```

---

## Intent and Musical Dimensions

Landscape trajectory is the only external intent input.

```text
landscape_trajectory
```

All other musical state is derived deterministically from musical dimensions.

Phrase state, sub-phrase state, rhythmic archetype, motifs, transformers, and
rendered events are **not intent sources**. They are derived outputs of the
intent model.

No component may infer intent from generated output.

---

### Musical Dimensions

The system derives these musical dimensions:

```text
stability
pressure
sparsity
release
emphasis
```

These are the only v1.2 musical dimensions.

The following are not independent dimensions:

```text
anticipation
density
mutation_pressure
drop_proximity
```

---

### Stability

Stability is a dimension of the thelmic landscape.

It is derived from absolute landscape position.

Stability governs how much rhythmic deformation is allowed.

High stability:

- preserves archetype conformity
- limits mutation
- favours repetition/fixation
- allows clean withholding
- avoids destabilisation

Low stability:

- allows greater mutation
- allows destabilisation
- allows syncopation
- allows pattern deformation within archetype constraints

Stability must not override anchor preservation.

---

### Pressure

Pressure is derived from the journey between current and target landscape
positions.

It is created by movement through the landscape, especially when the performer
moves the slider toward a new target state.

Pressure drives anticipation mechanisms.

Low pressure:

- minimal change
- stable groove
- low mutation

Medium pressure:

- light sparsity
- small mutation
- limited repetition/fixation
- subtle emphasis shifts

High pressure:

- stronger sparsity
- withholding
- repetition/fixation
- destabilisation where stability allows it
- compression

Pressure must not directly cause structural change except through a legal drop
commit.

---

### Sparsity

Sparsity has two components:

**1. Positional sparsity** — derived from the stability of the current landscape position.
A Chaos peak with inherent low stability has a higher baseline sparsity than Oak.
This is permanent at that position: instruments withheld by positional sparsity do not return unless you move to a more stable position.

**2. Pressure sparsity** — derived from movement and drop proximity.
Adding to the positional baseline. Returns to baseline when movement stops.

```text
sparsity = positional_sparsity(stability_bias) + pressure_sparsity(pressure)
```

Positional sparsity drives the instrumentation floor:
- stability_bias ≥ 0.70 (Oak):     full instrumentation available
- stability_bias 0.45–0.70 (Nott): minor witholding (call/response may thin)
- stability_bias 0.25–0.45:        hook and call/response withheld
- stability_bias < 0.25 (deep Chaos): only kick + hat + bass survive

**Timing anchor rule:** At any moment, at least one of kick / snare / hat must be present. The system may strip all three down but never simultaneously.

Removal order under rising sparsity:
1. Hat off-beat steps thin first
2. Snare (beyond anchor steps) thins
3. Hat on-beat steps thin
4. Snare anchor steps thin
5. Kick anchor is last — never fully removed

This means before a drop or deep in a Chaos peak, the music may reduce to kick only for a bar or two. That IS the tension. Kick is the timing anchor of last resort.

**Return rule:** All withheld voices return as stability increases. Moving toward a stable position progressively reintroduces voices in reverse removal order — hat on-beats first, then off-beats, then snare ghost notes, then hook, then call/response. Full restoration requires reaching a position with stability_bias ≥ 0.70. Intermediate positions produce partial restoration.

Positional sparsity gates melodic/harmonic voices (hook, call/response) before it affects percussion. Percussion sparsity is driven by combined positional + pressure sparsity.

This creates the musical reality: **Chaos is stripped down. Stability is full.** The landscape defines what music is possible at each location.

Instrument return order on stability increase:
1. Call/response returns first (most context-sensitive)
2. Hook returns (melodic identity)
3. Snare ghost notes return
4. Last to return: all voices present

Instrument removal order on stability decrease (reverse):
1. Call/response withheld first
2. Hook withheld
3. Snare reduced to anchor only
4. Hat thinned toward kick-aligned only
5. Floor: kick + hat + bass always survive

Positional sparsity is a hard constraint. Pressure sparsity, heat, and user input cannot override the positional floor.

Sparsity is derived from pressure and position.

Sparsity is implemented through controlled removal of events.

Sparsity may contribute to anticipation.

Rules:

- sparsity must not remove anchor steps
- sparsity must not remove the timing anchor
- sparsity must not cause full-lane collapse
- sparsity may remove non-anchor events
- sparsity may persist as part of the rhythmic pattern if still legal under the active archetype and motif rules

Sparsity is not default emptiness. It is intentional contrast.

---

### Release

Release is provided at a drop.

Release resolves accumulated pressure.

Release may be complete or partial. A partial release may require later drops to
close the remaining landscape gap.

At release:

- structural change may commit
- sparsity may resolve
- withholding resolves
- repetition/fixation may break
- destabilisation resolves or resets
- pressure is reduced
- timing continuity must remain intact

Release must not cause timing loss.

---

### Emphasis

Emphasis is provided subtly in the events immediately after a drop.

Emphasis reinforces either the new structure or the continued structure after
release.

Emphasis may be implemented through:

- velocity emphasis
- anchor reinforcement
- instrument prominence
- transient clarity
- limited density reinforcement within archetype constraints

Emphasis must not create a second structural change.

---

### Anticipation

Anticipation is not an independent dimension.

Anticipation is what the listener feels when pressure is expressed through
controlled mechanisms such as sparsity, withholding, repetition, destabilisation,
compression, and survivor signal.

Anticipation must not be directly controlled or encoded as a hidden dimension.

```text
anticipation = emergent percept
```

---

## Anticipation Mechanisms

Anticipation mechanisms are controlled transformations driven by pressure and
bounded by stability.

They are not independent intent sources.

They are not structural changes unless they exceed the legal mutation limits or
replace phrase-level identity.

Mechanisms:

```text
withholding
repetition
destabilisation
compression
survivor_signal
```

General rules:

- mechanisms are triggered by pressure
- stability constrains which mechanisms are allowed
- mechanisms must preserve anchor rules
- mechanisms must preserve timing anchor
- mechanisms must not introduce structural change
- mechanisms must not replace rhythmic archetype
- mechanisms must not replace motif identity
- mechanisms must resolve at drop unless explicitly legal as a continuing motif mutation
- mechanisms must not persist beyond release as hidden state

---

### Withholding

Withholding removes or suppresses expected non-anchor elements.

Trigger:

- medium to high pressure

Effect:

- expected non-anchor events may be omitted
- secondary elements may be suppressed
- listener perceives something is being held back

Rules:

- must not remove kick/snare anchor steps
- must not remove timing anchor
- must not become full-lane removal
- must resolve at release unless the omission becomes a legal motif mutation

---

### Repetition / Fixation

Repetition reduces variation and locks the listener into a shorter perceived
cycle.

Trigger:

- medium to high pressure
- especially effective under high stability

Effect:

- mutation reduces
- a short loop or figure repeats
- anticipation builds through fixation rather than increased activity

Rules:

- must preserve archetype identity
- must preserve motif persistence rules
- must not create a new structural section
- should break or resolve at release

---

### Destabilisation

Destabilisation increases rhythmic instability without replacing the archetype.

Trigger:

- high pressure
- low stability

Effect:

- syncopation increases
- non-anchor variation increases
- pattern deformation increases within legal limits

Rules:

- must not remove anchors
- must remain recognisable as the active rhythmic archetype
- must not exceed motif mutation limits
- must resolve or reduce at release

---

### Compression

Compression creates a tightening feeling before release.

Trigger:

- increasing pressure

Effect:

- events cluster toward a boundary
- local activity may increase
- timing feels squeezed without changing grid resolution

Rules:

- must remain on the 1/16 grid
- must not introduce new anchor positions
- must not redefine the archetype
- must not cause full collapse after compression

---

### Survivor Signal

Survivor signal maintains time through high sparsity.

Trigger:

- high sparsity
- high pressure before release

Effect:

- one or a small number of elements preserve timing
- listener retains grid reference during thinning

Rules:

- must maintain timing anchor
- must not sound like normal full beat-bed activity
- must transition cleanly into release
- must not become hidden post-fix behaviour

---

## Rhythmic Archetype

A **rhythmic archetype** defines the base kick/snare/hat structure and the
associated sub/bass/ride expectations.

It is:

- phrase-level
- structural
- deterministic
- not inferred

Initial archetype set:

```text
HALF_STEP
TWO_STEP
SHUFFLED_TWO_STEP
STUTTER
ROLLING
BREAKBEAT_HARDCORE
AMEN
FOUR_ON_THE_FLOOR
HAPPY_HARDCORE
GABBER
```

Rules:

- one archetype is active per phrase
- archetype commits only at drop
- archetype must not change within a phrase
- archetype defines density tendency
- archetype defines grid conformity
- archetype defines anchor expectations
- archetype defines allowed deformation range
- generators must not invent archetype behaviour implicitly

Archetype is a constraint surface, not a frozen loop.

The engine may mutate the beat pattern, but mutation must remain legal under:

- motif persistence
- mutation <= one event or <= 20 percent
- anchor preservation
- phrase-level archetype identity
- structural change only at drop
- only one structural change per phrase

---

## Rhythmic Archetypes and Ride Layer

This section defines the canonical 1/16-step rhythmic archetype for all
archetypes and the associated ride layer behaviour.

### Grid Definition

```text
steps: 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15
notation:
x = hit
. = rest
```

All rhythmic archetypes are defined on a 16-step bar.

```text
1 step = 1/16 note
```

No 1/32 subdivision is part of the v1.2 archetype contract.

Dense archetypes express density through higher hit probability, velocity,
texture, and saturation of the 16-step grid, not through finer grid resolution.

---

### Core Rules

- archetypes are phrase-level structural identity
- one archetype is active per phrase
- archetype may change only at a drop
- archetypes define anchor positions and density expectations
- generators must approximate these patterns; they must not contradict them
- anchor steps must always be honoured
- additional events must not redefine the rhythmic archetype

---

### Anchor Definition

- Kick and snare define primary anchors.
- Hat defines subdivision support, not primary anchors.
- Any `x` in kick or snare is an anchor step.
- Anchor steps must always produce events.
- Anchors may be reinforced but not removed.
- Non-anchor steps may vary if archetype identity is preserved.

---

### Pattern Interpretation

- If an `x` step is an anchor, it is mandatory.
- If an `x` step is not an anchor, it is high-probability.
- A `.` step is low-probability, optional, or silent.
- Generators may vary non-anchor steps.
- Generators must not contradict the archetype identity.
- Mutations must remain within motif mutation limits unless committed structurally at a drop.

---

### Density Definition

Density is the proportion of active steps per bar.

```text
density = active_steps / 16
```

Density is not an independent intent dimension.

Archetypes define baseline density expectation.

Rules:

- density changes must not remove anchors
- density changes must remain consistent with archetype identity
- density changes are derived from pressure and sparsity
- density changes must remain legal under motif mutation rules

---

### Archetype Patterns

#### HALF_STEP

```text
kick:  x.......x.......
snare: ....x.......x...
hat:   x...x...x...x...
sub:   x...............
bass:  x...............
ride:  ................
```

#### TWO_STEP

```text
kick:  x.....x.....x...
snare: ....x.......x...
hat:   x.x.x.x.x.x.x.x.
sub:   ..x.......x.....
bass:  ..x...x...x...x.
ride:  ................
```

#### SHUFFLED_TWO_STEP

```text
kick:  x....x..x.......
snare: ....x.......x...
hat:   x..x.x..x.x..x..
sub:   ..x........x....
bass:  ..x..x....x..x..
ride:  ................
```

#### STUTTER

```text
kick:  x..x....x..x....
snare: ....x.......x...
hat:   xxxxxxxxxxxxxxxx
sub:   x..x............
bass:  x..x....x..x....
ride:  ..x.....x.....x.
```

#### ROLLING

```text
kick:  x...x.....x..x..
snare: ....x.......x...
hat:   xxxxxxxxxxxxxxxx
sub:   x...........x...
bass:  x..x.x...x..x...
ride:  ..x...x...x...x.
```

#### BREAKBEAT_HARDCORE

```text
kick:  x..x...x..x.....
snare: ....x...x...x...
hat:   x.xxxxxxxxxxxxx.
sub:   x...........x...
bass:  x...x...x...x...
ride:  ..x.x...x.x...x.
```

#### AMEN

```text
kick:  x..x....x.x.....
snare: ....x..x....x...
hat:   xxxxxxxxxxxxxxxx
sub:   x...........x...
bass:  x..x....x.x.....
ride:  ..x.x.x.x.x.x.x.
```

#### FOUR_ON_THE_FLOOR

```text
kick:  x...x...x...x...
snare: ....x.......x...
hat:   ..x...x...x...x.
sub:   x...x...x...x...
bass:  ..x...x...x...x.
ride:  ..x...x...x...x.
```

#### HAPPY_HARDCORE

```text
kick:  x...x...x...x...
snare: ....x.......x...
hat:   xxxxxxxxxxxxxxxx
sub:   x...x...x...x...
bass:  x.x.x.x.x.x.x.x.
ride:  x.x.x.x.x.x.x.x.
```

#### GABBER

```text
kick:  xxxxxxxxxxxxxxxx
snare: ....x.......x...
hat:   xxxxxxxxxxxxxxxx
sub:   xxxxxxxxxxxxxxxx
bass:  ................
ride:  xxxxxxxxxxxxxxxx
```

In high-density archetypes such as GABBER, sub may absorb the bass role and
bass may be suppressed entirely.

---

### Ride Layer Rules

- Ride is a high-frequency energy layer.
- Ride is not part of the primary kick/snare anchor structure.
- Ride must align to the 1/16 grid.
- Ride must not introduce new anchor positions.
- Ride must not override kick/snare anchors.
- Ride presence is deterministic per archetype.
- Ride presence is archetype-defined only.
- Ride must not appear unless explicitly defined in the archetype pattern.

---

### Additional Constraints

- These patterns define structural expectation, not exact event lists.
- Velocity, articulation, and motif rules apply on top.
- Motif mutation rules remain unchanged.
- Structural exclusivity remains unchanged.
- No archetype may violate core invariants.
- Ride must not redefine rhythmic identity.

---

### Invariant Compatibility

This section must not:

- introduce new behaviour outside allowed components
- override motif rules
- override drop rules
- introduce mid-phrase structural change
- change determinism

This section defines rhythmic archetype constraints only.

---

## Velocity Dynamics

Velocity is the primary energy instrument. The full 0–127 range is available and must be used expressively.

### Principle

Velocity contrast — the difference between loud hits and quiet hits — is the physical sensation of energy. Hard dance music uses extreme contrast as a structural device, not gentle modulation.

References: hardcore, hardstyle, industrial techno, drum and bass.

### Stability governs contrast

High stability (Oak character):
- Anchor velocity: 95–112
- Off-beat velocity: 55–75
- Ghost velocity: 20–38
- Consistent, uniform, predictable

Low stability (Chaos character):
- Anchor velocity: 110–127
- Off-beat velocity: 40–65 (or ducked to 8–20 on kick steps — see sidechain)
- Ghost velocity: 8–20
- Extreme peaks and valleys; the contrast IS the energy

### Emphasis

At the drop and for the first 32 steps of a new phrase, all velocities are boosted by ×1.15–1.25. This is the release burst.

Emphasis is automatic at every drop. It is not gated by user input.

### Sidechain pumping simulation

On kick-step positions (any step where the active archetype fires kick), hat velocity is ducked to 10–25% of its normal value.

On non-kick steps, hat velocity is at full or elevated level.

This creates the physical pumping sensation characteristic of hard dance music without requiring actual audio sidechain processing.

References: classic house pumping (e.g. French house), hardstyle sidechain, techno compression.

Rules:
- Hat anchor steps (on-beat, every 4 steps) are protected from sidechain duck beyond 15% of normal
- Hat off-beat steps may be fully ducked to near-silence on kick positions
- The duck ratio scales inversely with stability: high stability = shallow duck, low stability = deep duck

### Anticipation kicks

Under high pressure (pressure > 0.65), an anticipation kick fires at step 15 of each bar — the 16th step, immediately before beat 1 of the next bar.

This is one extra event per bar, which is a legal motif mutation.

This creates the "dragging" forward momentum characteristic of industrial techno and hardcore.

References: industrial techno (Paula Temple, Surgeon), old-school hardcore pre-beat stutter.

Rules:
- One anticipation kick per bar maximum
- Velocity is 50–60% of main kick velocity
- Duration shorter than main kick (0.05 vs 0.08)
- Must not fire during drop_prep compression phases

---

## Ghost Layer — 32nd Note Hits

Ghost hits at 32nd note positions are permitted as an ornamental layer only.

### Definition

A 32nd note hit falls at the half-step between two 1/16th grid positions.

```text
1/16 grid:  | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | ...
32nd ghost:     0.5   1.5   2.5   3.5   ...
```

### Rules

- Ghost hits must have velocity < 40
- Ghost hits carry no structural authority
- Ghost hits must not create new anchor positions
- Ghost hits must not appear unless the active archetype would not be contradicted
- Ghost hits must remain on the 1/32 grid
- Ghost hits are a separate voice layer — they never replace 1/16 events
- Ghost hit patterns are deterministic from (seed + archetype + phrase_index)
- Ghost hits must not persist if sparsity > 0.6

### Purpose

Ghost hits provide textural depth and the physical feel of a live drummer or programmer. They are the difference between a programmed grid and a played feel. They exist to serve the groove, never to define it.

High stability → ghost hits appear at predictable positions (consistent feel)
Low stability → ghost hits may appear at irregular positions (loose feel)
Heat modulates ghost hit density and velocity directly.

---

## Pre-Drop Anticipation Patterns

The approach to a drop uses one of two deterministic patterns depending on landscape stability. Both patterns are driven by `phrases_until_drop` and scale with heat.

### Pattern A — Compression (stability ≥ 0.50)

Subdivision of the timing anchor layer doubles as the drop approaches.
This creates the perceptual compression common to house, techno, and DnB builds.

```text
phrases_until_drop ≥ 2   full groove, no change
phrases_until_drop = 1   hat fires at 8th notes (every 2 steps) in final 8 bars
phrases_until_drop = 0   bars 1–12: quarter-note hat (every 4 steps)
                         bars 13–15: 8th-note hat (every 2 steps)
                         bar 16: 16th-note hat (every step)
                         → DROP
```

Heat scales the onset and depth:
- cold: compression begins only in `phrases_until_drop = 0`, final 4 bars
- hot: compression begins in `phrases_until_drop = 1`, deeper and earlier

### Pattern B — Mathematical Dissolution (stability < 0.50)

Events are removed in a deterministic algorithmic pattern. The specific shape is derived from `signature_rhythm.base_pattern_seed` — same seed, same dissolution curve.

Available removal patterns (selected by seed mod 3):

```text
0: Power-of-2 thinning   — keep every Nth step where N doubles each bar
                            (8 events → 4 events → 2 events → 1 event)
1: Euclidean removal     — E(k, 16) where k halves each bar
                            (distributes remaining events maximally)
2: Prime gap removal     — remove events at prime step indices first,
                            then composites (preserves mathematically irregular feel)
```

All patterns:
- NEVER remove kick anchor steps (step 0 always survives — minimum 1 event per bar)
- NEVER remove snare anchor steps
- Remove hat first, then call/response, then hook
- Bass survives always

Heat scales depth:
- cold: final phrase only, gentle thinning to 4 events per bar minimum
- hot: final 2 phrases, aggressive thinning to 1 event per bar (kick only)

### Invariants for both patterns

- Timing anchor must survive (minimum 1 kick per bar)
- Kick anchor steps must survive
- Snare anchor steps must survive
- Musical identity must remain recognisable until the final bar

### Emergent forms

The combination of archetype + ghost layer + compression/dissolution pattern creates a space of forms larger than the named archetype set. Specific (seed, heat, landscape_position) combinations will produce stable, reproducible musical identities that do not correspond to any named archetype but are valid musical forms.

These emergent forms are first-class outputs of the system. They are discovered through exploration and recovered through the same inputs. They are not errors or edge cases.

The system must not attempt to map emergent forms back to named archetypes. They exist as their own identities.

---

## Post-Drop Release

The drop is the moment of maximum energy return.

At the drop:
- All withheld instruments return immediately and completely
- Compression/dissolution state clears entirely
- Emphasis spikes and decays over the first 16 steps of the new phrase
- Ghost hit density may be elevated for the first 4 bars
- Velocity emphasis applies across all voices for the first 16 steps

Rules:
- Release must not fade in — it is instantaneous at step 0 of the new phrase
- Release must not create a second structural change (the drop was the structural change)
- Emphasis decay is linear over 16 steps, then zero
- Release is automatic and mandatory at every drop — it is not gated by user input

---

## Phrase State

Each phrase must expose:

```text
phrase_id
phrase_start_step
phrase_length_bars
active_rhythmic_archetype
active_motif_set
musical_dimensions
structural_change_committed
drop_prep_active
timing_anchor_lane
```

Rules:

- phrase state is authoritative
- phrase identity must remain stable between drops
- generators must not invent missing phrase identity
- phrase state fully determines rendering behaviour
- phrase state is derived from landscape trajectory and musical dimensions

---

## Sub-Phrase Structure

A sub-phrase is a structural unit inside a phrase.

It must:

- align to bar boundaries
- be contiguous
- have length = 2^n bars, where n >= 2
- have exactly one role

Expose:

```text
sub_phrase_id
parent_phrase_id
sub_phrase_start_step
sub_phrase_length_bars
sub_phrase_role
allowed_transformers
active_anticipation_mechanisms
```

Rules:

- sub-phrases define legal boundaries for controlled development
- sub-phrases do not directly generate events
- sub-phrases define legal boundaries for controlled variation
- generators must respect sub-phrase boundaries when applying motif mutation, density changes, instrument emphasis shifts, and anticipation mechanisms
- sub-phrases must not override phrase identity
- sub-phrases must not change rhythmic archetype
- sub-phrases must not introduce structural changes

---

## Controlled Intra-Phrase Evolution

Within a phrase, only bounded evolution is allowed.

Allowed:

```text
sparsity change
hat variation
velocity contour change
motif mutation within limits
drop-prep anchor tightening
instrument emphasis shift
anticipation mechanism activation
```

Not allowed:

```text
rhythmic archetype replacement
motif identity replacement
timing anchor loss
full lane removal
new structural section
second structural change
hidden intent inference
```

Rules:

- all intra-phrase evolution must be driven by musical dimensions
- all anticipation behaviour must occur through defined anticipation mechanisms
- any change beyond motif limits is structural
- structural changes only at drop
- maximum one structural change per phrase
- anchors must be preserved

---

## Motif System

Motif types:

```text
percussive pattern motif
drop-prep motif
hook motif
call/response motif
```

Rules:

- motif persists at least one phrase
- mutation <= 1 event OR <= 20 percent
- larger change is structural
- structural change = drop-only
- applies to all instruments
- motif mutation must preserve rhythmic archetype identity unless committed structurally at a drop

---

## Continuity and Anticipation

### Timing Anchor

A timing anchor must always be present.

### Normal State

Normal state requires:

- continuous percussive drive
- no full-lane removal
- no fading
- no drive reduction that causes collapse

### Drop-Prep State

Drop-prep is controlled compression before drop.

Drop-prep requires:

- timing anchor persists
- anchor may tighten or subdivide
- system feels like compression, not collapse
- anticipation mechanisms may operate if legal

### Reintroduction

Reintroduction occurs at or before the drop.

It must increase intensity.

It must not fade in.

Disallowed:

```text
loss of grid
loss of timing reference
gradual decay of drive
accidental silence
overlapping anticipation phases
```

---

## Sub-Phrase Roles and Transformers

Transformers describe musical intent only.

They must:

- attach to a sub-phrase
- be deterministic
- not directly affect generation in v1.2 unless explicitly mapped through musical dimensions and anticipation mechanisms

### Categories

#### Density

```text
density_increase
density_hold
density_thin
```

Density transformers must be interpreted through sparsity and pressure. Density
is not an independent intent dimension.

#### Stability

```text
stabilise
destabilise
```

Stability transformers must be interpreted through the stability dimension.

#### Emphasis

```text
kick_emphasis
snare_suppression
hat_drive
```

Emphasis transformers must be interpreted through post-drop emphasis or legal
instrument emphasis shifts.

#### Anticipation

```text
anticipation_build
pre_drop_non_silent
withholding
```

Anticipation transformers must be interpreted through pressure and anticipation
mechanisms.

#### Release

```text
release_resolve
release_thin
relock
```

Release transformers must occur only at or as part of drop/release handling.

---

### Transformer Assignment Rules

Transformers are selected based on sub-phrase role.

Assignment must be deterministic, rule-driven, and non-random.

No transformer may be assigned unless it is declared in this taxonomy and listed
as allowed for that role.

#### build

Allowed:

```text
density_increase
anticipation_build
withholding
```

Default:

```text
anticipation_build
```

#### hold

Allowed:

```text
density_hold
stabilise
```

Default:

```text
density_hold
```

#### release

Allowed:

```text
density_thin
release_resolve
pre_drop_non_silent
release_thin
relock
```

Default:

```text
release_resolve
```

#### transform

Allowed:

```text
destabilise
density_increase
density_thin
```

Default:

```text
destabilise
```

Rules:

- a sub-phrase may only use transformers listed under its role
- defaults are applied when no further rule overrides
- multiple transformers may be assigned only if they are compatible
- incompatible transformer combinations must fail validation
- any role not listed above emits no transformers
- transformer assignment must not bypass musical dimensions

---

## Structural Exclusivity

Only one structural change is allowed per phrase.

Structural changes include:

```text
motif introduction
major mutation
drop-prep activation
percussive omission strategy
rhythmic archetype change
phrase-level motif identity replacement
```

Anticipation mechanisms are not structural changes unless they exceed legal
mutation limits or replace phrase-level identity.

---

## Drop

A drop is the only valid structural boundary.

At drop:

- structure may change
- archetype may change
- motif may change
- release is provided
- emphasis may follow immediately after
- intensity must re-enter
- timing must remain continuous

Release may be partial.

A partial release may require later drops to close the remaining gap between
current and target landscape position.

---

## Planner vs Renderer Separation

Planner decides:

```text
phrase_state
sub_phrase_state
musical_dimensions
rhythmic_archetype
motif identity
structural change at drop
anticipation mechanisms
```

Renderer emits:

```text
events from state
```

Renderer rules:

- must obey rules
- must preserve anchors
- must preserve timing anchor
- must not invent structure
- must not infer intent
- must not repair invalid plans silently

---

## Pression Lanes

Pression lanes render musical dimensions and related derived signals for
external expression.

Pression lanes are expressive/control outputs.

They must not become hidden behaviour inputs.

v1.2 pression lanes should include:

```text
stability
pressure
sparsity
release
emphasis
```

### Sidechain lane (implemented)

The sidechain lane is a CC output that mirrors the kick pattern.

```text
channel:  7 (MIDI ch 8 in DAW)
cc:       1 (modwheel convention)
on kick:  value = 127
off kick: value = 0
```

Route this to compressor sidechain inputs in the DAW for physical audio sidechain pumping.

The sidechain lane fires at the musical resolution of the kick (1/16th grid), not at audio rate. The attack and release character is controlled by the receiving compressor's settings.

References: house pumping compression (French house, filter house), hardstyle sidechain, hard techno compressor groups.

Optional derived display lanes may include:

```text
withholding
repetition
destabilisation
compression
survivor_signal
```

Rules:

- pression lanes must be derived from declared state
- pression lanes must be deterministic
- pression lanes must not create note events
- pression lanes must not override note velocity for individual hits
- pression lanes must not infer intent from generated output
- pression lanes must not alter phrase/drop structure

---

## Diagnostics

Expose:

```text
phrase_id
sub_phrase_id
active_rhythmic_archetype
active_motif_set
musical_dimensions
sub_phrase_role
allowed_transformers
active_anticipation_mechanisms
timing_anchor_lane
drop_prep_active
structural_change_committed
```

Diagnostics must not affect output.

---

## Test Contract

Tests must:

- validate invariants only
- operate on final output
- ignore implementation details
- fail on any violation

v1.2 tests should validate:

```text
intent only from landscape trajectory
musical dimensions are deterministic
anchors are preserved
archetype identity is preserved under legal mutation
anticipation mechanisms preserve anchors
pression lanes do not generate notes
renderer does not invent structure
```

Legacy tests do not define v1.2 behaviour unless explicitly migrated into the
v1.2 test contract.

---

## Melodic Voice Tonality — Terrain, Genre, and Darkness

### Principle

The terrain defines what is musically available. Musical darkness, consonance, and tension scale with terrain stability. This is not a preference; it is the identity of each location.

```
Oak (stability ≥ 0.70)  →  resolved, warm, consonant
Nott (0.45–0.70)        →  searching, minor, tense
Chaos (< 0.45)          →  dissonant, sparse, deconstructed
```

This mapping applies to all non-percussive voices: bass, sub, hook, call, response.

---

### Pitch Material per Terrain

#### Oak — Resolved / Major character

Intervals available above root: unison, maj3 (+4), 5th (+7), maj7 (+11), octave (+12).

- Bass: root + fifth, medium sustain. Resolves confidently.
- Sub: root only. Long sustain. Physical low-frequency warmth.
- Hook: major scale phrases (root, maj3, 5th, maj7). Lyrical and settled.
- Call: ascending phrase from root to 5th or maj7. Clear question.
- Response: descending phrase back to root or maj3. Resolution.

References: French house (Daft Punk, Cassius), euphoric hardstyle, early hard house.

#### Nott — Searching / Minor character

Intervals available above root: unison, min3 (+3), 5th (+7), min7 (+10), octave (+12).

- Bass: root + minor third movement. Medium-short sustain. Purposeful but unsettled.
- Sub: root only. Medium sustain (shorter than Oak).
- Hook: minor phrases (root, min3, 5th, min7). Dark melodic identity.
- Call: upward motion with minor feel. Question unresolved.
- Response: partial answer — lands on 5th, not root. Tension remains.

References: industrial techno (Paula Temple, Surgeon), hard DnB, dark techno.

#### Chaos — Dissonant / Deconstructed

Intervals available above root: limited — root, min2 (+1), tritone (+6), octave (+12). All others withheld by positional sparsity.

- Bass: root only when present. Short duration (stab). May be suppressed by GABBER archetype.
- Sub: root. Shorter sustain than Oak or Nott.
- Hook: withheld below stability_bias 0.45. If present: atonal, irregular.
- Call/response: withheld below stability_bias 0.25. Not present at deep Chaos.

References: gabber, industrial techno, power noise, dark hardcore.

---

### Octave Placement

All non-percussive voices must occupy coherent octave registers:

```
sub:      root - 12     (one octave below bass root, typically MIDI 24–36)
bass:     root           (landscape-defined root note, typically MIDI 36–48)
hook:     root + 12      (one octave above bass, typically MIDI 48–60)
call:     root + 12–16   (same octave as hook, slightly higher phrases)
response: root + 12–9    (slightly lower than call — response resolves downward)
```

No voice may occupy the sub register (below bass root - 12) unless it IS the sub voice.
No voice may exceed root + 24 (two octaves above bass) — this creates hollowness, not energy.

The bass root note is the tonal anchor for the phrase. Hook, call, and response are melodic elaborations above it.

---

### Duration and Articulation by Archetype

Duration expresses the physical character of the genre. Short notes = stabs (percussive energy). Long notes = sustain (harmonic weight).

| Archetype | Bass duration | Sub duration | Character |
|-----------|--------------|--------------|-----------|
| HALF_STEP | 0.40–0.50s | 0.70–0.90s | Industrial mono-bass, long sustain |
| TWO_STEP | 0.25–0.35s | 0.55–0.75s | DnB reese bass character |
| SHUFFLED_TWO_STEP | 0.20–0.30s | 0.50–0.70s | Breakbeat sustain |
| STUTTER | 0.08–0.15s | 0.45–0.60s | Stutter stab, short punchy |
| ROLLING | 0.18–0.28s | 0.50–0.65s | Rolling groove, medium sustain |
| BREAKBEAT_HARDCORE | 0.06–0.12s | 0.40–0.55s | Hardcore stab, fast decay |
| AMEN | 0.30–0.45s | 0.55–0.70s | DnB reese, sustained |
| FOUR_ON_THE_FLOOR | 0.07–0.12s | 0.50–0.65s | French house pump stab |
| HAPPY_HARDCORE | 0.06–0.10s | 0.45–0.55s | Short bright stab, every 8th note |
| GABBER | — (suppressed) | 0.04–0.08s | Bass suppressed; sub minimal stab |

At high stability (Oak/Nott), multiply durations by 1.2–1.4.
At low stability (Chaos), multiply by 0.6–0.8.

---

### Bass: Archetype Pattern Authority

Bass firing steps are defined by the active rhythmic archetype (see Archetype Patterns section), NOT by the landscape SignatureRhythm alone. SignatureRhythm informs pitch (root_note) and note colour (density_bias, syncopation_bias). The archetype defines the rhythm grid.

Rule: `BassIntentStream` must derive firing steps from `PATTERNS[context.active_archetype].bass_steps`. The `sr.bass_steps` field may supplement note variety but must not override archetype-defined timing.

Exception: `sr.bass_steps` is used to select pitch variation (root, 5th, octave, colour tones). The archetype defines WHEN to fire; the SignatureRhythm defines WHAT to play.

GABBER exception: when `active_archetype == GABBER`, bass is entirely suppressed. Sub absorbs the bass role.

---

### Hook: Phrase Window

Hook is a lyrical, repeating motif. It fires across the full phrase unless sparsity gates it out. Hook is NOT restricted to specific sub-phrase windows unless an anticipation mechanism (drop-prep withholding) actively removes it.

Hook fires when `dims.sparsity < 0.50`.

---

### Call / Response: Temporal Structure

Call fires in the first half of the bar (steps 0–7). Response fires in the second half (steps 8–15). They are not simultaneous — call precedes response.

Both are gated by `dims.sparsity < 0.30`.

Pressure modulates density: at pressure = 0.0, call fires once per bar (the loudest slot). At pressure = 1.0, call may fire at all `call_slots`. Response fires only if a call fired in the same bar.

---

### Velocity Ranges for Melodic Voices

All melodic voices must use the full expressive range defined in Velocity Dynamics.

```
High stability (stability ≥ 0.70):   melodic peak  95–112, fill 55–75
Low stability  (stability < 0.30):   melodic peak 110–127, fill 40–65
Emphasis (post-drop burst):           +15–25% on all velocities
```

Hook, call, and response must apply stability-based contrast exactly as kick does.

---

### Citation

References for genre characteristics:
- Hardstyle: Headhunterz, Wildstylez, Da Tweekaz — kick-tail bass, root+fifth, Phrygian scale.
- Hardcore / Gabber: Angerfist, Paul Elstak, Rotterdam Terror Corps — stab bass, extreme contrast.
- Industrial techno: Paula Temple, Surgeon, Rebekah — sustained mono bass, tritone/min2 darkness.
- Drum and Bass: Goldie, LTJ Bukem, Photek, Andy C — Reese bass, Dorian/Phrygian, sustained.
- French house / Hard house: Daft Punk, Cassius, Thomas Bangalter — pump stab, root+5th+octave.

---

## Percussive Removal and Reintroduction

### Rule 1 — Removal Order Approaching a Drop

Instruments thin out from highest frequency to lowest. The general order is:

| Step | Element removed | Timing (bars before drop) |
|------|----------------|--------------------------|
| 1 | Open/closed hi-hats | 8–16 bars out |
| 2 | Clap / rimshot | 4–8 bars out |
| 3 | Snare (or snare layer) | 2–4 bars out |
| 4 | Kick sub/body (full kick muted or filtered) | 0–2 bars out |

Genre exceptions: In **drum and bass**, the break is looped and the kick+snare drop together as a unit when the Reese bass re-enters. In **hardcore/gabber**, the kick rarely disappears entirely — its distorted body stays as a wall of sound, but all other percussion strips away around it.

### Rule 2 — Reintroduction Order After a Drop

Return order is lowest-frequency first, rebuilding density:

1. Kick (full body, hard transient) — bar 1 of the drop
2. Snare / clap — bar 1 or bar 2, on the backbeat
3. Hi-hats (closed 16ths) — bars 2–4
4. Open hats / cymbals / rides — bars 4–8

**Hardstyle** typically hits all four simultaneously on the drop downbeat for maximum impact, then immediately thins to kick+clap only for the first 4-bar phrase, reintroducing hats in the second phrase.

### Rule 3 — Minimum Timing Anchor (Never Remove)

A single periodic pulse must remain audible or implied throughout every transition to prevent the listener losing metric footing:

| Genre | Minimum anchor |
|-------|---------------|
| Hardstyle | Kick on every quarter note (even if filtered to just sub click) |
| Hardcore / Gabber | Kick on every quarter note (distorted; effectively the drone) |
| Industrial techno | Kick on 1 and 3 or a single lo-passed pulse on beat 1 |
| Hard house | 4-on-the-floor kick; never fully absent |
| Drum and bass | A single snare hit on beat 3 of the break, or the kick on beat 1 |

If the kick is fully muted, a filtered sidechain pump, a bass thud, or a lo-passed reverb tail serves as the proxy anchor.

### Rule 4 — How Each Element Thins Before a Drop

| Genre | Kick | Snare / Clap | Hi-hats |
|-------|------|-------------|---------|
| Hardstyle | Reverse-reverb tail fades; kick body low-pass sweeps down | Clap removed 2 bars out; reverb tail lingers | 16th hats mute 8 bars out; synth stab takes over rhythmic role |
| Hardcore / Gabber | Kick distortion reduces; pitch may rise (scream kick) | Snare drops to ghost hits, then silence | Hats absent in main loop; only a white-noise sweep remains |
| Industrial techno | Kick velocity drops to sidestick thud or is gated to 2/4 | Snare replaced by metallic rim hit, then silenced | Hats morph to sparse 8th triplets, then a single 16th loop, then off |
| Hard house | Kick gains reverb wash (lengthens) rather than fading | Clap remains until 1 bar before drop, then cut | Hats reduced to offbeat 8ths, then silence |
| Drum and bass | Break chops shorten to a single kick hit | Snare kept on 3 as timing anchor; everything else muted | Hats and cymbals removed from break; noise sweep covers the gap |

### Rule 5 — The Grid Reminder (Pre-Drop Tension Device)

Each genre uses a device in the final 1–4 bars to reassert the grid and signal imminent release:

| Genre | Grid reminder device |
|-------|---------------------|
| Hardstyle | Snare or clap roll (32nd-note stutter) hard-compressed, often with pitch-rising reverse cymbal |
| Hardcore / Gabber | Gabber kick triplet fill or white-noise riser with sidechain pumping on every 16th |
| Industrial techno | Tightly gated hi-hat or metal loop cycling in 16th triplets, heavily sidechain compressed |
| Hard house | Pitch-filtered clap rolls (32nds) with increasing low-cut; classic filter sweep + clap stutter |
| Drum and bass | Amen/think-break stuttered into 32nd chops, each progressively shorter |

**Core principle:** the grid reminder is never melodic — it is purely percussive or noise-based, rhythmically dense, and metrically aligned to subdivisions of the governing pulse. Its compression or gating is deliberately audible, signalling controlled intensity rather than chaos.

### Implementation Mapping

The existing Thelmic anticipation engine implements these rules as follows:

| Rule | Thelmic mechanism |
|------|------------------|
| Hat removal 8–16 bars out | Compression mode: hat thins to 8th notes, then quarter notes |
| Snare removal 2–4 bars out | `anticipation_engine` dissolution mode withholds snare from step pool |
| Kick anchor always survives | `kick.py` never gated by sparsity; step 0 always fires |
| Grid reminder (final bars) | Compression mode bars 15–16: hat_interval=1 (full 16th rush) |
| Post-drop reintroduction | phrase_arc emphasis burst restores full velocity on drop |

Gap: the **snare** removal in bars 2–4 before a drop is not currently implemented. The `anticipation_engine` only gates hat, call, and response. Snare removal approaching a drop should be added as a dissolution mechanism when stability < 0.50.

---

## Snare Pre-Drop Fill Signatures

The snare fill approaching a drop must have a signature that matches the terrain character. It must not be the same generic roll every time.

### Two Fill Modes

Derived from the same stability-based selection as hat anticipation.

#### Compression Fill (stability ≥ 0.50)

The snare roll tightens progressively toward the drop. Ghost hits are added deterministically from `base_pattern_seed + bar_position`. The fill grows louder and denser in the final 4 bars. This creates the "snare stutter" characteristic of hardstyle, hard house, and hardcore builds.

- Bars 5–12: anchor steps only; occasional ghost (≤ 15% per step)
- Bars 13–14: anchor steps + more frequent ghosts (30–40% per step)
- Bar 15: dense ghost roll (60–70% per step), velocity rising
- Bar 16: near-continuous ghost roll, velocity at maximum before drop

Ghost velocity rises from 30% of anchor velocity at bar 5 to 85% by bar 16. The effect should feel like controlled compression, not chaos.

#### Dissolution Fill (stability < 0.50)

The snare pattern fragments. Anchor hits are intentionally dropped (deterministic gaps). Off-beat hits fire irregularly. This creates the "unsettled" feel before a Chaos-zone drop.

- Some anchor hits are removed (up to 3 gaps early, 0 near the drop — anchors must return by final 2 bars)
- Off-beat ghost hits appear at ~4% probability per step (sparse, irregular)
- The irregularity in gap position is determined by `base_pattern_seed mod 3`, creating signature variation across different terrain features

Both fills must remain deterministic: same `(seed, position, stability)` = same fill. No random behaviour.

Both fills stop on the drop itself — the drop beat resets to the full archetype pattern.

### Anchor Step Rule

Snare anchor steps (archetype-defined backbeat positions) must be the last to disappear and the first to return. They may be thinned but not erased until the final 2 bars before the drop.

This matches Rule 3 (minimum timing anchor) from Percussive Removal and Reintroduction: the snare backbeat is the secondary timing reference; the kick is the primary. Losing the snare before the final 2 bars removes listener orientation.

---

## Hook Phrase Window

Hook is a melodic identity voice. It functions as a STATEMENT — the phrase's signature melody that orients the listener. It must not persist across the entire phrase; that would make it background noise rather than identity.

### Hook Window Rule

Hook fires only at:
1. **Bars 1–2** (0-indexed: bars 0–1) — the phrase opening statement
2. **Sub-phrase boundaries** — the first bar of each new sub-phrase role (build, hold, release)

With the fixed 4+8+4 sub-phrase layout:
- Bar 0 (phrase start / build start) — hook fires
- Bar 1 — hook fires (continuation of opening statement)
- Bar 4 (hold start) — hook fires (1 bar re-statement at sub-phrase boundary)
- Bar 12 (release start) — hook fires (1 bar re-statement signals final section)

All other bars: hook is silent.

### Hook / Call-Response Mutual Exclusion

Hook and call/response never fire in the same bar. They are complementary voices:
- Hook bars: hook fires, call/response is silent
- Call/response bars: call/response fires, hook is silent

This prevents melodic crowding. The phrase alternates between lyrical identity (hook) and conversational development (call/response). This is the same structural principle as verse/chorus alternation in song composition.

Rule: if a bar is a hook bar, call_response_active = False. If a bar is not a hook bar, hook_active = False.

### Rationale

This creates audible phrase shape: the listener hears the hook at the start, then call/response conversation for the majority of the phrase, then a brief hook reminder at sub-phrase transitions. The hook never overstays.

References: drum machine programming conventions (Roland TR-style programming where lead elements are placed at phrase heads), classic techno "motif placement" (bars 1, 5, 9, 13 as structural points).

---

## Hi-Hat Density by Archetype

Continuous 16th-note hi-hats are characteristic of HIGH-DENSITY archetypes only. Lower-density archetypes use sparse or syncopated hat patterns that leave space for the kick transient to punch through.

### Rule

Constant 16th note hats (all 16 steps per bar): **GABBER and HAPPY_HARDCORE only**.

All other archetypes use patterns with deliberate gaps:

| Archetype | Hat character | Pattern type |
|-----------|--------------|--------------|
| HALF_STEP | Quarter-note hats | 4 hits/bar, on beats |
| TWO_STEP | 8th-note hats | 8 hits/bar |
| SHUFFLED_TWO_STEP | Sparse syncopated | 6 hits/bar, off-grid |
| STUTTER | Paired 16ths with gaps | 10 hits/bar, intentional gaps create the stutter |
| ROLLING | Rolling 8ths | 8 hits/bar, even |
| BREAKBEAT_HARDCORE | Dense 14-of-16 | Almost continuous, 2 gap steps |
| AMEN | Syncopated 11-of-16 | Amen break character, specific gaps |
| FOUR_ON_THE_FLOOR | Off-beat 8ths | 4 hits/bar on the "and" |
| HAPPY_HARDCORE | All 16 steps | Genre-correct constant hat |
| GABBER | All 16 steps | Genre-correct constant hat |

### Hat Sparsity Gating

Within any archetype, the sparsity gate applies on top:
- Off-beat hat steps thin first (threshold sparsity 0.52)
- On-beat hat steps thin last (threshold sparsity 0.88)

In the pre-drop anticipation phase, the hat subdivides (compression) or fragments (dissolution) per the anticipation patterns defined in Pre-Drop Anticipation Patterns.

### Rationale

In hardstyle and industrial techno, the 16th hat is used as a TENSION device approaching a drop — it enters from sparse to dense. If it plays constantly, the tension device loses its effect and the mix becomes fatiguing. Genre references (Paula Temple, Surgeon, Rebekah) demonstrate that the hat is sparse in the main groove and dense only in builds.

The GABBER and HAPPY_HARDCORE exceptions are genre-correct: constant 16ths are the defining character of these styles.

---

## Drone Voices

Three drone voices provide sustained tonal background that Ableton can process independently. They are not rhythmic — they provide the harmonic and textural foundation that percussion sits on top of.

All three drones fire deterministically from the same `(seed, position, phrase_index)` inputs that drive the rest of the system.

### Voice 1: Spacey Atmospheric Drone

Character: high-register sustained note. Evolves slowly. Provides the spacey/ethereal atmosphere above the rhythmic content.

- MIDI channel: 10 (DAW ch 11)
- Note: `root_note + 24` (two octaves above bass root) OR `root_note + 19` (two octaves + fifth)
- Duration: 16 bars (full phrase) — let Ableton shape with reverb, pitch, filter
- Velocity: scales with stability — stable/Oak: 60–75 (distant), Chaos: 40–55 (ghostly)
- Fires on: phrase start only (step 0 of bar 0 = step 0 of the bank)
- Gate: only at sparsity < 0.40 (stable terrain where there is space for atmosphere)
- Pitch selection: alternates between root+24 and root+19 per phrase, deterministic from phrase_index

References: psychedelic techno (Ben Klock, Marcel Dettmann pads), DnB atmospheric intro (LTJ Bukem), ambient techno (Aphex Twin Selected Ambient Works II).

### Voice 2: Low Rumble Drone

Character: sub-bass rumble, two octaves below the bass root. The felt presence below the sub bass. Provides physical body.

- MIDI channel: 11 (DAW ch 12)
- Note: `root_note - 12` (one octave below bass root, same as sub) OR `root_note` (unison with bass root)
- Duration: 8 bars (half phrase) — ties with the sub bass rhythm anchor
- Velocity: 50–80, scales with heat proxy — cold: 50 (rumble), hot: 75 (powerful)
- Fires on: bar 0 and bar 8 (twice per phrase)
- Gate: always present when playing (the rumble is terrain-independent)
- Pitch selection: alternates between root-12 and root for variety, deterministic from bar position

References: industrial techno (Paula Temple bassweight), gabber kick tail, Berghain-style sub-rumble, DnB Reese decay tail.

### Voice 3: Tension Chord Drone

Character: mid-range sustained power chord (root + fifth). Rhythmically triggered on the bar downbeat with a long decay that fills the bar. Creates the "chord pads behind the kick" feel.

- MIDI channel: 12 (DAW ch 13)
- Note: `root_note + 12` (one octave above bass root), sent as a single note (Ableton adds the chord)
- Duration: 3 beats (0.9s at 174 BPM) — decays before the next bar for rhythmic identity
- Velocity: scales with heat and pressure — low heat: 55–70, high heat: 75–95
- Fires on: bar downbeat (step 0 of each bar)
- Gate: sparsity < 0.50 AND stability > 0.30 (needs some structure to drive a chord)
- Development: velocity ramps up over the phrase (quieter at bar 1, louder at bar 13)

References: hardstyle power chord (Headhunterz, Wildstylez), French house chord stab (Daft Punk — Harder Better Faster), hard house rave chord.

### Drone Development Rules

All drones must develop over the phrase:
- Velocity rises from bar 1 toward the drop and falls at the phrase start
- This matches the genre conventions where drones build intensity with the rest of the mix
- The development curve is linear, deterministic, driven by `musical_step / 255`

No drone voice may produce more than one event per bar (single sustained note per bar maximum, except the tension drone which follows bar downbeats).

All drones are silent during drop preparation (final 4 bars before drop) to create space for the drop itself. They return on the drop bar as part of the release burst.

---

## Melodic Note Alignment and Key Rules

### Genre scale reference

Hard dance genres converge on a narrow set of modal/tonal choices:

- **Hardstyle / Hard House**: natural minor (Aeolian) or harmonic minor. The raised 7th (leading tone) appears on hook peaks and tension points. Major is rare — signals euphoric uplift only.
- **Hardcore / Industrial Techno**: Phrygian (b2, b6, b7) or Phrygian dominant (b2, maj3, b6, b7). Characteristic dark, aggressive flavour. Chromatic passing notes must resolve.
- **Drum and Bass (dark/neurofunk)**: Dorian (minor with raised 6th) or natural minor. The raised 6th creates the melancholic-but-driving DnB signature.

**Default for Thelmic**: natural minor (intervals 0, 2, 3, 5, 7, 8, 10) from the bass root.

---

### Alignment rules by voice

**Bass** is the harmonic anchor. All melodic voices derive from the bass root note.

**Sub** stays within root - 12 (one octave below). Does not harmonise — root reinforcement only. Moving sub to non-root pitches creates mud.

**Hook** must stay in key with the bass root. Minor palette: `(0, 3, 7, 10, 12, 15)` — root, b3, 5th, b7, octave, b10. The current major-7/9 palette `(0, 4, 7, 11, 12, 16)` conflicts with the dark hard dance register and must be replaced.

**Call** is in key during stable segments. In Chaos (low stability), tension notes are permitted (b2, tritone) provided:
1. The tension note is approached by step or falls by semitone from a chord tone
2. It resolves within 2 bars to a scale note
3. Only one tension note sounds at a time across call and response

**Response** resolves call. If call ends on a non-scale tone, response opens on the nearest scale tone. Response is never more chromatically active than call.

**Drones**:
- `drone_spacey`: root or 5th only, never moves
- `drone_rumble`: root only; reinforces sub
- `drone_tension`: b2 or tritone relative to root — designed to be dissonant. Never align with hook on identical beats.

---

### Simultaneous voice consonance guide

| Interval between simultaneous voices | Status |
|--------------------------------------|--------|
| Unison, octave, 5th | Always safe |
| b3, major 3rd | Safe in stable sections |
| b7, b6 | Acceptable tension colour |
| b2, tritone | Tension only; max one pair at a time |

---

### Oak vs Chaos alignment

- **Oak**: all melodic voices in scale. No tension intervals between simultaneous hook+call. drone_tension muted.
- **Chaos**: call may use up to 2 chromatic tension notes per 4-bar phrase. Response trails call with resolution. drone_tension active. Hook stays in scale — it is the listener's harmonic anchor even in Chaos.

---

### Implementation notes

1. **hook.py**: Replace `intervals = (0, 4, 7, 11, 12, 16)` with `(0, 3, 7, 10, 12, 15)` for minor palette. Consider `(0, 3, 7, 11, 12, 15)` for harmonic minor (raised 7th for tension) at high heat.
2. **call.py**: `tension_allowed = sr.stability_bias < 0.45`. When False, constrain to scale notes. When True, extend with [root+1, root+6] (b2, tritone) but enforce step-wise approach.
3. **response.py**: Check call's final note; if not in scale, open response on the nearest in-scale note.

---

## Pression Lane Dynamics Across the Phrase

Pression lanes are continuous CC signals (0–127) that evolve across the 16-bar phrase. They tell the DAW what the music is about to do and what it just did. Each lane has a distinct role and a different shape.

### Five phases

| Phase | Bars | Description |
|-------|------|-------------|
| Groove | bars 1–4 (build sub-phrase) | Baseline expression, identity established |
| Hold | bars 5–12 | Pattern locked, subtle evolution |
| Pre-drop 1 | bars 13–14 | Tension beginning to peak |
| Pre-drop 2 | bars 15–16 | Maximum tension, everything stripped |
| Drop | bar 1 of next phrase | Release burst, full reset |
| Post-drop | bars 2–16 of new phrase | Decay back to groove |

### Lane shapes

**PRESSURE** (CC 11): builds from groove baseline to 127 at the drop. Signals drive and urgency.
- Groove: 40–70 (medium)
- Hold: 60–80 (steady)
- Pre-drop: 80 → 127 (climbs)
- Drop bar 1: snap to 20 (release — drop is a reset of pressure)
- Post-drop: 20 → 70 over 16 bars (rebuilds)

**SPARSITY** (CC 12): climbs as instruments thin out approaching drop.
- Groove: 55–70 (medium density)
- Pre-drop: 70 → 127 (strips to kick only)
- Drop bar 1: snap to 0 (full instrumentation returns)
- Post-drop: 0 → 60 over 16 bars (thin out into groove)

**STABILITY** (CC 10): collapses approaching drop while pressure rises — the disintegration.
- Groove: 90–110 (very stable)
- Hold: 100 (locked)
- Pre-drop: 100 → 0 (pattern dissolves)
- Drop bar 1: snap to 120 (maximum lock — new pattern asserts)
- Post-drop: 120 → 90 (settles into groove stability)

**RELEASE** (CC 13): dry during tension build, maximum at drop, then decays.
- Groove/Hold/Pre-drop: flat at 35 (mostly dry — reverb conserved for drop)
- Pre-drop 2 (bars 15–16): drop to 0 (bone dry — silence creates contrast)
- Drop bar 1: snap to 127 (full reverb burst)
- Post-drop: 127 → 35 over 8 bars, then flat

**EMPHASIS** (CC 14): brightness/energy envelope. Maps to filter cutoff.
- Groove: 60–80
- Pre-drop: 60 → 0 (filter closes as strip-down happens)
- Drop bar 1: 127 (filter wide open)
- Post-drop: 127 → 70 over 16 bars

### Musical logic summary

PRESSURE and SPARSITY BOTH rise before the drop: one tracks drive (pressure), the other tracks absence (sparsity). Both peaking simultaneously is the "wall of silence with maximum energy" — the classic hard dance pre-drop moment.

STABILITY collapses in the opposite direction: the pattern dissolves while energy rises. The snap back to 120 at the drop is the "lock" — everything snaps to grid perfectly at the release.

RELEASE is purposely dry throughout the build (conserved) so the reverb burst at the drop creates a physical space expansion. "The room opens" when the drop lands.

### Implementation

```python
def compute_pression(musical_step, phrases_until_drop, dims, heat):
    bar = musical_step // 16    # 0–15 within phrase
    t   = musical_step / 255.0  # 0→1 over phrase

    if phrases_until_drop == 0:
        # Final phrase: maximum anticipation
        pressure  = min(127, int(60 + t * 67))
        sparsity  = min(127, int(70 + t * 57))
        stability = max(0,   int(100 - t * 100))
        release   = 0 if bar >= 14 else 35
        emphasis  = max(0,   int(80 - t * 80))
    elif phrases_until_drop == 1:
        # Pre-drop phrase: building
        pressure  = int(50 + t * 30)
        sparsity  = int(60 + t * 20)
        stability = int(100 - t * 20)
        release   = 35
        emphasis  = int(70 - t * 20)
    else:
        # Groove: steady with subtle breathing
        pressure  = int(dims.pressure * 70 + 30)
        sparsity  = int(dims.sparsity * 70 + 30)
        stability = int(dims.stability * 40 + 70)
        release   = 35
        emphasis  = int(60 + heat * 20)

    return dict(pressure=pressure, sparsity=sparsity,
                stability=stability, release=release, emphasis=emphasis)

def compute_pression_post_drop(musical_step, dims):
    """Post-drop decay: EMPHASIS and RELEASE decay back to groove baseline."""
    t = musical_step / 255.0
    return dict(
        pressure  = int(20 + t * 50),
        sparsity  = int(t * 60),
        stability = int(120 - t * 30),
        release   = int(127 - t * 92),
        emphasis  = int(127 - t * 57),
    )
```

References: hardstyle energy arc (Headhunterz), industrial techno build (Paula Temple), DnB drop reintroduction (Goldie Timeless era).

---

## Call/Response Phrase Timing

### Core Rule

Call/response operates at the **sub-phrase level**, not the bar level. A call phrase spans 2–4 bars; the response spans the next 2–4 bars. Call and response do NOT occur within the same bar.

### Standard patterns by genre

| Genre | Call length | Response length | Notes |
|-------|------------|-----------------|-------|
| Hardstyle / Hardcore | 4 bars | 4 bars | Dominant 4+4 template across 16-bar phrase |
| Industrial techno | 4 bars | 4 bars | Lead/vox call, synth/noise response |
| Hard house | 2 bars | 2 bars | Compressed to fit 8-bar sub-phrase |
| DnB (170+ BPM) | 2 bars | 2 bars | Inside 8-bar phrase unit |

### Phrase position rules

1. **Calls must start at sub-phrase boundaries**: bars 1, 5, 9, or 13 of a 16-bar phrase (0-indexed: 0, 4, 8, 12).
2. **Response enters immediately** on beat 1 of the bar after the call ends — no silence gap.
3. **4+4+4+4 layout** across a 16-bar phrase: call (bars 1–4), response (bars 5–8), call variation (bars 9–12), response resolution (bars 13–16).
4. **Suppress response in bars 13–16 of the pre-drop phrase** (phrases_until_drop=0) — the final sub-phrase belongs to tension, not resolution.
5. A call MUST NOT straddle a phrase boundary (no calls starting in bar 15–16 that would need to resolve in the next phrase).

### Relationship to sparsity

Call is gated by `dims.sparsity < 0.30`, same as before. But the WINDOW in which call fires is now bars 1–4 (call bars), not all bars indiscriminately. Response fires only in bars 5–8 (response bars) and only if a call fired in the current 4-bar window.

### Implementation notes

**call.py**: Replace `call_slots = (2, 6)` within-bar slots with a bar-window gate:
- Fire only if `(bar_index - 1) % 8 < 4` (first half of 8-bar cycle = bars 1–4)
- Within those bars, select 1–2 steps per bar for the call note (bars 1 and 3 of the call window)

**response.py**: Replace immediate within-bar response with:
- Fire only if `(bar_index - 1) % 8 >= 4` (second half of 8-bar cycle = bars 5–8)
- Only if a call fired in the preceding 4-bar window (already tracked by `_last_call_bar`)
- Response enters on beat 1 of bar 5 (first bar after call window)

This creates audible melodic conversation across bars rather than within-bar call/answer chatter that is too fast to register.

---

## Rhythmic Pattern Minimum Hold — 4 Bar Rule

Rhythm instruments (kick, snare, hat, open_hat) must maintain their pattern for a minimum of 4 consecutive bars before any change takes effect. This applies to:
- Pre-drop thinning (hat removal, snare removal)
- Compression mode transitions (16ths → 8ths → quarters)
- Dissolution mode pattern changes

**Rule:** Pattern changes are quantised to 4-bar boundaries within the phrase. The anticipation engine may compute a different state per step, but the hat and snare patterns must not change mid-bar or mid-4-bar block.

**Why:** In hard dance, structural changes land at phrase points. A hat that changes every bar sounds anxious and random. A hat that changes every 4 bars sounds intentional and building. The listener needs time to register the new pattern before it changes again.

**Implementation:** `compute_anticipation` computes per-step state. Before applying that state to the hat/snare voice, quantise the `musical_step` to the nearest 4-bar block boundary:
```python
block = (musical_step // 64) * 64  # 4 bars = 64 steps
ant = compute_anticipation(block, ...)  # use block-start step
```
This means the anticipation state changes at most once per 4 bars, not once per step.

**Exception:** the final 4 bars before a drop (bars 13-16 of the final phrase) may change more rapidly — this is the "maximum tension" zone where the grid reminder fires.
