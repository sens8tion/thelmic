from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .force_engine import ForceState, _clamp
from .transition_engine import Transition


@dataclass
class BehaviourField:
    ghost_intensity: float
    ghost_clustering: float
    anchor_drop_prob: float
    filter_target: float
    gate_tightness: float
    energy_level: float
    accent_strength: float
    ghost_velocity: float
    anchor_velocity: float
    anticipation: float = 0.0
    instability: float = 0.0
    release_pressure: float = 0.0


def compute_behaviour_field(
    force: ForceState,
    transition: Optional[Transition],
) -> BehaviourField:
    anticipation = force.anticipation
    instability = force.instability
    release = force.release_pressure

    progress = transition.progress if transition else 0.0
    velocity = transition.velocity if transition else 0.0

    ghost_intensity = (anticipation * 0.6) + (instability * 0.4)
    ghost_clustering = min(1.0, anticipation * (0.5 + velocity))

    anchor_drop_prob = release * progress

    filter_target = (1.0 - anticipation) * 0.7 + release * 0.3

    gate_tightness = anticipation * 0.8 + instability * 0.2
    energy_level = (anticipation * 0.6) + (instability * 0.4)
    accent_strength = release
    ghost_velocity = 0.3 + (energy_level * 0.4)
    anchor_velocity = 0.6 + (release * 0.4)

    return BehaviourField(
        ghost_intensity=_clamp(ghost_intensity),
        ghost_clustering=_clamp(ghost_clustering),
        anchor_drop_prob=_clamp(anchor_drop_prob),
        filter_target=_clamp(filter_target),
        gate_tightness=_clamp(gate_tightness),
        energy_level=_clamp(energy_level),
        accent_strength=_clamp(accent_strength),
        ghost_velocity=_clamp(ghost_velocity),
        anchor_velocity=_clamp(anchor_velocity),
        anticipation=_clamp(anticipation),
        instability=_clamp(instability),
        release_pressure=_clamp(release),
    )
