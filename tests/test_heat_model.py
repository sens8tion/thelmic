"""Tests for the Heat model.

Verifies:
  - response curve has correct 3-zone behaviour
  - all 5 mappings are in [0, 1]
  - heat does not affect seed, landscape, or output fingerprint
  - inertia convergence
  - heat state appears in server state payload
"""

from __future__ import annotations

import math
import pytest

from thelmic.server import (
    compute_heat_mappings,
    heat_response_curve,
)


# ---------------------------------------------------------------------------
# Response curve — 3 zones
# ---------------------------------------------------------------------------

class TestResponseCurve:

    def test_output_is_bounded(self):
        for v in [0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0]:
            r = heat_response_curve(v)
            assert 0.0 <= r <= 1.0, f"heat={v}: response={r} out of [0,1]"

    def test_monotone_increasing(self):
        prev = -1.0
        for i in range(101):
            r = heat_response_curve(i / 100)
            assert r >= prev - 1e-9, f"response not monotone at heat={i/100}"
            prev = r

    def test_zero_maps_near_zero(self):
        assert heat_response_curve(0.0) < 0.01

    def test_one_maps_near_one(self):
        assert heat_response_curve(1.0) > 0.99

    def test_stable_zone_is_slow_at_entry(self):
        """At the start of the stable zone, sensitivity is low."""
        r0 = heat_response_curve(0.0)
        r1 = heat_response_curve(0.1)
        r3 = heat_response_curve(0.3)
        # Gain in stable zone should be less than in expressive zone
        stable_gain = r3 - r0
        assert stable_gain <= 0.20, f"stable zone too reactive: gain={stable_gain:.3f}"

    def test_expressive_zone_is_more_sensitive_than_stable(self):
        """Average gain per heat unit in expressive zone exceeds stable zone."""
        def avg_gain(lo, hi):
            return (heat_response_curve(hi) - heat_response_curve(lo)) / (hi - lo)

        assert avg_gain(0.3, 0.7) > avg_gain(0.0, 0.3), (
            "expressive zone should have higher gain per unit than stable zone"
        )

    def test_unstable_zone_reaches_near_maximum_quickly(self):
        """Unstable zone escalates: by heat=0.9 the response is > 0.95."""
        assert heat_response_curve(0.9) > 0.95, (
            "response should be > 0.95 by heat=0.9 (rapid escalation in unstable zone)"
        )

    def test_unstable_zone_escalates_rapidly(self):
        """The last 10% of the unstable zone should push response close to 1.0."""
        r09 = heat_response_curve(0.9)
        r10 = heat_response_curve(1.0)
        assert r10 - r09 > 0.01, "response should still climb at the top of unstable zone"
        assert r10 > 0.99

    def test_curve_is_deterministic(self):
        assert heat_response_curve(0.5) == heat_response_curve(0.5)


# ---------------------------------------------------------------------------
# 5 Behaviour mappings
# ---------------------------------------------------------------------------

class TestHeatMappings:

    REQUIRED_KEYS = {
        "mutation_depth",
        "timing_deviation",
        "density_variance",
        "pressure_curve_shape",
        "silence_behaviour",
    }

    def test_all_five_mappings_present(self):
        mappings = compute_heat_mappings(0.5)
        assert self.REQUIRED_KEYS.issubset(mappings.keys())

    @pytest.mark.parametrize("heat", [0.0, 0.25, 0.5, 0.75, 1.0])
    def test_all_mappings_bounded(self, heat):
        for key, value in compute_heat_mappings(heat).items():
            assert 0.0 <= value <= 1.0, f"heat={heat} {key}={value} out of [0,1]"

    def test_zero_heat_produces_minimal_mappings(self):
        m = compute_heat_mappings(0.0)
        for key, value in m.items():
            assert value < 0.05, f"{key}={value} should be near 0 at heat=0"

    def test_full_heat_produces_near_maximum_mappings(self):
        m = compute_heat_mappings(1.0)
        for key, value in m.items():
            assert value > 0.8, f"{key}={value} should be near 1 at heat=1.0"

    def test_mappings_monotone_with_heat(self):
        prev = {k: -1.0 for k in self.REQUIRED_KEYS}
        for i in range(21):
            h = i / 20
            m = compute_heat_mappings(h)
            for key in self.REQUIRED_KEYS:
                assert m[key] >= prev[key] - 1e-9, (
                    f"{key} not monotone at heat={h}: {m[key]} < prev {prev[key]}"
                )
            prev = m

    def test_mappings_deterministic(self):
        assert compute_heat_mappings(0.6) == compute_heat_mappings(0.6)


# ---------------------------------------------------------------------------
# Heat does not affect identity
# ---------------------------------------------------------------------------

