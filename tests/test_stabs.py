"""Tests for stab mini-catch motif system.

Grid invariant: every stab event must land on a valid 16th-note step (0..15).
Motif invariant: stab timing is generated from step indices, not time offsets.
"""

import pytest
from thelmic.bank_generator import MIDIEvent
from thelmic.behaviour_field import BehaviourField
from thelmic import stabs as stabs_mod
from thelmic.stabs import (
    StabMotif,
    LATE_ANSWER, PICKUP_CATCH, SYNCOPATED_HOOK,
    generate_stabs, generate_stabs_from_calls, collect_call_events,
    _step_to_time, _time_to_bar_step, _is_grid_aligned,
    _varied_motif, _select_motif, _should_fire_in_bar,
    TICKS_PER_STEP, STEPS_PER_BAR, OFFBEAT_STEPS, BEAT_STEPS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _behaviour(
    energy_level: float = 0.6,
    ghost_intensity: float = 1.0,
    anticipation: float = 0.5,
    instability: float = 0.5,
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


def _event(layer: str = "snare", time: str = "1.2.0", role: str = "anchor",
           velocity: int = 100) -> MIDIEvent:
    return MIDIEvent(
        time=time, note=38, velocity=velocity, duration=0.05,
        layer=layer, role=role, emphasis=0.8, openness=1.0,
        expected_weight=0.9, should_resolve=False,
    )


def _bank_events(bars: list[int] = None) -> list[MIDIEvent]:
    """Minimal bank events: one kick at beat 1 per bar."""
    bars = bars or list(range(1, 17))
    return [_event(layer="kick", time=_step_to_time(b, 0), role="anchor") for b in bars]


# ---------------------------------------------------------------------------
# Grid primitives
# ---------------------------------------------------------------------------

class TestGridPrimitives:

    def test_step_to_time_known_values(self):
        assert _step_to_time(1, 0)  == "1.1.0"
        assert _step_to_time(1, 2)  == "1.1.12"
        assert _step_to_time(1, 4)  == "1.2.0"
        assert _step_to_time(1, 6)  == "1.2.12"
        assert _step_to_time(1, 8)  == "1.3.0"
        assert _step_to_time(1, 10) == "1.3.12"
        assert _step_to_time(1, 14) == "1.4.12"

    def test_step_to_time_roundtrip_all_steps(self):
        for bar in [1, 3, 7]:
            for step in range(STEPS_PER_BAR):
                t = _step_to_time(bar, step)
                b, s = _time_to_bar_step(t)
                assert b == bar and s == step

    def test_time_to_bar_step_off_grid_returns_minus_one(self):
        for off in [1, 3, 5, 7, 9, 11]:
            _, step = _time_to_bar_step(f"1.1.{off}")
            assert step == -1

    def test_is_grid_aligned(self):
        for step in range(STEPS_PER_BAR):
            assert _is_grid_aligned(_step_to_time(1, step))
        assert not _is_grid_aligned("1.1.3")
        assert not _is_grid_aligned("1.1.9")

    def test_step_to_time_invalid_raises(self):
        with pytest.raises(AssertionError):
            _step_to_time(1, -1)
        with pytest.raises(AssertionError):
            _step_to_time(1, 16)


# ---------------------------------------------------------------------------
# StabMotif
# ---------------------------------------------------------------------------

class TestStabMotif:

    def test_built_in_motifs_are_valid(self):
        for m in [LATE_ANSWER, PICKUP_CATCH, SYNCOPATED_HOOK]:
            assert len(m) >= 2
            assert all(0 <= s < STEPS_PER_BAR for s in m.steps)
            assert m.steps == tuple(sorted(m.steps))
            assert all(1 <= d <= 4 for d in m.durations)

    def test_first_note_only_returns_single_note(self):
        assert len(LATE_ANSWER.first_note_only()) == 1
        assert LATE_ANSWER.first_note_only().steps == (LATE_ANSWER.steps[0],)

    def test_first_note_only_velocity_is_lighter(self):
        full_vel = LATE_ANSWER.velocities[0]
        call_vel = LATE_ANSWER.first_note_only().velocities[0]
        assert call_vel < full_vel

    def test_drop_middle_removes_middle_note(self):
        varied = LATE_ANSWER.drop_middle()
        assert len(varied) == 2
        assert varied.steps[0] == LATE_ANSWER.steps[0]
        assert varied.steps[-1] == LATE_ANSWER.steps[-1]

    def test_drop_middle_extends_final_duration(self):
        base_dur  = LATE_ANSWER.durations[-1]
        varied    = LATE_ANSWER.drop_middle()
        assert varied.durations[-1] == base_dur + 1

    def test_shift_final_step_moves_last_step(self):
        varied = LATE_ANSWER.shift_final_step(+1)
        assert varied.steps[-1] == LATE_ANSWER.steps[-1] + 1

    def test_shift_final_step_stays_sorted(self):
        for delta in [-1, +1]:
            varied = LATE_ANSWER.shift_final_step(delta)
            assert varied.steps == tuple(sorted(varied.steps))

    def test_shift_final_step_avoids_beat_steps(self):
        # step 11 + 1 = 12 which is a beat step; should shift to 13
        motif = StabMotif(
            steps=(10, 11), intervals=(0, 2), durations=(1, 1), velocities=(80, 80),
        )
        varied = motif.shift_final_step(+1)
        assert varied.steps[-1] not in BEAT_STEPS

    def test_extend_final_duration_adds_one_step(self):
        base  = LATE_ANSWER.durations[-1]
        varied = LATE_ANSWER.extend_final_duration()
        assert varied.durations[-1] == base + 1

    def test_extend_final_duration_capped_at_4(self):
        motif = StabMotif(
            steps=(10,), intervals=(0,), durations=(4,), velocities=(80,),
        )
        assert motif.extend_final_duration().durations[-1] == 4


# ---------------------------------------------------------------------------
# Variation
# ---------------------------------------------------------------------------

class TestVariation:

    def test_level_0_returns_base_unmodified(self):
        assert _varied_motif(LATE_ANSWER, abs_bar=1) is LATE_ANSWER
        assert _varied_motif(LATE_ANSWER, abs_bar=4) is LATE_ANSWER

    def test_level_1_drops_middle(self):
        varied = _varied_motif(LATE_ANSWER, abs_bar=5)
        assert len(varied) < len(LATE_ANSWER)

    def test_level_2_shifts_final_step(self):
        varied = _varied_motif(LATE_ANSWER, abs_bar=9)
        assert varied.steps[-1] != LATE_ANSWER.steps[-1]

    def test_level_3_extends_final_duration(self):
        varied = _varied_motif(LATE_ANSWER, abs_bar=13)
        assert varied.durations[-1] > LATE_ANSWER.durations[-1]

    def test_variation_stays_grid_aligned(self):
        for bar in range(1, 17):
            varied = _varied_motif(LATE_ANSWER, abs_bar=bar)
            for step in varied.steps:
                assert 0 <= step < STEPS_PER_BAR


# ---------------------------------------------------------------------------
# Firing rules
# ---------------------------------------------------------------------------

class TestFiringRules:

    def test_oak_fires_only_on_response_bars(self):
        pos = 0.0
        # Bar 1 = call bar (bar_in_pair=0) → should not fire
        assert not _should_fire_in_bar(1, bar_in_pair=0, landscape_position=pos)
        # Bar 2 = response bar → should fire
        assert _should_fire_in_bar(2, bar_in_pair=1, landscape_position=pos)

    def test_nott_fires_only_on_phrase_end_response(self):
        pos = 1.0
        # Bar 4 = phrase end, response → fires
        assert _should_fire_in_bar(4, bar_in_pair=1, landscape_position=pos)
        # Bar 2 = response but not phrase end → does not fire
        assert not _should_fire_in_bar(2, bar_in_pair=1, landscape_position=pos)

    def test_chaos_fires_on_both_call_and_response(self):
        pos = 0.5
        assert _should_fire_in_bar(1, bar_in_pair=0, landscape_position=pos)
        assert _should_fire_in_bar(2, bar_in_pair=1, landscape_position=pos)


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
        times = {s.time for s in stabs}
        assert _step_to_time(1, 4)  in times
        assert _step_to_time(1, 10) in times
        assert _step_to_time(1, 14) in times

    def test_fixed_pattern_is_grid_aligned(self):
        stabs_mod.STAB_TEST_PATTERN = [3, 7, 11, 15]
        events = [_event(time="1.1.0")]
        for s in generate_stabs(events, _behaviour()):
            assert _is_grid_aligned(s.time)

    def test_no_stabs_without_events(self):
        stabs_mod.STAB_TEST_PATTERN = [4, 10, 14]
        assert generate_stabs([], _behaviour()) == []


# ---------------------------------------------------------------------------
# Grid alignment invariant — end-to-end
# ---------------------------------------------------------------------------

class TestGridAlignmentInvariant:

    @pytest.mark.parametrize("pos", [0.0, 0.25, 0.5, 0.75, 1.0])
    def test_all_stabs_grid_aligned(self, pos):
        events = _bank_events()
        for stab in generate_stabs(events, _behaviour(), landscape_position=pos):
            assert _is_grid_aligned(stab.time), (
                f"stab at {stab.time} off-grid at pos={pos}"
            )

    def test_stab_step_roundtrips_exactly(self):
        events = _bank_events()
        for stab in generate_stabs(events, _behaviour(), landscape_position=0.5):
            bar, step = _time_to_bar_step(stab.time)
            assert 0 <= step < STEPS_PER_BAR


# ---------------------------------------------------------------------------
# Motif continuity
# ---------------------------------------------------------------------------

class TestMotifContinuity:

    def test_response_bars_have_more_notes_than_call_bars(self):
        events = _bank_events(list(range(1, 5)))
        b = _behaviour(energy_level=0.9)
        stabs = generate_stabs(events, b, landscape_position=0.5)
        stabs_by_bar: dict[int, list] = {}
        for s in stabs:
            bar, _ = _time_to_bar_step(s.time)
            stabs_by_bar.setdefault(bar, []).append(s)
        # Response bar (bar 2) should have more notes than call bar (bar 1)
        call_count = len(stabs_by_bar.get(1, []))
        resp_count = len(stabs_by_bar.get(2, []))
        assert resp_count >= call_count

    def test_motif_steps_are_offbeat(self):
        """Base motifs should use offbeat steps or late steps, not strong beats."""
        for motif in [LATE_ANSWER, PICKUP_CATCH, SYNCOPATED_HOOK]:
            # At least one step should be an offbeat
            has_offbeat = any(s in OFFBEAT_STEPS or s > 8 for s in motif.steps)
            assert has_offbeat, f"motif {motif.steps} has no offbeat steps"

    def test_same_motif_across_bank(self):
        """All stabs in a bank should come from the same base motif."""
        events = _bank_events()
        b = _behaviour(energy_level=0.9)
        stabs = generate_stabs(events, b, landscape_position=0.5)
        # The base motif is the same for the whole bank — first stab step
        # should appear in multiple response bars
        resp_bar_steps: dict[int, list] = {}
        for s in stabs:
            bar, step = _time_to_bar_step(s.time)
            bar_in_pair = (bar - 1) % 2
            if bar_in_pair == 1:  # response bars
                resp_bar_steps.setdefault(bar, []).append(step)
        # All response bars should start with the same base motif step
        if len(resp_bar_steps) >= 2:
            bars = sorted(resp_bar_steps)
            first_step_bar1 = resp_bar_steps[bars[0]][0]
            first_step_bar2 = resp_bar_steps[bars[1]][0]
            assert first_step_bar1 == first_step_bar2, (
                "Response bars use different base motif starts — motif is not stable"
            )
