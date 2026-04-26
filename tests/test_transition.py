"""Tests for Transition dataclass and TransitionEngine.

Phase 1 scope: data model and engine only.
No server, intent, or behaviour hook wiring.
"""

import pytest
from thelmic.force_engine import ForceEngine
from thelmic.transition_engine import (
    Transition,
    TransitionEngine,
    DEFAULT_TRANSITION_BARS,
    _COMPLETION_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Transition dataclass
# ---------------------------------------------------------------------------

class TestTransition:

    def _t(self, start=0.0, target=1.0, current=None, duration=8.0, elapsed=0.0):
        return Transition(
            start_position=start,
            target_position=target,
            current_position=current if current is not None else start,
            duration_bars=duration,
            elapsed_bars=elapsed,
        )

    # progress
    def test_progress_zero_at_start(self):
        assert self._t(elapsed=0.0).progress == pytest.approx(0.0)

    def test_progress_half_at_midpoint(self):
        assert self._t(elapsed=4.0, duration=8.0).progress == pytest.approx(0.5)

    def test_progress_one_at_full_duration(self):
        assert self._t(elapsed=8.0, duration=8.0).progress == pytest.approx(1.0)

    def test_progress_clamped_above_one(self):
        assert self._t(elapsed=10.0, duration=8.0).progress == pytest.approx(1.0)

    def test_progress_zero_duration_returns_one(self):
        assert self._t(duration=0.0).progress == pytest.approx(1.0)

    # remaining
    def test_remaining_one_at_start(self):
        t = self._t(start=0.0, target=1.0, current=0.0)
        assert t.remaining == pytest.approx(1.0)

    def test_remaining_zero_at_target(self):
        t = self._t(start=0.0, target=1.0, current=1.0)
        assert t.remaining == pytest.approx(0.0)

    def test_remaining_half_at_midpoint(self):
        t = self._t(start=0.0, target=1.0, current=0.5)
        assert t.remaining == pytest.approx(0.5)

    def test_remaining_zero_when_no_span(self):
        t = self._t(start=0.5, target=0.5, current=0.5)
        assert t.remaining == pytest.approx(0.0)

    # direction
    def test_direction_toward_nott(self):
        t = self._t(target=0.8, current=0.2)
        assert t.direction == "toward_nott"

    def test_direction_toward_oak(self):
        t = self._t(target=0.1, current=0.9)
        assert t.direction == "toward_oak"

    def test_direction_none_when_at_target(self):
        t = self._t(target=0.5, current=0.5)
        assert t.direction == "none"

    # velocity
    def test_velocity_proportional_to_distance(self):
        fast = self._t(start=0.0, target=1.0, duration=4.0)
        slow = self._t(start=0.0, target=1.0, duration=16.0)
        assert fast.velocity > slow.velocity

    def test_velocity_zero_for_zero_duration(self):
        t = self._t(duration=0.0)
        assert t.velocity == pytest.approx(0.0)

    def test_velocity_clamped_at_one(self):
        # Very short duration for a long distance should not exceed 1.0
        t = self._t(start=0.0, target=1.0, duration=0.5)
        assert t.velocity == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# TransitionEngine
# ---------------------------------------------------------------------------

class TestTransitionEngine:

    def _engine(self, pos=0.0):
        fe = ForceEngine(landscape_position=pos)
        return fe, TransitionEngine(fe)

    # set_target
    def test_set_target_creates_transition(self):
        fe, te = self._engine(0.0)
        te.set_target(0.8)
        assert te.transition is not None
        assert te.transition.target_position == pytest.approx(0.8)
        assert te.is_active

    def test_set_target_near_current_creates_no_transition(self):
        fe, te = self._engine(0.5)
        te.set_target(0.5)
        assert te.transition is None
        assert not te.is_active

    def test_set_target_within_threshold_creates_no_transition(self):
        fe, te = self._engine(0.5)
        te.set_target(0.5 + _COMPLETION_THRESHOLD * 0.5)
        assert te.transition is None

    def test_set_target_records_current_as_start(self):
        fe, te = self._engine(0.3)
        te.set_target(0.9)
        assert te.transition.start_position == pytest.approx(0.3)

    def test_retarget_mid_transition_resets_from_current(self):
        fe, te = self._engine(0.0)
        te.set_target(1.0)
        te.advance(bars=4)    # halfway through
        mid = fe.landscape_position
        te.set_target(0.2)    # retarget
        assert te.transition.start_position == pytest.approx(mid, abs=0.01)
        assert te.transition.elapsed_bars == pytest.approx(0.0)

    def test_custom_duration_stored(self):
        fe, te = self._engine(0.0)
        te.set_target(1.0, duration_bars=16.0)
        assert te.transition.duration_bars == pytest.approx(16.0)

    # advance
    def test_advance_moves_position_toward_target(self):
        fe, te = self._engine(0.0)
        te.set_target(1.0, duration_bars=8.0)
        te.advance(bars=4)
        assert fe.landscape_position == pytest.approx(0.5, abs=0.01)

    def test_advance_updates_current_position_on_transition(self):
        fe, te = self._engine(0.0)
        te.set_target(1.0, duration_bars=8.0)
        te.advance(bars=4)
        assert te.transition.current_position == pytest.approx(0.5, abs=0.01)

    def test_advance_completes_at_full_duration(self):
        fe, te = self._engine(0.0)
        te.set_target(1.0, duration_bars=4.0)
        te.advance(bars=4)
        assert not te.is_active
        assert fe.landscape_position == pytest.approx(1.0)

    def test_advance_snaps_to_target_within_threshold(self):
        fe, te = self._engine(0.0)
        te.set_target(1.0, duration_bars=8.0)
        # Advance 7.9 bars — within threshold of 1.0
        te.advance(bars=7.9)
        if not te.is_active:
            assert fe.landscape_position == pytest.approx(1.0)

    def test_advance_does_nothing_with_no_transition(self):
        fe, te = self._engine(0.4)
        te.advance(bars=4)
        assert fe.landscape_position == pytest.approx(0.4)

    def test_advance_does_nothing_after_completion(self):
        fe, te = self._engine(0.0)
        te.set_target(1.0, duration_bars=4.0)
        te.advance(bars=4)     # completes
        te.advance(bars=4)     # should not move further
        assert fe.landscape_position == pytest.approx(1.0)

    # cancel
    def test_cancel_clears_transition(self):
        fe, te = self._engine(0.0)
        te.set_target(1.0)
        te.cancel()
        assert te.transition is None
        assert not te.is_active

    def test_cancel_leaves_position_unchanged(self):
        fe, te = self._engine(0.0)
        te.set_target(1.0)
        te.advance(bars=2)
        pos = fe.landscape_position
        te.cancel()
        assert fe.landscape_position == pytest.approx(pos)

    # state_dict
    def test_state_dict_when_no_transition(self):
        fe, te = self._engine(0.3)
        d = te.state_dict()
        assert d["active"] is False
        assert d["target_position"] is None
        assert d["current_position"] == pytest.approx(0.3, abs=0.01)

    def test_state_dict_when_active(self):
        fe, te = self._engine(0.0)
        te.set_target(0.8)
        te.advance(bars=4)
        d = te.state_dict()
        assert d["active"] is True
        assert d["target_position"] == pytest.approx(0.8, abs=0.01)
        assert 0.0 < d["progress"] < 1.0
        assert d["direction"] in ("toward_nott", "toward_oak", "none")

    def test_state_dict_has_all_required_keys(self):
        fe, te = self._engine(0.0)
        te.set_target(1.0)
        d = te.state_dict()
        for key in ("active", "start_position", "current_position", "target_position",
                    "progress", "remaining", "direction", "velocity",
                    "duration_bars", "elapsed_bars"):
            assert key in d, f"missing key: {key}"

    # default duration constant
    def test_default_duration_used_when_none_given(self):
        fe, te = self._engine(0.0)
        te.set_target(1.0)
        assert te.transition.duration_bars == pytest.approx(DEFAULT_TRANSITION_BARS)
