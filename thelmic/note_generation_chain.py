"""Thelmic v1.0 note generation chain — orchestrator.

Drives voice intent streams through the StructureFrame sequence and resolves
them into a Bank.  Musical decisions live in the voice modules; this file
only assembles and routes.

Phase C adds: phrase engine, bass voice, dimensions from landscape trajectory.
"""

from __future__ import annotations

from typing import Optional

from thelmic.bank_generator import (
    BARS_PER_PHRASE,
    MIDIEvent,
    PHRASES_PER_BANK,
    Bank,
    Phrase,
)
from thelmic.dimensions import Dimensions, PhraseContext
from thelmic.stream_engine import Intent, ResolveStream, StructureFrame, StructureProfile, StructureStream, Tick
from thelmic.voices.kick import KickIntentStream
from thelmic.voices.snare import SnareIntentStream
from thelmic.voices.hat import HatIntentStream
from thelmic.voices.bass import BassIntentStream
from thelmic.voices.sub import SubIntentStream
from thelmic.voices.hook import HookIntentStream
from thelmic.voices.call import CallIntentStream
from thelmic.voices.response import ResponseIntentStream
from thelmic.voices.ghost_32nd import Ghost32ndStream
from thelmic.voices.drones import DroneSpaceyStream, DroneRumbleStream, DroneTensionStream
from thelmic.phrase_engine import context_for_phrase, pending_archetype_for
from thelmic.landscape_map import SignatureRhythm
from thelmic.phrase_arc import compute_arc, ArcDimensions
from thelmic.anticipation_engine import compute_anticipation, AnticipationState


VERSION    = "v1.0"
BANK_STEPS = BARS_PER_PHRASE * PHRASES_PER_BANK * 16

_kick_stream     = KickIntentStream()
_snare_stream    = SnareIntentStream()
_hat_stream      = HatIntentStream()
_bass_stream     = BassIntentStream()
_sub_stream      = SubIntentStream()
_hook_stream     = HookIntentStream()
_call_stream     = CallIntentStream()
_response_stream = ResponseIntentStream()
_ghost_stream    = Ghost32ndStream()
_drone_spacey    = DroneSpaceyStream()
_drone_rumble    = DroneRumbleStream()
_drone_tension   = DroneTensionStream()


