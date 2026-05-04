"""StaticDrone — no climax, no impacts, only continuous textural variation.

Eliane Radigue, La Monte Young, ambient drone metal, Sunn O))) at certain
moments, Tim Hecker's slower work, etc.

Sections describe textural states ('warming', 'shimmering', 'darkening')
not narrative roles. Transitions are always slow blends. There is no
anticipation in the build-drop sense — only gradual evolution.
"""
from __future__ import annotations
from .base import Grammar, Section, TransitionSpec, AnticipationSpec


class StaticDrone:
    name = "static_drone"
    section_palette = [
        "ground",       # establishing the drone
        "warming",      # gentle harmonic sweetening
        "darkening",    # introducing dissonance
        "shimmering",   # high partials swelling
        "thickening",   # added layers
        "thinning",     # removed layers
        "phasing",      # interference between layers
        "stillness",    # held without change
        "dissolution",  # gradual disappearance
    ]

    def transition_between(self, prev: Section, nxt: Section) -> TransitionSpec:
        # Always slow blend; no cuts in drone music
        crossfade_beats = 8.0
        # Special case: dissolution → none (silence) gets a longer fade
        if nxt.role == "dissolution":
            crossfade_beats = 32.0
        return TransitionSpec(type="fade", pre_window_beats=crossfade_beats,
                                post_window_beats=crossfade_beats)

    def anticipation_for(self, section: Section,
                          previous=None) -> AnticipationSpec:
        # Drone music does not anticipate. There is no impact to set up.
        # If a section role implies textural intensification (e.g.
        # 'thickening' or 'shimmering'), describe a gradual swell.
        if section.role in ("thickening", "shimmering"):
            return AnticipationSpec(
                enabled=True,
                pattern="continuous_swell",
                duration_beats=section.duration_bars * 4,
                intensity_curve="log",
                extras={"layered_entry": True, "no_impact": True},
            )
        return AnticipationSpec(enabled=False)
