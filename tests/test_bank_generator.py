import pytest
from thelmic.bank_generator import (
    BankGenerator, PHRASES_PER_BANK, BARS_PER_PHRASE, EXPECTATION_ANCHOR_THRESHOLD
)
from thelmic.controls import Controls
from thelmic.force_engine import ForceState
from thelmic.landscape import OAK_PROFILE, CHAOS_PROFILE, NOTT_PROFILE

VALID_ROLES  = {"anchor", "ghost", "disruption", "impact", "withheld_resolution"}
VALID_LAYERS = {"kick", "snare", "hat"}


def _gen(force: ForceState, pos: float = 0.0, seed: int = 42) -> "Bank":
    return BankGenerator(controls=Controls(), seed=seed).generate(force, 0, pos)


class TestBankStructure:
    def test_correct_phrase_count(self):
        assert len(_gen(OAK_PROFILE).phrases) == PHRASES_PER_BANK

    def test_bank_has_events(self):
        assert len(_gen(OAK_PROFILE).all_events()) > 0

    def test_all_events_have_valid_layer(self):
        for e in _gen(OAK_PROFILE).all_events():
            assert e.layer in VALID_LAYERS

    def test_all_roles_valid(self):
        for e in _gen(CHAOS_PROFILE, pos=0.5).all_events():
            assert e.role in VALID_ROLES

    def test_velocities_in_range(self):
        for e in _gen(CHAOS_PROFILE, pos=0.5).all_events():
            assert 0 <= e.velocity <= 127

    def test_withheld_events_have_zero_velocity(self):
        for e in _gen(CHAOS_PROFILE, pos=0.5).all_events():
            if e.role == "withheld_resolution":
                assert e.velocity == 0

    def test_non_withheld_events_have_nonzero_velocity(self):
        for e in _gen(OAK_PROFILE).all_events():
            if e.role != "withheld_resolution":
                assert e.velocity > 0


class TestArchetypeDrivenDensity:
    def test_half_step_sparse(self):
        sparse = ForceState(
            anticipation=0.1, release_pressure=0.0,
            instability=0.2, density=0.2, control_vs_chaos=0.3,
        )
        bank = _gen(sparse, pos=0.9)
        kick_per_bar = len([e for e in bank.all_events() if e.layer == "kick" and e.velocity > 0]) / (PHRASES_PER_BANK * BARS_PER_PHRASE)
        assert kick_per_bar <= 2.5, f"Expected sparse kick in half-step, got {kick_per_bar:.1f} kicks/bar"

    def test_four_on_floor_denser_than_two_step(self):
        two_step = ForceState(
            anticipation=0.2, release_pressure=0.1,
            instability=0.05, density=0.45, control_vs_chaos=0.1,
        )
        four_otf = ForceState(
            anticipation=0.2, release_pressure=0.1,
            instability=0.05, density=0.85, control_vs_chaos=0.1,
        )
        hits_ts  = len([e for e in _gen(two_step, pos=0.1, seed=1).all_events() if e.velocity > 0])
        hits_4tf = len([e for e in _gen(four_otf, pos=0.1, seed=1).all_events() if e.velocity > 0])
        assert hits_ts <= hits_4tf

    def test_gabber_disruption_denser_than_stable_chaos(self):
        # density > 0.65 at chaos selects GABBER as disruption archetype;
        # high instability blends toward it → more events than low instability
        base_force = ForceState(
            anticipation=0.3, release_pressure=0.2,
            instability=0.0, density=0.7, control_vs_chaos=0.5,
        )
        disrupted = ForceState(
            anticipation=0.3, release_pressure=0.2,
            instability=0.9, density=0.7, control_vs_chaos=0.5,
        )
        hits_stable    = len([e for e in _gen(base_force,  pos=0.5, seed=3).all_events() if e.velocity > 0])
        hits_disrupted = len([e for e in _gen(disrupted,   pos=0.5, seed=3).all_events() if e.velocity > 0])
        assert hits_disrupted > hits_stable


class TestRoleAssignment:
    def test_anchor_present(self):
        assert any(e.role == "anchor" for e in _gen(OAK_PROFILE).all_events())

    def test_disruption_appears_under_high_instability(self):
        found = any(
            e.role == "disruption"
            for seed in range(30)
            for e in _gen(CHAOS_PROFILE, pos=0.5, seed=seed).all_events()
        )
        assert found

    def test_withheld_resolution_appears_under_high_anticipation(self):
        high_ant = ForceState(
            anticipation=0.95, release_pressure=0.5,
            instability=0.1, density=0.6, control_vs_chaos=0.1,
        )
        found = any(
            e.role == "withheld_resolution"
            for seed in range(40)
            for e in _gen(high_ant, pos=0.1, seed=seed).all_events()
        )
        assert found

    def test_withheld_only_on_high_expectation_slots(self):
        high_ant = ForceState(
            anticipation=0.95, release_pressure=0.5,
            instability=0.05, density=0.6, control_vs_chaos=0.1,
        )
        for seed in range(20):
            for e in _gen(high_ant, pos=0.1, seed=seed).all_events():
                if e.role == "withheld_resolution":
                    assert e.expected_weight >= EXPECTATION_ANCHOR_THRESHOLD

    def test_impact_appears_under_release_pressure(self):
        high_rp = ForceState(
            anticipation=0.5, release_pressure=0.85,
            instability=0.1, density=0.6, control_vs_chaos=0.2,
        )
        found = any(
            e.role == "impact"
            for seed in range(20)
            for e in _gen(high_rp, pos=0.1, seed=seed).all_events()
        )
        assert found


class TestControls:
    def test_chaos_limit_suppresses_disruptions(self):
        controls = Controls(chaos_limit=0.0)
        bank = BankGenerator(controls=controls, seed=5).generate(CHAOS_PROFILE, 0, 0.5)
        assert not any(e.role == "disruption" for e in bank.all_events())

    def test_density_ceiling_reduces_hit_count(self):
        low  = Controls(density_ceiling=0.1)
        high = Controls(density_ceiling=1.0)
        hits_low  = len(BankGenerator(controls=low,  seed=7).generate(OAK_PROFILE, 0, 0.1).all_events())
        hits_high = len(BankGenerator(controls=high, seed=7).generate(OAK_PROFILE, 0, 0.1).all_events())
        assert hits_low <= hits_high
