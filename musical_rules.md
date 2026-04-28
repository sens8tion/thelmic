# Musical Rules

> This document captures the musical laws, style rules, and behavioural constraints of the
> thelmic sequencer. It sits alongside `ARCHITECTURE.md`, which describes system structure
> and phases.
>
> `ARCHITECTURE.md` = system mechanics  
> `musical_rules.md` = musical laws
>
> **Categories used throughout:**
> - **[HARD]** — Must always hold. No exceptions.
> - **[PREF]** — Preferred or usual behaviour. May vary under stated conditions.
> - **[ARCH]** — Depends on territory (Oak / Chaos / Nott).
> - **[OPEN]** — Unclear, inconsistent in code, or needing review.

---

## Purpose

The thelmic sequencer generates live hard electronic music driven by performer intent.

Its core musical claim:

> *The performer sets destination. The system performs the journey.*

All musical rules serve this claim. Structure emerges from intention, not from random variation.

---

## Core Musical Model

The sequencer operates as a **tension / release machine** shaped by landscape position
(Oak → Chaos → Nott axis) and drop boundaries.

**[HARD]** Musical state changes come in two forms only:
1. **Progressive bias** — gradual movement between drops
2. **Instantaneous commit** — only at an authorised drop boundary

**[HARD]** Drop boundaries are the only valid point for instant structural mutation.
Between drops, structure evolves continuously or holds.

**[PREF]** The musical cycle is approximately:
```
stable bed → call introduces tension → response answers → silence thins → drop relocks
```

**[HARD]** The phrase plan is the planner's authority. Generators are renderers,
not independent composers.

---

## Phrase Modes

Within a phrase (between drops), the system chooses **one** foreground mode:

| Mode | Description |
|------|-------------|
| `CALL_RESPONSE_MODE` | Stab or selected leader calls; hook absent or reduced |
| `HOOK_MODE` | Hook is primary foreground; call/response disabled or minimal |

**[HARD]** Hook-led sections and call/response sections are **mutually exclusive** within
a single phrase. A phrase is either one or the other — not both.

- Hook requires space and stability to be perceived as identity.
- Call/response requires alternation and contrast.
- Combining them causes masking and loss of musical intent.

**[HARD]** `pending_phrase_mode` may be prepared at any time.  
`active_phrase_mode` commits **only at a drop boundary**.  
`active_phrase_mode` must **not change between drops**.

**[PREF]** Approximately 80% CALL_RESPONSE_MODE, 20% HOOK_MODE.  
`phase11.py:325–340` — `h % 5 == 0` → HOOK_MODE.

### HOOK_MODE

**[HARD]** Hook is the foreground identity voice.

**[HARD]** Call/response is disabled or reduced to tiny fills. Stab must not lead a full
call/response pattern while HOOK_MODE is active.

**[PREF]** Sparsity may clear space for hook. Beat bed may thin slightly for hook focus.

**[HARD]** Bass and sub remain supportive and stable — they do not compete with hook.

**Acceptance:** A HOOK_MODE phrase produces recognisable melodic/identity material.
No active call/response alternation is present.

### CALL_RESPONSE_MODE

**[HARD]** Stab leads call/response approximately 90% of the time. Other valid leaders:
bass, hook (background only), snare.

**[HARD]** Hook is absent, minimal, or background-only. No dominant hook motif runs across
the phrase.

**[HARD]** Phrase motion comes from call → response interaction, not from a continuous
foreground identity voice.

**Acceptance:** A CALL_RESPONSE_MODE phrase produces conversational movement.
No dominant hook motif is present.

### Structural lock

**[HARD]** Phrase mode is structural. It follows the same commit rules as archetype and
call/response leader:

```
pending_phrase_mode   — may be prepared anytime
active_phrase_mode    — commits only at drop
                     — must not change between drops
```

---

## Archetypes

Archetype determines the rhythmic skeleton (kick/snare/hat probability maps).

**Archetype density indices** (`archetypes.py`):

