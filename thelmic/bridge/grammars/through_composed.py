"""ThroughComposed — narrative without return.

Each section is new. No reprises. Common in art-song, programmatic
classical, modern composition (Górecki, Pärt, Adams' minimalism).
"""
from __future__ import annotations
from .base import Grammar, Section, TransitionSpec, AnticipationSpec


class ThroughComposed:
    name = "through_composed"
    section_palette = [
        "exposition", "development", "intensification",
        "climax", "denouement", "coda",
    ]

    def transition_between(self, prev: Section, nxt: Section) -> TransitionSpec:
        if nxt.role == "climax":
            return TransitionSpec(type="cut", pre_window_beats=4.0)
        if nxt.role == "coda":
            return TransitionSpec(type="fade", pre_window_beats=8.0)
        return TransitionSpec(type="cut")

    def anticipation_for(self, section: Section,
                          previous=None) -> AnticipationSpec:
        if section.role == "climax":
            return AnticipationSpec(
                enabled=True,
                pattern="harmonic_tension_buildup",
                duration_beats=32.0,
                intensity_curve="exp",
            )
        return AnticipationSpec(enabled=False)
