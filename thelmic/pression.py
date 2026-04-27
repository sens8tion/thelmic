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
PHRASE_LENGTH_CHOICES: tuple[int, ...] = (4, 8, 12, 16)
DEFAULT_PHRASE_LENGTH_BARS: int = 8
DEFAULT_PHRASE_STRENGTH: float = 1.0
PHRASE_LEVEL_WEIGHT: float = 0.7
INTRA_BAR_WEIGHT: float = 0.2
EVENT_SPIKE_WEIGHT: float = 0.1

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
    "bass_intensity",
    "stab_intensity",
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
    "bass_intensity":     "#4f7fd0",
    "stab_intensity":     "#df7db8",
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
    "bass_intensity":     (0, 30),
    "stab_intensity":     (0, 31),
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


@dataclass(frozen=True)
class PressionLanePhrase:
    """Phrase-level lane movement for one Pression dimension."""
    current_value: float
    target_value: float
    phrase_position: float
    phrase_length_bars: int
    tension: float = 0.0
    anticipation: float = 0.0
    release_proximity: float = 0.0
    thinning: float = 0.0

    def to_dict(self) -> dict:
        return {
            "current_value": round(self.current_value, 3),
            "target_value": round(self.target_value, 3),
            "phrase_position": round(self.phrase_position, 3),
            "phrase_length_bars": self.phrase_length_bars,
            "tension": round(self.tension, 3),
            "anticipation": round(self.anticipation, 3),
            "release_proximity": round(self.release_proximity, 3),
            "thinning": round(self.thinning, 3),
        }


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
    bass_intensity:     list[int] = field(default_factory=lambda: [0] * STEPS_PER_BAR)
    stab_intensity:     list[int] = field(default_factory=lambda: [0] * STEPS_PER_BAR)
    landing_strength:   list[int] = field(default_factory=lambda: [0] * STEPS_PER_BAR)
    pre_warning:        list[int] = field(default_factory=lambda: [0] * STEPS_PER_BAR)
    overlays:           list[PressionOverlay] = field(default_factory=list)
    phrase_state:       dict[str, PressionLanePhrase] = field(default_factory=dict)

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
            "phrase_state": {k: v.to_dict() for k, v in self.phrase_state.items()},
        }


def empty_timeline() -> list[PressionBar]:
    return [PressionBar() for _ in range(BARS_PER_BANK)]


# ---------------------------------------------------------------------------
# Mapping mode helpers
# ---------------------------------------------------------------------------

