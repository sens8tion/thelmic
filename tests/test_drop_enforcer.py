"""Phase 9 — Drop construction and enforcement tests.

Acceptance criteria:
  - DROP_RELOCK regions are detected
  - bass is present at drop relock
  - hook is present at drop relock
  - kick/bass/hook align at drop relock
  - drop does not emit inside silence_mask
  - unresolved call/response events do not leak into drop
  - Pression does not create drop notes
  - no echo-style lower-velocity motif repeats are introduced
"""

from thelmic.bank_generator import Bank, Phrase, MIDIEvent, KICK_NOTE
from thelmic.behaviour_field import BehaviourField
from thelmic.call_response import Mode
from thelmic.drop_enforcer import (
    enforce_drop_relock,
    DROP_STEP, ECHO_VELOCITY_THRESHOLD,
)
from thelmic.force_engine import ForceState
from thelmic.phrase_plan import (
    PhrasePlan, PlanNote, SilenceMask, PhraseState, generate_phrase_plan,
)
from thelmic.pression import (
    compute_bank_timeline, audit_pression_compliance, DEFAULT_CC_MAP,
)
from thelmic.syntax_enforcer import enforce_phrase_syntax, time_to_bar_step


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _event(time: str = "1.1.0", layer: str = "kick", role: str = "anchor",
           velocity: int = 100, note: int = 36) -> MIDIEvent:
    return MIDIEvent(
        time=time, note=note, velocity=velocity, duration=0.08,
        layer=layer, role=role,
        emphasis=0.8, openness=1.0, expected_weight=0.9, should_resolve=False,
    )


def _bank(*events: MIDIEvent) -> Bank:
    return Bank(bank_index=0, phrases=[Phrase(phrase_index=0, events=list(events))])


def _behaviour() -> BehaviourField:
    return BehaviourField(
        ghost_intensity=0.0, ghost_clustering=0.0, anchor_drop_prob=0.0,
        filter_target=0.0, gate_tightness=0.0, energy_level=0.7,
        accent_strength=0.0, ghost_velocity=0.4, anchor_velocity=0.8,
    )


def _plan_with_drop(
    drop_bar: int = 3,
    silence_before: bool = True,
    call_slots: dict | None = None,
    response_slots: dict | None = None,
    bass_at_drop_step: bool = False,
    kick_at_drop_step: bool = False,
    hook_at_drop_step: bool = False,
) -> tuple[PhrasePlan, Bank]:
    """Build a plan and bank for drop testing.

    drop_bar:         bar with DROP_RELOCK state
    silence_before:   if True, bar drop_bar-1 has HOLD_SILENCE (good contrast)
    *_at_drop_step:   pre-seed these layers at the drop step in the bank
    """
    states: dict[int, PhraseState] = {}
    if silence_before and drop_bar > 1:
        states[drop_bar - 1] = PhraseState.HOLD_SILENCE
    states[drop_bar] = PhraseState.DROP_RELOCK
    # Fill other bars with RESOLVED_STABLE
    for bar in range(1, max(drop_bar + 2, 4)):
        states.setdefault(bar, PhraseState.RESOLVED_STABLE)

    silence: dict[int, tuple] = {drop_bar: tuple(range(0, 4))}
    if silence_before and drop_bar > 1:
        silence[drop_bar - 1] = tuple(range(16))

    plan = PhrasePlan(
        bass_pattern=(PlanNote(bar=drop_bar, step=0, pitch=36),),
        hook_pattern=(PlanNote(bar=drop_bar, step=0, pitch=60),),
        phrase_state=states,
        call_slots=call_slots or {},
        response_slots=response_slots or {},
        silence_mask=SilenceMask(silence),
        pressure_curve={b: 0.5 for b in states},
    )

    events: list[MIDIEvent] = []
    # Add a seed kick in the drop bar to ensure there's a phrase template
    events.append(_event(f"{drop_bar}.2.0", layer="kick", role="anchor"))
    if bass_at_drop_step:
        events.append(_event(f"{drop_bar}.2.0", layer="bass", role="bass", note=36))
    if kick_at_drop_step:
        events.append(_event(f"{drop_bar}.2.0", layer="kick", role="anchor"))
    if hook_at_drop_step:
        events.append(_event(f"{drop_bar}.2.0", layer="hook", role="hook", note=60))

    bank = _bank(*events)
    return plan, bank


def _step_to_time(bar: int, step: int) -> str:
    from drop_enforcer import _step_to_time as _s
    return _s(bar, step)


def _has_layer_at(bank: Bank, bar: int, step: int, layer: str) -> bool:
    for e in bank.all_events():
        b, s = time_to_bar_step(e.time)
        if b == bar and s == step and e.layer == layer:
            return True
    return False


