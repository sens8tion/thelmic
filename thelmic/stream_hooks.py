"""Hook voice migration onto the stream-processing spine."""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable, Sequence

from thelmic.bank_generator import MIDIEvent
from thelmic.phrase_plan import PhrasePlan, PlanNote
from thelmic.stream_engine import (
    Intent,
    ResolveResult,
    ResolveStream,
    ResolvedEvent,
    StructureFrame,
    STEPS_PER_BAR,
)


TICKS_PER_BEAT = 24
TICKS_PER_STEP = 6


def step_to_time(step: int) -> str:
    bar = step // STEPS_PER_BAR + 1
    step_in_bar = step % STEPS_PER_BAR
    tick_in_bar = step_in_bar * TICKS_PER_STEP
    beat = tick_in_bar // TICKS_PER_BEAT + 1
    tick = tick_in_bar % TICKS_PER_BEAT
    return f"{bar}.{beat}.{tick}"


class HookIntentStream:
    """Emit hook intents from StructureFrame only.

    The stream intentionally emits hook candidates wherever the phrase-plan motif
    rhythm appears. ResolveStream decides which candidates are structurally
    allowed. This gives us suppression diagnostics without allowing the hook
    generator to become a permission authority.
    """

    source = "stream_hook"

    def __init__(self, plan: PhrasePlan) -> None:
        self.plan = plan
        self._notes_by_step = _notes_by_step(plan.hook_pattern)
        self._motif_length_steps = _motif_length_steps(plan.hook_pattern)

    def intents_for_frame(self, frame: StructureFrame) -> tuple[Intent, ...]:
        if not self._notes_by_step:
            return ()
        motif_step = frame.step_in_phrase % self._motif_length_steps
        notes = self._notes_by_step.get(motif_step, ())
        if not notes:
            return ()
        return tuple(
            Intent(
                step=frame.global_step,
                instrument="hook",
                role="hook",
                velocity=_clamp_velocity(note.velocity),
                duration=max(1, note.duration_steps) * 0.08,
                phrase_index=frame.phrase_index,
                subphrase_index=frame.subphrase_index,
                priority=4,
                source=self.source,
                reason=(
                    "phrase_start_hook"
                    if frame.is_phrase_start
                    else "planned_hook_candidate"
                ),
                intent_id=f"{self.source}:{frame.global_step}:{note.pitch}",
                payload={
                    "pitch": note.pitch,
                    "global_step": frame.global_step,
                    "musical_step": frame.musical_step,
                    "bar_index": frame.bar_index,
                    "phrase_index": frame.phrase_index,
                    "step_in_bar": frame.step_in_bar,
                },
            )
            for note in notes
        )


def render_stream_hook_events(
    frames: Sequence[StructureFrame],
    plan: PhrasePlan,
    template_events: Sequence[MIDIEvent],
    resolver: ResolveStream | None = None,
) -> tuple[list[MIDIEvent], dict]:
    """Render hook via Intent -> Resolve -> MIDIEvent adapter.

    This is the migration bridge: downstream UI/MIDI still read the legacy
    Bank event bus, but hook events now originate from the stream engine.
    """

    stream = HookIntentStream(plan)
    resolver = resolver or ResolveStream()
    template = _source_template(template_events)
    if template is None:
        return [], {
            "hook_source": "stream_engine",
            "hook_intents_attempted": 0,
            "hook_events_resolved": 0,
            "hook_intents_suppressed": 0,
            "hook_suppressions": {},
        }

    rendered: list[MIDIEvent] = []
    suppressions: dict[str, int] = {}
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

    return rendered, {
        "hook_source": "stream_engine",
        "hook_intents_attempted": attempted,
        "hook_events_resolved": resolved,
        "hook_intents_suppressed": suppressed,
        "hook_suppressions": suppressions,
    }


def _to_midi_event(template: MIDIEvent, event: ResolvedEvent) -> MIDIEvent:
    intent = event.origin_intent
    _require_stream_provenance(event)
    pitch = int(intent.payload.get("pitch", 60))
    # Use musical_step (bank-relative) not global_step — same fix as stream_drums.
    musical_step = int(intent.payload.get("musical_step", event.step % 256))
    return replace(
        template,
        time=step_to_time(musical_step),
        note=pitch,
        velocity=event.velocity,
        duration=event.duration,
        layer="hook",
        role="hook",
        emphasis=0.72,
        openness=0.5,
        expected_weight=0.7,
        should_resolve=False,
        active=True,
        structural_authority=True,
        deformation={**template.deformation, "hook": 1.0, "stream_hook": 1.0},
        origin_source=intent.source,
        origin_reason=intent.reason,
        resolution_reason=event.resolution_reason,
        source="stream",
        reason=intent.reason,
        intent_id=intent.intent_id,
        resolved_event_id=event.resolved_event_id,
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
        if getattr(event, "active", True) and event.layer in {"kick", "snare", "hat"}:
            return event
    return next((event for event in events if getattr(event, "active", True)), None)


def _notes_by_step(notes: Iterable[PlanNote]) -> dict[int, tuple[PlanNote, ...]]:
    grouped: dict[int, list[PlanNote]] = {}
    for note in notes:
        step = (note.bar - 1) * STEPS_PER_BAR + note.step
        grouped.setdefault(step, []).append(note)
    return {step: tuple(items) for step, items in grouped.items()}


def _motif_length_steps(notes: Iterable[PlanNote]) -> int:
    max_step = 0
    for note in notes:
        max_step = max(max_step, (note.bar - 1) * STEPS_PER_BAR + note.step + note.duration_steps)
    return max(STEPS_PER_BAR, max_step)


def _clamp_velocity(value: int) -> int:
    return max(1, min(127, int(value)))
