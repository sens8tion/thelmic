import pytest
from thelmic.bank_generator import (
    BankGenerator, PHRASES_PER_BANK, BARS_PER_PHRASE, EXPECTATION_ANCHOR_THRESHOLD
)
from thelmic.controls import Controls
from thelmic.force_engine import ForceState
from thelmic.landscape import OAK_PROFILE, CHAOS_PROFILE, NOTT_PROFILE

# Without deformations registered, only these roles are produced deterministically.
# disruption and withheld_resolution are deformation concerns — tested once implemented.
VALID_ROLES  = {"anchor", "ghost", "impact"}
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

    def test_all_events_have_nonzero_velocity(self):
        # No withheld events without deformations — every fired slot plays
        for e in _gen(OAK_PROFILE).all_events():
            assert e.velocity > 0

    def test_output_is_deterministic(self):
        # Same inputs must always produce identical output — no hidden RNG
        bank_a = _gen(CHAOS_PROFILE, pos=0.5, seed=0)
        bank_b = _gen(CHAOS_PROFILE, pos=0.5, seed=0)
        times_a = [(e.time, e.layer, e.velocity) for e in bank_a.all_events()]
        times_b = [(e.time, e.layer, e.velocity) for e in bank_b.all_events()]
        assert times_a == times_b

    def test_territory_does_not_change_pattern(self):
        # Territory (landscape_position) is a deformation parameter only.
        # With no deformations, the same archetype at different positions plays identically.
        force = ForceState(
            anticipation=0.3, release_pressure=0.2,
            instability=0.3, density=0.5, control_vs_chaos=0.3,
        )
        bank_oak   = _gen(force, pos=0.0)
        bank_chaos = _gen(force, pos=0.5)
        bank_nott  = _gen(force, pos=1.0)
        events_oak   = [(e.time, e.layer) for e in bank_oak.all_events()]
        events_chaos = [(e.time, e.layer) for e in bank_chaos.all_events()]
        events_nott  = [(e.time, e.layer) for e in bank_nott.all_events()]
        assert events_oak == events_chaos == events_nott


class TestArchetypeDrivenDensity:
    def test_half_step_sparse(self):
        sparse = ForceState(
            anticipation=0.1, release_pressure=0.0,
            instability=0.2, density=0.1, control_vs_chaos=0.3,
        )
        bank = _gen(sparse, pos=0.9)
        kick_per_bar = len([e for e in bank.all_events() if e.layer == "kick"]) / (PHRASES_PER_BANK * BARS_PER_PHRASE)
        assert kick_per_bar <= 2.5, f"Expected sparse kick, got {kick_per_bar:.1f} kicks/bar"

    def test_four_on_floor_denser_than_two_step(self):
        two_step = ForceState(
            anticipation=0.2, release_pressure=0.1,
            instability=0.05, density=0.45, control_vs_chaos=0.1,
        )
        four_otf = ForceState(
            anticipation=0.2, release_pressure=0.1,
            instability=0.05, density=0.85, control_vs_chaos=0.1,
        )
        hits_ts  = len(_gen(two_step, pos=0.1).all_events())
        hits_4tf = len(_gen(four_otf, pos=0.1).all_events())
        assert hits_ts <= hits_4tf

    def test_higher_density_selects_denser_archetype(self):
        sparse = ForceState(
            anticipation=0.2, release_pressure=0.1,
            instability=0.0, density=0.1, control_vs_chaos=0.1,
        )
        dense = ForceState(
            anticipation=0.2, release_pressure=0.1,
            instability=0.0, density=0.95, control_vs_chaos=0.1,
        )
        kick_sparse = len([e for e in _gen(sparse).all_events() if e.layer == "kick"])
        kick_dense  = len([e for e in _gen(dense).all_events()  if e.layer == "kick"])
        assert kick_dense > kick_sparse


class TestRoleAssignment:
    def test_anchor_present(self):
        assert any(e.role == "anchor" for e in _gen(OAK_PROFILE).all_events())

    def test_impact_appears_under_release_pressure(self):
        high_rp = ForceState(
            anticipation=0.5, release_pressure=0.85,
            instability=0.1, density=0.6, control_vs_chaos=0.2,
        )
        assert any(e.role == "impact" for e in _gen(high_rp, pos=0.1).all_events())


class TestControls:
    def test_density_ceiling_reduces_hit_count(self):
        low  = Controls(density_ceiling=0.1)
        high = Controls(density_ceiling=1.0)
        hits_low  = len(BankGenerator(controls=low).generate(OAK_PROFILE, 0, 0.1).all_events())
        hits_high = len(BankGenerator(controls=high).generate(OAK_PROFILE, 0, 0.1).all_events())
        assert hits_low <= hits_high
