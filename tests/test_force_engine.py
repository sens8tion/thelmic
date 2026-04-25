import pytest
from thelmic.force_engine import ForceEngine, ForceState
from thelmic.landscape import OAK_PROFILE, CHAOS_PROFILE, NOTT_PROFILE, territory_at, axis_to_force


class TestTerritoryAt:
    def test_oak_range(self):
        assert territory_at(0.0) == "oak"
        assert territory_at(0.2) == "oak"

    def test_chaos_range(self):
        assert territory_at(0.4) == "chaos"
        assert territory_at(0.5) == "chaos"

    def test_nott_range(self):
        assert territory_at(0.8) == "nott"
        assert territory_at(1.0) == "nott"


class TestAxisToForce:
    def test_oak_extreme_matches_profile(self):
        f = axis_to_force(0.0)
        assert abs(f.instability - OAK_PROFILE.instability) < 1e-6

    def test_chaos_centre_matches_profile(self):
        f = axis_to_force(0.5)
        assert abs(f.instability - CHAOS_PROFILE.instability) < 1e-6

    def test_nott_extreme_matches_profile(self):
        f = axis_to_force(1.0)
        assert abs(f.instability - NOTT_PROFILE.instability) < 1e-6

    def test_midpoint_oak_chaos_is_interpolated(self):
        f = axis_to_force(0.25)
        expected_instability = (OAK_PROFILE.instability + CHAOS_PROFILE.instability) / 2
        assert abs(f.instability - expected_instability) < 1e-6

    def test_all_dimensions_in_range(self):
        for pos in [0.0, 0.1, 0.33, 0.5, 0.67, 0.9, 1.0]:
            f = axis_to_force(pos)
            for dim in (f.anticipation, f.release_pressure, f.instability,
                        f.density, f.control_vs_chaos):
                assert 0.0 <= dim <= 1.0, f"dim out of range at pos={pos}: {dim}"


class TestForceEngine:
    def test_initial_force_matches_landscape(self):
        engine = ForceEngine(landscape_position=0.0)
        expected = axis_to_force(0.0)
        assert abs(engine.force_state.instability - expected.instability) < 1e-6

    def test_set_position_updates_force(self):
        engine = ForceEngine(landscape_position=0.0)
        engine.set_landscape_position(1.0)
        expected = axis_to_force(1.0)
        assert abs(engine.force_state.instability - expected.instability) < 1e-6

    def test_position_clamped(self):
        engine = ForceEngine()
        engine.set_landscape_position(2.0)
        assert engine.landscape_position == 1.0
        engine.set_landscape_position(-0.5)
        assert engine.landscape_position == 0.0

    def test_bank_history_grows(self):
        engine = ForceEngine()
        for _ in range(3):
            snapshot = engine.begin_bank()
            engine.commit_bank(snapshot)
        assert len(engine.bank_history) == 3

    def test_interrupted_bank_marked_incomplete(self):
        engine = ForceEngine(landscape_position=0.5)
        snapshot = engine.begin_bank()
        engine.interrupt_bank(snapshot, exit_position=0.3)
        assert not engine.bank_history[0].completed

    def test_transition_recorded_on_territory_change(self):
        engine = ForceEngine(landscape_position=0.1)  # Oak
        snapshot = engine.begin_bank()
        engine.commit_bank(snapshot)

        engine.set_landscape_position(0.6)  # Chaos
        snapshot2 = engine.begin_bank()
        engine.commit_bank(snapshot2)

        assert snapshot2.transition is not None
        assert snapshot2.transition.from_territory == "oak"
        assert snapshot2.transition.to_territory == "chaos"

    def test_resolution_likelihood_in_range(self):
        for pos in [0.0, 0.5, 1.0]:
            engine = ForceEngine(landscape_position=pos)
            assert 0.0 <= engine.resolution_likelihood <= 1.0

    def test_resolution_likelihood_high_under_pressure(self):
        # High release_pressure + low instability → high resolution_likelihood
        engine = ForceEngine(landscape_position=0.45)  # near chaos peak on release_pressure
        # Manually set a state with high release and low instability to test the formula
        engine.force_state = ForceState(
            anticipation=0.5, release_pressure=0.9, instability=0.0,
            density=0.5, control_vs_chaos=0.5
        )
        engine.resolution_likelihood = engine._calc_resolution_likelihood()
        assert engine.resolution_likelihood > 0.7