# ---------------------------------------------------------------------------
# DROP_RELOCK detection
# ---------------------------------------------------------------------------

class TestDropRegionDetection:

    def test_detects_drop_relock_bars(self):
        plan, bank = _plan_with_drop(drop_bar=3)
        stats = enforce_drop_relock(bank, plan)
        assert stats["drop_regions_detected"] >= 1

    def test_no_drop_regions_when_no_drop_relock(self):
        plan = PhrasePlan(
            bass_pattern=(PlanNote(bar=1, step=0, pitch=36),),
            hook_pattern=(PlanNote(bar=1, step=0, pitch=60),),
            phrase_state={1: PhraseState.RESOLVED_STABLE, 2: PhraseState.CALL_UNRESOLVED},
            call_slots={2: (2,)},
            response_slots={},
            silence_mask=SilenceMask({}),
            pressure_curve={1: 0.0, 2: 0.5},
        )
        bank = _bank(_event("1.1.0"))
        stats = enforce_drop_relock(bank, plan)
        assert stats["drop_regions_detected"] == 0

    def test_detects_multiple_drop_regions(self):
        states = {
            1: PhraseState.DROP_RELOCK,
            2: PhraseState.RESOLVED_STABLE,
            3: PhraseState.DROP_RELOCK,
        }
        plan = PhrasePlan(
            bass_pattern=(PlanNote(bar=1, step=0, pitch=36),),
            hook_pattern=(PlanNote(bar=1, step=0, pitch=60),),
            phrase_state=states,
            call_slots={},
            response_slots={},
            silence_mask=SilenceMask({1: tuple(range(4)), 3: tuple(range(4))}),
            pressure_curve={b: 0.5 for b in states},
        )
        bank = _bank(_event("1.2.0"), _event("3.2.0"))
        stats = enforce_drop_relock(bank, plan)
        assert stats["drop_regions_detected"] == 2


# ---------------------------------------------------------------------------
# Bass, kick, hook presence at drop step
# ---------------------------------------------------------------------------

class TestDropPresence:

    def test_bassline_added_at_drop_step_when_missing(self):
        plan, bank = _plan_with_drop(drop_bar=2)
        enforce_drop_relock(bank, plan)
        assert _has_layer_at(bank, 2, DROP_STEP, "bassline"), (
            f"Bassline missing at bar=2 step={DROP_STEP}"
        )

    def test_kick_added_at_drop_step_when_missing(self):
        plan, bank = _plan_with_drop(drop_bar=2)
        # Remove all kicks from the drop bar at the drop step to ensure missing
        for phrase in bank.phrases:
            phrase.events = [
                e for e in phrase.events
                if not (time_to_bar_step(e.time) == (2, DROP_STEP) and e.layer == "kick")
            ]
        enforce_drop_relock(bank, plan)
        assert _has_layer_at(bank, 2, DROP_STEP, "kick")

    def test_hook_added_at_drop_step_when_missing(self):
        plan, bank = _plan_with_drop(drop_bar=2)
        enforce_drop_relock(bank, plan)
        assert _has_layer_at(bank, 2, DROP_STEP, "hook"), (
            f"Hook missing at bar=2 step={DROP_STEP}"
        )

    def test_hook_requirement_deferred_when_stream_hook_authority_enabled(self):
        plan, bank = _plan_with_drop(drop_bar=2)

        stats = enforce_drop_relock(bank, plan, hook_authority="stream")

        assert not _has_layer_at(bank, 2, DROP_STEP, "hook")
        assert stats["hook_requirements_deferred"] == 1

    def test_bass_not_added_when_already_present(self):
        plan, bank = _plan_with_drop(drop_bar=2)
        # Manually add bass at drop step
        bank.phrases[0].events.append(
            _event(f"2.2.0", layer="bass", note=36, velocity=100)
        )
        count_before = sum(1 for e in bank.all_events() if e.layer == "bass"
                           and time_to_bar_step(e.time) == (2, DROP_STEP))
        enforce_drop_relock(bank, plan)
        count_after = sum(1 for e in bank.all_events() if e.layer == "bass"
                          and time_to_bar_step(e.time) == (2, DROP_STEP))
        assert count_after == count_before  # no duplicate added

    def test_kick_bassline_hook_all_at_same_step(self):
        """All three must align at the drop step for structural impact."""
        plan, bank = _plan_with_drop(drop_bar=2)
        enforce_drop_relock(bank, plan)

        kick_present = _has_layer_at(bank, 2, DROP_STEP, "kick")
        bass_present = _has_layer_at(bank, 2, DROP_STEP, "bassline")
        hook_present = _has_layer_at(bank, 2, DROP_STEP, "hook")

        assert kick_present, "Kick missing at drop step"
        assert bass_present, "Bassline missing at drop step"
        assert hook_present, "Hook missing at drop step"

    def test_added_events_count_tracked(self):
        plan, bank = _plan_with_drop(drop_bar=2)
        stats = enforce_drop_relock(bank, plan)
        assert stats["drop_relock_events_added"] > 0


