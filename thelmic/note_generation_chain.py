"""Thelmic v1.0 note generation chain.

This is the only active v1.0 musical event generator. It deliberately emits a
simple continuous v1 output: stable kick, snare, hat subdivision, and a timing
anchor during drop-prep. It does not rely on post-generation rescue systems.
"""

from __future__ import annotations

from typing import Iterable

from thelmic.bank_generator import (
    BARS_PER_PHRASE,
    CLOSED_HAT_NOTE,
    KICK_NOTE,
    MIDIEvent,
    OPEN_HAT_NOTE,
    PHRASES_PER_BANK,
    SNARE_NOTE,
    Bank,
    Phrase,
)
from thelmic.stream_engine import Intent, ResolveStream, StructureFrame, StructureProfile, StructureStream, Tick


VERSION = "v1.0"
BANK_STEPS = BARS_PER_PHRASE * PHRASES_PER_BANK * 16


def generate_bank(bank_index: int = 0) -> Bank:
    profile = StructureProfile(
        phrase_length_bars=BARS_PER_PHRASE * PHRASES_PER_BANK,
        subphrase_length_bars=4,
        origin_step=bank_index * BANK_STEPS,
    )
    stream = StructureStream(profile)
    frames = list(
        stream.frames(
            Tick(global_step=bank_index * BANK_STEPS + step)
            for step in range(BANK_STEPS)
        )
    )
    resolver = ResolveStream()
    phrases = [Phrase(phrase_index=index) for index in range(PHRASES_PER_BANK)]
    for frame in frames:
        result = resolver.resolve(frame, intents_for_frame(frame))
        for event in result.events:
            midi_event = _resolved_to_midi_event(event, frame)
            phrases[(midi_event.bar_index - 1) // BARS_PER_PHRASE].events.append(midi_event)
    return Bank(bank_index=bank_index, phrases=phrases)


def structure_frames(bank_index: int = 0) -> list[StructureFrame]:
    profile = StructureProfile(
        phrase_length_bars=BARS_PER_PHRASE * PHRASES_PER_BANK,
        subphrase_length_bars=4,
        origin_step=bank_index * BANK_STEPS,
    )
    stream = StructureStream(profile)
    return list(
        stream.frames(
            Tick(global_step=bank_index * BANK_STEPS + step)
            for step in range(BANK_STEPS)
        )
    )


def intents_for_frame(frame: StructureFrame) -> tuple[Intent, ...]:
    intents: list[Intent] = []
    intents.extend(_kick(frame))
    intents.extend(_snare(frame))
    intents.extend(_hat(frame))
    intents.extend(_grid_reminder(frame))
    return tuple(intents)


def _kick(frame: StructureFrame) -> Iterable[Intent]:
    if frame.is_drop:
        yield _intent(frame, "kick", "timing_anchor", 124, 0.08, "drop_anchor", KICK_NOTE, 10)
        return
    if frame.is_drop_prep:
        if frame.step_in_bar in (0, 8):
            yield _intent(frame, "kick", "timing_anchor", 108, 0.07, "compressed_kick_anchor", KICK_NOTE, 10)
        return
    if frame.step_in_bar in (0, 8):
        yield _intent(frame, "kick", "timing_anchor", 112, 0.08, "continuous_kick_anchor", KICK_NOTE, 10)


def _snare(frame: StructureFrame) -> Iterable[Intent]:
    if frame.is_drop_prep:
        if frame.step_in_bar == 12:
            yield _intent(frame, "snare", "backbeat", 78, 0.05, "drop_prep_backbeat_reference", SNARE_NOTE, 8)
        return
    if frame.step_in_bar in (4, 12):
        yield _intent(frame, "snare", "backbeat", 96, 0.06, "stable_backbeat", SNARE_NOTE, 8)


def _hat(frame: StructureFrame) -> Iterable[Intent]:
    if frame.is_drop_prep:
        if frame.step_in_bar % 2 == 0:
            yield _intent(frame, "hat", "grid_reminder", 54, 0.025, "drop_prep_grid_reminder", CLOSED_HAT_NOTE, 5)
        return
    if frame.step_in_bar % 2 == 0:
        note = OPEN_HAT_NOTE if frame.step_in_bar in (6, 14) else CLOSED_HAT_NOTE
        velocity = 76 if note == OPEN_HAT_NOTE else 64
        yield _intent(frame, "hat", "subdivision", velocity, 0.035, "continuous_hat_subdivision", note, 5)


def _grid_reminder(frame: StructureFrame) -> Iterable[Intent]:
    if not frame.is_drop_prep:
        return
    if frame.step_in_bar % 2 == 1:
        yield _intent(frame, "hat", "timing_anchor", 38, 0.02, "tightening_grid_reminder", CLOSED_HAT_NOTE, 4)


def _intent(
    frame: StructureFrame,
    instrument: str,
    role: str,
    velocity: int,
    duration: float,
    reason: str,
    note: int,
    priority: int,
) -> Intent:
    intent_id = f"note_generation_chain:{frame.global_step}:{instrument}:{reason}"
    return Intent(
        step=frame.global_step,
        instrument=instrument,
        role=role,
        velocity=velocity,
        duration=duration,
        phrase_index=frame.phrase_index,
        subphrase_index=frame.subphrase_index,
        priority=priority,
        source="note_generation_chain",
        reason=reason,
        intent_id=intent_id,
        payload={
            "note": note,
            "global_step": frame.global_step,
            "musical_step": frame.musical_step,
            "bar_index": frame.bar_index,
            "step_in_bar": frame.step_in_bar,
            "phrase_index": frame.phrase_index,
            "is_drop": frame.is_drop,
            "is_drop_prep": frame.is_drop_prep,
        },
    )


def _resolved_to_midi_event(event, frame: StructureFrame) -> MIDIEvent:
    intent = event.origin_intent
    musical_step = int(intent.payload["musical_step"])
    return MIDIEvent(
        time=bank_step_to_time(musical_step),
        note=int(intent.payload["note"]),
        velocity=event.velocity,
        duration=event.duration,
        layer=intent.instrument,
        role=intent.role,
        emphasis=1.0 if intent.instrument == "kick" else 0.7,
        openness=1.0,
        expected_weight=1.0,
        should_resolve=False,
        active=True,
        structural_authority=intent.instrument in {"kick", "snare"},
        origin_source=intent.source,
        origin_reason=intent.reason,
        resolution_reason=event.resolution_reason,
        source="stream",
        reason=intent.reason,
        intent_id=intent.intent_id,
        resolved_event_id=event.resolved_event_id,
        global_step=int(intent.payload["global_step"]),
        musical_step=musical_step,
        phrase_index=intent.phrase_index,
        bar_index=int(intent.payload["bar_index"]),
    )


def bank_step_to_time(step: int) -> str:
    if not 0 <= step < BANK_STEPS:
        raise ValueError(f"bank step out of range: {step}")
    bar = step // 16 + 1
    step_in_bar = step % 16
    beat = step_in_bar // 4 + 1
    tick = (step_in_bar % 4) * 6
    return f"{bar}.{beat}.{tick}"