| Archetype | Density Index | Grid Conformity | Character |
|-----------|--------------|-----------------|-----------|
| HALF_STEP | 0.10 | 0.90 | Minimal, sparse |
| TWO_STEP | 0.35 | 0.75 | Basic 2-step |
| SHUFFLED_TWO_STEP | 0.45 | 0.50 | Loose 2-step |
| STUTTER | 0.50 | 0.85 | Broken regularity |
| ROLLING | 0.60 | 0.70 | Flowing beat |
| BREAKBEAT_HARDCORE | 0.55 | 0.55 | Breakbeat feel |
| AMEN | 0.70 | 0.40 | Amen breaks |
| FOUR_ON_THE_FLOOR | 0.75 | 1.00 | 4×4 kick |
| HAPPY_HARDCORE | 0.85 | 0.90 | Fast 4×4 |
| GABBER | 1.00 | 0.95 | Maximum density |

**[HARD]** Archetype is selected once per bank and locked for all 16 bars.  
Within-bank regeneration (quantize boundaries) uses the locked archetype.  
`bank_generator.py:100` — `active_archetype` parameter.

**[HARD]** Archetype may change instantly only at drop commit.  
`server.py` — active_archetype = pending_archetype at drop.

**[PREF]** Between drops, archetype bias shifts progressively via `pending_archetype`.
The listener hears the committed archetype until the next drop.

**[HARD]** `ANCHOR_EXPECTATION_THRESHOLD = 0.7` (`archetypes.py:50`) —  
Slots at or above this expectation are structural anchors. Deformations must preserve them.

**[HARD]** `EXPECTATION_GHOST_THRESHOLD = 0.25` (`bank_generator.py:32`) —  
Slots below this are ghost candidates.

### Archetype-territory relationship

**[ARCH]** Territory (Oak/Chaos/Nott) is **not** the same as archetype. Territory is a continuous
position on the slider (0.0–1.0). Archetype is a discrete rhythmic structure selected by density.

**[ARCH]** Territory shapes:
- Build length
- Sparsity mode
- Bassline pattern
- Sub pattern
- Survivor feel
- Ghost density

**[OPEN]** There is no explicit rule mapping specific archetypes to specific territories.
The selection is density-driven. High density → denser archetype. It is not guaranteed
that oak always uses a sparse archetype.

---

## Drop and Transition Rules

### Drop boundary

**[HARD]** A DROP_RELOCK bar requires:
- Bass asserting tonal centre at `DROP_STEP = 4` (first non-muted step)
- Kick present at `DROP_STEP = 4`
- Hook present at `DROP_STEP = 4`

**[HARD]** `DROP_STEP = 4` — Steps 0–3 are muted in DROP_RELOCK bars by the silence mask.
`drop_enforcer.py:52`

**[HARD]** Kick, bass, and hook should align at the drop step.
Drop velocities: kick=115, bass=110, hook=90.
`drop_enforcer.py:55–57`

**[HARD]** Unresolved call/response material must not leak into DROP_RELOCK bars.
Events with `role="call"` or `role="response"` are suppressed.
`drop_enforcer.py:_suppress_illegal_events`

**[HARD]** No echo-style lower-velocity copies of authority material in the drop bar.
A supporting event at the same step/pitch as bass/hook but below 80% of authority
velocity is suppressed. `ECHO_VELOCITY_THRESHOLD = 0.80` (`drop_enforcer.py:73`)

**[PREF]** Pre-drop contrast is expected: either HOLD_SILENCE in the preceding bar,
or event density ≤ 3. `drop_enforcer.py:516–539`

### Structural commit at drop

**[HARD]** At drop commit, the following lock simultaneously:
- `active_archetype` ← `pending_archetype`
- `call_response_leader` ← `pending_call_response_leader`
- `phrase_mode` ← `pending_phrase_mode`

**[HARD]** None of these may change between drops.

### Build length

**[ARCH]** Build length (tension runway before drop) by territory:

| Territory | Low | High | Preferred |
|-----------|-----|------|-----------|
| Oak (< 0.33) | 4 | 8 | 6 bars |
| Chaos (0.33–0.67) | 2 | 12 | 6 bars |
| Nott (≥ 0.67) | 8 | 24 | 16 bars |

Formula: `preferred + (distance × (high-preferred)) − (velocity × (preferred-low))`  
`phase11.py:408–429`