# ---------------------------------------------------------------------------
# Drop does not emit inside silence_mask
# ---------------------------------------------------------------------------

class TestDropRespectssilence:

    def test_added_drop_events_are_not_in_muted_steps(self):
        """Events added by the drop enforcer must be at DROP_STEP (4),
        which is NOT in the silence mask (0-3 are muted)."""
        plan, bank = _plan_with_drop(drop_bar=2)
        enforce_drop_relock(bank, plan)

        muted_steps = set(range(0, 4))
        for e in bank.all_events():
            b, s = time_to_bar_step(e.time)
            if b == 2:
                assert s not in muted_steps, (
                    f"Event at step {s} is inside silence_mask: {e}"
                )

    def test_drop_step_is_outside_silence_mask(self):
        assert DROP_STEP >= 4, "DROP_STEP must be outside default silence mask (0-3)"


# ---------------------------------------------------------------------------
# No unresolved call/response in drop
# ---------------------------------------------------------------------------

class TestNoCallResponseLeakage:

    def test_call_event_suppressed_in_drop_bar(self):
        plan, bank = _plan_with_drop(drop_bar=2)
        # Inject a call event into the drop bar
        bank.phrases[0].events.append(
            _event("2.1.12", layer="stab", role="call")
        )
        stats = enforce_drop_relock(bank, plan)
        assert stats["drop_illegal_events_suppressed"] >= 1
        remaining_calls = [e for e in bank.all_events()
                           if "call" in e.role.lower()
                           and time_to_bar_step(e.time)[0] == 2]
        assert remaining_calls == []

    def test_response_event_suppressed_in_drop_bar(self):
        plan, bank = _plan_with_drop(drop_bar=2)
        bank.phrases[0].events.append(
            _event("2.2.12", layer="stab", role="response")
        )
        stats = enforce_drop_relock(bank, plan)
        assert stats["drop_illegal_events_suppressed"] >= 1
        remaining_responses = [e for e in bank.all_events()
                                if "response" in e.role.lower()
                                and time_to_bar_step(e.time)[0] == 2]
        assert remaining_responses == []

    def test_normal_events_not_suppressed_in_drop(self):
        plan, bank = _plan_with_drop(drop_bar=2)
        # Add a normal kick at drop step — should survive
        bank.phrases[0].events.append(
            _event("2.2.0", layer="kick", role="anchor")
        )
        stats = enforce_drop_relock(bank, plan)
        remaining_kicks = [e for e in bank.all_events()
                           if e.layer == "kick"
                           and time_to_bar_step(e.time)[0] == 2]
        assert len(remaining_kicks) > 0


# ---------------------------------------------------------------------------
# No echo-style lower-velocity copies
# ---------------------------------------------------------------------------

class TestNoEchoMotifCopies:

    def test_echo_stab_at_same_step_as_bass_is_suppressed(self):
        """A supporting event (stab) at the same step/pitch as bass but at
        lower velocity is an echo copy — must be suppressed."""
        plan, bank = _plan_with_drop(drop_bar=2)
        # Add bass at the drop step
        bass = _event("2.2.0", layer="bass", note=36, velocity=110)
        # Add stab at same step/pitch but much lower velocity (echo)
        echo = _event("2.2.0", layer="stab", note=36,
                      velocity=int(110 * ECHO_VELOCITY_THRESHOLD * 0.8))
        bank.phrases[0].events.extend([bass, echo])

        stats = enforce_drop_relock(bank, plan)

        remaining_stabs = [e for e in bank.all_events()
                           if e.layer == "stab"
                           and time_to_bar_step(e.time)[0] == 2]
        assert len(remaining_stabs) == 0
        assert stats["drop_illegal_events_suppressed"] >= 1

    def test_supporting_event_at_different_pitch_not_suppressed(self):
        """A stab at a DIFFERENT pitch than bass is not an echo — keep it."""
        plan, bank = _plan_with_drop(drop_bar=2)
        bass = _event("2.2.0", layer="bass", note=36, velocity=110)
        stab = _event("2.2.0", layer="stab", note=62, velocity=80)  # different note
        bank.phrases[0].events.extend([bass, stab])

        enforce_drop_relock(bank, plan)

        stabs = [e for e in bank.all_events()
                 if e.layer == "stab" and time_to_bar_step(e.time)[0] == 2]
        assert len(stabs) == 1

    def test_supporting_event_at_full_velocity_not_suppressed(self):
        """A stab at similar velocity to bass is not an echo — keep it."""
        plan, bank = _plan_with_drop(drop_bar=2)
        bass = _event("2.2.0", layer="bass", note=36, velocity=110)
        strong_stab = _event("2.2.0", layer="stab", note=36, velocity=105)
        bank.phrases[0].events.extend([bass, strong_stab])

        enforce_drop_relock(bank, plan)

        stabs = [e for e in bank.all_events()
                 if e.layer == "stab" and time_to_bar_step(e.time)[0] == 2]
        assert len(stabs) == 1


