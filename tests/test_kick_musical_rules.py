"""Kick musical rule tests.

Verifies that KickIntentStream produces territory-appropriate patterns.
All assertions use StructureFrame → Intent → output; no legacy paths.

Territory character:
  Oak   (lpos < 0.33)   — stable two-step, consistent velocity
  Chaos (0.33–0.67)     — density-scaled from two-step to dense 4×4 + synco
  Nott  (lpos >= 0.67)  — sparse, pressure-weighted, heavy downbeat
"""

import pytest
from thelmic.stream_drums import KickIntentStream, _territory
from thelmic.stream_engine import (
    Intent, PhraseRole, StructureFrame, StructureProfile, StructureStream, Tick,
    SubphraseRole,
)
from dataclasses import replace


STEPS_PER_BANK = 256


def _frame(
    step_in_bar: int = 0,
    landscape_position: float = 0.0,
    density: float = 0.5,
    pressure: float = 0.3,
    silence: float = 0.0,
    is_bar_start: bool = False,
    is_drop: bool = False,
    is_relock: bool = False,
    phrase_role: PhraseRole = PhraseRole.GROOVE,
) -> StructureFrame:
    """Build a minimal StructureFrame for unit testing."""
    return StructureFrame(
        global_step=step_in_bar,
        time=0.0,
        musical_step=step_in_bar,
        bar_index=1,
        step_in_bar=step_in_bar,
        phrase_index=0,
        step_in_phrase=step_in_bar,
        subphrase_index=0,
        step_in_subphrase=step_in_bar,
        phrase_role=phrase_role,
        subphrase_role=SubphraseRole.STATEMENT,
        is_bar_start=is_bar_start,
        is_phrase_start=False,
        is_subphrase_start=False,
        is_drop=is_drop,
        is_relock=is_relock,
        pressure=pressure,
        impact=0.0,
        density=density,
        silence=silence,
        landscape_position=landscape_position,
        archetype=_territory(landscape_position),
    )


def _kick_steps_at(landscape_position: float, density: float, pressure: float = 0.3):
    """Return the set of steps that produce kick intents for a full bar."""
    stream = KickIntentStream()
    fired: set[int] = set()
    for s in range(16):
        frame = _frame(
            step_in_bar=s,
            landscape_position=landscape_position,
            density=density,
            pressure=pressure,
            is_bar_start=(s == 0),
        )
        intents = stream.intents_for_frame(frame)
        if intents:
            fired.add(s)
    return fired


def _kick_roles_at(landscape_position: float, density: float, pressure: float = 0.3):
    """Return {step: role} for a full bar."""
    stream = KickIntentStream()
    result: dict[int, str] = {}
    for s in range(16):
        frame = _frame(
            step_in_bar=s,
            landscape_position=landscape_position,
            density=density,
            pressure=pressure,
        )
        intents = stream.intents_for_frame(frame)
        if intents:
            result[s] = intents[0].role
    return result


def _velocity_at(step: int, landscape_position: float, density: float, pressure: float):
    stream = KickIntentStream()
    frame = _frame(step_in_bar=step, landscape_position=landscape_position,
                   density=density, pressure=pressure)
    intents = stream.intents_for_frame(frame)
    return intents[0].velocity if intents else None


# ---------------------------------------------------------------------------
# Territory helper
# ---------------------------------------------------------------------------

class TestTerritoryHelper:
    def test_oak(self):    assert _territory(0.0)  == "oak"
    def test_chaos(self):  assert _territory(0.5)  == "chaos"
    def test_nott(self):   assert _territory(1.0)  == "nott"
    def test_boundary_chaos_low(self):  assert _territory(0.33) == "chaos"
    def test_boundary_nott_low(self):   assert _territory(0.67) == "nott"


# ---------------------------------------------------------------------------
# Structure-mandatory: drop and relock always fire
# ---------------------------------------------------------------------------

class TestDropAndRelockAlwaysFire:

    def test_drop_fires_regardless_of_silence(self):
        stream = KickIntentStream()
        frame = _frame(step_in_bar=0, silence=1.0, is_drop=True,
                       landscape_position=0.5)
        assert stream.intents_for_frame(frame)

    def test_relock_fires_regardless_of_silence(self):
        stream = KickIntentStream()
        frame = _frame(step_in_bar=4, silence=1.0, is_relock=True,
                       landscape_position=0.0)
        assert stream.intents_for_frame(frame)

    def test_drop_velocity_is_boosted(self):
        stream = KickIntentStream()
        normal = _frame(step_in_bar=0, is_bar_start=True, landscape_position=0.5,
                        density=0.5, pressure=0.3)
        drop   = _frame(step_in_bar=0, is_bar_start=True, landscape_position=0.5,
                        density=0.5, pressure=0.3, is_drop=True)
        v_normal = stream.intents_for_frame(normal)[0].velocity
        v_drop   = stream.intents_for_frame(drop)[0].velocity
        assert v_drop > v_normal

    def test_drop_intent_uses_drop_reason(self):
        stream = KickIntentStream()
        frame = _frame(step_in_bar=0, is_drop=True, landscape_position=0.0)
        intent = stream.intents_for_frame(frame)[0]
        assert "drop_relock" in intent.reason

    def test_non_drop_uses_territory_reason(self):
        stream = KickIntentStream()
        frame = _frame(step_in_bar=0, is_bar_start=True, landscape_position=0.0,
                       density=0.5)
        intent = stream.intents_for_frame(frame)[0]
        assert "oak" in intent.reason