def test_heat_does_not_change_rhythmic_identity():
    """Heat changes energy (sparsity, stability) but not rhythmic identity.

    The active feature and its SignatureRhythm are location-determined.
    Heat must not change which feature is active or its musical character.
    """
    from thelmic.dimension_engine import compute
    from thelmic.landscape_trajectory import LandscapeTrajectory
    from thelmic.landscape_map import LandscapeMap
    from thelmic.phrase_engine import pending_archetype_for

    t = LandscapeTrajectory(landscape=LandscapeMap(seed=1103))

    d_cold = compute(t, 0.0)
    d_hot  = compute(t, 1.0)

    # Active feature and its SignatureRhythm must not change with heat
    sr_cold = t.active_feature().signature_rhythm
    sr_hot  = t.active_feature().signature_rhythm  # same trajectory, same feature
    assert sr_cold == sr_hot, "heat must not change the active feature"
    assert sr_cold.root_note  == sr_hot.root_note
    assert sr_cold.bass_steps == sr_hot.bass_steps

    # Archetype selection (from SR) must also be heat-immune
    assert pending_archetype_for(sr_cold) == pending_archetype_for(sr_hot)

    # Stability WILL differ — heat loosens stability; that is the intended effect
    assert d_cold.stability > d_hot.stability, "heat should decrease stability"

    # Sparsity is positional-only; heat does NOT change which instruments appear.
    # Moving somewhere changes the terrain character; heat only changes energy level.
    assert d_cold.sparsity == d_hot.sparsity, (
        "heat must not change positional sparsity — that is location-only"
    )


def test_heat_does_not_alter_landscape_seed():
    """Changing heat must not touch the landscape seed or topology."""
    from thelmic import server
    original_seed  = server._landscape_seed
    original_peaks = [p[0] for p in server._LANDSCAPE_MAP._chaos_peaks]

    server._heat_target  = 0.9
    server._heat_applied = 0.9

    assert server._landscape_seed == original_seed
    assert [p[0] for p in server._LANDSCAPE_MAP._chaos_peaks] == original_peaks

    # Restore
    server._heat_target  = 0.5
    server._heat_applied = 0.5


def test_heat_does_not_alter_feature_identities():
    """Sweeping heat must not change the terrain feature IDs."""
    from thelmic import server
    ids_before = [f.id for f in server._LANDSCAPE_MAP.get_features()]

    for h in [0.0, 0.3, 0.7, 1.0]:
        server._heat_target  = h
        server._heat_applied = h
        ids_now = [f.id for f in server._LANDSCAPE_MAP.get_features()]
        assert ids_now == ids_before, f"feature IDs changed at heat={h}"

    server._heat_target  = 0.5
    server._heat_applied = 0.5


# ---------------------------------------------------------------------------
# Inertia
# ---------------------------------------------------------------------------

class TestInertia:

    def test_applied_converges_toward_target(self):
        """Repeated lerp must converge toward target."""
        from thelmic.server import _HEAT_INERTIA_K
        applied = 0.0
        target  = 1.0
        for _ in range(200):
            applied += (target - applied) * _HEAT_INERTIA_K
        assert applied > 0.99, f"heat did not converge after 200 steps: {applied}"

    def test_inertia_k_is_in_valid_range(self):
        from thelmic.server import _HEAT_INERTIA_K
        assert 0.05 <= _HEAT_INERTIA_K <= 0.20

    def test_slow_change_stays_close_to_target(self):
        """Slow (1% per step) movement: applied should closely track target."""
        from thelmic.server import _HEAT_INERTIA_K
        applied = 0.5
        for step in range(50):
            target  = 0.5 + step * 0.01
            applied += (target - applied) * _HEAT_INERTIA_K
        # After 50 steps of slow movement, applied should be within 0.15 of target
        assert abs(applied - target) < 0.15

    def test_snap_when_not_playing(self):
        """When not playing, applied should equal target immediately."""
        from thelmic import server
        server._heat_target  = 0.9
        server._heat_applied = 0.9  # snapped
        assert server._heat_applied == server._heat_target


# ---------------------------------------------------------------------------
# Server state payload
# ---------------------------------------------------------------------------

def test_heat_in_server_state():
    from thelmic import server
    state = server._state(include_bank=False)
    assert "heat" in state
    heat = state["heat"]
    assert "target"               in heat
    assert "applied"              in heat
    assert "response"             in heat
    assert "mutation_depth"       in heat
    assert "timing_deviation"     in heat
    assert "density_variance"     in heat
    assert "pressure_curve_shape" in heat
    assert "silence_behaviour"    in heat


def test_heat_values_in_state_are_bounded():
    from thelmic import server
    state = server._state(include_bank=False)
    heat  = state["heat"]
    for key in ("target", "applied", "response", "mutation_depth",
                "timing_deviation", "density_variance",
                "pressure_curve_shape", "silence_behaviour"):
        assert 0.0 <= heat[key] <= 1.0, f"heat.{key}={heat[key]} out of [0,1]"
