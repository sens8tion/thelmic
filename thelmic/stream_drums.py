"""Kick and hat voices migrated onto the stream-processing spine."""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Sequence

_log = logging.getLogger("thelmic.stream_drums")

from thelmic.bank_generator import (
    CLOSED_HAT_NOTE,
    KICK_NOTE,
    MIDIEvent,
    OPEN_HAT_NOTE,
    SNARE_NOTE,
)
from thelmic.stream_engine import Intent, ResolveStream, ResolvedEvent, StructureFrame
from thelmic.stream_hooks import bank_step_to_time


class KickIntentStream:
    source = "stream_kick"

    def intents_for_frame(self, frame: StructureFrame) -> tuple[Intent, ...]:
        if not (frame.is_bar_start or frame.is_drop or frame.is_relock):
            return ()
        velocity = 116 if frame.is_drop else 100
        reason = "drop_relock_kick" if frame.is_drop or frame.is_relock else "bar_start_kick"
        return (
            Intent(
                step=frame.global_step,
                instrument="kick",
                role="anchor",
                velocity=velocity,
                duration=0.08,
                phrase_index=frame.phrase_index,
                subphrase_index=frame.subphrase_index,
                priority=8,
                source=self.source,
                reason=reason,
                intent_id=f"{self.source}:{frame.global_step}:{reason}",
                payload={
                    "note": KICK_NOTE,
                    "global_step": frame.global_step,
                    "musical_step": frame.musical_step,
                    "bar_index": frame.bar_index,
                    "phrase_index": frame.phrase_index,
                    "step_in_bar": frame.step_in_bar,
                    "is_bar_start": frame.is_bar_start,
                    "is_phrase_start": frame.is_phrase_start,
                    "is_drop": frame.is_drop,
                },
            ),
        )


class HatIntentStream:
    source = "stream_hat"

    def intents_for_frame(self, frame: StructureFrame) -> tuple[Intent, ...]:
        interval = _hat_interval(frame)
        if frame.step_in_bar % interval != 0:
            return ()
        open_hat = frame.step_in_bar % 8 == 4 and frame.density >= 0.55
        note = OPEN_HAT_NOTE if open_hat else CLOSED_HAT_NOTE
        role = "anchor" if frame.step_in_bar % 4 == 0 else "ghost"
        velocity = _hat_velocity(frame, role)
        return (
            Intent(
                step=frame.global_step,
                instrument="hat",
                role=role,
                velocity=velocity,
                duration=0.06 if open_hat else 0.03,
                phrase_index=frame.phrase_index,
                subphrase_index=frame.subphrase_index,
                priority=2,
                source=self.source,
                reason="density_subdivision_hat",
                intent_id=f"{self.source}:{frame.global_step}:density_subdivision_hat",
                payload={
                    "global_step": frame.global_step,
                    "musical_step": frame.musical_step,
                    "bar_index": frame.bar_index,
                    "phrase_index": frame.phrase_index,
                    "note": note,
                    "density": frame.density,
                    "pressure": frame.pressure,
                    "step_in_bar": frame.step_in_bar,
                },
            ),
        )


def render_stream_kick_events(
    frames: Sequence[StructureFrame],
    template_events: Sequence[MIDIEvent],
    resolver: ResolveStream | None = None,
) -> tuple[list[MIDIEvent], dict]:
    return _render_stream_drum_events(
        frames,
        template_events,
        stream=KickIntentStream(),
        source="stream_kick",
        stat_prefix="kick",
        resolver=resolver,
    )


def render_stream_hat_events(
    frames: Sequence[StructureFrame],
    template_events: Sequence[MIDIEvent],
    resolver: ResolveStream | None = None,
) -> tuple[list[MIDIEvent], dict]:
    return _render_stream_drum_events(
        frames,
        template_events,
        stream=HatIntentStream(),
        source="stream_hat",
        stat_prefix="hat",
        resolver=resolver,
    )


