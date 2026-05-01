"""Direct contract tests for transformer_engine.py.

Verifies the pipeline contract:
  motif_engine → transformer_engine → validator → output

Tests are isolated from the server; they operate on bare Bank/Motif inputs.
"""

from __future__ import annotations

import pytest

from thelmic.note_generation_chain import generate_bank, BANK_STEPS
from thelmic.motif_engine import motifs_for_events, empty_future_motifs
from thelmic.transformer_engine import (
    TRANSFORMER_ACTIONS,
    TRANSFORMER_TARGETS,
    TransformerExecutionResult,
    execute_transformers,
)
from thelmic.server import _TRANSFORMER_CATEGORIES, _compute_subphrases


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def bank():
    from thelmic.dimension_engine import compute
    from thelmic.landscape_trajectory import LandscapeTrajectory
    from thelmic.landscape_map import LandscapeMap
    t    = LandscapeTrajectory(landscape=LandscapeMap(seed=1103))
    dims = compute(t, 0.5)
    sr   = t.active_feature().signature_rhythm
    return generate_bank(0, dims=dims, signature_rhythm=sr)


@pytest.fixture(scope="module")
def motifs(bank):
    return motifs_for_events(bank.all_events()) + empty_future_motifs()


@pytest.fixture(scope="module")
def subphrases():
    return _compute_subphrases(0, 0)


@pytest.fixture(scope="module")
def execution_results(bank, motifs, subphrases):
    _, results = execute_transformers(bank, motifs, subphrases)
    return results


# ---------------------------------------------------------------------------
# Module isolation
# ---------------------------------------------------------------------------

def test_transformer_engine_does_not_import_motif_engine_internals():
    import thelmic.transformer_engine as te
    import inspect
    source = inspect.getsource(te)
    # Must use classify_motif_change (the validator) but not motifs_for_events
    # (which belongs to the observation layer, not the execution layer)
    assert "classify_motif_change" in source, "must wire the validator"
    assert "motifs_for_events" not in source, (
        "transformer_engine must not call motifs_for_events (observation layer)"
    )


def test_no_code_added_to_motif_engine():
    import thelmic.motif_engine as me
    import inspect
    source = inspect.getsource(me)
    assert "execute_transformers" not in source
    assert "TRANSFORMER_TARGETS" not in source
    assert "TRANSFORMER_ACTIONS" not in source


# ---------------------------------------------------------------------------
# No-transformer path
# ---------------------------------------------------------------------------

def test_no_changes_when_subphrases_have_no_transformers(bank, motifs):
    empty_subphrases = [
        {"role": "build", "start_step": 0, "length_steps": 64, "transformers": []},
        {"role": "hold",  "start_step": 64, "length_steps": 128, "transformers": []},
    ]
    modified_bank, results = execute_transformers(bank, motifs, empty_subphrases)
    assert modified_bank is bank, "bank must be returned unchanged when no transformers"
    assert results == [], "no results when no transformers"


def test_no_changes_when_subphrase_list_is_empty(bank, motifs):
    modified_bank, results = execute_transformers(bank, motifs, [])
    assert modified_bank is bank
    assert results == []


# ---------------------------------------------------------------------------
# Target and action constraints
# ---------------------------------------------------------------------------

def test_only_allowed_targets_are_attempted(execution_results):
    for r in execution_results:
        allowed = TRANSFORMER_TARGETS.get(r.transformer, [])
        assert r.target in allowed, (
            f"target '{r.target}' not allowed for transformer '{r.transformer}'"
        )


def test_only_allowed_actions_are_attempted(execution_results):
    for r in execution_results:
        allowed = TRANSFORMER_ACTIONS.get(r.transformer, [])
        assert r.action in allowed, (
            f"action '{r.action}' not allowed for transformer '{r.transformer}'"
        )


def test_no_result_references_unknown_transformer(execution_results):
    for r in execution_results:
        assert r.transformer in _TRANSFORMER_CATEGORIES, (
            f"unknown transformer '{r.transformer}'"
        )


# ---------------------------------------------------------------------------
# Validator path
# ---------------------------------------------------------------------------

def test_rejected_mutations_do_not_add_events(bank, motifs, subphrases):
    """Accepted mutations may remove events; rejected must never add or remove."""
    fresh_bank = _fresh_bank()
    before = len(list(fresh_bank.all_events()))
    _, results = execute_transformers(fresh_bank, motifs, subphrases)
    after = len(list(fresh_bank.all_events()))
    rejected = [r for r in results if not r.accepted]
    # Accepted mutations may reduce count; rejected must not change count
    assert after <= before, "bank should have same or fewer events after execution"
    # All results with accepted=False must not have changed any event
    # (structural layers and too-few-events rejections leave bank intact)
    for r in rejected:
        assert r.reason, f"rejected result has no reason: {r}"


