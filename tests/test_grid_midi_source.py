from thelmic.bank_generator import Bank, MIDIEvent, Phrase
from thelmic.midi_out import LAYER_CHANNELS, is_grid_midi_event
from thelmic import server
from thelmic.server import _bank_events_list


def _event(
    layer: str = "hook",
    velocity: int = 80,
    active: bool = True,
) -> MIDIEvent:
    return MIDIEvent(
        time="1.1.0",
        note=60,
        velocity=velocity,
        duration=0.08,
        layer=layer,
        role=layer,
        emphasis=0.8,
        openness=1.0,
        expected_weight=0.8,
        should_resolve=False,
        active=active,
    )


def _bank(*events: MIDIEvent) -> Bank:
    return Bank(bank_index=0, phrases=[Phrase(phrase_index=0, events=list(events))])


def test_grid_midi_event_predicate_is_final_note_source():
    audible = _event("hook", velocity=72)
    silent = _event("hook", velocity=0)
    inactive = _event("hat", active=False)
    survivor = _event("survivor", velocity=80)
    unknown = _event("unknown", velocity=80)

    assert is_grid_midi_event(audible) is True
    assert is_grid_midi_event(silent) is False
    assert is_grid_midi_event(inactive) is False
    assert is_grid_midi_event(survivor) is False
    assert is_grid_midi_event(unknown) is False


def test_bank_event_grid_payload_marks_exact_midi_sendability():
    bank = _bank(
        _event("hook", velocity=72),
        _event("hook", velocity=0),
        _event("hat", active=False),
        _event("survivor", velocity=80),
    )

    payload = _bank_events_list(bank)

    assert [item["midi_send"] for item in payload] == [True, False, False]
    assert all(item["layer"] != "survivor" for item in payload)
    assert payload[0]["midi_channel"] == LAYER_CHANNELS["hook"]
    assert payload[0]["note"] == 60
    assert payload[0]["duration"] == 0.08


def test_live_state_carries_stable_ui_identity_fields():
    if server._engine is None or server._generator is None:
        server._init_engine()

    state = server._live_state_dict()

    assert "midi_port" in state
    assert "midi_cc_port" in state
    assert "archetype" in state
    assert "selected_archetype" in state
    assert "active_archetype" in state
    assert "pending_archetype" in state
    assert "survivor" not in state["midi_layer_channels"]