**[HARD]** Build and silence are distinct:
- Build = progressive tension phase
- Silence = final Phase 10 pre-drop suppression

**[PREF]** Longer builds are used when trajectory distance is large, pressure is rising
slowly, Nott influence is high, or the structural change is significant.

### Progressive change between drops

**[HARD]** `ALLOWED_PROGRESSIVE_STEP_DELTA = 0.20` (`phase11.py:31`) —  
Structural change per step between drops must not exceed this. Larger changes require a drop.

**[HARD]** The following may update freely between drops:
- `target_archetype`, `pending_archetype`
- `pending_phrase_mode`, `pending_call_response_leader`
- Behaviour field values (ghost intensity, density, etc.)
- Trajectory and slider dynamics

**[HARD]** The following may only commit at drops:
- `active_archetype`
- `phrase_mode`
- `call_response_leader`
- Bassline identity (major restructuring)
- Sub pattern identity

---

## Survivor / Pre-Drop Rules

**[HARD]** The survivor signal carries timing through pre-drop silence.
Events with `role="survivor"` or `survives_silence=True` pass through the silence mask.
`syntax_enforcer.py:113`

**[PREF]** Hat is the primary survivor lane.
`SURVIVOR_LANE_PRIORITY = ("hat", "ghost", "snare", "stab", "hook", "kick", "bass")`  
`drop_enforcer.py:61–63`

**[PREF]** Survivor signal properties:
- Note: 84 (typically hat material, `SURVIVOR_RENDER_LANE = "hat"`)
- Velocity range: 5–24 (very quiet, `SURVIVOR_MIN_VELOCITY=5`, `SURVIVOR_MAX_VELOCITY=24`)
- Duration: 0.025 seconds (very short)

`drop_enforcer.py:58–68`

**[HARD]** Survivor signal must not sound like a normal beat-bed event.
It is a continuity marker, not a rhythmic anchor.

---

## Beat Bed Rules

**[PREF]** Kick, snare, and hat normally form a **populated, continuous rhythmic bed**.

> Sparsity is intentional interruption of a normally populated beat bed.
> It is not the default state.

**Default beat bed** (`arrangement.py:118–121`):

| Layer | Steps | Default Velocity |
|-------|-------|-----------------|
| kick | 0, 8 (beats 1 & 3) | 96 |
| snare | 4, 12 (beats 2 & 4) | 88 |
| hat | 0, 2, 4, 6, 8, 10, 12, 14 (every 2 steps) | 58 |

**[PREF]** Hat is normally the densest beat-bed component, carrying subdivision.

**[PREF]** Kick anchors the grid. Regular presence unless sparsity explicitly removes it.

**[PREF]** Snare provides rhythmic authority. Should be reliably populated.

**[HARD]** Beat bed elements may be reduced only for clear musical reasons:
hook focus, bass/sub dominance, pre-drop silence, intentional stripped impact, or meaningful
contrast. If no reason exists, restore beat-bed density.

**[PREF]** In HOOK_MODE, hat may thin and snare may ghost briefly to focus attention on hook.
Kick usually remains. This creates attention, not dead air.

**Sparsity reasons** (`arrangement.py:82–94`):
- `hook_focus` — hook in foreground
- `bass_sub_dominance` — bass/sub taking weight
- `intentional_stripped_impact` — hard sparsity mode, level > 0.4
- `trajectory_sparsity` — sparsity level > 0.35
- `none` — no reason; beat bed should be full

---

## Call / Response Rules

**[HARD]** All call events must originate from `PhrasePlan.call_slots`.
`calls.py:_planned_slots_for_rendered_bars`

**[HARD]** All response events must originate from `PhrasePlan.response_slots`.
`responses.py:_planned_response_slots_for_bars`

**[HARD]** No response event may fire before step 8 (beat 3).
`RESPONSE_WINDOW_MIN = 8` (`call_response.py:35`)

**[HARD]** Call window: steps 0–7 (beats 1–2).  
Response window: steps 8–15 (beats 3–4).

**[HARD]** A response requires a valid preceding call. No call → no response.

**[HARD]** Call/response mode must not change between drops.

**[PREF]** Approximately 90% STAB_LEADS, 10% alternatives.  
`phase11.py:342–354` — `h % 10 != 0` → stab.

