# Thelmic Music Rules v1.0

Status: Active v1.0 contract
Historical baseline: `docs/music_rules_v0.9.md`

This file is the canonical musical rules source for v1.0 implementation.
All behaviour-producing components must obey this contract.

## Version Alignment

```text
thelmic: v1.0.0
music_rules: v1.0
note_generation_chain: v1.0
motif_engine: v1.0
stream_engine: v1.0
pression_engine: v0.9-disabled, future v1.0
test_contract: v1.0
```

Mixed-version musical execution is not permitted. A component cannot claim
v1.0 unless it passes the v1.0 invariant tests.

## Behaviour Boundary

Only these components may produce musical behaviour:

```text
music_rules
note_generation_chain
motif_engine
stream_engine
pression_engine
test_contract
```

No other component may generate events, mutate events, alter timing or
structure, influence motifs or drops, or apply musical logic.

Behaviour-transparent infrastructure includes UI, visualisation, MIDI output,
clock, transport, config, logging, diagnostics, and test harness plumbing.
These must not add or remove events, change timing, alter motif identity,
affect phrase/drop structure, apply rules, or compensate for invalid
generation. If they do, they must become a versioned behaviour component.

## Component Responsibilities

### music_rules

Defines constraints. It has no runtime behaviour.

### note_generation_chain

Generates all musical events directly from the rules. It includes the
percussive backbone, motif instantiation, drop-prep behaviour, and timing
anchor maintenance.

### motif_engine

Controls motif identity and legal mutation.

### stream_engine

Schedules and emits valid events. It must not make musical decisions.

### pression_engine

Disabled for v1.0 reset. Future expressive modulation only.

### test_contract

Validates final-output invariants.

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
```

## Continuity and Anticipation

The system must maintain continuous temporal drive at all times while allowing
a single controlled anticipation sequence before a drop.

This rule replaces legacy lane removal rules and rhythm continuity rules.

### Timing Anchor

A timing anchor must always be present.

### Normal State

Normal state requires:

- continuous percussive drive
- no full-lane removal
- no fading
- no drive reduction

### Drop-Prep State

Drop-prep is the only state where controlled reduction is allowed.

Drop-prep requires:

- timing anchor persists
- anchor may tighten or subdivide
- system feels like compression, not collapse

### Reintroduction

Reintroduction occurs at or before the drop. It must increase intensity. It
must not fade in.

### Disallowed

The following are disallowed:

- full loss of grid
- loss of timing reference
- gradual decay of drive
- accidental gaps
- overlapping anticipation phases

## Motif System

Motif types:

```text
percussive pattern motif
drop-prep anchor-tightening motif
hook motif
call/response motif
```

Motif rules:

- A motif must persist at least one phrase.
- A legal mutation may add or remove one event.
- A legal mutation may change at most 20 percent of the motif.
- A larger change is structural.
- Structural changes are allowed only at drops.
- These rules apply to every instrument.

## Structural Exclusivity

Only one structural change is allowed per phrase.

Structural changes include:

- motif introduction
- major mutation
- drop-prep activation
- percussive omission strategy

## Drop-Prep Grid Reminder

v1.0 does not have a gap-removal model.

Drop-prep is compression before drop. It must preserve a clear timing anchor
or grid reminder.

The stream must never lose the grid.

## Drop

A drop is the only valid boundary for structural change.

At a drop:

- timing remains continuous
- the timing anchor is present
- a structural change may commit
- intensity must be reintroduced at or before the drop

## Test Contract

v1.0 tests must:

- validate invariants only
- operate on final output
- ignore implementation details
- fail on any violation

Legacy tests do not define v1.0 behaviour unless explicitly migrated into the
v1.0 test contract.

## Hard Rule

```text
No hidden behaviour.
No post-fix systems.
No rule bypasses.
No hidden corrections.
```

All behaviour must exist inside declared components and obey v1.0 rules.