# ---------------------------------------------------------------------------
# Pre-drop contrast
# ---------------------------------------------------------------------------

class TestPreDropContrast:

    def test_no_contrast_warning_when_silence_precedes_drop(self):
        """HOLD_SILENCE before drop = good contrast, no warning."""
        plan, bank = _plan_with_drop(drop_bar=3, silence_before=True)
        stats = enforce_drop_relock(bank, plan)
        assert stats["drop_missing_contrast"] == 0

    def test_contrast_warning_when_dense_bar_precedes_drop(self):
        """High-density bar before drop = missing contrast."""
        plan, bank = _plan_with_drop(drop_bar=3, silence_before=False)
        # Fill the preceding bar with events (high density)
        for step in range(0, 16, 2):
            tick = step * 6
            beat = tick // 24 + 1
            t = tick % 24
            bank.phrases[0].events.append(
                _event(f"2.{beat}.{t}", layer="kick")
            )
        stats = enforce_drop_relock(bank, plan)
        assert stats["drop_missing_contrast"] >= 1


# ---------------------------------------------------------------------------
# Pression compliance at drop
# ---------------------------------------------------------------------------

class TestPressionDoesNotCreateDropNotes:

    def test_pression_adds_no_events_during_drop(self):
        """compute_bank_timeline must not create note events regardless of
        whether the bank contains a DROP_RELOCK bar."""
        plan, bank = _plan_with_drop(drop_bar=2)
        count_before = len(list(bank.all_events()))
        compute_bank_timeline(
            force=ForceState(),
            behaviour=_behaviour(),
            transition=None,
            cr_mode=Mode.STAB_LEADS,
            bank=bank,
        )
        count_after = len(list(bank.all_events()))
        assert count_after == count_before

    def test_pression_audit_event_creations_zero_at_drop(self):
        plan, bank = _plan_with_drop(drop_bar=2)
        enforce_drop_relock(bank, plan)
        timeline = compute_bank_timeline(
            force=ForceState(),
            behaviour=_behaviour(),
            transition=None,
            cr_mode=Mode.STAB_LEADS,
            bank=bank,
        )
        audit = audit_pression_compliance(timeline, bank, DEFAULT_CC_MAP)
        assert audit["pression_attempted_event_creations"] == 0


# ---------------------------------------------------------------------------
# Debug counters
# ---------------------------------------------------------------------------

class TestDebugCounters:

    def test_all_required_counters_present(self):
        plan, bank = _plan_with_drop()
        stats = enforce_drop_relock(bank, plan)
        required = {
            "drop_regions_detected",
            "drop_relock_events_added",
            "drop_relock_events_adjusted",
            "drop_missing_contrast",
            "drop_illegal_events_suppressed",
        }
        assert required.issubset(stats.keys())

    def test_events_added_counter_accurate(self):
        plan, bank = _plan_with_drop(drop_bar=2)
        # _plan_with_drop seeds a kick at DROP_STEP, so only bass + hook are added
        stats = enforce_drop_relock(bank, plan)
        assert stats["drop_relock_events_added"] >= 2  # at minimum bass + hook

    def test_suppressed_counter_zero_when_no_violations(self):
        plan, bank = _plan_with_drop(drop_bar=2)
        stats = enforce_drop_relock(bank, plan)
        assert stats["drop_illegal_events_suppressed"] == 0

    def test_no_drop_stats_when_no_drop_state(self):
        plan = PhrasePlan(
            bass_pattern=(PlanNote(bar=1, step=0, pitch=36),),
            hook_pattern=(PlanNote(bar=1, step=0, pitch=60),),
            phrase_state={1: PhraseState.RESOLVED_STABLE},
            call_slots={},
            response_slots={},
            silence_mask=SilenceMask({}),
            pressure_curve={1: 0.0},
        )
        bank = _bank(_event("1.1.0"))
        stats = enforce_drop_relock(bank, plan)
        assert stats["drop_regions_detected"] == 0
        assert stats["drop_relock_events_added"] == 0
        assert stats["drop_illegal_events_suppressed"] == 0