# ---------------------------------------------------------------------------
# Silence gate
# ---------------------------------------------------------------------------

class TestSilenceGate:

    def test_high_silence_suppresses_non_structural_kick(self):
        stream = KickIntentStream()
        frame = _frame(step_in_bar=0, silence=0.90, landscape_position=0.5)
        assert stream.intents_for_frame(frame) == ()

    def test_moderate_silence_allows_kick(self):
        steps = _kick_steps_at(0.5, density=0.6)
        # Below threshold (0.85 default): kicks still fire
        assert len(steps) > 0

    def test_silence_does_not_suppress_drop(self):
        stream = KickIntentStream()
        frame = _frame(step_in_bar=0, silence=1.0, is_drop=True,
                       landscape_position=0.0)
        assert stream.intents_for_frame(frame)


# ---------------------------------------------------------------------------
# Oak: stable two-step character
# ---------------------------------------------------------------------------

class TestOakKickPattern:

    def test_oak_low_density_fires_beats_1_and_3(self):
        steps = _kick_steps_at(0.0, density=0.35)
        assert 0 in steps, "beat 1 must fire"
        assert 8 in steps, "beat 3 must fire"

    def test_oak_high_density_adds_syncopation(self):
        low_d  = _kick_steps_at(0.0, density=0.35)
        high_d = _kick_steps_at(0.0, density=0.70)
        assert len(high_d) >= len(low_d), "more steps at higher density"

    def test_oak_extra_steps_are_ghost_role(self):
        roles = _kick_roles_at(0.0, density=0.70)
        for step, role in roles.items():
            if step not in (0, 8):
                assert role == "ghost", f"step {step} should be ghost in Oak"

    def test_oak_velocity_is_consistent(self):
        """Oak velocity should not vary much across density range."""
        v_low  = _velocity_at(0, 0.0, density=0.2, pressure=0.3)
        v_high = _velocity_at(0, 0.0, density=0.9, pressure=0.3)
        assert v_low and v_high
        # Oak base is 94–102; should not swing wildly
        assert abs(v_high - v_low) < 20, f"Oak velocity swing too wide: {v_low}→{v_high}"

    def test_oak_downbeat_louder_than_off_step(self):
        """Step 0 should be louder than a ghost step."""
        roles_map = _kick_roles_at(0.0, density=0.70)
        stream = KickIntentStream()
        v_beat1 = _velocity_at(0, 0.0, density=0.70, pressure=0.3)
        # Find any ghost step
        ghost_steps = [s for s, r in roles_map.items() if r == "ghost"]
        if ghost_steps:
            v_ghost = _velocity_at(ghost_steps[0], 0.0, density=0.70, pressure=0.3)
            assert v_beat1 > v_ghost, "downbeat should be louder than ghost"


# ---------------------------------------------------------------------------
# Chaos: density-scaled, syncopated
# ---------------------------------------------------------------------------

class TestChaosKickPattern:

    def test_chaos_scales_with_density(self):
        """More density → more kick steps."""
        steps_low  = _kick_steps_at(0.5, density=0.35)
        steps_mid  = _kick_steps_at(0.5, density=0.60)
        steps_high = _kick_steps_at(0.5, density=0.80)
        assert len(steps_mid) >= len(steps_low)
        assert len(steps_high) >= len(steps_mid)

    def test_chaos_mid_density_has_more_steps_than_oak(self):
        """Chaos at similar density should be denser than Oak."""
        oak_steps   = _kick_steps_at(0.1, density=0.6)
        chaos_steps = _kick_steps_at(0.5, density=0.6)
        # Chaos enriched density (×1.0) vs Oak (×0.75) → chaos should be denser
        assert len(chaos_steps) >= len(oak_steps)

    def test_chaos_high_density_approaches_4on_the_floor(self):
        """Dense chaos should include all four main beats."""
        steps = _kick_steps_at(0.5, density=0.75)
        for beat_step in (0, 4, 8, 12):
            assert beat_step in steps, f"4×4 beat at step {beat_step} missing in dense Chaos"

    def test_chaos_includes_synco_at_max_density(self):
        """Maximum density Chaos should include syncopated steps."""
        steps = _kick_steps_at(0.5, density=0.90)
        non_beat_steps = {s for s in steps if s % 4 != 0}
        assert non_beat_steps, "no syncopation at max Chaos density"

    def test_chaos_velocity_scales_with_density(self):
        v_low  = _velocity_at(0, 0.5, density=0.2, pressure=0.3)
        v_high = _velocity_at(0, 0.5, density=0.9, pressure=0.3)
        assert v_high > v_low, "Chaos velocity should scale with density"


# ---------------------------------------------------------------------------
# Nott: sparse, pressure-weighted
# ---------------------------------------------------------------------------

