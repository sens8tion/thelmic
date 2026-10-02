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
"""

from __future__ import annotations

from thelmic import jungle
from thelmic.bank_generator import CLOSED_HAT_NOTE, KICK_NOTE, OPEN_HAT_NOTE, SNARE_NOTE
from thelmic.landscape_map import SignatureRhythm
from thelmic.stream_engine import STEPS_PER_BAR, Intent, StructureFrame
from thelmic.voices import make_intent

# Seconds at 174 BPM, as everywhere in the voices.
_KICK_DUR     = 0.08
_SNARE_DUR    = 0.06
_GHOST_DUR    = 0.03
_HAT_DUR      = 0.035
_OPEN_HAT_DUR = 0.12


def global_bar(frame: StructureFrame) -> int:
    """The bar's number from the start of the piece, across banks."""
    return frame.global_step // STEPS_PER_BAR


class JungleBreakStream:
    """Kick, snare, ghost snare and hat for one frame of a JUNGLE phrase."""

    def intents_for_frame(self, frame: StructureFrame, sr: SignatureRhythm) -> tuple[Intent, ...]:
        deal = jungle.deal_bar(sr.base_pattern_seed, global_bar(frame))
        return tuple(
            _intent(frame, hit) for hit in deal.hits if hit.slot == frame.step_in_bar
        )


def _intent(frame: StructureFrame, hit: jungle.Hit) -> Intent:
    reason = f"jungle_{hit.kind}"
    if hit.lane == "low":
        return make_intent(frame, "kick", "timing_anchor", hit.velocity, _KICK_DUR,
                           reason, KICK_NOTE, 10 if hit.kind == "spine" else 6)
    if hit.lane == "mid":
        if hit.kind == "between":
            return make_intent(frame, "ghost_snare", "ghost", hit.velocity, _GHOST_DUR,
                               "jungle_ghost", SNARE_NOTE, 3)
        role = "backbeat" if hit.kind == "spine" else "fill" if hit.kind == "fill" else "signature"
        return make_intent(frame, "snare", role, hit.velocity, _SNARE_DUR,
                           reason, SNARE_NOTE, 8 if hit.kind == "spine" else 6)
    if hit.kind == "signature":
        return make_intent(frame, "open_hat", "signature", hit.velocity, _OPEN_HAT_DUR,
                           reason, OPEN_HAT_NOTE, 5)
    return make_intent(frame, "hat", "subdivision", hit.velocity, _HAT_DUR,
                       reason, CLOSED_HAT_NOTE, 5)
