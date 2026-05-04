"""BuildDropRelease — the dance-music grammar (intro → build → drop → release).

The form most current aesthetic packs (dnb_jungle, idm_glitch with caveats,
gabber, dubstep, ...) use. Drops are climactic; anticipation precedes drops;
descents follow.
"""
from __future__ import annotations
from .base import Grammar, Section, TransitionSpec, AnticipationSpec


class BuildDropRelease:
    name = "build_drop_release"
    section_palette = [
        "intro", "stirring", "build", "riser", "anticipation",
        "drop", "fake_drop", "breakdown", "pivot", "rebuild",
        "second_drop", "chaos_peak", "sustained_peak", "descent",
        "reprise", "outro",
        # genre-flavored sub-roles (caller may use any; these are recognised)
        "footwork", "jungle_return",
    ]

    DROP_ROLES = {"drop", "second_drop", "chaos_peak"}
    ANTICIPATION_ROLES = {"riser", "anticipation", "rebuild"}
    QUIET_ROLES = {"intro", "breakdown", "outro"}

    def transition_between(self, prev: Section, nxt: Section) -> TransitionSpec:
        # Drop entries: hard slam preceded by short silence
        if nxt.role in self.DROP_ROLES:
            return TransitionSpec(type="drop", silence_beats=4.0,
                                    pre_window_beats=4.0)
        # Outro: long fade out / staggered exits
        if nxt.role == "outro":
            return TransitionSpec(type="fade", post_window_beats=8.0)
        # Reprise / quiet → stirring: gentle re-entry
        if nxt.role in self.QUIET_ROLES:
            return TransitionSpec(type="fade", pre_window_beats=2.0)
        return TransitionSpec(type="cut")

    def anticipation_for(self, section: Section,
                          previous=None) -> AnticipationSpec:
        if section.role in self.DROP_ROLES:
            return AnticipationSpec(
                enabled=True,
                pattern="tightening_hats_then_silence_then_impact",
                duration_beats=16.0,
                intensity_curve="exp",
                extras={"tighten_steps": ["16th", "32nd", "64th"],
                        "void_beats": 4,
                        "sacred_impact": True},
            )
        if section.role in self.ANTICIPATION_ROLES:
            return AnticipationSpec(
                enabled=True,
                pattern="filter_open_and_drum_rolls",
                duration_beats=16.0,
                intensity_curve="log",
            )
        return AnticipationSpec(enabled=False)