# Triangle-wave test pulse: 0 → 127 → 0 over 16 steps.
# Used when mapping mode is active to give a clear moving signal in Ableton
# without waiting for musical content.  Values are never written to the
# stored pression timeline — they replace per-call before CC injection.
TEST_PULSE_VALUES: list[int] = [
    int(s * 127 / 7) if s < 8 else int((15 - s) * 127 / 7)
    for s in range(16)
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _i(v: float) -> int:
    """Clamp float [0,1] to int [0,127]."""
    return max(0, min(127, int(v * 127.0)))


def _f(v: float) -> float:
    return max(0.0, min(1.0, v))


def _decay(values: list[float], decay: float = 0.6) -> list[float]:
    """Apply per-step exponential decay to a 16-element list."""
    result = [0.0] * STEPS_PER_BAR
    carry = 0.0
    for s in range(STEPS_PER_BAR):
        carry = max(values[s], carry * decay)
        result[s] = carry
    return result


def _smoothstep(t: float) -> float:
    t = _f(t)
    return t * t * (3.0 - 2.0 * t)


def _valid_phrase_length(value: int) -> int:
    return value if value in PHRASE_LENGTH_CHOICES else DEFAULT_PHRASE_LENGTH_BARS


def _window_t(start: float, end: float, value: float) -> float:
    if end <= start:
        return 1.0 if value >= end else 0.0
    return _f((value - start) / (end - start))


def _drop_signals(phrase_position: float) -> dict[str, float]:
    pos = _f(phrase_position)
    tension = _smoothstep(pos)
    anticipation = _smoothstep(_window_t(0.45, 1.0, pos))
    release_proximity = _smoothstep(_window_t(0.72, 1.0, pos))
    thinning = _smoothstep(_window_t(0.70, 0.96, pos))
    post_drop = _f(1.0 - pos / 0.16)
    early_mid = _f(1.0 - abs(pos - 0.45) / 0.45)
    final_warning = _smoothstep(_window_t(0.86, 1.0, pos))
    return {
        "tension": tension,
        "anticipation": anticipation,
        "release_proximity": release_proximity,
        "thinning": thinning,
        "post_drop": post_drop,
        "early_mid": early_mid,
        "final_warning": final_warning,
    }


def _compose_phrase_lane(values: list[int], phrase_level: float) -> list[int]:
    phrase = _f(phrase_level)
    result: list[int] = []
    for value in values:
        local = max(0.0, min(1.0, value / 127.0))
        composed = (
            PHRASE_LEVEL_WEIGHT * phrase
            + (INTRA_BAR_WEIGHT + EVENT_SPIKE_WEIGHT) * local
        )
        result.append(_i(composed))
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


def _choose_phrase_targets(
    force: "ForceState",
    behaviour: "BehaviourField",
    transition: Optional["Transition"],
    cr_mode: "Mode",
    phrase_start_bar: int,
) -> dict[str, float]:
    """Choose musical phrase targets from current pressure and role context."""
    from thelmic.call_response import Mode as CRMode

    t_active = transition is not None and transition.active
    t_progress = transition.progress if t_active else 0.0
    t_remaining = transition.remaining if t_active else 1.0
    t_velocity = transition.velocity if t_active else 0.0

    nearing_release = _f((0.35 - t_remaining) / 0.35) if t_active else force.release_pressure
    phrase_phase = (phrase_start_bar % BARS_PER_BANK) / max(1, BARS_PER_BANK - 1)
    phrase_climax = _f(phrase_phase * 0.45 + nearing_release * 0.55)
    energy = _f(behaviour.energy_level)

    pressure = _f(
        force.anticipation * 0.42
        + force.release_pressure * 0.30
        + t_progress * 0.14
        + t_velocity * 0.08
        + phrase_climax * 0.06
    )
    density = _f(
        energy * 0.42
        + force.instability * 0.24
        + force.anticipation * 0.16
        + phrase_climax * 0.12
    )
    silence = _f(nearing_release * 0.48 + force.release_pressure * 0.22 + (1.0 - density) * 0.20)
    riser = _f(phrase_climax)
    impact = _f(force.release_pressure * 0.62 + nearing_release * 0.25 + energy * 0.13)
    leadership = 1.0 if cr_mode == CRMode.STAB_LEADS else 0.0
    call = _f(
        energy * 0.44
        + force.anticipation * 0.24
        + (1.0 - force.release_pressure) * 0.10
        + phrase_climax * 0.12
    )
    response = _f(energy * 0.34 + force.release_pressure * 0.34 + phrase_climax * 0.20)
    landing = _f(force.release_pressure * 0.58 + phrase_climax * 0.28 + energy * 0.14)
    pre_warning = _f(nearing_release * 0.52 + t_velocity * 0.26 + force.anticipation * 0.22)

    if cr_mode == CRMode.BASS_LEADS:
        bass = call
        stab = response
    else:
        bass = response
        stab = call

    return {
        "pressure": _f(pressure + 0.18),
        "impact": _f(impact * 0.55),
        "density": _f(density + 0.10),
        "silence": _f(silence + 0.08),
        "riser": _f(riser + 0.18),
        "leadership": leadership,
        "call_intensity": call,
        "response_intensity": response,
        "bass_intensity": bass,
        "stab_intensity": stab,
        "landing_strength": _f(landing * 0.45),
        "pre_warning": _f(pre_warning + 0.10),
    }


def _initial_phrase_values(targets: dict[str, float]) -> dict[str, float]:
    """Start a bank from a quieter settled version of the first target."""
    result = {}
    for name in DIMENSION_NAMES:
        target = targets.get(name, 0.0)
        if name == "silence":
            result[name] = _f(target * 0.65)
        elif name == "leadership":
            result[name] = target
        else:
            result[name] = _f(target * 0.45)
    return result


def _phrase_state_for_bank(
    force: "ForceState",
    behaviour: "BehaviourField",
    transition: Optional["Transition"],
    cr_mode: "Mode",
    phrase_length_bars: int,
    phrase_strength: float,
) -> list[dict[str, PressionLanePhrase]]:
    phrase_length = _valid_phrase_length(phrase_length_bars)
    strength = _f(phrase_strength)
    first_targets = _choose_phrase_targets(force, behaviour, transition, cr_mode, 0)
    current_values = _initial_phrase_values(first_targets)
    state_by_bar: list[dict[str, PressionLanePhrase]] = []

    for phrase_start in range(0, BARS_PER_BANK, phrase_length):
        desired = _choose_phrase_targets(
            force, behaviour, transition, cr_mode, phrase_start
        )
        targets = {
            name: _f(current_values.get(name, 0.0) + (desired.get(name, 0.0) - current_values.get(name, 0.0)) * strength)
            for name in DIMENSION_NAMES
        }

        for offset in range(phrase_length):
            if len(state_by_bar) >= BARS_PER_BANK:
                break
            phrase_position = offset / max(1, phrase_length)
            signals = _drop_signals(phrase_position)
            state_by_bar.append({
                name: PressionLanePhrase(
                    current_value=current_values.get(name, 0.0),
                    target_value=targets.get(name, 0.0),
                    phrase_position=phrase_position,
                    phrase_length_bars=phrase_length,
                    tension=signals["tension"],
                    anticipation=signals["anticipation"],
                    release_proximity=signals["release_proximity"],
                    thinning=signals["thinning"],
                )
                for name in DIMENSION_NAMES
            })

        current_values = targets

    return state_by_bar


def _phrase_levels_for_bar(
    phrase_state: dict[str, PressionLanePhrase],
) -> dict[str, float]:
    result: dict[str, float] = {}
    for name, state in phrase_state.items():
        t = _smoothstep(state.phrase_position)
        base = state.current_value + (state.target_value - state.current_value) * t
        signals = _drop_signals(state.phrase_position)
        tension = signals["tension"]
        anticipation = signals["anticipation"]
        release_proximity = signals["release_proximity"]
        thinning = signals["thinning"]
        post_drop = signals["post_drop"]
        early_mid = signals["early_mid"]
        final_warning = signals["final_warning"]

        if name == "pressure":
            value = base + tension * 0.24 - post_drop * 0.22
        elif name == "riser":
            hold_pos = 0.72
            hold_t = _smoothstep(hold_pos)
            hold_base = (
                state.current_value
                + (state.target_value - state.current_value) * hold_t
            )
            hold_level = hold_base + _drop_signals(hold_pos)["anticipation"] * 0.42
            build_level = base + anticipation * 0.42
            gap = release_proximity * thinning
            held_level = hold_level - thinning * 0.16
            if gap > 0.2:
                build_level = min(build_level, held_level)
            value = build_level * (1.0 - gap) + held_level * gap
            value -= post_drop * 0.55
        elif name == "silence":
            value = base + thinning * 0.48 - post_drop * 0.50
        elif name == "impact":
            gap = release_proximity * thinning
            value = base * (1.0 - release_proximity * 0.55) * (1.0 - gap * 0.75) + post_drop * 0.70
        elif name == "landing_strength":
            gap = release_proximity * thinning
            value = base * (1.0 - release_proximity * 0.45) * (1.0 - gap * 0.65) + post_drop * 0.78
        elif name == "density":
            value = base + early_mid * 0.16 - thinning * 0.38 + post_drop * 0.28
        elif name in {"bass_intensity", "stab_intensity", "call_intensity", "response_intensity"}:
            value = base + early_mid * 0.14 - thinning * 0.30 + post_drop * 0.24
        elif name == "pre_warning":
            value = base + final_warning * 0.46 - post_drop * 0.20
        else:
            value = base

        result[name] = _f(value)
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
    phrase_state: Optional[dict[str, PressionLanePhrase]] = None,
) -> PressionBar:
    """Compute one PressionBar at 16th-note resolution.

    All output values are int 0–127.
    No side effects; no global state read or written.
    """
    from thelmic.call_response import Mode as CRMode

    by_step  = _events_at_steps(bar_events)
    all_vels = [e.velocity for evts in by_step.values() for e in evts]
    phrase_state = phrase_state or {}
    phrase_levels = _phrase_levels_for_bar(phrase_state) if phrase_state else {}

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

    pressure = _compose_phrase_lane(
        pressure, phrase_levels.get("pressure", p_scalar)
    )
    impact = _compose_phrase_lane(
        impact, phrase_levels.get("impact", max(impact_raw) if impact_raw else 0.0)
    )
    density = _compose_phrase_lane(
        density, phrase_levels.get("density", density_scalar)
    )
    silence = _compose_phrase_lane(
        silence, phrase_levels.get("silence", 1.0 - density_scalar)
    )
    riser = _compose_phrase_lane(
        riser, phrase_levels.get("riser", riser_scalar)
    )
    leadership = _compose_phrase_lane(
        leadership, phrase_levels.get("leadership", lead_val / 127.0)
    )
    call_intensity = _compose_phrase_lane(
        call_intensity, phrase_levels.get("call_intensity", behaviour.energy_level)
    )
    response_intensity = _compose_phrase_lane(
        response_intensity, phrase_levels.get("response_intensity", behaviour.energy_level)
    )

    if cr_mode == CRMode.BASS_LEADS:
        bass_intensity = call_intensity
        stab_intensity = response_intensity
    else:
        bass_intensity = response_intensity
        stab_intensity = call_intensity

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
    landing_strength = _compose_phrase_lane(
        landing_strength, phrase_levels.get("landing_strength", final_vel)
    )
    pre_warning = _compose_phrase_lane(
        pre_warning, phrase_levels.get("pre_warning", pw_scalar)
    )

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
        bass_intensity=bass_intensity,
        stab_intensity=stab_intensity,
        landing_strength=landing_strength,
        pre_warning=pre_warning,
        overlays=overlays,
        phrase_state=phrase_state,
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
    phrase_length_bars: int = DEFAULT_PHRASE_LENGTH_BARS,
    phrase_strength: float = DEFAULT_PHRASE_STRENGTH,
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

    phrase_states = _phrase_state_for_bank(
        force=force,
        behaviour=behaviour,
        transition=transition,
        cr_mode=cr_mode,
        phrase_length_bars=phrase_length_bars,
        phrase_strength=phrase_strength,
    )

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
            phrase_state=phrase_states[bar_idx],
        )
        prev_density = min(1.0, len([e for evts in _events_at_steps(bar_events).values()
                                     for e in evts]) / 24.0)
        timeline.append(pb)

    # role_flip overlay: add to bars where cr_mode is different from the bank default
    # (this is approximate; the server adds flip overlays when the mode actually changes)
    return timeline
