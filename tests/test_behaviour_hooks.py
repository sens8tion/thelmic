"""Tests for behaviour_hooks — automatic deformation modulation.

Phase 3 scope: compute_behaviour_overrides() and the ghost_inject hook.
No server or intent wiring tested here.
"""

import math
import pytest
from thelmic.force_engine import ForceState
from thelmic.transition_engine import Transition
from thelmic.behaviour_hooks import compute_behaviour_overrides, _ghost_inject_hook


def _transition(start=0.0, target=1.0, current=None, elapsed=0.0, duration=8.0, active=True):
    return Transition(
        start_position=start,
        target_position=target,
        current_position=current if current is not None else start,
        duration_bars=duration,
        elapsed_bars=elapsed,
        active=active,
    )

def _force(instability=0.5, density=0.5):
    return ForceState(instability=instability, density=density)


# ---------------------------------------------------------------------------
# ghost_inject hook
# ---------------------------------------------------------------------------

class TestGhostInjectHook:

    def test_zero_when_no_instability(self):
        t = _transition(start=0.0, target=1.0, elapsed=4.0)
        f = _force(instability=0.0)
        assert _ghost_inject_hook(t, f) == pytest.approx(0.0)

    def test_toward_nott_peaks_near_midpoint(self):
        f = _force(instability=1.0)
        mid = _transition(start=0.0, target=1.0, current=0.5, elapsed=4.0)
        at_start = _transition(start=0.0, target=1.0, current=0.0, elapsed=0.1)
        assert _ghost_inject_hook(mid, f) > _ghost_inject_hook(at_start, f)

    def test_toward_nott_is_zero_at_start(self):
        f = _force(instability=1.0)
        t = _transition(start=0.0, target=1.0, elapsed=0.0)
        assert _ghost_inject_hook(t, f) == pytest.approx(0.0, abs=0.01)

    def test_toward_nott_is_zero_at_end(self):
        f = _force(instability=1.0)
        t = _transition(start=0.0, target=1.0, elapsed=8.0, duration=8.0)
        assert _ghost_inject_hook(t, f) == pytest.approx(0.0, abs=0.01)

    def test_toward_oak_decays_over_time(self):
        f = _force(instability=1.0)
        early = _transition(start=1.0, target=0.0, current=0.9, elapsed=0.5)
        late  = _transition(start=1.0, target=0.0, current=0.1, elapsed=6.0)
        assert _ghost_inject_hook(early, f) > _ghost_inject_hook(late, f)

    def test_toward_oak_lower_than_toward_nott_peak(self):
        f = _force(instability=1.0)
        nott_peak = _transition(start=0.0, target=1.0, current=0.5, elapsed=4.0)
        oak_start = _transition(start=1.0, target=0.0, current=1.0, elapsed=0.0)
        assert _ghost_inject_hook(nott_peak, f) > _ghost_inject_hook(oak_start, f)

    def test_output_clamped_to_unit_interval(self):
        f = _force(instability=1.0)
        t = _transition(start=0.0, target=1.0, current=0.5, elapsed=4.0)
        val = _ghost_inject_hook(t, f)
        assert 0.0 <= val <= 1.0

    def test_direction_none_returns_zero(self):
        f = _force(instability=1.0)
        t = _transition(start=0.5, target=0.5, current=0.5, elapsed=4.0)
        assert _ghost_inject_hook(t, f) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# compute_behaviour_overrides
# ---------------------------------------------------------------------------

class TestComputeBehaviourOverrides:

    def test_returns_empty_when_no_transition(self):
        f = _force(instability=1.0)
        result = compute_behaviour_overrides(None, f, {})
        assert result == {}

    def test_returns_empty_when_transition_inactive(self):
        f = _force(instability=1.0)
        t = _transition(active=False)
        result = compute_behaviour_overrides(t, f, {})
        assert result == {}

    def test_hook_fires_during_active_transition(self):
        f = _force(instability=1.0)
        t = _transition(start=0.0, target=1.0, current=0.5, elapsed=4.0)
        result = compute_behaviour_overrides(t, f, {})
        assert "ghost_inject" in result
        assert result["ghost_inject"] > 0.0

    def test_manual_wins_over_hook_for_same_key(self):
        f = _force(instability=1.0)
        t = _transition(start=0.0, target=1.0, current=0.5, elapsed=4.0)
        manual = {"ghost_inject": 0.9}
        result = compute_behaviour_overrides(t, f, manual)
        assert result["ghost_inject"] == pytest.approx(0.9)

    def test_manual_on_one_key_does_not_suppress_hooks_on_other_keys(self):
        """Per amendment 2: per-target merge only."""
        f = _force(instability=1.0)
        t = _transition(start=0.0, target=1.0, current=0.5, elapsed=4.0)
        manual = {"cc:0:74": 0.8}   # manual on a CC key
        result = compute_behaviour_overrides(t, f, manual)
        # CC key preserved
        assert result["cc:0:74"] == pytest.approx(0.8)
        # ghost_inject hook still fires
        assert "ghost_inject" in result
        assert result["ghost_inject"] > 0.0

    def test_manual_overrides_passed_through_when_no_active_transition(self):
        f = _force()
        manual = {"ghost_inject": 0.5, "cc:0:74": 0.3}
        result = compute_behaviour_overrides(None, f, manual)
        assert result == manual

    def test_empty_manual_with_active_transition_returns_hook_values(self):
        f = _force(instability=0.8)
        t = _transition(start=0.0, target=1.0, current=0.5, elapsed=4.0)
        result = compute_behaviour_overrides(t, f, {})
        assert len(result) >= 1

    def test_result_values_in_unit_interval(self):
        f = _force(instability=1.0)
        t = _transition(start=0.0, target=1.0, current=0.5, elapsed=4.0)
        result = compute_behaviour_overrides(t, f, {})
        for key, val in result.items():
            assert 0.0 <= val <= 1.0, f"{key}={val} out of range"
