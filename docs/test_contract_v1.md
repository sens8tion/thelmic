# Thelmic Test Contract v1.0

Status: Draft invariant contract

v1.0 tests validate the final musical output against `musical_rules.md`.
They must not encode implementation details, legacy module behaviour, UI
rendering choices, or hidden correction passes.

## Test Scope

Tests inspect final output from the v1.0 behaviour-producing system:

```text
music_rules -> note_generation_chain -> motif_engine -> stream_engine -> final events
```

The test contract may use harness plumbing to run the generator, but the
assertions must be phrased in terms of musical invariants.

## Required Invariants

### Percussive Drive

The final output must contain continuous percussive drive in normal state.
The drive must not collapse into isolated marker hits.

### Drop-Prep Silence

Silence is valid only inside drop-prep. Any full silence outside drop-prep is
invalid.

### Timing Anchor

A timing anchor must always survive. This includes drop-prep.

### Motif Persistence

Every active motif must persist for at least one phrase.

### Motif Mutation Limit

Within a phrase, motif mutation must not exceed one event or 20 percent.

### Structural Drop Boundary

Structural changes may commit only at drops.

### Structural Exclusivity

Only one structural change may occur per phrase.

### Instrument Compliance

All instruments must obey the rules. No instrument may bypass motif,
continuity, drop, or structural exclusivity rules.

## Disallowed Tests

Do not write v1.0 tests that depend on:

- file/function names
- legacy system stages
- private counters as behavioural proof
- UI rendering details
- MIDI port implementation
- post-fix correction behaviour

Diagnostics may help explain failures, but final-output invariants decide pass
or fail.