def _render_stream_drum_events(
    frames: Sequence[StructureFrame],
    template_events: Sequence[MIDIEvent],
    *,
    stream,
    source: str,
    stat_prefix: str,
    resolver: ResolveStream | None = None,
) -> tuple[list[MIDIEvent], dict]:
    resolver = resolver or ResolveStream()
    template = _source_template(template_events)
    if template is None:
        return [], _empty_stats(source, stat_prefix)

    rendered: list[MIDIEvent] = []
    suppressions: dict[str, int] = {}
    event_frames: list[dict] = []
    attempted = 0
    resolved = 0
    suppressed = 0
    for frame in frames:
        intents = stream.intents_for_frame(frame)
        attempted += len(intents)
        result = resolver.resolve(frame, intents)
        resolved += len(result.events)
        suppressed += len(result.suppressions)
        for suppression in result.suppressions:
            suppressions[suppression.reason] = suppressions.get(suppression.reason, 0) + 1
        for event in result.events:
            rendered.append(_to_midi_event(template, event))
            if stat_prefix == "kick":
                payload = event.origin_intent.payload
                event_frames.append({
                    "global_step": payload.get("global_step"),
                    "musical_step": payload.get("musical_step"),
                    "bar_index": payload.get("bar_index"),
                    "phrase_index": payload.get("phrase_index"),
                    "step_in_bar": payload.get("step_in_bar"),
                    "is_bar_start": payload.get("is_bar_start"),
                    "is_phrase_start": payload.get("is_phrase_start"),
                    "is_drop": payload.get("is_drop"),
                    "source": event.origin_intent.source,
                    "reason": event.origin_intent.reason,
                    "intent_id": event.origin_intent.intent_id,
                    "resolved_event_id": event.resolved_event_id,
                })

    global_steps = [f.global_step for f in frames]
    musical_steps = [f.musical_step for f in frames]
    _log.debug(
        "%s stream render: frames=%d global_step=%d..%d musical_step=%d..%d "
        "events_resolved=%d events_suppressed=%d",
        stat_prefix, len(frames),
        min(global_steps, default=0), max(global_steps, default=0),
        min(musical_steps, default=0), max(musical_steps, default=0),
        resolved, suppressed,
    )
    return rendered, {
        f"{stat_prefix}_source": "stream_engine",
        f"{stat_prefix}_intents_attempted": attempted,
        f"{stat_prefix}_events_resolved": resolved,
        f"{stat_prefix}_intents_suppressed": suppressed,
        f"{stat_prefix}_suppressions": suppressions,
        f"{stat_prefix}_event_frames": event_frames,
    }


def _to_midi_event(template: MIDIEvent, event: ResolvedEvent) -> MIDIEvent:
    intent = event.origin_intent
    _require_stream_provenance(event)
    note = int(intent.payload.get("note", KICK_NOTE))
    layer = intent.instrument
    # Use musical_step (bank-relative 0..255) not global_step for time conversion.
    # global_step is absolute across banks (bank1 starts at 256, bank2 at 512 …).
    # step_to_time() expects a bank-relative step; using global_step produces
    # bar numbers ≥ 17 for bank 1+, which causes events to be silently dropped.
    musical_step = int(intent.payload.get("musical_step", event.step % 256))
    return replace(
        template,
        time=bank_step_to_time(musical_step),
        note=note,
        velocity=event.velocity,
        duration=event.duration,
        layer=layer,
        role=intent.role,
        emphasis=1.0 if layer == "kick" else (0.70 if intent.role == "anchor" else 0.38),
        openness=1.0,
        expected_weight=1.0 if layer == "kick" else float(intent.payload.get("density", 0.5)),
        should_resolve=False,
        active=True,
        structural_authority=layer == "kick",
        deformation={**template.deformation, layer: 1.0, intent.source: 1.0},
        origin_source=intent.source,
        origin_reason=intent.reason,
        resolution_reason=event.resolution_reason,
        source="stream",
        reason=intent.reason,
        intent_id=intent.intent_id,
        resolved_event_id=event.resolved_event_id,
        global_step=int(intent.payload.get("global_step", event.step)),
        musical_step=musical_step,
        phrase_index=intent.phrase_index,
        bar_index=int(intent.payload.get("bar_index", 0)),
    )


def _require_stream_provenance(event: ResolvedEvent) -> None:
    intent = event.origin_intent
    missing: list[str] = []
    if not intent.source:
        missing.append("source")
    if not intent.intent_id:
        missing.append("intent_id")
    if not event.resolved_event_id:
        missing.append("resolved_event_id")
    if int(intent.payload.get("musical_step", -1)) < 0:
        missing.append("musical_step")
    if int(intent.payload.get("global_step", -1)) < 0:
        missing.append("global_step")
    if intent.phrase_index < 0:
        missing.append("phrase_index")
    if int(intent.payload.get("bar_index", 0)) < 1:
        missing.append("bar_index")
    if not intent.reason:
        missing.append("reason")
    if missing:
        raise RuntimeError(
            f"stream {intent.instrument} event missing provenance: "
            + ", ".join(missing)
        )


def _source_template(events: Sequence[MIDIEvent]) -> MIDIEvent | None:
    for event in events:
        if getattr(event, "active", True) and event.layer == "snare":
            return event
    return next((event for event in events if getattr(event, "active", True)), _default_template())


def _default_template() -> MIDIEvent:
    return MIDIEvent(
        time="1.1.0",
        note=SNARE_NOTE,
        velocity=90,
        duration=0.08,
        layer="snare",
        role="anchor",
        emphasis=1.0,
        openness=1.0,
        expected_weight=1.0,
        should_resolve=False,
    )


def _empty_stats(source: str, prefix: str) -> dict:
    return {
        f"{prefix}_source": "stream_engine",
        f"{prefix}_intents_attempted": 0,
        f"{prefix}_events_resolved": 0,
        f"{prefix}_intents_suppressed": 0,
        f"{prefix}_suppressions": {},
        f"{prefix}_event_frames": [],
    }


def _hat_interval(frame: StructureFrame) -> int:
    if frame.density >= 0.62 or frame.pressure >= 0.65:
        return 2
    return 4


def _hat_velocity(frame: StructureFrame, role: str) -> int:
    base = 68 if role == "anchor" else 40
    value = base * (0.85 + frame.density * 0.20 + frame.pressure * 0.10)
    return max(1, min(127, int(value)))
