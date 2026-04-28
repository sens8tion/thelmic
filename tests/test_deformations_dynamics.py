from thelmic.bank_generator import Bank, MIDIEvent, Phrase
from thelmic.behaviour_field import BehaviourField
from thelmic.deformations_dynamics import apply_behaviour_dynamics


def _behaviour(ghost_velocity: float, anchor_velocity: float) -> BehaviourField:
    return BehaviourField(
        ghost_intensity=0.0,
        ghost_clustering=0.0,
        anchor_drop_prob=0.0,
        filter_target=0.0,
        gate_tightness=0.0,
        energy_level=0.0,
        accent_strength=0.0,
        ghost_velocity=ghost_velocity,
        anchor_velocity=anchor_velocity,
    )


def _event(layer: str, role: str, velocity: int, deformation: dict[str, float] | None = None) -> MIDIEvent:
    return MIDIEvent(
        time="1.1.0",
        note=38,
        velocity=velocity,
        duration=0.05,
        layer=layer,
        role=role,
        emphasis=0.8,
        openness=1.0,
        expected_weight=0.9,
        should_resolve=False,
        deformation=deformation or {},
    )


def _bank(events: list[MIDIEvent]) -> Bank:
    return Bank(bank_index=0, phrases=[Phrase(phrase_index=0, events=events)])


def test_scales_ghost_and_anchor_velocity_from_behaviour():
    ghost = _event("snare", "ghost", 50)
    anchor = _event("snare", "anchor", 100)
    bank = _bank([ghost, anchor])

    apply_behaviour_dynamics(bank, _behaviour(ghost_velocity=0.5, anchor_velocity=0.9))

    assert ghost.velocity == 25
    assert anchor.velocity == 90


def test_ghost_injected_event_uses_ghost_velocity_even_if_role_is_anchor():
    event = _event("kick", "anchor", 100, deformation={"ghost_inject": 1.0})
    bank = _bank([event])

    apply_behaviour_dynamics(bank, _behaviour(ghost_velocity=0.4, anchor_velocity=1.0))

    assert event.velocity == 40


def test_inactive_event_is_not_rescaled():
    event = _event("snare", "anchor", 0)
    event.active = False
    bank = _bank([event])

    apply_behaviour_dynamics(bank, _behaviour(ghost_velocity=0.7, anchor_velocity=1.0))

    assert event.velocity == 0


def test_velocity_is_clamped_to_midi_range():
    event = _event("snare", "anchor", 127)
    bank = _bank([event])

    apply_behaviour_dynamics(bank, _behaviour(ghost_velocity=1.0, anchor_velocity=2.0))

    assert event.velocity == 127


def test_effective_ghost_velocity_stays_below_anchor_velocity():
    ghost = _event("snare", "ghost", 100)
    anchor = _event("snare", "anchor", 100)
    bank = _bank([ghost, anchor])

    apply_behaviour_dynamics(bank, _behaviour(ghost_velocity=0.7, anchor_velocity=0.6))

    assert ghost.velocity < anchor.velocity
