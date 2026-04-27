"""Tests for the dual-modal call/response system.

Hard rule tested throughout:
  No responder event may fire before step 8.
"""

import pytest
from thelmic.call_response import (
    Mode, CallResponseState, default_state,
    CALL_WINDOW, RESPONSE_WINDOW, RESPONSE_WINDOW_MIN, RESPONSE_WINDOW_MAX,
    derive_response_steps, advance_mode, should_flip,
    _gate_hash, _next_duration,
)
from thelmic.bank_generator import MIDIEvent
from thelmic.behaviour_field import BehaviourField
from thelmic.stabs import (
    _step_to_time, _time_to_bar_step, _is_grid_aligned,
    generate_stab_call, generate_stab_response_from_steps,
    CALL_EARLY, CALL_SYNCO, CALL_OFFBEAT, CALL_WINDOW as STAB_CALL_WINDOW,
)
from thelmic.bass import (
    generate_bass_call, generate_bass_response_from_steps, LOW_NOTE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _behaviour(energy_level: float = 0.6) -> BehaviourField:
    return BehaviourField(
        ghost_intensity=0.5, ghost_clustering=0.0,
        anchor_drop_prob=0.0, filter_target=0.0, gate_tightness=0.0,
        energy_level=energy_level, accent_strength=0.0,
        ghost_velocity=0.4, anchor_velocity=0.8,
        anticipation=0.5, instability=0.5, release_pressure=0.0,
    )


def _kick(bar: int = 1, step: int = 0) -> MIDIEvent:
    return MIDIEvent(
        time=_step_to_time(bar, step), note=36, velocity=100,
        duration=0.08, layer="kick", role="anchor",
        emphasis=0.8, openness=1.0, expected_weight=0.9, should_resolve=False,
    )


def _state(mode=Mode.STAB_LEADS, bars=0, duration=8, force=None) -> CallResponseState:
    return CallResponseState(
        mode=mode, bars_in_mode=bars, mode_duration_bars=duration, force_mode=force,
    )


# ---------------------------------------------------------------------------
# Window constants
# ---------------------------------------------------------------------------

class TestWindowConstants:
    def test_call_window_is_0_to_7(self):
        assert CALL_WINDOW == frozenset(range(0, 8))

    def test_response_window_is_8_to_15(self):
        assert RESPONSE_WINDOW == frozenset(range(8, 16))

    def test_windows_disjoint(self):
        assert CALL_WINDOW & RESPONSE_WINDOW == frozenset()

    def test_windows_cover_16_steps(self):
        assert CALL_WINDOW | RESPONSE_WINDOW == frozenset(range(16))

    def test_response_window_min_max(self):
        assert RESPONSE_WINDOW_MIN == 8
        assert RESPONSE_WINDOW_MAX == 15


# ---------------------------------------------------------------------------
# derive_response_steps — HARD RULE enforced here
# ---------------------------------------------------------------------------

class TestDeriveResponseSteps:

    def test_leader_plus_8_primary_mapping(self):
        assert derive_response_steps([0]) == [8]
        assert derive_response_steps([4]) == [12]
        assert derive_response_steps([7]) == [15]

    def test_all_results_in_response_window(self):
        for ls in range(8):
            for s in derive_response_steps([ls]):
                assert RESPONSE_WINDOW_MIN <= s <= RESPONSE_WINDOW_MAX

    def test_hard_rule_no_step_below_8(self):
        """HARD RULE: no responder step ever below 8."""
        for leader in [[0], [7], [0, 3, 6], list(range(8))]:
            for s in derive_response_steps(leader):
                assert s >= 8, f"violation: step {s} for leader={leader}"

    def test_no_duplicates(self):
        result = derive_response_steps([0, 1])
        assert len(result) == len(set(result))

    def test_collision_bumps_up(self):
        # 0→8, 1→9; both land without collision
        result = derive_response_steps([0, 1])
        assert sorted(result) == result
        assert all(s >= 8 for s in result)

    def test_steps_outside_call_window_ignored(self):
        # step 8 is in RESPONSE_WINDOW, not CALL_WINDOW — should be ignored
        assert derive_response_steps([8]) == []
        assert derive_response_steps([0, 12]) == [8]  # only 0 is in CALL_WINDOW

    def test_empty_input(self):
        assert derive_response_steps([]) == []

    def test_result_sorted(self):
        result = derive_response_steps([5, 2, 6])
        assert result == sorted(result)

    def test_saturated_window_no_duplicates(self):
        result = derive_response_steps(list(range(8)))
        assert len(result) == len(set(result))
        assert all(RESPONSE_WINDOW_MIN <= s <= RESPONSE_WINDOW_MAX for s in result)


# ---------------------------------------------------------------------------
# Mode state machine
# ---------------------------------------------------------------------------

class TestAdvanceMode:

    def test_increments_bars_in_mode(self):
        s = _state(bars=3)
        assert advance_mode(s, abs_bar=1).bars_in_mode == 4

    def test_no_flip_when_bars_below_minimum(self):
        # bars_in_mode = 2 → after increment = 3 < max(4, 8) — no flip
        s = _state(bars=2, duration=8)
        new_s = advance_mode(s, abs_bar=4)   # phrase boundary
        assert new_s.mode == Mode.STAB_LEADS

    def test_no_flip_off_phrase_boundary(self):
        s = _state(bars=20, duration=4)
        for bar in [1, 2, 3, 5, 6, 7, 9, 10, 11]:
            new_s = advance_mode(s, abs_bar=bar)
            assert new_s.mode == s.mode, f"unexpected flip at bar {bar}"

    def test_flip_only_at_phrase_boundary(self):
        s = _state(bars=20, duration=4)
        for bar in range(1, 200):
            new_s = advance_mode(s, abs_bar=bar)
            if new_s.mode != s.mode:
                assert bar % 4 == 0, f"flip at non-boundary bar {bar}"
            s = new_s

    def test_flip_resets_bars_in_mode(self):
        s = _state(mode=Mode.BASS_LEADS, bars=20, duration=4)
        flipped = False
        for bar in range(4, 400, 4):
            new_s = advance_mode(s, abs_bar=bar)
            if new_s.mode != s.mode:
                assert new_s.bars_in_mode == 0
                flipped = True
                break
        assert flipped, "expected at least one flip in 100 phrase boundaries"

    def test_force_mode_overrides_always(self):
        s = _state(bars=100, duration=4, force=Mode.BASS_LEADS)
        for bar in range(1, 50):
            s = advance_mode(s, abs_bar=bar)
            assert s.mode == Mode.BASS_LEADS

    def test_min_4_bars_hard_floor(self):
        # bars_in_mode=0 → after increment=1 → can't flip even at phrase boundary
        s = _state(bars=0, duration=4)
        new_s = advance_mode(s, abs_bar=4)
        assert new_s.mode == Mode.STAB_LEADS
        # bars_in_mode=2 → after increment=3 < 4 → still no flip
        s2 = _state(bars=2, duration=4)
        new_s2 = advance_mode(s2, abs_bar=4)
        assert new_s2.mode == Mode.STAB_LEADS

    def test_gate_hash_is_deterministic(self):
        assert _gate_hash(4, salt=42) == _gate_hash(4, salt=42)
        assert _gate_hash(8, salt=42) != _gate_hash(4, salt=42)

    def test_default_state_is_stab_leads(self):
        s = default_state()
        assert s.mode == Mode.STAB_LEADS
        assert s.bars_in_mode == 0


# ---------------------------------------------------------------------------
# Call-window motifs
# ---------------------------------------------------------------------------

class TestCallMotifs:

    def test_call_motif_steps_in_call_window(self):
        for motif in [CALL_EARLY, CALL_SYNCO, CALL_OFFBEAT]:
            for step in motif.steps:
                assert step in CALL_WINDOW, (
                    f"{motif.__class__} step {step} not in CALL_WINDOW"
                )

    def test_call_motif_steps_sorted(self):
        for motif in [CALL_EARLY, CALL_SYNCO, CALL_OFFBEAT]:
            assert motif.steps == tuple(sorted(motif.steps))

    def test_stab_call_window_matches_call_window(self):
        assert STAB_CALL_WINDOW == CALL_WINDOW


# ---------------------------------------------------------------------------
# generate_stab_call
# ---------------------------------------------------------------------------

class TestGenerateStabCall:

    def test_events_in_call_window(self):
        evts, _ = generate_stab_call(abs_bar=1, behaviour=_behaviour())
        for e in evts:
            _, step = _time_to_bar_step(e.time)
            assert step in CALL_WINDOW, f"stab call step {step} outside CALL_WINDOW"

    def test_leader_steps_in_call_window(self):
        _, leaders = generate_stab_call(abs_bar=1, behaviour=_behaviour())
        for s in leaders:
            assert s in CALL_WINDOW

    def test_events_grid_aligned(self):
        evts, _ = generate_stab_call(abs_bar=3, behaviour=_behaviour())
        for e in evts:
            assert _is_grid_aligned(e.time)

    def test_returns_lists(self):
        evts, leaders = generate_stab_call(abs_bar=1, behaviour=_behaviour())
        assert isinstance(evts, list)
        assert isinstance(leaders, list)

    @pytest.mark.parametrize("pos", [0.0, 0.5, 1.0])
    def test_all_positions(self, pos):
        evts, _ = generate_stab_call(abs_bar=1, behaviour=_behaviour(),
                                     landscape_position=pos)
        for e in evts:
            _, step = _time_to_bar_step(e.time)
            assert step in CALL_WINDOW


# ---------------------------------------------------------------------------
# generate_stab_response_from_steps — HARD RULE
# ---------------------------------------------------------------------------

class TestGenerateStabResponse:

    def test_hard_rule_no_event_before_step_8(self):
        """HARD RULE: stab response never fires before step 8."""
        for leader in [[0], [3, 6], [0, 4, 7], list(range(8))]:
            evts = generate_stab_response_from_steps(
                leader_steps=leader, abs_bar=1, behaviour=_behaviour(),
            )
            for e in evts:
                _, step = _time_to_bar_step(e.time)
                assert step >= 8, (
                    f"VIOLATION: stab response step {step} < 8 for leader={leader}"
                )

    def test_response_in_response_window(self):
        evts = generate_stab_response_from_steps(
            leader_steps=[0, 4], abs_bar=1, behaviour=_behaviour(),
        )
        for e in evts:
            _, step = _time_to_bar_step(e.time)
            assert RESPONSE_WINDOW_MIN <= step <= RESPONSE_WINDOW_MAX

    def test_primary_mapping_0_to_8_4_to_12(self):
        evts = generate_stab_response_from_steps(
            leader_steps=[0, 4], abs_bar=1, behaviour=_behaviour(),
            landscape_position=0.5,
        )
        steps = {_time_to_bar_step(e.time)[1] for e in evts}
        assert 8 in steps
        assert 12 in steps

    def test_grid_aligned(self):
        evts = generate_stab_response_from_steps(
            leader_steps=[1, 5], abs_bar=2, behaviour=_behaviour(),
        )
        for e in evts:
            assert _is_grid_aligned(e.time)

    @pytest.mark.parametrize("pos", [0.0, 0.5, 1.0])
    def test_across_landscape(self, pos):
        evts = generate_stab_response_from_steps(
            leader_steps=[2, 6], abs_bar=1, behaviour=_behaviour(),
            landscape_position=pos,
        )
        for e in evts:
            _, step = _time_to_bar_step(e.time)
            assert step >= 8


# ---------------------------------------------------------------------------
# generate_bass_call / generate_bass_response_from_steps
# ---------------------------------------------------------------------------

class TestBassCallAndResponse:

    def _src(self, bar: int = 1) -> list[MIDIEvent]:
        return [_kick(bar=bar)]

    def test_bass_call_fires_at_steps_0_and_4(self):
        evts = generate_bass_call(self._src(1), _behaviour())
        steps = {_time_to_bar_step(e.time)[1] for e in evts}
        assert 0 in steps
        assert 4 in steps

    def test_bass_call_steps_in_call_window(self):
        for e in generate_bass_call(self._src(2), _behaviour()):
            _, step = _time_to_bar_step(e.time)
            assert step in CALL_WINDOW

    def test_bass_call_note_is_low_note(self):
        for e in generate_bass_call(self._src(), _behaviour()):
            assert e.note == LOW_NOTE

    def test_bass_call_grid_aligned(self):
        for e in generate_bass_call(self._src(3), _behaviour()):
            assert _is_grid_aligned(e.time)

    def test_bass_response_hard_rule_no_step_below_8(self):
        """HARD RULE: bass response never fires before step 8."""
        leader_by_bar = {1: [8, 12], 2: [9, 13]}
        for e in generate_bass_response_from_steps(
            leader_by_bar, self._src(1), _behaviour()
        ):
            _, step = _time_to_bar_step(e.time)
            assert step >= 8, f"VIOLATION: bass response step {step} < 8"

    def test_bass_response_note_is_low_note(self):
        leader_by_bar = {1: [10, 14]}
        for e in generate_bass_response_from_steps(
            leader_by_bar, self._src(), _behaviour()
        ):
            assert e.note == LOW_NOTE

    def test_bass_call_layer_and_role(self):
        for e in generate_bass_call(self._src(), _behaviour()):
            assert e.layer == "bass"
            assert e.role == "bass_call"

    def test_bass_response_layer_and_role(self):
        for e in generate_bass_response_from_steps(
            {1: [10]}, self._src(), _behaviour()
        ):
            assert e.layer == "bass"
            assert e.role == "bass_response"


# ---------------------------------------------------------------------------
# Integration — stab calls derive bass response correctly
# ---------------------------------------------------------------------------

class TestStabLeadsIntegration:

    def test_stab_call_steps_derive_to_response_window(self):
        _, leaders = generate_stab_call(abs_bar=1, behaviour=_behaviour(),
                                        landscape_position=0.5)
        resp_steps = derive_response_steps(leaders)
        for s in resp_steps:
            assert RESPONSE_WINDOW_MIN <= s <= RESPONSE_WINDOW_MAX

    def test_no_collision_between_call_and_response(self):
        _, leaders = generate_stab_call(abs_bar=2, behaviour=_behaviour())
        resp_steps = derive_response_steps(leaders)
        assert not (set(leaders) & set(resp_steps)), (
            f"collision: call={leaders} response={resp_steps}"
        )

    def test_response_always_after_call(self):
        for abs_bar in [1, 2, 5, 8]:
            _, leaders = generate_stab_call(abs_bar=abs_bar, behaviour=_behaviour())
            resp_steps = derive_response_steps(leaders)
            if leaders and resp_steps:
                assert min(resp_steps) > max(leaders), (
                    f"response {resp_steps} not all after call {leaders}"
                )