class TestNottKickPattern:

    def test_nott_low_pressure_is_sparse(self):
        """Nott at low pressure: only beat 1."""
        steps = _kick_steps_at(1.0, density=0.5, pressure=0.1)
        assert steps == {0}, f"Nott low pressure should be single beat: got {steps}"

    def test_nott_high_pressure_adds_beat_3(self):
        steps = _kick_steps_at(1.0, density=0.5, pressure=0.55)
        assert 0 in steps
        assert 8 in steps, "Nott high pressure should add beat 3"

    def test_nott_is_sparser_than_chaos_at_same_density(self):
        nott_steps  = _kick_steps_at(1.0, density=0.6, pressure=0.3)
        chaos_steps = _kick_steps_at(0.5, density=0.6, pressure=0.3)
        assert len(nott_steps) <= len(chaos_steps), (
            f"Nott should be sparser than Chaos: "
            f"nott={nott_steps} chaos={chaos_steps}"
        )

    def test_nott_velocity_scales_with_pressure(self):
        v_low  = _velocity_at(0, 1.0, density=0.5, pressure=0.1)
        v_high = _velocity_at(0, 1.0, density=0.5, pressure=0.9)
        assert v_high > v_low, "Nott velocity should scale with pressure"

    def test_nott_downbeat_is_heavy(self):
        """Nott beat 1 should be among the loudest kick velocities."""
        v_nott = _velocity_at(0, 1.0, density=0.5, pressure=0.7)
        v_oak  = _velocity_at(0, 0.0, density=0.5, pressure=0.7)
        # At high pressure Nott should be as loud or louder
        assert v_nott is not None
        assert v_nott >= 96, f"Nott downbeat velocity should be heavy: {v_nott}"


# ---------------------------------------------------------------------------
# Provenance — all intents have required fields
# ---------------------------------------------------------------------------

class TestKickProvenance:

    def test_all_intents_have_source(self):
        stream = KickIntentStream()
        for lpos in (0.0, 0.5, 1.0):
            for s in range(16):
                frame = _frame(step_in_bar=s, landscape_position=lpos,
                               density=0.7, pressure=0.5)
                for intent in stream.intents_for_frame(frame):
                    assert intent.source == "stream_kick"

    def test_all_intents_have_intent_id(self):
        stream = KickIntentStream()
        for lpos in (0.0, 0.5, 1.0):
            for s in range(16):
                frame = _frame(step_in_bar=s, landscape_position=lpos,
                               density=0.7, pressure=0.5)
                for intent in stream.intents_for_frame(frame):
                    assert intent.intent_id

    def test_intents_carry_territory_in_payload(self):
        stream = KickIntentStream()
        for lpos, expected in ((0.0, "oak"), (0.5, "chaos"), (1.0, "nott")):
            frame = _frame(step_in_bar=0, landscape_position=lpos,
                           density=0.5, pressure=0.3)
            for intent in stream.intents_for_frame(frame):
                assert intent.payload.get("territory") == expected

    def test_intents_carry_musical_step(self):
        stream = KickIntentStream()
        frame = _frame(step_in_bar=4, landscape_position=0.5, density=0.8)
        for intent in stream.intents_for_frame(frame):
            assert intent.payload.get("musical_step") is not None

    def test_drop_intent_has_drop_territory_reason(self):
        stream = KickIntentStream()
        frame = _frame(step_in_bar=0, is_drop=True, landscape_position=0.5)
        intent = stream.intents_for_frame(frame)[0]
        assert "drop_relock" in intent.reason


# ---------------------------------------------------------------------------
# Differs meaningfully between territories at same density/pressure
# ---------------------------------------------------------------------------

class TestTerritoryDifference:

    def test_oak_chaos_nott_differ_at_medium_density(self):
        """Three territories must produce different step sets."""
        oak   = _kick_steps_at(0.1, density=0.6, pressure=0.4)
        chaos = _kick_steps_at(0.5, density=0.6, pressure=0.4)
        nott  = _kick_steps_at(0.9, density=0.6, pressure=0.4)
        # Not all the same
        assert not (oak == chaos == nott), (
            f"all territories produce same pattern: {oak}"
        )

    def test_chaos_denser_than_oak_denser_than_nott(self):
        """At medium density: chaos ≥ oak ≥ nott in step count."""
        oak   = _kick_steps_at(0.1, density=0.6, pressure=0.35)
        chaos = _kick_steps_at(0.5, density=0.6, pressure=0.35)
        nott  = _kick_steps_at(0.9, density=0.6, pressure=0.35)
        assert len(chaos) >= len(oak), f"chaos={chaos} should be ≥ oak={oak}"
        assert len(oak) >= len(nott), f"oak={oak} should be ≥ nott={nott}"

    def test_velocity_profile_differs_by_territory(self):
        v_oak   = _velocity_at(0, 0.1, density=0.5, pressure=0.5)
        v_chaos = _velocity_at(0, 0.5, density=0.5, pressure=0.5)
        v_nott  = _velocity_at(0, 0.9, density=0.5, pressure=0.5)
        assert not (v_oak == v_chaos == v_nott), (
            "all territories produce same velocity"
        )
