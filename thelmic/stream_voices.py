"""Stream intent generators for all remaining musical voices.

Each voice follows the same pattern as stream_drums / stream_hooks:
  IntentStream  → emits Intents from StructureFrames
  render_*()    → produces (list[MIDIEvent], stats)

Step vocabulary
---------------
  global_step   — absolute transport position (never pass to bank_step_to_time)
  musical_step  — bank-relative 0..255  (use for time conversion)
  step_in_bar   — local 0..15 within one bar

Authority
---------
All functions respect their caller's authority flag. When authority="stream"
the legacy path should no-op before calling these functions. Legacy code
remains intact behind the authority gate for rollback.

Voices covered here
-------------------
  snare       — bar-position-driven anchor beats
  bassline    — territory-shaped repeating phrase
  sub         — sparse long-hold foundation
  call        — call-window intents (steps 0–7)
  response    — response-window intents (steps 8–15)
  stab        — call/response combined
  ghost       — density-driven ghost fills around anchor positions
  drop_relock — intent requirements emitted at drop/relock frames

Provenance requirements (from architecture contract)
-----------------------------------------------------
Every ResolvedEvent must carry in its origin_intent:
  source, intent_id, reason, phrase_index, subphrase_index
  payload: global_step, musical_step, bar_index, step_in_bar
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Sequence

from thelmic.bank_generator import (
    CLOSED_HAT_NOTE,
    KICK_NOTE,
    MIDIEvent,
    OPEN_HAT_NOTE,
    SNARE_NOTE,
)
from thelmic.stream_engine import Intent, ResolveStream, ResolvedEvent, StructureFrame
from thelmic.stream_hooks import bank_step_to_time

_log = logging.getLogger("thelmic.stream_voices")

# ---------------------------------------------------------------------------
# MIDI note assignments
# ---------------------------------------------------------------------------
BASSLINE_NOTE   = 36   # C2
SUB_NOTE        = 24   # C1
CALL_NOTE       = 62   # D4
RESPONSE_NOTE   = 57   # A3
STAB_CALL_NOTE  = 62   # D4
STAB_RESP_NOTE  = 57   # A3
GHOST_NOTE      = 38   # snare ghost
SURVIVOR_NOTE   = CLOSED_HAT_NOTE


# ---------------------------------------------------------------------------
# Shared provenance payload builder
# ---------------------------------------------------------------------------

def _base_payload(frame: StructureFrame) -> dict:
    return {
        "global_step":       frame.global_step,
        "musical_step":      frame.musical_step,
        "bar_index":         frame.bar_index,
        "step_in_bar":       frame.step_in_bar,
        "phrase_index":      frame.phrase_index,
        "subphrase_index":   frame.subphrase_index,
        "is_bar_start":      frame.is_bar_start,
        "is_phrase_start":   frame.is_phrase_start,
        "is_drop":           frame.is_drop,
        "density":           frame.density,
        "pressure":          frame.pressure,
        "silence":           frame.silence,
    }


def _make_intent(
    frame: StructureFrame,
    source: str,
    instrument: str,
    role: str,
    velocity: int,
    duration: float,
    reason: str,
    note: int,
    priority: int = 4,
    **extra_payload,
) -> Intent:
    intent_id = f"{source}:{frame.global_step}:{reason}"
    return Intent(
        step=frame.global_step,
        instrument=instrument,
        role=role,
        velocity=velocity,
        duration=duration,
        phrase_index=frame.phrase_index,
        subphrase_index=frame.subphrase_index,
        priority=priority,
        source=source,
        reason=reason,
        intent_id=intent_id,
        payload={
            **_base_payload(frame),
            "note": note,
            **extra_payload,
        },
    )


# ---------------------------------------------------------------------------
# Snare
# ---------------------------------------------------------------------------

class SnareIntentStream:
    source = "stream_snare"

    def intents_for_frame(self, frame: StructureFrame) -> tuple[Intent, ...]:
        # Snare anchors beats 2 and 4 (step_in_bar 4 and 12)
        if frame.step_in_bar not in (4, 12):
            return ()
        # Thin snare during silence / pre-drop
        if frame.silence > 0.7:
            return ()
        velocity = self._velocity(frame)
        reason = "snare_drop" if frame.is_drop else "snare_anchor"
        return (
            _make_intent(
                frame, self.source, "snare", "anchor",
                velocity, 0.05, reason, SNARE_NOTE,
                priority=7,
                is_backbeat=True,
            ),
        )

    def _velocity(self, frame: StructureFrame) -> int:
        base = 105 if frame.is_drop else 90
        return max(1, min(127, int(base * (0.8 + frame.density * 0.2))))


# ---------------------------------------------------------------------------
# Bassline
# ---------------------------------------------------------------------------

class BasslineIntentStream:
    source = "stream_bassline"

    # Patterns: (steps_in_bar, duration_steps)
    _PATTERNS = {
        "driving":     ([0, 4, 8, 12], 2),
        "offbeat":     ([2, 6, 10, 14], 2),
        "half_bar":    ([0, 8], 8),
        "full_bar":    ([0], 16),
        "syncopated":  ([2, 6, 10, 12, 14], 2),
    }

    def _pattern_name(self, frame: StructureFrame) -> str:
        if frame.density >= 0.75:
            return "driving"
        if frame.density >= 0.55:
            # Alternate offbeat/driving based on pressure
            return "offbeat" if frame.pressure < 0.4 else "syncopated"
        if frame.density >= 0.35:
            return "half_bar"
        return "full_bar"

    def intents_for_frame(self, frame: StructureFrame) -> tuple[Intent, ...]:
        if frame.silence > 0.8:
            return ()
        pattern_name = self._pattern_name(frame)
        steps, dur_steps = self._PATTERNS[pattern_name]
        if frame.step_in_bar not in steps:
            return ()
        velocity = max(1, min(127, int(100 * (0.85 + frame.density * 0.15))))
        duration = 0.08 * dur_steps
        return (
            _make_intent(
                frame, self.source, "bassline", "bass",
                velocity, duration, f"bassline_{pattern_name}", BASSLINE_NOTE,
                priority=6,
                pattern_name=pattern_name,
                duration_steps=dur_steps,
            ),
        )


# ---------------------------------------------------------------------------
# Sub
# ---------------------------------------------------------------------------

class SubIntentStream:
    source = "stream_sub"

    def intents_for_frame(self, frame: StructureFrame) -> tuple[Intent, ...]:
        # Sub fires at bar start only, with territory-shaped hold lengths
        if not frame.is_bar_start:
            return ()
        # Sub holds through silence (foundational — stays when other layers thin)
        duration_steps, reason = self._pattern(frame)
        duration_s = 0.08 * duration_steps
        velocity = max(1, min(127, int(88 * (0.82 + frame.density * 0.18))))
        return (
            _make_intent(
                frame, self.source, "sub", "sub",
                velocity, duration_s, reason, SUB_NOTE,
                priority=9,   # high priority — sub is foundational
                duration_steps=duration_steps,
                sub_pattern=reason,
            ),
        )

    def _pattern(self, frame: StructureFrame) -> tuple[int, str]:
        if frame.density >= 0.67:
            # Nott-style: long multi-bar hold
            if frame.phrase_index % 4 == 0:
                return 32, "long_multi_bar_hold"
            return 16, "full_bar_hold"
        if frame.density >= 0.35 and frame.pressure >= 0.5:
            return 8, "half_bar_pulse"
        return 16, "full_bar_hold"


# ---------------------------------------------------------------------------
# Call / Response / Stab
# ---------------------------------------------------------------------------

class CallIntentStream:
    """Emits call intents in steps 0–7 (beats 1–2)."""
    source = "stream_call"

    def intents_for_frame(self, frame: StructureFrame) -> tuple[Intent, ...]:
        # Calls fire at steps 2 and 6 (offbeat, in call window)
        if frame.step_in_bar not in (2, 6):
            return ()
        if frame.silence > 0.5:
            return ()
        # Only in call-appropriate phrase phases (not pre-drop silence)
        if frame.phrase_role.value in ("pre_drop", "drop"):
            return ()
        index = 0 if frame.step_in_bar == 2 else 1
        velocity = max(60, min(95, 72 + index * 8))
        note = CALL_NOTE + (index % 3) * 2
        return (
            _make_intent(
                frame, self.source, "stab", "call",
                velocity, 0.06, "planned_call", note,
                priority=5,
                call_index=index,
            ),
        )


class ResponseIntentStream:
    """Emits response intents in steps 8–15 (beats 3–4)."""
    source = "stream_response"

    def intents_for_frame(self, frame: StructureFrame) -> tuple[Intent, ...]:
        # Responses fire at steps 10, 13, 14
        if frame.step_in_bar not in (10, 13, 14):
            return ()
        if frame.silence > 0.5:
            return ()
        if frame.phrase_role.value in ("pre_drop", "drop"):
            return ()
        index = {10: 0, 13: 1, 14: 2}[frame.step_in_bar]
        # Landing emphasis: escalate velocity toward final note
        base = 80 + index * 6
        velocity = max(1, min(127, base))
        note = RESPONSE_NOTE - (index % 3) * 3
        return (
            _make_intent(
                frame, self.source, "stab", "response",
                velocity, 0.08 if index < 2 else 0.16,
                "planned_response", note,
                priority=5,
                response_index=index,
                is_landing=(index == 2),
            ),
        )


class StabIntentStream:
    """Combined call + response for stab voice."""

    def __init__(self) -> None:
        self._call    = CallIntentStream()
        self._response = ResponseIntentStream()

    def intents_for_frame(self, frame: StructureFrame) -> tuple[Intent, ...]:
        return self._call.intents_for_frame(frame) + self._response.intents_for_frame(frame)


# ---------------------------------------------------------------------------
# Ghost / support
# ---------------------------------------------------------------------------

class GhostIntentStream:
    source = "stream_ghost"

    def intents_for_frame(self, frame: StructureFrame) -> tuple[Intent, ...]:
        # Ghost notes between bar anchors when density is high enough
        if frame.density < 0.45:
            return ()
        if frame.silence > 0.4:
            return ()
        # Fire at step 2 and 10 (between strong beats)
        if frame.step_in_bar not in (2, 10):
            return ()
        velocity = max(1, min(64, int(38 * (0.8 + frame.density * 0.5))))
        return (
            _make_intent(
                frame, self.source, "snare", "ghost",
                velocity, 0.04, "ghost_fill", GHOST_NOTE,
                priority=2,
                ghost_density=frame.density,
            ),
        )


# ---------------------------------------------------------------------------
# Survivor / pre-drop timing carrier
# ---------------------------------------------------------------------------

class SurvivorIntentStream:
    source = "stream_survivor"

    def intents_for_frame(self, frame: StructureFrame) -> tuple[Intent, ...]:
        if frame.silence <= 0.0:
            return ()
        tightening = max(0.0, min(1.0, frame.silence))
        interval = _survivor_interval(tightening)
        if frame.step_in_bar % interval != 0:
            return ()
        velocity = _survivor_velocity(tightening)
        return (
            _make_intent(
                frame, self.source, "hat", "survivor",
                velocity, 0.025, "survivor_timing_carrier", SURVIVOR_NOTE,
                priority=1,
                survives_silence=True,
                structural_authority=False,
                tightening=round(tightening, 3),
                density_intent=frame.density_intent,
                silence_intent=frame.silence_intent,
            ),
        )


def _survivor_interval(tightening: float) -> int:
    if tightening >= 0.75:
        return 1
    if tightening >= 0.35:
        return 2
    return 4


def _survivor_velocity(tightening: float) -> int:
    # Quietest at the final held-breath moment.
    return max(5, min(24, int(24 - tightening * 19)))


# ---------------------------------------------------------------------------
# Drop / relock requirements
# ---------------------------------------------------------------------------

class DropRelockIntentStream:
    """Emit relock requirements at drop/relock frames.

    These are structural authority intents. ResolveStream decides whether
    to emit bass+kick+hook events or suppression diagnostics. The enforcer
    does not directly inject final notes here.
    """
    source = "stream_drop_relock"

    def intents_for_frame(self, frame: StructureFrame) -> tuple[Intent, ...]:
        if not (frame.is_drop or frame.is_relock):
            return ()
        # Kick is already emitted by KickIntentStream (which fires at is_drop).
        # Bassline is emitted by BasslineIntentStream at step patterns covering drop step.
        # DropRelockIntentStream emits requirements only when the core streams
        # would not otherwise fire (e.g. non-standard drop step positions).
        # For now: emit bassline at drop only if BasslineIntentStream would miss it.
        # BasslineIntentStream fires at step_in_bar in {0,4,8,12} for driving pattern.
        # DROP_STEP = 4 is in that set. This stream acts as a fallback.
        if frame.step_in_bar == 4:
            # BasslineIntentStream driving pattern covers step 4 — no fallback needed.
            return ()
        # Fallback bassline at non-standard drop steps
        return (
            _make_intent(
                frame, self.source, "bassline", "bass",
                110, 0.14, "drop_relock_bass_fallback", BASSLINE_NOTE,
                priority=10,
                drop_event=True,
            ),
        )


# ---------------------------------------------------------------------------
# Render functions
# ---------------------------------------------------------------------------

def _require_provenance(event: ResolvedEvent) -> None:
    intent = event.origin_intent
    missing: list[str] = []
    if not intent.source:               missing.append("source")
    if not intent.intent_id:            missing.append("intent_id")
    if not event.resolved_event_id:     missing.append("resolved_event_id")
    if intent.phrase_index < 0:         missing.append("phrase_index")
    if not intent.reason:               missing.append("reason")
    if intent.payload.get("musical_step") is None:  missing.append("musical_step")
    if intent.payload.get("global_step") is None:   missing.append("global_step")
    if not intent.payload.get("bar_index"):  missing.append("bar_index")
    if missing:
        raise RuntimeError(
            f"stream {intent.instrument} missing provenance: {', '.join(missing)}"
        )


def _to_midi_event(template: MIDIEvent, event: ResolvedEvent) -> MIDIEvent:
    intent = event.origin_intent
    _require_provenance(event)
    musical_step = int(intent.payload.get("musical_step", 0))
    note = int(intent.payload.get("note", template.note))
    layer_map = {
        "kick": "kick", "snare": "snare", "hat": "hat",
        "bassline": "bassline", "sub": "sub", "hook": "hook",
        "stab": "stab",
    }
    layer = layer_map.get(intent.instrument, intent.instrument)
    return replace(
        template,
        time=bank_step_to_time(musical_step),
        note=note,
        velocity=event.velocity,
        duration=event.duration,
        layer=layer,
        role=intent.role,
        emphasis=0.85 if intent.role in ("anchor", "bass") else 0.45,
        openness=1.0,
        expected_weight=0.8,
        should_resolve=False,
        active=True,
        survives_silence=bool(intent.payload.get("survives_silence", False)),
        structural_authority=(intent.instrument in ("kick", "bassline", "sub")),
        deformation={**template.deformation, layer: 1.0, intent.source: 1.0},
        # Full provenance fields
        source="stream",
        reason=intent.reason,
        intent_id=intent.intent_id,
        resolved_event_id=event.resolved_event_id,
        global_step=int(intent.payload.get("global_step", event.step)),
        musical_step=musical_step,
        origin_source=intent.source,
        origin_reason=intent.reason,
        resolution_reason=event.resolution_reason,
        phrase_index=intent.phrase_index,
        bar_index=int(intent.payload.get("bar_index", 0)),
    )


def _source_template(events: Sequence[MIDIEvent]) -> MIDIEvent | None:
    for e in events:
        if getattr(e, "active", True) and e.layer in ("snare", "kick"):
            return e
    return next((e for e in events if getattr(e, "active", True)), None)


def _render(
    frames: Sequence[StructureFrame],
    template_events: Sequence[MIDIEvent],
    *intent_streams,
    stat_prefix: str,
    resolver: ResolveStream | None = None,
) -> tuple[list[MIDIEvent], dict]:
    resolver = resolver or ResolveStream()
    template = _source_template(template_events)
    if template is None:
        return [], {
            f"{stat_prefix}_source": "stream_engine",
            f"{stat_prefix}_intents_attempted": 0,
            f"{stat_prefix}_events_resolved": 0,
            f"{stat_prefix}_intents_suppressed": 0,
            f"{stat_prefix}_suppressions": {},
            f"{stat_prefix}_requirement_trace": [],
        }

    rendered: list[MIDIEvent] = []
    attempted = resolved = suppressed = 0
    suppressions: dict[str, int] = {}
    requirement_trace: list[dict] = []

    for frame in frames:
        intents: list[Intent] = []
        for stream in intent_streams:
            intents.extend(stream.intents_for_frame(frame))
        attempted += len(intents)
        result = resolver.resolve(frame, intents)
        resolved += len(result.events)
        suppressed += len(result.suppressions)
        for s in result.suppressions:
            suppressions[s.reason] = suppressions.get(s.reason, 0) + 1
            requirement_trace.append({
                "requirement_id": s.origin_intent.intent_id,
                "intent_id": s.origin_intent.intent_id,
                "instrument": s.origin_intent.instrument,
                "role": s.origin_intent.role,
                "global_step": s.origin_intent.payload.get("global_step"),
                "musical_step": s.origin_intent.payload.get("musical_step"),
                "status": "suppressed",
                "suppression_reason": s.reason,
            })
        for event in result.events:
            rendered.append(_to_midi_event(template, event))
            requirement_trace.append({
                "requirement_id": event.origin_intent.intent_id,
                "intent_id": event.origin_intent.intent_id,
                "resolved_event_id": event.resolved_event_id,
                "instrument": event.origin_intent.instrument,
                "role": event.origin_intent.role,
                "global_step": event.origin_intent.payload.get("global_step"),
                "musical_step": event.origin_intent.payload.get("musical_step"),
                "status": "resolved",
            })

    gs = [f.global_step for f in frames]
    ms = [f.musical_step for f in frames]
    _log.debug(
        "%s render: frames=%d gs=%d..%d ms=%d..%d resolved=%d suppressed=%d",
        stat_prefix, len(frames),
        min(gs, default=0), max(gs, default=0),
        min(ms, default=0), max(ms, default=0),
        resolved, suppressed,
    )
    return rendered, {
        f"{stat_prefix}_source": "stream_engine",
        f"{stat_prefix}_intents_attempted": attempted,
        f"{stat_prefix}_events_resolved": resolved,
        f"{stat_prefix}_intents_suppressed": suppressed,
        f"{stat_prefix}_suppressions": suppressions,
        f"{stat_prefix}_requirement_trace": requirement_trace,
    }


def render_stream_snare_events(frames, template_events, resolver=None):
    return _render(frames, template_events, SnareIntentStream(),
                   stat_prefix="snare", resolver=resolver)


def render_stream_bassline_events(frames, template_events, resolver=None):
    return _render(frames, template_events, BasslineIntentStream(),
                   stat_prefix="bassline", resolver=resolver)


def render_stream_sub_events(frames, template_events, resolver=None):
    return _render(frames, template_events, SubIntentStream(),
                   stat_prefix="sub", resolver=resolver)


def render_stream_call_events(frames, template_events, resolver=None):
    return _render(frames, template_events, CallIntentStream(),
                   stat_prefix="call", resolver=resolver)


def render_stream_response_events(frames, template_events, resolver=None):
    return _render(frames, template_events, ResponseIntentStream(),
                   stat_prefix="response", resolver=resolver)


def render_stream_stab_events(frames, template_events, resolver=None):
    return _render(frames, template_events, StabIntentStream(),
                   stat_prefix="stab", resolver=resolver)


def render_stream_ghost_events(frames, template_events, resolver=None):
    return _render(frames, template_events, GhostIntentStream(),
                   stat_prefix="ghost", resolver=resolver)


def render_stream_survivor_events(frames, template_events, resolver=None):
    return _render(frames, template_events, SurvivorIntentStream(),
                   stat_prefix="survivor", resolver=resolver)


def render_stream_drop_relock_events(frames, template_events, resolver=None):
    return _render(frames, template_events, DropRelockIntentStream(),
                   stat_prefix="drop_relock", resolver=resolver)
