"""Jungle voices - the JUNGLE archetype's rhythm section.

Rules: musical_rules.md, "Jungle - measured rules".

The break here is the spine alone, played straight from the archetype table:
kick on 1 and the "and" of 3, snares on 2 and 4, hats where the table has
them. Unlike the other archetypes' drums it has no drop-prep bar, no
anticipation kick and no phrase-start accent: the spine is in every bar.
"""

from __future__ import annotations

from thelmic.archetypes import PATTERNS, RhythmicArchetype
from thelmic.bank_generator import CLOSED_HAT_NOTE, KICK_NOTE, SNARE_NOTE
from thelmic.stream_engine import Intent, StructureFrame
from thelmic.voices import make_intent

_PATTERN = PATTERNS[RhythmicArchetype.JUNGLE]

# Seconds at 174 BPM, as everywhere in the voices.
_KICK_DUR  = 0.08
_SNARE_DUR = 0.06
_HAT_DUR   = 0.035

# The spine is prominent (jungle_scene_rules.md): the downbeat kick leads,
# the "and" of 3 sits a little under it.
_KICK_VELOCITY  = {0: 122, 10: 112}
_SNARE_VELOCITY = 118


class JungleBreakStream:
    """Kick, snare and hat for one frame of a JUNGLE phrase."""

    def intents_for_frame(self, frame: StructureFrame) -> tuple[Intent, ...]:
        step = frame.step_in_bar
        intents: list[Intent] = []
        if step in _PATTERN.kick_steps:
            intents.append(make_intent(frame, "kick", "timing_anchor", _KICK_VELOCITY[step],
                                       _KICK_DUR, "jungle_spine", KICK_NOTE, 10))
        if step in _PATTERN.snare_steps:
            intents.append(make_intent(frame, "snare", "backbeat", _SNARE_VELOCITY,
                                       _SNARE_DUR, "jungle_spine", SNARE_NOTE, 8))
        if step in _PATTERN.closed_hat_steps:
            intents.append(make_intent(frame, "hat", "subdivision", 84 if step % 4 == 0 else 76,
                                       _HAT_DUR, "jungle_carrier", CLOSED_HAT_NOTE, 5))
        return tuple(intents)
