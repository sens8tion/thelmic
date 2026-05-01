# Thelmic v1.0 Reset

Status: Draft execution charter
System version target: v1.0.0

This document defines the complete reset of Thelmic from v0.9 to v1.0.
It establishes a clean architectural boundary, a version-controlled musical
rules contract, a minimal invariant test strategy, a controlled sunset of
legacy systems, and a rebuild sequence for a rule-driven generator.

This is the authoritative transition plan for v1.0. Runtime behaviour is not
changed by this document alone.

## Core Philosophy

```text
Rules -> Generation -> Streaming -> later Expression -> Validation
```

- Rules are contractual.
- Tests validate invariants only.
- Generator must produce valid output directly.
- There are no post-fix or hidden correction systems.
- All behaviour is explicit and versioned.

## Versioning Model

Thelmic is versioned as a coherent system:

```text
thelmic: v1.0.0
music_rules: v1.0
note_generation_chain: v1.0
motif_engine: v1.0
stream_engine: v1.0
pression_engine: v0.9-disabled, future v1.0
test_contract: v1.0
```

All behaviour-producing components must be version-aligned. Mixed-version
execution is not permitted. A component cannot claim v1.0 unless it passes the
v1.0 invariant tests.

## System Boundary

Behaviour-producing components:

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

Behaviour-transparent infrastructure:

```text
UI / visualisation
MIDI output / renderer
clock / transport
config
logging / diagnostics
test harness plumbing
```

These must not add or remove events, change timing, alter motif identity,
affect phrase/drop structure, apply rules, or compensate for invalid
generation. If they do, they must become versioned behaviour-producing
components.

## Component Responsibilities

### music_rules

Defines all constraints. No runtime behaviour.

### note_generation_chain

Generates all musical events, including percussive backbone, motif
instantiation, drop-prep behaviour, and timing anchor maintenance.

### motif_engine

Controls motif identity and legal mutation.

### stream_engine

Schedules and emits valid events. It must not make musical decisions.

### pression_engine

Deferred. Future expressive modulation only.

### test_contract

Validates all invariants against final output.

## Rules Versions

`docs/music_rules_v0.9.md` is the frozen historical baseline. Do not modify it
except to correct archive metadata.

`musical_rules.md` is the current v1.0 contract and is the canonical source of
truth for new v1.0 implementation.

## Music Rules v1.0 Core Invariants

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

This replaces legacy lane removal rules and rhythm continuity rules.

The system must maintain continuous temporal drive at all times while allowing
a single controlled anticipation sequence before a drop.

Core invariant: a timing anchor must always be present.

Normal state:

- Continuous percussive drive
- No full-lane removal
- No fading
- No drive reduction

Drop-prep state:

- Controlled reduction is allowed
- Timing anchor must persist
- Anchor may tighten or subdivide
- System must feel like compression, not collapse

Reintroduction:

- Occurs at or before drop
- Must increase intensity
- No fade-ins

Disallowed:

- Full loss of grid
- Loss of timing reference
- Gradual decay of drive
- Accidental gaps
- Overlapping anticipation phases

## Motif System

Motif types:

```text
percussive pattern motif
drop-prep anchor-tightening motif
hook motif
call/response motif
```

Motif rules:

- Must persist at least one phrase.
- Mutation is limited to adding or removing one event, or a maximum 20 percent
  change.
- Larger change is structural.
- Structural changes are allowed only at drops.
- These rules apply to all instruments.

## Structural Exclusivity

Only one structural change is allowed per phrase.

This includes motif introduction, major mutation, drop-prep activation, and
percussive omission strategy.

## Test Contract v1.0

Tests must validate invariants only, operate on final output, ignore
implementation details, and fail on any violation.

Legacy tests are sunset during the v1.0 rebuild. Until a legacy test is removed
or replaced, it does not define v1.0 behaviour.

## Sunset Plan

Delete during the v1.0 reset:

```text
old generation engine
post-fix systems
legacy gap-removal model
legacy drive scoring system
old pression engine
legacy tests
hidden behavioural utilities
```

Retain if behaviour-neutral:

```text
event model
phrase timing model
output/rendering
```

## Rebuild Sequence

```text
1. Commit this document
2. Freeze v0.9 rules
3. Create v1.0 rules
4. Define invariant tests
5. Delete legacy tests
6. Disable old engine
7. Build minimal generator
8. Implement motif system
9. Implement drop-prep behaviour
10. Apply structural exclusivity
11. Rebuild pression later
```

## Minimal Generator Requirement

The first v1.0 generator must maintain timing anchor, maintain percussive
continuity, obey motif rules, preserve the grid through drop-prep, and pass all
invariant tests.

It does not need to sound good, be complex, or include pression.

## Hard Rule

```text
No hidden behaviour.
No post-fix systems.
No rule bypasses.
No hidden corrections.
```

All behaviour must exist inside declared components and obey v1.0 rules.