Valid non-stab leaders: bass, hook, snare.  
`CALL_RESPONSE_LEADERS = ("stab", "bass", "hook", "snare")` (`phase11.py:32`)

**[PREF]** Mode flip probabilities (within-cycle, at phrase boundaries):
- STAB_LEADS → BASS_LEADS: 20%
- BASS_LEADS → STAB_LEADS: 35%  
`call_response.py:154–161`

**[HARD]** Mode flips only at phrase boundaries (`abs_bar % 4 == 0`) and only after
a minimum duration (4 bars). `call_response.py:182–183`

### Response emphasis shape

**[PREF]** Response should feel like a landing, not just later notes.
Velocity escalation: approach=80%, middle=90%, final=110% of base.  
Final note duration: minimum 2 steps.  
`call_response.py:69–97`

### Call pitch and velocity

Default call root: **MIDI 62 (D4)**.  
Call pitches rotate: 62, 64, 66 (D4, E4, F#4).  
`calls.py:64–65`

Call velocities: base 72 + (index × 8), scaled by energy_level.  
`calls.py:68–70`

---

## Hook Rules

**[HARD]** Hook is rendered from `PhrasePlan.hook_pattern`. It does not invent its own timing.
`hook.py`

**[PREF]** Default hook root: MIDI 60 (C4).  
Default hook motif: steps (0, 3, 6, 10), pitches C4, Eb4, G4, Eb4.  
`phrase_plan.py:115–126`

**[HARD]** Hook events are authority-layer events. Supporting events at the same step
as a hook event (non-drum, non-bass) are suppressed.  
`support_enforcer.py:AUTHORITY_LAYERS`

**[HARD]** In CALL_RESPONSE_MODE, hook is absent or heavily reduced. No dominant motif.

**[HARD]** In HOOK_MODE, hook is primary foreground. Call/response is disabled or minimal.

---

## Bassline Rules

**[HARD]** Bassline is a distinct channel from bass (channel 7 vs 3).
It is not occasional hits — it is a continuous musical voice.

**[HARD]** Bassline intervals are constrained to root, perfect 5th, and octave only.  
`ALLOWED_BASS_INTERVALS = {0, 7, 12}` (`bass.py:20`)

**[HARD]** Bassline note durations use a fixed vocabulary only.  
`ALLOWED_BASSLINE_DURATIONS = {1, 2, 3, 4, 8, 16}` steps (`bass.py:21`)

**[PREF]** Bassline should favour medium to long notes. Short notes for accents only.
The bassline must not become a random hit lane.

**[ARCH]** Bassline pattern by territory:

| Territory | Pattern | Steps | Duration (steps) | Notes |
|-----------|---------|-------|-----------------|-------|
| Oak (≤ 0.33) | driving_loop | 0, 4, 8, 12 | 2 each | 4×4 bass |
| Chaos (default) | offbeat_pulse | 2, 6, 10, 14 | 2 each | Offbeat syncopation |
| Chaos (high energy) | kick_answer | 2, 6, 10, 14 | 2, 3, 2, 3 | Longer on even beats |
| Chaos (high instab, ~every 4 bars) | syncopated_cluster | 2, 6, 11, 12, 14 | 2, 2, 1, 1, 2 | Dense cluster |
| Nott (default) | nott_hold | 0 | 16 (full bar) | Long hold |
| Nott (high energy, ~every 4 bars) | held_fill | 0, 12, 14 | 8, 1, 2 | Drop + fill |

`bass.py:171–181`

**[PREF]** Bassline repeats within a section (between drops) with only minor variation allowed:
small rhythmic variation, velocity accents, note length variation, minor phrase mutation,
occasional passing notes.

**[HARD]** Between drops, these are not allowed: complete bassline replacement, new unrelated
motif, archetype-incompatible behaviour, loss of groove alignment.

**[PREF]** Bassline aligns with kick grid authority. Bassline call steps are {0, 4} (beats 1–2).
`bass.py:325`

**[PREF]** Off-beat bassline probability (Chaos, high instability):
`min(0.25, chaos_factor × (instability − 0.4) × 0.6)`  
`bass.py:293` — maximum 25% chance of offbeat doubling.

---

## Sub Rules

**[HARD]** Sub is a distinct channel from bassline and bass (channel 8).
Sub is not a busy bassline — it is the physical foundation.

**[HARD]** Sub note pitch is calculated from bassline root:
`pitch = 24 + ((source.note − 36) % 12)`  
`arrangement.py:181` — root note at C1 (24), stays in root pitch class.

**[HARD]** Sub patterns use only these duration values (in steps):
`ALLOWED_SUB_DURATIONS = {4, 8, 16, 32, 64}` (`arrangement.py:22`)  
Converting to seconds at 174 BPM: 0.32s, 0.64s, 1.28s, 2.56s, 5.12s.

**[ARCH]** Sub pattern by territory:

| Territory | Pattern | Trigger Steps | Duration Steps |
|-----------|---------|---------------|----------------|
| Oak (≤ 0.33) | full_bar_hold | step 0 | 16 (1 bar) |
| Chaos (0.33–0.67), energy > 0.75 | kick_aligned_reinforcement | 0, 8 | 4 (¼ bar) |
| Chaos (default) | half_bar_pulse | 0, 8 | 8 (½ bar) |
| Nott (≥ 0.67) | long_multi_bar_hold | step 0 | 32 (2 bars) |

`arrangement.py:151–158`

**[PREF]** Sub is very sparse. Much sparser than bassline.

**[PREF]** Sub usually holds long notes. When other layers thin, sub often becomes
more exposed — it is not removed by ordinary sparsity.

**[PREF]** At drop, kick + bass + sub should normally align or intentionally interlock.

**[HARD]** Sub must not exhibit: fast rhythmic patterns, busy sequencing, melodic behaviour,
random short hits.

**[OPEN]** The relationship between sub dynamics and pression CC output is not yet
formalised. Sub should probably track `impact` and `density` pression lanes.

---

## Sparsity Rules

**[HARD]** Sparsity is intentional contrast, not default emptiness.

**[HARD]** Sparsity has a reason. Reason codes:
- `hook_focus` — hook in foreground
- `bass_sub_dominance` — bass/sub taking structural weight
- `intentional_stripped_impact` — hard mode, high level
- `trajectory_sparsity` — trajectory-driven
- `none` — no reason; beat bed should be populated

`arrangement.py:82–94`

**Sparsity modes** (`phase11.py:SparsityMode`):

| Mode | Behaviour |
|------|-----------|
| SOFT | Light thinning; low-priority layers at odd steps |
| HARD | Priority ≤ 3 OR steps 0/8 only |
| PULSED | Bar/step alternating; priority ≤ 2 always |
| DOMINANT_BURST | Beats only for priority ≤ 4 |

**[ARCH]** Sparsity level by trajectory role:

| Role | Dominant Instrument | Mode | Level Formula |
|------|---------------------|------|---------------|
| peak | bassline | HARD | 0.55 + distance × 0.7 |
| intensify | snare | PULSED | 0.25 + energy × 0.6 |
| resolve | hook | DOMINANT_BURST | 0.25 + distance × 0.3 |
| transition | — | SOFT | 0.10 + energy × 0.25 |

`phase11.py:362–381`

**[HARD]** `CORE_DROP_LAYERS = {kick, sub, bassline}` are always exempt from sparsity.
They must be present at drop. `phase11.py`

---

## Instrument Priority Rules

**[HARD]** Instrument priority (highest to lowest):

```
kick → sub → bassline → bass → snare → hook → stab → hat → ghost → survivor
```

`phase11.py:INSTRUMENT_PRIORITY:19–21`

**[HARD]** Authority layers: `{bass, hook}`.  
Supporting events may not collide at the same step as authority events.  
`support_enforcer.py:AUTHORITY_LAYERS`

**[HARD]** Drum layers `{kick, snare, hat}` are exempt from authority-collision suppression
(kick+bass co-occurrence is intentional and normal).

**[PREF]** In HOOK_MODE, hook takes authority. Other layers step back:
- Snare velocity × 0.78
- Hat velocity × 0.78
- Hook velocity × 0.88 (present but slightly pulled)

`phase11.py:468–475`

---

## Velocity and Loudness Rules

**[HARD]** Note velocity is the authoritative mechanism for hit loudness.

```
hit loudness = note velocity
```

**[HARD]** CCs must not be used as the primary mechanism for:
- Individual hit volume
- Accent strength
- Ghost-note loudness
- Drop-hit loudness
- Dominant instrument loudness

**[HARD]** `note_velocity_source: "note_event_bus"` — diagnostic invariant.  
**[HARD]** `cc_volume_control_used: false` — diagnostic invariant.  
`arrangement.py:arrangement_diagnostics`

**Velocity ranges by layer** (`bank_generator.py:305–318`):

| Layer | Role | Base | Density Scale | Typical Range |
|-------|------|------|---------------|---------------|
| kick | anchor | 100 | 0.8–1.0 | 80–120 |
| kick | ghost | 52 | 0.8–1.0 | 42–62 |
| kick | impact | 127 | 0.8–1.0 | ≤ 127 |
| snare | anchor | 95 | 0.8–1.0 | 76–114 |
| snare | ghost | 40 | 0.8–1.0 | 32–48 |
| hat | anchor | 72 | 0.75–1.0 | 54–90 |
| hat | ghost | 38 | 0.75–1.0 | 29–48 |
| drop kick | — | 115 | — | 115 |
| drop bass | — | 110 | — | 110 |
| drop hook | — | 90 | — | 90 |

**Velocity formula:** `max(1, min(127, int(base × (0.8 + force.density × 0.2))))`

---

## CC / Expression Rules

**[HARD]** CCs are expressive and environmental. They may control:
- Pressure / tension envelope
- Impact macro (overall hit weight)
- Filter (cutoff, resonance)
- Distortion
- Send amounts / reverb
- Texture and bus colour

**[HARD]** CCs must not override the note event bus for individual hit loudness.

### Pression CC dimensions

Default mapping (all channel 0):

| Dimension | CC | Colour | Meaning |
|-----------|-----|--------|---------|
| pressure | 20 | red | Anticipation + release + transition |
| impact | 21 | orange | Peak velocity, decaying |
| density | 22 | yellow | Event count per step |
| silence | 23 | blue | Inverse density / gaps |
| riser | 24 | purple | Phrase position ramp |
| leadership | 25 | green | 0=bass leads, 127=stab leads |
| call_intensity | 26 | light blue | Beats 1–2 activity |
| response_intensity | 27 | magenta | Beats 3–4 activity (bass/stab only) |
| landing_strength | 28 | gold | Final response note hold |
| pre_warning | 29 | dark red | Transition proximity warning |

`pression.py:54–82`

**Pression composition weights** (`pression.py:46–48`):
- Phrase level: 70%
- Intra-bar: 20%
- Event spikes: 10%

---

## Pattern and Duration Rules

### Grid resolution

**[HARD]** All events are placed on 16th-note step boundaries.
- 16 steps per bar
- 6 ticks per step (24 PPQN / 4)
- Step 0 = beat 1, step 4 = beat 2, step 8 = beat 3, step 12 = beat 4

`bank_generator.py:19–23`, `phrase_plan.py:15`

**[HARD]** No free timing. All generated events must land on valid step indices 0–15.
Off-grid events are treated as the containing step for silence purposes.

### Stab motif timing

**Response motifs** (steps 6–15, beats 2–4):

| Motif | Steps | Intervals | Velocities |
|-------|-------|-----------|------------|
| LATE_ANSWER | (10, 13, 14) | (0, 3, 5) | (90, 78, 105) |
| PICKUP_CATCH | (11, 14, 15) | (0, 2, 0) | (85, 75, 95) |
| SYNCOPATED_HOOK | (6, 10, 13) | (0, 5, 3) | (88, 82, 100) |

**Call motifs** (steps 0–7, beats 1–2):

| Motif | Steps | Intervals | Velocities |
|-------|-------|-----------|------------|
| CALL_EARLY | (2, 6) | (0, 3) | (88, 80) |
| CALL_SYNCO | (1, 5, 7) | (0, 5, 3) | (90, 78, 85) |
| CALL_OFFBEAT | (2, 4, 6) | (0, 2, 5) | (85, 78, 95) |

`stabs.py:209–253`

**[PREF]** Stab motif variation schedule within a 16-bar bank:
- Bars 1–4: base motif
- Bars 5–8: drop middle note
- Bars 9–12: shift final step +1
- Bars 13–16: extend final note duration by 1 step

**Stab root notes by territory** (`stabs.py:570–582`):
- Oak: `bass_note + 24` — same pitch class, 2 octaves up
- Chaos: `bass_note + 31` — perfect 5th, harmonic lift
- Nott: `bass_note + 21` — minor 3rd, unresolved tension

### Note durations

**[HARD]** `bar_end_abs` caps all note-offs. Note-offs cannot extend past bar boundary.  
`midi_out.py:play_bar_in_phrase_blocking` — `t_off = min(t_on + duration, bar_end_s)`

---

## Progressive vs Instantaneous Change

**[HARD]** Allowed progressive (between drops):
- Slider position bias
- Pending archetype / pending phrase mode
- Behaviour field values (ghost intensity, density)
- Trajectory and sparsity level
- Bassline minor variation
- Sub hold length variation (minor)
- Velocity scaling

**[HARD]** Requires drop boundary:
- Active archetype commit
- Phrase mode commit
- Call/response leader commit
- Bassline major restructuring
- Sub major pattern change

**[HARD]** `can_apply_instant_structural_change(step, drop_step)` must return True
before any instant structural mutation. `phase11.py`

**[HARD]** `ALLOWED_PROGRESSIVE_STEP_DELTA = 0.20` — max structural movement per step
between drops. `phase11.py:31`

---

## Diagnostics / Invariants

These values should always be true in a healthy system:

| Diagnostic | Expected Value | File |
|------------|----------------|------|
| `note_velocity_source` | `"note_event_bus"` | arrangement.py |
| `cc_volume_control_used` | `false` | arrangement.py |
| `pression_attempted_event_creations` | `0` | pression.py |
| `support_events_suppressed_by_silence` | `0` (after Phase 6) | support_enforcer.py |
| `bass_source` | `"phrase_plan"` | server.py |
| `hook_source` | `"phrase_plan"` | server.py |
| `call_response_leader` | Not changing between drops | phase11.py |
| `phrase_mode` | Not changing between drops | phase11.py |
| `active_archetype` | Not changing between drops | server.py |

---

## Rules Found Embedded in Code

These rules exist in code but are not explicitly documented elsewhere:

| Rule | Value | Source |
|------|-------|--------|
| Default phrase length | 8 bars | `phrase_plan.py:DEFAULT_BARS=16` |
| Bass root note (C2) | MIDI 36 | `phrase_plan.py:ROOT_NOTE=36` |
| Hook root note (C4) | MIDI 60 | `phrase_plan.py:HOOK_ROOT=60` |
| Sub base note (C1) | MIDI 24 | `arrangement.py:SUB_NOTE=24` |
| Survivor render note (closed hat) | MIDI 42 | `drop_enforcer.py:SURVIVOR_RENDER_NOTE` |
| Offbeat steps | {2, 6, 10, 14} | `stabs.py:OFFBEAT_STEPS` |
| Beat steps (strong) | {0, 4, 8, 12} | `stabs.py:BEAT_STEPS` |
| Late-phrase steps | {11, 14, 15} | `stabs.py:LATE_PHRASE` |
| Conformance peaks at Oak and Nott | distance from 0.5 × 2 | `rhythm.py:conformance_for_landscape` |
| Ghost ceiling probability | 0.72 | `deformations.py:_GHOST_CEILING` |
| Anchor expectation threshold | 0.7 | `archetypes.py:50` |
| Ghost threshold | 0.25 | `bank_generator.py:32` |
| Response final note minimum | 2 steps | `call_response.py:response_duration_steps` |
| Response landing velocity | 110% of base | `call_response.py:response_velocity` |
| Call root pitch | MIDI 62 (D4) | `calls.py:CALL_ROOT=62` |
| Response root pitch | MIDI 57 (A3) | `responses.py:RESPONSE_ROOT=57` |
| Slider spring stiffness | 0.18 | `phase11.py:SliderDynamics` |
| Slider damping | 0.72 | `phase11.py:SliderDynamics` |
| Constraint basin widths | oak/nott=0.33, chaos=0.34 | `phase11.py` |
| Pre-drop contrast threshold | ≤ 3 events | `drop_enforcer.py:516` |
| Echo suppression threshold | 80% of authority velocity | `drop_enforcer.py:ECHO_VELOCITY_THRESHOLD` |
| Offbeat bass max probability | 25% | `bass.py:293` |
| Hook-focus snare softening | × 0.78 | `phase11.py:470` |
| Hook-focus hat softening | × 0.78 | `phase11.py:470` |
| Survivor secondary signal start | at 80% through pre-drop | `drop_enforcer.py:SURVIVOR_SECONDARY_START=0.80` |
| MIDI channel: kick | 0 (DAW ch 1) | `midi_out.py:LAYER_CHANNELS` |
| MIDI channel: snare | 1 (DAW ch 2) | `midi_out.py:LAYER_CHANNELS` |
| MIDI channel: hat | 2 (DAW ch 3) | `midi_out.py:LAYER_CHANNELS` |
| MIDI channel: bass | 3 (DAW ch 4) | `midi_out.py:LAYER_CHANNELS` |
| MIDI channel: stab | 4 (DAW ch 5) | `midi_out.py:LAYER_CHANNELS` |
| MIDI channel: hook | 5 (DAW ch 6) | `midi_out.py:LAYER_CHANNELS` |
| MIDI channel: bassline | 7 (DAW ch 8) | `midi_out.py:LAYER_CHANNELS` |
| MIDI channel: sub | 8 (DAW ch 9) | `midi_out.py:LAYER_CHANNELS` |

---

## Open Questions / Rules Needing Review

These items are unclear, inconsistently implemented, or need explicit decision:

1. **Sub and Pression coupling** — Sub becoming exposed during sparsity is mentioned but
   the relationship between sub presence and `silence`/`density` pression CC lanes is not
   formalised. Should sub muting/exposure be reflected in pression output?

2. **HOOK_MODE suppression mechanics** — The phrase mode `HOOK_MODE` is now tracked and
   committed at drop. However, the actual suppression of call/response events when
   `phrase_mode == HOOK_MODE` is not yet enforced in the event pipeline. This is a code gap.

3. **Archetype to territory mapping** — There is no explicit rule preventing a dense
   archetype (e.g. FOUR_ON_THE_FLOOR) from being selected in an Oak passage. The system
   relies on density being low in Oak, but density can be raised by the slider. Is this
   intentional?

4. **Bassline committed at drop** — Between drops, minor bassline variation is allowed.
   But what qualifies as "major restructuring" that requires a drop? The boundary is not
   quantified.

5. **Multiple leaders in CALL_RESPONSE_MODE** — The spec says stab leads ~90% of the time,
   with bass, hook, and snare as alternatives. But in `BASS_LEADS` call_response mode
   (from `call_response.py`), bass leads the call window. Is this the same concept as
   non-stab leadership? The two mode systems (call_response.py and phase11.py leader) may
   overlap in unclear ways.

6. **Hat density rule** — Hat is described as normally the densest beat-bed component
   (every 2 steps). But in sparsity modes, hat is suppressed before kick. Should there be
   an explicit minimum hat density?

7. **Survivor on non-hat lanes** — The `SURVIVOR_LANE_PRIORITY` allows survivor on ghost,
   snare, stab, hook, kick, and bass if hat is unavailable. The musical intent of a
   survivor snare or hook is not documented.

8. **Ghost injection in relation to territory** — Ghost notes appear via deformation.
   The ghost ceiling (0.72) applies regardless of territory. Should ghost density scale
   with territory? (Oak = fewer ghosts, Nott = more or fewer?)

9. **Response pitch rules** — Response pitches descend toward tonal centre (A3, G3, E3).
   This is hard-coded. Is this the intended musical rule across all archetypes and territories?

10. **CC mapping configurability vs defaults** — CC channels are configurable at runtime.
    But the default mapping puts all pression on channel 0 (CCs 20–29). Is this the
    intended DAW routing? The distinction between the "notes" MIDI port and the "CC"
    MIDI port is in the code but not documented as a setup requirement.
