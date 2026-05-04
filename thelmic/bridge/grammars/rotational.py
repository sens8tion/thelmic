"""Rotational — variations cycling, no global arc.

The form of much modal jazz (head / solos / head), South-Indian
classical (rāga elaboration around fixed structure), minimalist process
music with periodic cell rotation.
"""
from __future__ import annotations
from .base import Grammar, Section, TransitionSpec, AnticipationSpec


class Rotational:
    name = "rotational"
    section_palette = [
        "head",         # the fixed/known material
        "variation",    # one rotation through it (with elaboration)
        "interlude",    # bridge between rotations
        "outhead",      # closing return to the head
    ]

    def transition_between(self, prev: Section, nxt: Section) -> TransitionSpec:
        # Rotation is continuous; transitions are short or absent
        return TransitionSpec(type="cut")

    def anticipation_for(self, section: Section,
                          previous=None) -> AnticipationSpec:
        # No anticipation — the form has no climax
        return AnticipationSpec(enabled=False)
