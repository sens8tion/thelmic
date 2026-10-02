"""Jungle voices - the JUNGLE archetype's rhythm section.

Rules: musical_rules.md, "Jungle - Measured Rules".

The break is dealt, not read from a table: thelmic/jungle.py deals each bar
from the section's distribution and this module turns the deal into intents.
Unlike the other archetypes' drums the break has no drop-prep bar, no
anticipation kick and no phrase-start accent, and sparsity does not thin it:
the spine is in every bar.

Lanes and layers:
  low   kick
  mid   snare (spine, signature and fill hits), ghost_snare (the in-between hits)
  high  hat (the 16th carrier), open_hat (a signature accent)

The sub plays a riff written once and repeated (layer "sub"); the hook plays
short shapes in the low mids in about 3 bars of every 8 (layer "hook").

Drops are subtraction (J9). In the phrase before a drop nothing is withheld and
nothing builds: the break runs on at full density and the sub is taken out for
the last bar and a quarter. In the drop phrase nothing bursts: the first bar is
thinner than a groove bar and the sub holds one note on the fundamental.
"""

from __future__ import annotations

from dataclasses import replace

from thelmic import jungle
from thelmic.bank_generator import (
    BARS_PER_PHRASE, CLOSED_HAT_NOTE, KICK_NOTE, OPEN_HAT_NOTE, PHRASES_PER_BANK, SNARE_NOTE,
)
from thelmic.dimensions import Dimensions
from thelmic.landscape_map import SignatureRhythm
from thelmic.stream_engine import STEPS_PER_BAR, Intent, StructureFrame
from thelmic.voices import make_intent

# Seconds at 174 BPM, as everywhere in the voices.
_KICK_DUR     = 0.08
_SNARE_DUR    = 0.06
_GHOST_DUR    = 0.03
_HAT_DUR      = 0.035
_OPEN_HAT_DUR = 0.12
_BEAT          = 60.0 / 174.0
_SIXTEENTH     = _BEAT / 4.0

# The sub leaves at the sparsity the other archetypes' sub leaves at; the hook
# leaves before it (removal order: hook, then sub; the break never).
SUB_SPARSITY_GATE  = 0.65
HOOK_SPARSITY_GATE = 0.50


_BANK_BARS  = BARS_PER_PHRASE * PHRASES_PER_BANK
_BANK_STEPS = _BANK_BARS * STEPS_PER_BAR


def global_bar(frame: StructureFrame) -> int:
    """The bar's number from the start of the piece, across banks."""
    return frame.global_step // STEPS_PER_BAR


def before_drop(is_drop_phrase: bool, phrases_until_drop: int) -> bool:
    """This bank is the one a drop follows."""
    return phrases_until_drop == 0 and not is_drop_phrase


class JungleBreakStream:
    """Kick, snare, ghost snare and hat for one frame of a JUNGLE phrase."""

    def intents_for_frame(
        self, frame: StructureFrame, dims: Dimensions, sr: SignatureRhythm,
        is_drop_phrase: bool = False, phrases_until_drop: int = 8,
    ) -> tuple[Intent, ...]:
        seed, bar = sr.base_pattern_seed, global_bar(frame)
        under_hook = hook_sounds(dims) and jungle.has_hook(seed, bar)
        if is_drop_phrase and frame.bar_index == 1:
            state = "drop"
        elif dims.sparsity >= SUB_SPARSITY_GATE:
            state = "breakdown"
        else:
            state = "groove"
        # The bar before a drop: by default neither a roll nor a gap.
        last = before_drop(is_drop_phrase, phrases_until_drop) and frame.bar_index == _BANK_BARS
        roll = last and jungle.drop_has_roll(seed, bar + 1)
        gap = last and jungle.drop_has_gap(seed, bar + 1)
        deal = jungle.deal_bar(seed, bar, under_hook, state, roll, gap)
        return tuple(
            _intent(frame, hit) for hit in deal.hits if hit.slot == frame.step_in_bar
        )


def hook_sounds(dims: Dimensions) -> bool:
    return dims.sparsity < HOOK_SPARSITY_GATE


