"""IsoRhythm — a repeating rhythmic cell with parameter drift.

Steve Reich's phasing pieces, African polyrhythmic music in fixed-cell
form, minimalism. The "section" structure isn't narrative — sections
mark phases of the drift / process.
"""
from __future__ import annotations
from .base import Grammar, Section, TransitionSpec, AnticipationSpec


class IsoRhythm:
    name = "iso_rhythm"
    section_palette = [
        "exposition",       # cell stated cleanly
        "drift_in",         # second voice begins to phase
        "deep_phase",       # voices fully out of alignment
        "reconvergence",    # phasing reduces, voices realigning
        "unity",            # back in phase
        "expansion",        # cell augmented
        "contraction",      # cell diminished
        "resolution",       # final statement
    ]

    def transition_between(self, prev: Section, nxt: Section) -> TransitionSpec:
        # Iso-rhythmic music transitions through process, not cuts. The
        # transitions are continuous — voices simply continue.
        return TransitionSpec(type="cut", pre_window_beats=0, post_window_beats=0)

    def anticipation_for(self, section: Section,
                          previous=None) -> AnticipationSpec:
        # The process IS the anticipation in iso-rhythm.
        return AnticipationSpec(enabled=False)
