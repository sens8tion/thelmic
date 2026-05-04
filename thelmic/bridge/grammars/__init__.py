"""Narrative grammars — the SHAPE a piece of music has over time.

`BuildDropRelease` is the dance-music grammar (build → impact → release).
`StaticDrone` has no climax, just textural variation.
`IsoRhythm` is a repeating rhythmic cell with parameter drift.
`ThroughComposed` has no return, no recurring sections.
`Rotational` cycles through variations without a global arc.

Aesthetic packs declare which grammar they use; the timeline engine
consults the grammar for transition specs and anticipation patterns.
"""
from .base                  import (Grammar, Section, Fragment,
                                     TransitionSpec, AnticipationSpec)
from .build_drop_release    import BuildDropRelease
from .static_drone          import StaticDrone
from .iso_rhythm            import IsoRhythm
from .through_composed      import ThroughComposed
from .rotational            import Rotational

__all__ = [
    "Grammar", "Section", "Fragment", "TransitionSpec", "AnticipationSpec",
    "BuildDropRelease", "StaticDrone", "IsoRhythm", "ThroughComposed", "Rotational",
]
