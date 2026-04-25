import pytest
from thelmic.bank_generator import BankGenerator, PHRASES_PER_BANK, BARS_PER_PHRASE
from thelmic.controls import Controls
from thelmic.force_engine import ForceState
from thelmic.landscape import OAK_PROFILE, CHAOS_PROFILE, NOTT_PROFILE

VALID_ROLES = {"anchor", "ghost", "disruption", "impact", "withheld_resolution"}


def _gen(force: ForceState, seed: int = 42) -> "Bank":
    return BankGenerator(controls=Controls(), seed=seed).generate(force, bank_index=0)


class TestBankStructure:
    def test_correct_phrase_count(self):
        bank = _gen(OAK_PROFILE)
        assert len(bank.phrases) == PHRASES_PER_BANK

    def test_bank_has_events(self):
        bank = _gen(OAK_PROFILE)
        assert len(bank.all_events()) > 0

    def test_all_events_are_kick(self):
        bank = _gen(OAK_PROFILE)
        for e in bank.all_events():
            assert e.layer == "kick"

    def test_all_roles_valid(self):
        bank = _gen(OAK_PROFILE)
        for e in bank.all_events():
            assert e.role in VALID_ROLES, f"Unknown role: {e.role}"

    def test_velocities_in_range(self):
        bank = _gen(CHAOS_PROFILE)
        for e in bank.all_events():
            assert 1 <= e.velocity <= 127

    def test_emphasis_in_range(self):
        bank = _gen(OAK_PROFILE)
        for e in bank.all_events():
            assert 0.0 <= e.emphasis <= 1.0


class TestDensityMapping:
    def test_oak_fewer_events_than_chaos(self):
        oak_bank = _gen(OAK_PROFILE, seed=1)
        chaos_bank = _gen(CHAOS_PROFILE, seed=1)
        assert len(oak_bank.all_events()) <= len(chaos_bank.all_events())

    def test_density_ceiling_limits_events(self):
        controls_low = Controls(density_ceiling=0.0)
        bank_low = BankGenerator(controls=controls_low, seed=7).generate(OAK_PROFILE, 0)
        controls_high = Controls(density_ceiling=1.0)
        bank_high = BankGenerator(controls=controls_high, seed=7).generate(OAK_PROFILE, 0)
        assert len(bank_low.all_events()) <= len(bank_high.all_events())

    def test_chaos_limit_reduces_instability_effect(self):
        controls_limited = Controls(chaos_limit=0.0)
        # With instability clamped to 0, should produce no disruption roles
        bank = BankGenerator(controls=controls_limited, seed=5).generate(CHAOS_PROFILE, 0)
        roles = [e.role for e in bank.all_events()]
        assert "disruption" not in roles


class TestRoleDistribution:
    def test_anchor_present_in_oak(self):
        bank = _gen(OAK_PROFILE)
        roles = [e.role for e in bank.all_events()]
        assert "anchor" in roles

    def test_high_instability_produces_disruptions(self):
        # Run many seeds to ensure disruptions appear when instability is high
        found = False
        for seed in range(20):
            bank = BankGenerator(seed=seed).generate(CHAOS_PROFILE, 0)
            if any(e.role == "disruption" for e in bank.all_events()):
                found = True
                break
        assert found, "Expected disruption roles with high instability"

    def test_withheld_resolution_appears_under_anticipation(self):
        high_anticipation = ForceState(
            anticipation=0.95, release_pressure=0.5,
            instability=0.1, density=0.7, control_vs_chaos=0.5,
        )
        found = False
        for seed in range(30):
            bank = BankGenerator(seed=seed).generate(high_anticipation, 0)
            if any(e.role == "withheld_resolution" for e in bank.all_events()):
                found = True
                break
        assert found, "Expected withheld_resolution roles with high anticipation"