def fundamental(sr: SignatureRhythm) -> int:
    """The sub's lowest note: an octave under the bass root, as for every archetype."""
    return max(0, min(127, sr.root_note - 12))


class JungleSubStream:
    """The sub: a riff of struck notes above the fundamental, falling to it."""

    def intents_for_frame(
        self, frame: StructureFrame, dims: Dimensions, sr: SignatureRhythm,
        is_drop_phrase: bool = False, phrases_until_drop: int = 8,
    ) -> tuple[Intent, ...]:
        if dims.sparsity >= SUB_SPARSITY_GATE:
            return ()
        if is_drop_phrase and frame.bar_index == 1:
            # The drop is the bass: one held note on the fundamental, the riff from bar 2.
            if frame.step_in_bar != 0:
                return ()
            return (make_intent(frame, "sub", "sub_drop", 122,
                                round(jungle.DROP_NOTE_BEATS * _BEAT, 3), "jungle_drop",
                                fundamental(sr), 9),)
        # Before a drop the low end is out for the last bar and a quarter.
        out_from = _BANK_STEPS
        if before_drop(is_drop_phrase, phrases_until_drop):
            out_from = _BANK_STEPS - jungle.LOW_END_OUT_STEPS
        if frame.musical_step >= out_from:
            return ()
        room = (out_from - frame.musical_step) / 4.0 if out_from < _BANK_STEPS else jungle.SUB_MAX_BEATS
        return tuple(
            make_intent(frame, "sub", f"sub_{note.kind}", note.velocity,
                        round(min(note.beats, room) * _BEAT, 3), f"jungle_{note.kind}",
                        fundamental(sr) + note.offset, 8)
            for note in jungle.sub_bar(sr.base_pattern_seed, global_bar(frame))
            if note.slot == frame.step_in_bar
        )


class JungleHookStream:
    """Hooks: fragments of a beat or so, 233-392 Hz, in about 3 bars of every 8."""

    def intents_for_frame(
        self, frame: StructureFrame, dims: Dimensions, sr: SignatureRhythm,
    ) -> tuple[Intent, ...]:
        if not hook_sounds(dims):
            return ()
        intents = []
        for n, note in enumerate(jungle.hook_bar(sr.base_pattern_seed, global_bar(frame), sr.root_note)):
            if note.slot != frame.step_in_bar:
                continue
            intent = make_intent(frame, "hook", "hook", note.velocity,
                                 round(note.steps * _SIXTEENTH - 0.01, 3), "jungle_hook", note.note, 7)
            intents.append(_distinct(intent, n))
        return tuple(intents)


def _distinct(intent: Intent, n: int) -> Intent:
    """A dyad is two intents on one step; each needs its own id."""
    return replace(intent, intent_id=f"{intent.intent_id}:{n}")


def _intent(frame: StructureFrame, hit: jungle.Hit) -> Intent:
    reason = f"jungle_{hit.kind}"
    if hit.lane == "low":
        return make_intent(frame, "kick", "timing_anchor", hit.velocity, _KICK_DUR,
                           reason, KICK_NOTE, 10 if hit.kind == "spine" else 6)
    if hit.lane == "mid":
        if hit.kind == "between":
            return make_intent(frame, "ghost_snare", "ghost", hit.velocity, _GHOST_DUR,
                               "jungle_ghost", SNARE_NOTE, 3)
        role = "backbeat" if hit.kind == "spine" else "signature" if hit.kind == "signature" else "fill"
        return make_intent(frame, "snare", role, hit.velocity, _SNARE_DUR,
                           reason, SNARE_NOTE, 8 if hit.kind == "spine" else 6)
    if hit.kind == "signature":
        return make_intent(frame, "open_hat", "signature", hit.velocity, _OPEN_HAT_DUR,
                           reason, OPEN_HAT_NOTE, 5)
    return make_intent(frame, "hat", "subdivision", hit.velocity, _HAT_DUR,
                       reason, CLOSED_HAT_NOTE, 5)
