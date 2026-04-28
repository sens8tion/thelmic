import pytest

from thelmic.behaviour_field import compute_behaviour_field
from thelmic.force_engine import ForceState
from thelmic.transition_engine import Transition


def test_compute_behaviour_field_uses_force_and_transition():
    force = ForceState(anticipation=0.5, instability=0.25, release_pressure=0.8)
    transition = Transition(
        start_position=0.0,
        target_position=1.0,
        current_position=0.5,
        duration_bars=4.0,
        elapsed_bars=2.0,
    )

    behaviour = compute_behaviour_field(force, transition)

    assert behaviour.ghost_intensity == pytest.approx(0.4)
    assert behaviour.ghost_clustering == pytest.approx(0.375)
    assert behaviour.anchor_drop_prob == pytest.approx(0.4)
    assert behaviour.filter_target == pytest.approx(0.59)
    assert behaviour.gate_tightness == pytest.approx(0.45)
    assert behaviour.energy_level == pytest.approx(0.4)
    assert behaviour.accent_strength == pytest.approx(0.8)
    assert behaviour.ghost_velocity == pytest.approx(0.46)
    assert behaviour.anchor_velocity == pytest.approx(0.92)
    assert behaviour.anticipation == pytest.approx(0.5)
    assert behaviour.instability == pytest.approx(0.25)
    assert behaviour.release_pressure == pytest.approx(0.8)


def test_compute_behaviour_field_defaults_transition_values_to_zero():
    force = ForceState(anticipation=0.5, instability=0.25, release_pressure=0.8)

    behaviour = compute_behaviour_field(force, None)

    assert behaviour.ghost_clustering == pytest.approx(0.25)
    assert behaviour.anchor_drop_prob == pytest.approx(0.0)