def generate_bank(
    bank_index: int = 0,
    dims: Optional[Dimensions] = None,
    is_drop_phrase: bool = False,
    signature_rhythm: Optional[SignatureRhythm] = None,
    previous_active_archetype=None,
    phrases_until_drop: int = 8,
    heat: float = 0.5,
) -> Bank:
    """Generate one bank of events.

    dims:                     current Dimensions (None = rhythm section only)
    is_drop_phrase:           whether this phrase commits a structural change
    signature_rhythm:         active feature's SignatureRhythm (for bass/hook notes)
    previous_active_archetype: archetype from prior phrase (for commitment logic)
    """
    profile = StructureProfile(
        phrase_length_bars=BARS_PER_PHRASE * PHRASES_PER_BANK,
        subphrase_length_bars=4,
        origin_step=bank_index * BANK_STEPS,
    )
    stream   = StructureStream(profile)
    frames   = list(
        stream.frames(
            Tick(global_step=bank_index * BANK_STEPS + step)
            for step in range(BANK_STEPS)
        )
    )

    # Build phrase context once per bank (same phrase for all 256 steps)
    context: Optional[PhraseContext] = None
    if dims is not None and signature_rhythm is not None:
        phrase_start = next(f for f in frames if f.is_phrase_start)
        context = context_for_phrase(
            phrase_start, dims, signature_rhythm,
            previous_active_archetype, is_drop_phrase,
        )

    _response_stream.reset()
    resolver = ResolveStream()
    phrases  = [Phrase(phrase_index=index) for index in range(PHRASES_PER_BANK)]
    for frame in frames:
        # Compute per-frame arc dimensions (release burst + anticipation withholding)
        arc = compute_arc(frame.musical_step, is_drop_phrase, phrases_until_drop, heat)
        # 4-bar minimum hold rule (musical_rules.md): anticipation state changes
        # at most once per 4-bar block (64 steps). Exception: bars 13-16 of the
        # final phrase (musical_step ≥ 192 with phrases_until_drop=0) may change
        # per step — this is the "maximum tension" zone.
        _STEPS_PER_4BARS = 64
        is_final_tension = (phrases_until_drop == 0
                            and frame.musical_step >= 192)
        if is_final_tension:
            ant_step = frame.musical_step   # per-step resolution in final 4 bars
        else:
            # Quantise to 4-bar block boundary — pattern changes land every 4 bars
            block_start  = (frame.musical_step // _STEPS_PER_4BARS) * _STEPS_PER_4BARS
            ant_step     = block_start
        ant = (
            compute_anticipation(
                ant_step, frame.step_in_bar,
                phrases_until_drop, dims.stability, heat,
                signature_rhythm.base_pattern_seed if signature_rhythm else 0,
            )
            if dims is not None else None
        )
        # Merge base dims with arc offsets
        frame_dims = _apply_arc(dims, arc) if dims is not None else None
        result = resolver.resolve(frame, intents_for_frame(
            frame, context, frame_dims, signature_rhythm, arc, ant,
        ))
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


def _apply_arc(dims: Dimensions, arc: ArcDimensions) -> Dimensions:
    """Merge base dims with per-frame arc offsets."""
    return Dimensions(
        stability = dims.stability,
        pressure  = dims.pressure,
        sparsity  = min(1.0, dims.sparsity + arc.sparsity_offset),
        release   = arc.emphasis,
        emphasis  = arc.emphasis,
    )


def intents_for_frame(
    frame: StructureFrame,
    context: Optional[PhraseContext] = None,
    dims: Optional[Dimensions] = None,
    sr: Optional[SignatureRhythm] = None,
    arc: Optional[ArcDimensions] = None,
    ant: Optional[AnticipationState] = None,
) -> tuple[Intent, ...]:
    intents: list[Intent] = [
        *_kick_stream.intents_for_frame(frame, context, dims),
        *_snare_stream.intents_for_frame(frame, context, dims, sr=sr, ant=ant),
        *_hat_stream.intents_for_frame(frame, context, dims, ant=ant),
    ]
    # Ghost 32nd note hats removed: hard dance is mechanically quantized.
    # Ghost notes create off-grid flutter that conflicts with the genre feel.
    # Snare ghost notes (via snare.py dissolution fills) are kept — different character.
    # Re-enable here if wanted: _ghost_stream.intents_for_frame(frame, context, dims, sr)
    if context is not None and dims is not None and sr is not None:
        # ── Per-voice sparsity gates (positional instrumentation floor) ──────
        # Removal order: call/response → hook → (bass and kick never removed)
        sp = dims.sparsity

        # ── Hook window rule (musical_rules.md) ─────────────────────────────
        # Hook fires only in bars 0–1 (phrase statement) and sub-phrase
        # boundaries (bars 4, 12 = hold start, release start).
        # Hook and call/response are MUTUALLY EXCLUSIVE within a bar.
        bar_0idx  = frame.bar_index - 1        # 0-indexed bar within phrase
        _HOOK_BARS = frozenset({0, 1, 4, 12})  # sub-phrase layout: build/hold/release
        is_hook_bar = bar_0idx in _HOOK_BARS

        hook_active          = sp < 0.50 and is_hook_bar
        call_response_active = sp < 0.30 and not is_hook_bar   # mutually exclusive

        intents.extend(_bass_stream.intents_for_frame(frame, context, dims, sr))

        # Sub bass: voice handles its own sparsity gate internally (0.65 threshold)
        intents.extend(_sub_stream.intents_for_frame(frame, context, dims, sr))

        if hook_active:
            intents.extend(_hook_stream.intents_for_frame(frame, context, dims, sr))

        # Calls and responses: sparsity gate + anticipation gate + hook exclusion
        if call_response_active:
            call_allowed     = ant.call_allowed     if ant else True
            response_allowed = ant.response_allowed if ant else True
            if call_allowed:
                call_intents = _call_stream.intents_for_frame(frame, context, dims, sr)
                if call_intents:
                    _response_stream.record_call(frame.bar_index)
                intents.extend(call_intents)
            if response_allowed:
                intents.extend(_response_stream.intents_for_frame(frame, context, dims, sr))

    # ── Drone voices (sustained, Ableton-processed) ─────────────────────────
    if context is not None and dims is not None and sr is not None:
        intents.extend(_drone_spacey.intents_for_frame(frame, context, dims, sr, ant))
        intents.extend(_drone_rumble.intents_for_frame(frame, context, dims, sr, ant))
        intents.extend(_drone_tension.intents_for_frame(frame, context, dims, sr, ant))

    return tuple(intents)


def _resolved_to_midi_event(event, frame: StructureFrame) -> MIDIEvent:
    intent       = event.origin_intent
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


def bank_step_to_time(step) -> str:
    """Convert a bank step to "bar.beat.tick" notation.

    Accepts integer steps (1/16th notes) or half-steps (0.5 increment = 1/32nd note).
    With TICKS_PER_BEAT=24 and BEATS_PER_BAR=4: 1 step = 6 ticks, 1 half-step = 3 ticks.
    """
    half     = (step % 1) >= 0.5
    int_step = int(step)
    if not 0 <= int_step < BANK_STEPS:
        raise ValueError(f"bank step out of range: {step}")
    bar         = int_step // 16 + 1
    step_in_bar = int_step % 16
    beat        = step_in_bar // 4 + 1
    tick        = (step_in_bar % 4) * 6 + (3 if half else 0)
    return f"{bar}.{beat}.{tick}"
