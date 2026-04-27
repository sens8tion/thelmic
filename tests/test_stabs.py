"""Tests for stab generation — step-index-first architecture.

All stab events must land on valid 16th-note step indices (0..15).
The generation flow is:
  call → (bar, call_step) → candidate steps → selected step → time string

No time-offset arithmetic; no free timing.
"""

import pytest
from thelmic.bank_generator import MIDIEvent
from thelmic.behaviour_field import BehaviourField
from thelmic import stabs as stabs_mod
from thelmic.stabs import (
    generate_stabs,
    generate_stabs_from_calls,
    collect_call_events,
    _step_to_time,
    _time_to_bar_step,
    _is_grid_aligned,
    _candidate_steps,
    TICKS_PER_STEP,
    STEPS_PER_BAR,
    OFFBEAT_STEPS,
    BEAT_STEPS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _event(role: str = "anchor", layer: str = "snare", time: str = "1.2.0",
           velocity: int = 100, emphasis: float = 0.8) -> MIDIEvent:
    return MIDIEvent(
        time=time,
        note=38,
        velocity=velocity,
        duration=0.05,
        layer=layer,
        role=role,
        emphasis=emphasis,
        openness=1.0,
        expected_weight=0.9,
        should_resolve=False,
    )


# ---------------------------------------------------------------------------
# Grid primitives
# ---------------------------------------------------------------------------

class TestGridPrimitives:

    def test_step_to_time_step_0(self):
        assert _step_to_time(1, 0) == "1.1.0"

    def test_step_to_time_step_4(self):
        # step 4 = 4*6 = 24 ticks = beat 2, tick 0
        assert _step_to_time(1, 4) == "1.2.0"

    def test_step_to_time_step_8(self):
        # step 8 = 48 ticks = beat 3, tick 0
        assert _step_to_time(1, 8) == "1.3.0"

    def test_step_to_time_step_2(self):
        # step 2 = 12 ticks = beat 1, tick 12
        assert _step_to_time(1, 2) == "1.1.12"

    def test_step_to_time_step_6(self):
        # step 6 = 36 ticks = beat 2, tick 12
        assert _step_to_time(1, 6) == "1.2.12"

    def test_step_to_time_step_10(self):
        # step 10 = 60 ticks = beat 3, tick 12
        assert _step_to_time(1, 10) == "1.3.12"

    def test_step_to_time_step_14(self):
        # step 14 = 84 ticks = beat 4, tick 12
        assert _step_to_time(1, 14) == "1.4.12"

    def test_step_to_time_roundtrip(self):
        for bar in [1, 2, 5]:
            for step in range(STEPS_PER_BAR):
                time_str = _step_to_time(bar, step)
                parsed_bar, parsed_step = _time_to_bar_step(time_str)
                assert parsed_bar == bar
                assert parsed_step == step

    def test_time_to_bar_step_aligned(self):
        assert _time_to_bar_step("1.1.0")  == (1, 0)
        assert _time_to_bar_step("1.1.6")  == (1, 1)
        assert _time_to_bar_step("1.1.12") == (1, 2)
        assert _time_to_bar_step("1.2.0")  == (1, 4)
        assert _time_to_bar_step("2.1.0")  == (2, 0)

    def test_time_to_bar_step_off_grid(self):
        _, step = _time_to_bar_step("1.1.3")
        assert step == -1
        _, step = _time_to_bar_step("1.1.7")
        assert step == -1

    def test_is_grid_aligned_valid(self):
        for step in range(STEPS_PER_BAR):
            assert _is_grid_aligned(_step_to_time(1, step))

    def test_is_grid_aligned_invalid(self):
        assert not _is_grid_aligned("1.1.3")
        assert not _is_grid_aligned("1.1.9")
        assert not _is_grid_aligned("1.1.1")

    def test_offbeat_steps_not_on_beats(self):
        assert OFFBEAT_STEPS.isdisjoint(BEAT_STEPS)

    def test_step_to_time_rejects_out_of_range(self):
        with pytest.raises(AssertionError):
            _step_to_time(1, 16)
        with pytest.raises(AssertionError):
            _step_to_time(1, -1)


# ---------------------------------------------------------------------------
# Candidate steps
# ---------------------------------------------------------------------------

class TestCandidateSteps:

    def test_candidates_are_after_call(self):
        candidates = _candidate_steps(call_step=4, bar=1, occupied=set(), landscape_position=0.5)
        assert all(s > 4 for s in candidates)

    def test_candidates_are_offbeat(self):
        candidates = _candidate_steps(call_step=0, bar=1, occupied=set(), landscape_position=0.5)
        assert all(s in OFFBEAT_STEPS for s in candidates)

    def test_candidates_exclude_occupied(self):
        candidates = _candidate_steps(call_step=0, bar=1, occupied={6, 10}, landscape_position=0.5)
        assert 6 not in candidates
        assert 10 not in candidates

    def test_candidates_empty_when_call_too_late(self):
        # Call at step 14 — no offbeat after 14 in same bar
        candidates = _candidate_steps(call_step=14, bar=1, occupied=set(), landscape_position=0.5)
        assert candidates == []

    def test_nott_prefers_late_phrase_steps(self):
        candidates = _candidate_steps(call_step=0, bar=1, occupied=set(), landscape_position=0.9)
        # Should only contain late-phrase steps (10-15 range)
        assert all(s >= 10 for s in candidates)


# ---------------------------------------------------------------------------
# Test pattern mode
# ---------------------------------------------------------------------------

class TestTestPattern:

    def setup_method(self):
        stabs_mod.STAB_TEST_PATTERN = None

    def teardown_method(self):
        stabs_mod.STAB_TEST_PATTERN = None

    def test_fixed_pattern_fires_at_correct_steps(self):
        stabs_mod.STAB_TEST_PATTERN = [4, 10, 14]
        events = [_event(time="1.1.0")]
        stabs = generate_stabs(events, _behaviour())

        assert len(stabs) == 3
        times = {s.time for s in stabs}
        assert _step_to_time(1, 4)  in times
        assert _step_to_time(1, 10) in times
        assert _step_to_time(1, 14) in times

    def test_fixed_pattern_steps_are_grid_aligned(self):
        stabs_mod.STAB_TEST_PATTERN = [3, 7, 11, 15]
        events = [_event(time="2.1.0")]
        stabs = generate_stabs(events, _behaviour())
        for s in stabs:
            assert _is_grid_aligned(s.time), f"stab at {s.time} is off-grid"

    def test_fixed_pattern_layer_and_role(self):
        stabs_mod.STAB_TEST_PATTERN = [6]
        events = [_event(time="1.1.0")]
        stabs = generate_stabs(events, _behaviour())
        assert stabs[0].layer == "stab"
        assert stabs[0].role  == "stab"

    def test_no_stabs_without_events(self):
        stabs_mod.STAB_TEST_PATTERN = [4, 10, 14]
        stabs = generate_stabs([], _behaviour())
        assert stabs == []


# ---------------------------------------------------------------------------
# Musical generation — all stabs must be grid-aligned
# ---------------------------------------------------------------------------

class TestGridAlignmentInvariant:

    @pytest.mark.parametrize("pos", [0.0, 0.16, 0.33, 0.5, 0.67, 0.84, 1.0])
    def test_all_stabs_grid_aligned_across_landscape(self, pos):
        events = [
            _event(time=_step_to_time(1, s)) for s in [0, 4, 8, 12]
        ]
        b = _behaviour(energy_level=0.8)
        for stab in generate_stabs(events, b, landscape_position=pos):
            assert _is_grid_aligned(stab.time), (
                f"stab at {stab.time} off-grid at pos={pos}"
            )

    def test_all_stabs_grid_aligned_multi_bar(self):
        events = []
        for bar in range(1, 5):
            for step in [0, 8]:
                events.append(_event(time=_step_to_time(bar, step)))
        b = _behaviour(energy_level=0.9)
        for stab in generate_stabs(events, b, landscape_position=0.5):
            assert _is_grid_aligned(stab.time)

    def test_stab_time_reconstructs_to_same_step(self):
        events = [_event(time=_step_to_time(1, 8))]
        b = _behaviour(energy_level=0.9)
        for stab in generate_stabs(events, b, landscape_position=0.5):
            bar, step = _time_to_bar_step(stab.time)
            assert step >= 0, f"stab step negative from {stab.time}"
            assert 0 <= step < STEPS_PER_BAR


# ---------------------------------------------------------------------------
# Musical constraints
# ---------------------------------------------------------------------------

class TestMusicalConstraints:

    def test_stab_does_not_land_on_strong_beat(self):
        events = [_event(time=_step_to_time(1, 0))]
        b = _behaviour(energy_level=0.9)
        for stab in generate_stabs(events, b, landscape_position=0.5):
            _, step = _time_to_bar_step(stab.time)
            assert step not in BEAT_STEPS, f"stab landed on strong beat step {step}"

    def test_stab_is_after_call(self):
        call_step = 4
        events = [_event(time=_step_to_time(1, call_step))]
        b = _behaviour(energy_level=0.9)
        for stab in generate_stabs(events, b, landscape_position=0.5):
            stab_bar, stab_step = _time_to_bar_step(stab.time)
            call_bar = 1
            # stab must be after call in the same bar, or in next bar
            if stab_bar == call_bar:
                assert stab_step > call_step
            else:
                assert stab_bar > call_bar

    def test_at_most_one_stab_per_bar(self):
        # Multiple calls in the same bar should produce at most 1 stab
        events = [
            _event(time=_step_to_time(1, 0)),
            _event(time=_step_to_time(1, 4)),
            _event(time=_step_to_time(1, 8)),
        ]
        b = _behaviour(energy_level=0.9)
        stabs = generate_stabs(events, b, landscape_position=0.5)
        bars = [_time_to_bar_step(s.time)[0] for s in stabs]
        for bar in bars:
            assert bars.count(bar) <= 1, f"multiple stabs in bar {bar}"

    def test_oak_fires_on_odd_bars_only(self):
        events = []
        for bar in [1, 2, 3, 4]:
            events.append(_event(time=_step_to_time(bar, 8), role="anchor"))
        b = _behaviour(energy_level=0.9)
        stabs = generate_stabs(events, b, landscape_position=0.0)
        stab_bars = {_time_to_bar_step(s.time)[0] for s in stabs}
        assert all(bar % 2 == 1 for bar in stab_bars), (
            f"Oak stabs fired on even bars: {stab_bars}"
        )
