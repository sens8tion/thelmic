"""Pression Dimensions — time-varying musical control signals.

Guardrails
----------
- Pure module: no MIDI, no UI, no global mutable state.
- All values are int 0–127. Internal arithmetic may use floats; output is int.
- Computation happens at bank-generation time; playback loop only reads.
- CC map is a parameter — never assumed or hardcoded.
- Do not feed pression values back into note generation.
- "pressure_curves" (CurveEngine) is a separate system; do not touch it.

Data model
----------
Each bar is represented as a PressionBar containing:
  - one list[int] of 16 values (one per 16th-note step) for each dimension
  - a list of PressionOverlay event markers

The bank is a list[PressionBar] of length BARS_PER_BANK (16).

Usage in playback loop (only permitted operation)
--------------------------------------------------
  timeline = compute_bank_timeline(...)
  bar_data  = timeline[bar_idx]          # look up pre-computed bar
  step_vals = bar_data.at_step(step)     # read {dim: int} for one step
  — or —
  bar_vals  = bar_data.bar_peak()        # single int per dim (peak over bar)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from thelmic.force_engine import ForceState
    from thelmic.behaviour_field import BehaviourField
    from thelmic.transition_engine import Transition
    from thelmic.call_response import Mode
    from thelmic.bank_generator import MIDIEvent

STEPS_PER_BAR: int = 16
BARS_PER_BANK: int = 16

# ---------------------------------------------------------------------------
# Dimensions
# ---------------------------------------------------------------------------

DIMENSION_NAMES: tuple[str, ...] = (
    "pressure",
    "impact",
    "density",
    "silence",
    "riser",
    "leadership",
    "call_intensity",
    "response_intensity",
    "landing_strength",
    "pre_warning",
)

DIMENSION_COLOURS: dict[str, str] = {
    "pressure":           "#c05050",
    "impact":             "#e07030",
    "density":            "#c0a030",
    "silence":            "#4a7a9a",
    "riser":              "#7a50c0",
    "leadership":         "#50a050",
    "call_intensity":     "#6090c0",
    "response_intensity": "#c060a0",
    "landing_strength":   "#e0a040",
    "pre_warning":        "#a04040",
}

# Default CC map — always pass this (or a modified copy) explicitly.
DEFAULT_CC_MAP: dict[str, tuple[int, int]] = {
    "pressure":           (0, 20),
    "impact":             (0, 21),
    "density":            (0, 22),
    "silence":            (0, 23),
    "riser":              (0, 24),
    "leadership":         (0, 25),
    "call_intensity":     (0, 26),
    "response_intensity": (0, 27),
    "landing_strength":   (0, 28),
    "pre_warning":        (0, 29),
}

# ---------------------------------------------------------------------------
# Event overlay — structural marker
# ---------------------------------------------------------------------------

OVERLAY_KINDS: tuple[str, ...] = (
    "call_start",
    "response_start",
    "landing",
    "role_flip",
    "riser",
    "silence_gap",
    "drop",
)


@dataclass(frozen=True)
class PressionOverlay:
    """A structural event marker at a specific bar/step position.

    kind:     one of OVERLAY_KINDS
    step:     0–15 (16th-note step within bar)
    strength: 0–127
    """
    kind:     str
    step:     int
    strength: int

    def to_dict(self) -> dict:
        return {"kind": self.kind, "step": self.step, "strength": self.strength}


# ---------------------------------------------------------------------------
# Per-bar pression data
# ---------------------------------------------------------------------------

@dataclass
class PressionBar:
    """Pression values for one bar at 16th-note resolution.

    Each dimension: list of STEPS_PER_BAR int values (0–127).
    Overlays: structural event markers within this bar.
    """
    pressure:           list[int] = field(default_factory=lambda: [0] * STEPS_PER_BAR)
    impact:             list[int] = field(default_factory=lambda: [0] * STEPS_PER_BAR)
    density:            list[int] = field(default_factory=lambda: [0] * STEPS_PER_BAR)
    silence:            list[int] = field(default_factory=lambda: [0] * STEPS_PER_BAR)
    riser:              list[int] = field(default_factory=lambda: [0] * STEPS_PER_BAR)
    leadership:         list[int] = field(default_factory=lambda: [0] * STEPS_PER_BAR)
    call_intensity:     list[int] = field(default_factory=lambda: [0] * STEPS_PER_BAR)
    response_intensity: list[int] = field(default_factory=lambda: [0] * STEPS_PER_BAR)
    landing_strength:   list[int] = field(default_factory=lambda: [0] * STEPS_PER_BAR)
    pre_warning:        list[int] = field(default_factory=lambda: [0] * STEPS_PER_BAR)
    overlays:           list[PressionOverlay] = field(default_factory=list)

    def at_step(self, step: int) -> dict[str, int]:
        """Return {dimension: value} for one step. Safe: clamps step to 0–15."""
        s = max(0, min(STEPS_PER_BAR - 1, step))
        return {name: getattr(self, name)[s] for name in DIMENSION_NAMES}

    def bar_peak(self) -> dict[str, int]:
        """Return {dimension: peak_value} across all 16 steps of this bar."""
        return {name: max(getattr(self, name)) for name in DIMENSION_NAMES}

    def to_dict(self) -> dict:
        return {
            **{name: getattr(self, name) for name in DIMENSION_NAMES},
            "overlays": [o.to_dict() for o in self.overlays],
        }


def empty_timeline() -> list[PressionBar]:
    return [PressionBar() for _ in range(BARS_PER_BANK)]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _i(v: float) -> int:
    """Clamp float [0,1] to int [0,127]."""
    return max(0, min(127, int(v * 127.0)))


def _decay(values: list[float], decay: float = 0.6) -> list[float]:
    """Apply per-step exponential decay to a 16-element list."""
    result = [0.0] * STEPS_PER_BAR
    carry = 0.0
    for s in range(STEPS_PER_BAR):
        carry = max(values[s], carry * decay)
        result[s] = carry
    return result


# ---------------------------------------------------------------------------
# Intra-bar shape functions
#
# Each returns a float multiplier in [0, 1] for step s.
# Combined as: value[s] = phrase_component + shape(s) * local_range
# ---------------------------------------------------------------------------

# Precomputed: call/response tension arc within one bar.
# Rises through beats 1–2 (call), peaks at beat 3 arrival, decays in beat 4.
_CALL_RESPONSE_ARC: tuple[float, ...] = (
    0.05, 0.10, 0.18, 0.24,   # beat 1: slow build
    0.28, 0.30, 0.30, 0.28,   # beat 2: sustained call peak
    0.26, 0.22, 0.18, 0.14,   # beat 3: response arrival, releasing
    0.10, 0.08, 0.06, 0.04,   # beat 4: settled
)

def _call_response_arc(s: int) -> float:
    return _CALL_RESPONSE_ARC[s]

def _riser_arc(s: int, phrase_scale: float) -> float:
    """Accelerating ramp within the bar, scaled by phrase position (0.25–1.0).
    Bar 0 of phrase: gentle rise.  Bar 3: steep acceleration toward beat 4.
    """
    step_ramp = ((s + 1) / 16.0) ** (1.0 + phrase_scale)   # exponent 1.25–2.0
    return phrase_scale * step_ramp

def _pre_warning_ramp(s: int) -> float:
    """Quiet in beats 1–2, accelerating rise through beats 3–4.
    Used to signal 'something is approaching'.
    """
    if s < 8:
        return s / 7.0 * 0.30            # slow build: 0 → 0.30
    return 0.30 + (s - 8) / 7.0 * 0.70  # fast rise: 0.30 → 1.0


def _events_at_steps(bar_events: list["MIDIEvent"]) -> dict[int, list["MIDIEvent"]]:
    """Group events by their step index (0–15). Off-grid events are dropped."""
    from thelmic.stabs import _time_to_bar_step
    result: dict[int, list] = {s: [] for s in range(STEPS_PER_BAR)}
    for e in bar_events:
        if not getattr(e, "active", True) or e.velocity == 0:
            continue
        _, step = _time_to_bar_step(e.time)
        if 0 <= step < STEPS_PER_BAR:
            result[step].append(e)
    return result


# ---------------------------------------------------------------------------
# Per-bar computation
# ---------------------------------------------------------------------------

def compute_pression_bar(
    force:       "ForceState",
    behaviour:   "BehaviourField",
    transition:  Optional["Transition"],
    cr_mode:     "Mode",
    bar_events:  list["MIDIEvent"],
    bar_idx:     int,     # 0-based within bank (0–15)
    bank_idx:    int = 0,
    prev_density: float = 0.0,  # previous bar's density (for drop detection)
) -> PressionBar:
    """Compute one PressionBar at 16th-note resolution.

    All output values are int 0–127.
    No side effects; no global state read or written.
    """
    from thelmic.call_response import Mode as CRMode

    by_step  = _events_at_steps(bar_events)
    all_vels = [e.velocity for evts in by_step.values() for e in evts]

    # --- Transition state ---
    t_active    = transition is not None and transition.active
    t_progress  = transition.progress  if t_active else 0.0
    t_remaining = transition.remaining if t_active else 1.0
    t_velocity  = transition.velocity  if t_active else 0.0

    # --- Bar-level scalar values (computed once, spread across steps) ---

    # pressure: force state + transition
    p_scalar = min(1.0,
        force.anticipation     * 0.40
        + force.release_pressure * 0.30
        + t_progress             * 0.20
        + t_velocity             * 0.10
    )

    # density over full bar
    density_scalar = min(1.0, len(all_vels) / 24.0)

    # riser: position in phrase (bar 0 of phrase = 0.25, bar 3 = 1.0)
    bar_in_phrase  = bar_idx % 4
    riser_scalar   = (bar_in_phrase + 1) / 4.0

    # leadership: constant across bar
    lead_val = 127 if cr_mode == CRMode.STAB_LEADS else 0

    # pre_warning: ramps as transition approaches end
    pw_scalar = 0.0
    if t_active:
        nearness  = max(0.0, (0.3 - t_remaining) / 0.3)
        pw_scalar = min(1.0, nearness * 0.7 + t_velocity * 0.3)

    # --- Per-step arrays ---
    # Each dimension = phrase_component + bar_arc + event_component
    # phrase_component  → macro tension across bars (already in scalars above)
    # bar_arc           → within-bar motion (call/response shape, riser ramp, etc.)
    # event_component   → spikes and decay from actual note events

    # ── pressure ────────────────────────────────────────────────────────────
    # phrase scalar + call/response arc + hit spikes
    # The arc encodes musical expectation: rising call, resolving response.
    pressure = []
    for s in range(STEPS_PER_BAR):
        arc   = _call_response_arc(s) * (1.0 - p_scalar * 0.5)  # more arc when quiet
        base  = min(1.0, p_scalar + arc)
        evts  = by_step[s]
        spike = (max(e.velocity for e in evts) / 127.0 * 0.20) if evts else 0.0
        pressure.append(_i(min(1.0, base + spike)))

    # ── impact ──────────────────────────────────────────────────────────────
    # Event velocity spikes with exponential decay — most expressive when dense
    impact_raw = [
        max(e.velocity / 127.0 for e in by_step[s]) if by_step[s] else 0.0
        for s in range(STEPS_PER_BAR)
    ]
    impact = [_i(v) for v in _decay(impact_raw, decay=0.5)]

    # ── density ─────────────────────────────────────────────────────────────
    # Event count per step, smoothed with decay — shows local activity
    density_raw = [
        min(1.0, len(by_step[s]) / 4.0)
        for s in range(STEPS_PER_BAR)
    ]
    density = [_i(v) for v in _decay(density_raw, decay=0.7)]

    # ── silence ─────────────────────────────────────────────────────────────
    # Inverse of density — grows in gaps, spikes between phrases
    silence = [max(0, 127 - d) for d in density]

    # ── riser ───────────────────────────────────────────────────────────────
    # Accelerating ramp within bar, steeper at later phrase positions.
    # Bar 0 of phrase: gentle rise.  Bar 3: near-vertical toward beat 4.
    riser = [_i(_riser_arc(s, riser_scalar)) for s in range(STEPS_PER_BAR)]

    # ── leadership ──────────────────────────────────────────────────────────
    # Constant within bar (macro concept — no intra-bar variation needed).
    leadership = [lead_val] * STEPS_PER_BAR

    # ── call_intensity ──────────────────────────────────────────────────────
    # Structural baseline (rises through beats 1–2 based on energy) +
    # actual event spikes. Baseline ensures the dimension moves even in
    # sparse bars so it remains musically readable.
    call_raw = [0.0] * STEPS_PER_BAR
    for s in range(0, 8):
        # structural: rises 0→0.3 across beats 1–2
        structural = behaviour.energy_level * (s / 7.0 * 0.30)
        call_raw[s] = structural
        evts = by_step[s]
        if evts:
            peak  = max(e.velocity for e in evts) / 127.0
            bonus = 0.25 if any(e.layer in {"stab", "bass"} for e in evts) else 0.0
            call_raw[s] = min(1.0, peak + bonus)
    call_intensity = [_i(v) for v in _decay(call_raw, decay=0.6)]

    # ── response_intensity ──────────────────────────────────────────────────
    # Structural baseline (rises through beats 3–4) + event spikes.
    resp_raw = [0.0] * STEPS_PER_BAR
    for s in range(8, 16):
        structural = behaviour.energy_level * ((s - 8) / 7.0 * 0.35)
        resp_raw[s] = structural
        evts = by_step[s]
        if evts:
            peak  = max(e.velocity for e in evts) / 127.0
            bonus = 0.25 if any(e.layer in {"stab", "bass"} for e in evts) else 0.0
            resp_raw[s] = min(1.0, peak + bonus)
    response_intensity = [_i(v) for v in _decay(resp_raw, decay=0.6)]

    # ── landing_strength ────────────────────────────────────────────────────
    # Spike at the final response note (steps 12–15), held to end of bar.
    land_raw = [0.0] * STEPS_PER_BAR
    final_step = -1
    final_vel  = 0.0
    for s in range(12, 16):
        evts = [e for e in by_step[s] if e.layer in {"stab", "bass"}]
        if evts:
            v = max(e.velocity for e in evts) / 127.0
            if v > final_vel:
                final_vel  = v
                final_step = s
    if final_step >= 0:
        for s in range(final_step, STEPS_PER_BAR):
            land_raw[s] = final_vel
    landing_strength = [_i(v) for v in land_raw]

    # ── pre_warning ─────────────────────────────────────────────────────────
    # Low in beats 1–2, accelerating rise through beats 3–4 when transition
    # is approaching completion. Creates clear anticipation signal.
    pre_warning = [_i(pw_scalar * _pre_warning_ramp(s)) for s in range(STEPS_PER_BAR)]

    # --- Event overlays ---
    overlays: list[PressionOverlay] = []

    # call_start: first step in 0–7 with a stab/bass call event
    for s in range(0, 8):
        if any(e.layer in {"stab", "bass"} for e in by_step[s]):
            strength = _i(max(e.velocity / 127.0 for e in by_step[s]
                             if e.layer in {"stab", "bass"}))
            overlays.append(PressionOverlay("call_start", s, strength))
            break

    # response_start: first step in 8–15 with a stab/bass response event
    for s in range(8, 16):
        if any(e.layer in {"stab", "bass"} for e in by_step[s]):
            strength = _i(max(e.velocity / 127.0 for e in by_step[s]
                             if e.layer in {"stab", "bass"}))
            overlays.append(PressionOverlay("response_start", s, strength))
            break

    # landing: final note in response window
    if final_step >= 0:
        overlays.append(PressionOverlay("landing", final_step, _i(final_vel)))

    # riser: annotate phrase position
    if bar_in_phrase == 3:
        overlays.append(PressionOverlay("riser", 15, _i(riser_scalar)))

    # silence_gap: bars with very low density
    if density_scalar < 0.1 and len(all_vels) == 0:
        overlays.append(PressionOverlay("silence_gap", 0, 0))

    # drop: sudden density decrease from previous bar
    if density_scalar < prev_density * 0.4 and prev_density > 0.3:
        overlays.append(PressionOverlay("drop", 0, _i(prev_density - density_scalar)))

    return PressionBar(
        pressure=pressure,
        impact=impact,
        density=density,
        silence=silence,
        riser=riser,
        leadership=leadership,
        call_intensity=call_intensity,
        response_intensity=response_intensity,
        landing_strength=landing_strength,
        pre_warning=pre_warning,
        overlays=overlays,
    )


# ---------------------------------------------------------------------------
# Bank-level computation
# ---------------------------------------------------------------------------

def compute_bank_timeline(
    force:      "ForceState",
    behaviour:  "BehaviourField",
    transition: Optional["Transition"],
    cr_mode:    "Mode",
    bank,       # Bank object with .all_events() and .bank_index
) -> list[PressionBar]:
    """Compute pression for all 16 bars in a bank.

    Returns list[PressionBar] of length BARS_PER_BANK (16), indexed 0–15.
    This is the only function the server should call; it has no side effects.
    """
    from thelmic.stabs import _time_to_bar_step

    # Group events by 0-based bar_idx within bank
    events_by_bar: dict[int, list] = {i: [] for i in range(BARS_PER_BANK)}
    for e in bank.all_events():
        bar_1indexed, _ = _time_to_bar_step(e.time)
        idx = bar_1indexed - 1
        if 0 <= idx < BARS_PER_BANK:
            events_by_bar[idx].append(e)

    timeline: list[PressionBar] = []
    prev_density = 0.0
    for bar_idx in range(BARS_PER_BANK):
        bar_events = events_by_bar[bar_idx]
        pb = compute_pression_bar(
            force=force,
            behaviour=behaviour,
            transition=transition,
            cr_mode=cr_mode,
            bar_events=bar_events,
            bar_idx=bar_idx,
            bank_idx=bank.bank_index,
            prev_density=prev_density,
        )
        prev_density = min(1.0, len([e for evts in _events_at_steps(bar_events).values()
                                     for e in evts]) / 24.0)
        timeline.append(pb)

    # role_flip overlay: add to bars where cr_mode is different from the bank default
    # (this is approximate; the server adds flip overlays when the mode actually changes)
    return timeline