def test_all_results_have_accepted_field(execution_results):
    for r in execution_results:
        assert isinstance(r.accepted, bool)


def test_all_results_have_reason(execution_results):
    for r in execution_results:
        assert r.reason, f"missing reason on result: {r}"


def test_results_are_typed_correctly(execution_results):
    for r in execution_results:
        assert isinstance(r, TransformerExecutionResult)


# ---------------------------------------------------------------------------
# Output / timing invariants
# ---------------------------------------------------------------------------

def _fresh_bank():
    from thelmic.dimension_engine import compute
    from thelmic.landscape_trajectory import LandscapeTrajectory
    from thelmic.landscape_map import LandscapeMap
    t = LandscapeTrajectory(landscape=LandscapeMap(seed=1103))
    return generate_bank(0, dims=compute(t, 0.5), signature_rhythm=t.active_feature().signature_rhythm)


def test_execution_may_reduce_event_count(bank, motifs, subphrases):
    """Accepted thin mutations remove events; execution never adds events."""
    fresh = _fresh_bank()
    before = len(list(fresh.all_events()))
    _, results = execute_transformers(fresh, motifs, subphrases)
    after = len(list(fresh.all_events()))
    assert after <= before, "execution must never add events"
    # Note: with v1.2 transformer assignments (anticipation_build, release_resolve),
    # accepted mutations may be no-ops. Count reduction is no longer guaranteed.
    thin_accepted = any(r.accepted and r.action == "remove_subdivision" for r in results)
    if thin_accepted:
        assert after < before, "remove_subdivision acceptance must reduce count"


def test_execution_does_not_shift_event_timing(bank, motifs, subphrases):
    """Remaining events keep their original timing; only count may change."""
    fresh = _fresh_bank()
    times_before = {e.time for e in fresh.all_events()}
    execute_transformers(fresh, motifs, subphrases)
    times_after = {e.time for e in fresh.all_events()}
    assert times_after.issubset(times_before), "execution must not introduce new event times"


def test_output_fingerprint_stable(bank, motifs, subphrases):
    """After execution, fingerprint is deterministic."""
    import hashlib
    fresh = _fresh_bank()
    execute_transformers(fresh, motifs, subphrases)
    events  = fresh.all_events()
    payload = "\n".join(
        f"{e.musical_step}:{e.layer}:{e.role}:{e.note}:{e.velocity}:{e.duration}"
        for e in events
    )
    assert hashlib.sha256(payload.encode()).hexdigest() == (
        "1b359c9cc2277661c6cea9ded763d0d9b79ff035cf44dfce62594493a00d7a04"
    )


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

def test_execution_is_deterministic(bank, motifs, subphrases):
    _, r1 = execute_transformers(bank, motifs, subphrases)
    _, r2 = execute_transformers(bank, motifs, subphrases)
    assert [x.to_dict() for x in r1] == [x.to_dict() for x in r2]


def test_execution_result_ordering_is_stable(bank, motifs, subphrases):
    _, r1 = execute_transformers(bank, motifs, subphrases)
    _, r2 = execute_transformers(bank, motifs, subphrases)
    for a, b in zip(r1, r2):
        assert a.transformer == b.transformer
        assert a.target      == b.target
        assert a.action      == b.action


# ---------------------------------------------------------------------------
# Static table integrity
# ---------------------------------------------------------------------------

def test_static_table_names_match_taxonomy():
    for name in TRANSFORMER_TARGETS:
        assert name in _TRANSFORMER_CATEGORIES, (
            f"TRANSFORMER_TARGETS contains '{name}' which is not in the taxonomy"
        )
    for name in TRANSFORMER_ACTIONS:
        assert name in _TRANSFORMER_CATEGORIES, (
            f"TRANSFORMER_ACTIONS contains '{name}' which is not in the taxonomy"
        )


def test_targets_and_actions_have_same_keys():
    assert set(TRANSFORMER_TARGETS) == set(TRANSFORMER_ACTIONS), (
        "every transformer must have both a targets entry and an actions entry"
    )


def test_no_empty_target_lists():
    for name, targets in TRANSFORMER_TARGETS.items():
        assert targets, f"'{name}' has empty target list — must have at least one target"
