import pytest
from thelmic.bank_generator import MIDIEvent
from thelmic.behaviour_field import BehaviourField
from thelmic.stabs import (
    generate_stabs, generate_stabs_from_calls, collect_call_events,
    _snap_to_grid_step, _is_grid_aligned, _response_delay_ticks,
    TICKS_PER_STEP,
)


def _behaviour(
    energy_level: float = 0.5,
    ghost_intensity: float = 1.0,
    anticipation: float = 0.5,
    instability: float = 1.0,
    release_pressure: float = 0.0,
) -> BehaviourField:
    return BehaviourField(
        ghost_intensity=ghost_intensity,
        ghost_clustering=0.0,
        anchor_drop_prob=0.0,
        filter_target=0.0,
        gate_tightness=0.0,
        energy_level=energy_level,
        accent_strength=0.0,
        ghost_velocity=0.4,
        anchor_velocity=0.8,
        anticipation=anticipation,
        instability=instability,
        release_pressure=release_pressure,
    )


def _event(role: str = "anchor", velocity: int = 100) -> MIDIEvent:
    return MIDIEvent(
        time="1.2.0",
        note=38,
        velocity=velocity,
        duration=0.05,
        layer="snare",
        role=role,
        emphasis=0.8,
        openness=1.0,
        expected_weight=0.9,
        should_resolve=False,
    )


def test_stab_responds_after_anchor():
    stabs = generate_stabs([_event()], _behaviour(energy_level=0.6))

    assert stabs[0].layer == "stab"
    assert stabs[0].role == "stab"
    assert stabs[0].time == "1.2.12"
    assert stabs[0].note == 60
    assert stabs[0].velocity < 80


def test_stab_uses_sixteenth_response_at_lower_energy():
    event = _event()
    event.time = "2.2.0"
    stabs = generate_stabs([event], _behaviour(energy_level=0.8, anticipation=0.0), landscape_position=0.5)

    assert stabs[0].time in {"2.2.12", "2.2.18", "2.3.0"}


def test_stab_does_not_fire_when_behaviour_gate_misses():
    event = _event()
    event.time = "1.2.0"
    assert generate_stabs([event], _behaviour(energy_level=0.2), landscape_position=0.5) == []


def test_stab_ignores_non_anchor_events():
    assert generate_stabs([_event(role="ghost")], _behaviour()) == []


def test_high_release_suppresses_response():
    event = _event()
    event.time = "1.2.0"
    assert generate_stabs([event], _behaviour(release_pressure=0.9), landscape_position=0.5) == []


def test_dropped_anchor_boosts_response_probability():
    event = _event(velocity=0)
    event.time = "1.1.0"
    event.active = False
    event.deformation["anchor_withholding"] = 1.0

    stabs = generate_stabs([event], _behaviour(instability=0.0, anticipation=0.0), landscape_position=0.5)

    assert stabs[0].layer == "stab"
    assert stabs[0].velocity > 0


def test_limits_stabs_per_bar():
    events = [_event(), _event()]
    events[1].time = "1.4.0"

    stabs = generate_stabs(events, _behaviour())

    assert len(stabs) == 1


def test_oak_stabs_are_predictable_every_other_bar():
    first = _event()
    first.time = "1.2.0"
    second = _event()
    second.time = "2.2.0"

    stabs = generate_stabs([first, second], _behaviour(), landscape_position=0.0)

    assert [event.time for event in stabs] == ["1.2.12"]


def test_nott_stabs_are_phrase_locked_and_lower():
    event = _event()
    event.time = "4.2.0"

    stabs = generate_stabs([event], _behaviour(), landscape_position=1.0)

    assert stabs[0].time == "5.1.12"
    assert stabs[0].note == 48


# ── Grid alignment invariant ─────────────────────────────────────────────────

class TestGridAlignment:

    def _event_at(self, time: str, role: str = "anchor") -> MIDIEvent:
        e = _event(role=role)
        e.time = time
        return e

    def _all_stab_times_grid_aligned(self, events, behaviour, pos) -> bool:
        stabs = generate_stabs(events, behaviour, landscape_position=pos)
        return all(_is_grid_aligned(s.time) for s in stabs)

    def test_snap_to_grid_step_exact(self):
        # Already-aligned times should be unchanged
        assert _snap_to_grid_step("1.1.0")  == "1.1.0"
        assert _snap_to_grid_step("1.1.6")  == "1.1.6"
        assert _snap_to_grid_step("1.1.12") == "1.1.12"
        assert _snap_to_grid_step("1.1.18") == "1.1.18"
        assert _snap_to_grid_step("1.2.0")  == "1.2.0"

    def test_snap_to_grid_step_rounds_off_grid(self):
        # Any off-grid input must produce a grid-aligned output.
        # We don't assert which adjacent step wins (Python banker's rounding
        # means ties go to the even step), only that the result is on-grid.
        for off_tick in [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 13, 14, 15, 16, 17]:
            result = _snap_to_grid_step(f"1.1.{off_tick}")
            assert _is_grid_aligned(result), (
                f"snap of tick={off_tick} gave {result!r}, not grid-aligned"
            )

    def test_is_grid_aligned_multiples_of_six(self):
        for tick in range(0, 25, 6):  # 0, 6, 12, 18, 24
            beat = tick // 24 + 1
            t = tick % 24
            assert _is_grid_aligned(f"1.{beat}.{t}"), f"tick {tick} should be aligned"

    def test_is_grid_aligned_rejects_off_grid(self):
        for off in [1, 2, 3, 4, 5, 7, 8, 9, 10, 11]:
            assert not _is_grid_aligned(f"1.1.{off}"), f"tick {off} should NOT be aligned"

    def test_response_delay_always_multiple_of_six(self):
        # Sweep anticipation across [0, 1] — all results must be step-multiples
        for i in range(11):
            anticipation = i / 10.0
            b = _behaviour(anticipation=anticipation)
            for pos in [0.0, 0.25, 0.5, 0.75, 1.0]:
                delay = _response_delay_ticks(b, pos)
                assert delay % TICKS_PER_STEP == 0, (
                    f"delay={delay} not a step multiple at anticipation={anticipation} pos={pos}"
                )

    @pytest.mark.parametrize("pos", [0.0, 0.16, 0.33, 0.5, 0.67, 0.84, 1.0])
    def test_all_stabs_grid_aligned_across_landscape(self, pos):
        events = [
            self._event_at("1.1.0"),
            self._event_at("1.2.0"),
            self._event_at("1.3.0"),
            self._event_at("2.1.0"),
            self._event_at("3.2.0"),
        ]
        b = _behaviour(energy_level=0.8, anticipation=0.5)
        stabs = generate_stabs(events, b, landscape_position=pos)
        for s in stabs:
            assert _is_grid_aligned(s.time), (
                f"stab at {s.time} is off-grid at landscape_position={pos}"
            )

    @pytest.mark.parametrize("anticipation", [0.1, 0.3, 0.5, 0.7, 0.9])
    def test_all_stabs_grid_aligned_across_anticipation(self, anticipation):
        events = [self._event_at(f"1.{b}.0") for b in range(1, 5)]
        b = _behaviour(energy_level=0.8, anticipation=anticipation)
        stabs = generate_stabs(events, b, landscape_position=0.5)
        for s in stabs:
            assert _is_grid_aligned(s.time), (
                f"stab at {s.time} off-grid at anticipation={anticipation}"
            )
