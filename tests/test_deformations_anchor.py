from thelmic.bank_generator import Bank, MIDIEvent, Phrase
from thelmic.behaviour_field import BehaviourField
from thelmic.deformations_anchor import apply_anchor_withholding, is_anchor_event


def _event(time: str, layer: str = "snare", role: str = "anchor") -> MIDIEvent:
    return MIDIEvent(
        time=time,
        note=38,
        velocity=100,
        duration=0.05,
        layer=layer,
        role=role,
        emphasis=0.8,
        openness=1.0,
        expected_weight=0.9,
        should_resolve=False,
    )


def _bank(events: list[MIDIEvent]) -> Bank:
    return Bank(bank_index=0, phrases=[Phrase(phrase_index=0, events=events)])


def _behaviour(anchor_drop_prob: float) -> BehaviourField:
    return BehaviourField(
        ghost_intensity=0.0,
        ghost_clustering=0.0,
        anchor_drop_prob=anchor_drop_prob,
        filter_target=0.0,
        gate_tightness=0.0,
        energy_level=0.0,
        accent_strength=0.0,
        ghost_velocity=0.3,
        anchor_velocity=0.6,
    )


def test_is_anchor_event_uses_role():
    assert is_anchor_event(_event("1.2.0"))
    assert not is_anchor_event(_event("1.2.6", role="ghost"))


def test_low_probability_does_not_drop(monkeypatch):
    bank = _bank([_event("1.2.0"), _event("1.4.0")])
    monkeypatch.setattr("thelmic.deformations_anchor.random.random", lambda: 0.0)

    runtime = apply_anchor_withholding(bank, _behaviour(0.09))

    assert runtime == {"anchors_dropped_per_bar": {}}
    assert all(event.active for event in bank.all_events())


def test_drops_snare_anchor_and_records_runtime(monkeypatch):
    events = [_event("1.1.0", "kick"), _event("1.2.0", "snare"), _event("1.4.0", "snare")]
    bank = _bank(events)
    monkeypatch.setattr("thelmic.deformations_anchor.random.random", lambda: 0.0)

    runtime = apply_anchor_withholding(bank, _behaviour(1.0))

    assert runtime["anchors_dropped_per_bar"] == {1: 2}
    assert [event.active for event in events] == [True, False, False]
    assert [event.velocity for event in events] == [100, 0, 0]


def test_never_drops_all_anchors_in_bar(monkeypatch):
    events = [_event("1.2.0", "snare"), _event("1.4.0", "snare")]
    bank = _bank(events)
    monkeypatch.setattr("thelmic.deformations_anchor.random.random", lambda: 0.0)

    apply_anchor_withholding(bank, _behaviour(1.0))

    assert sum(1 for event in events if event.active) == 1


def test_late_transition_progress_increases_probability(monkeypatch):
    events = [_event("1.1.0", "kick"), _event("1.2.0", "snare")]
    bank = _bank(events)
    monkeypatch.setattr("thelmic.deformations_anchor.random.random", lambda: 0.2)

    runtime = apply_anchor_withholding(bank, _behaviour(0.1), transition_progress=0.8)

    assert runtime["anchors_dropped_per_bar"] == {1: 1}
