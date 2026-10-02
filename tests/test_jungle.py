"""The JUNGLE archetype, measured against its own research.

Rules: musical_rules.md, "Jungle - Measured Rules" (J0-J11). The numbers the
assertions use are the research numbers quoted there, from
tracks/2026-09-16_reaper/ and tracks/2026-09-16_jungle_scene_rules.md.

Every test reads final output: the events generate_bank returns.
"""

from __future__ import annotations

from collections import defaultdict

import pytest

from thelmic.archetypes import PATTERNS, RhythmicArchetype, select_archetype
from thelmic.dimensions import Dimensions
from thelmic.landscape_map import SignatureRhythm, _derive_bass_steps
from thelmic.note_generation_chain import generate_bank


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------

DRUM_LAYERS = ("kick", "snare", "ghost_snare", "hat", "open_hat")


def _sr(seed: int = 1, root: int = 30) -> SignatureRhythm:
    # The biases are AMEN's: asking for jungle by name must win over them.
    return SignatureRhythm(
        id="jungle", base_pattern_seed=seed, density_bias=0.80, syncopation_bias=0.30,
        stability_bias=0.30, root_note=root, bass_steps=_derive_bass_steps(0.80, 0.30),
        hook_motif_seed=seed * 31 + 7,
    )


def _dims(sparsity: float = 0.2) -> Dimensions:
    return Dimensions(0.30, 0.2, sparsity, 0.0, 0.0)


def _bank(index: int = 0, seed: int = 1, sparsity: float = 0.2, **extra):
    extra.setdefault("phrases_until_drop", 8)
    return generate_bank(index, _dims(sparsity), signature_rhythm=_sr(seed),
                         heat=0.6, archetype="jungle", **extra)


def _slot(event) -> int:
    return int(event.musical_step) % 16


def _bar(event) -> int:
    """0-15: the bar within the bank."""
    return int(event.musical_step) // 16


def _bars(events, layers) -> dict[int, set[int]]:
    """bar -> the slots on which any of the layers sounds."""
    out: dict[int, set[int]] = defaultdict(set)
    for event in events:
        if event.layer in layers:
            out[_bar(event)].add(_slot(event))
    return out


# ---------------------------------------------------------------------------
# J0 - selection, and the callers that must not notice
# ---------------------------------------------------------------------------

# mindstream's table (mindstream/composer.py): it refuses to start if any of
# these stops selecting its archetype.
_SELECTOR_CONTRACT = {
    "half_step": (0.30, 0.30, 0.60), "two_step": (0.30, 0.60, 0.60),
    "four_on_the_floor": (0.55, 0.30, 0.60), "rolling": (0.80, 0.30, 0.60),
    "shuffled_two_step": (0.30, 0.60, 0.30), "stutter": (0.55, 0.60, 0.30),
    "amen": (0.80, 0.30, 0.30), "breakbeat_hardcore": (0.80, 0.60, 0.30),
    "happy_hardcore": (0.90, 0.30, 0.10), "gabber": (0.90, 0.60, 0.10),
}

# The ten inherited tables, as they were before JUNGLE: (kick, snare, closed hat, open hat, sub).
_INHERITED_TABLES = {
    "half_step": ({0, 8}, {4, 12}, {0, 2, 4, 6, 8, 10, 12, 14}, set(), {0}),
    "two_step": ({0, 6, 12}, {4, 12}, {0, 2, 4, 6, 8, 10, 12}, {14}, {2, 10}),
    "shuffled_two_step": ({0, 5, 8}, {4, 12}, {0, 5, 8, 10, 13}, {3}, {2, 11}),
    "stutter": ({0, 3, 8, 11}, {4, 12}, set(range(16)), set(), {0, 3}),
    "rolling": ({0, 4, 10, 13}, {4, 12}, {0, 4, 6, 8, 12, 14}, {2, 10}, {0, 12}),
    "breakbeat_hardcore": ({0, 3, 7, 10}, {4, 8, 12}, {0, 2, 3, 5, 6, 8, 9, 11, 12, 13, 14}, {4}, {0, 12}),
    "amen": ({0, 3, 8, 10}, {4, 7, 12}, {0, 2, 3, 6, 8, 9, 10, 13, 14}, {5, 12}, {0, 12}),
    "four_on_the_floor": ({0, 4, 8, 12}, {4, 12}, {0, 2, 4, 8, 10, 12}, {6, 14}, {0, 4, 8, 12}),
    "happy_hardcore": ({0, 4, 8, 12}, {4, 12}, {0, 2, 6, 8, 10, 14}, {4, 12}, {0, 4, 8, 12}),
    "gabber": (set(range(16)), {4, 12}, {0, 2, 4, 6, 8, 10, 12, 14}, {7, 15}, set(range(16))),
}


def test_selector_still_returns_the_ten_inherited_archetypes():
    for name, biases in _SELECTOR_CONTRACT.items():
        assert select_archetype(*biases).value == name


def test_selector_never_returns_jungle():
    grid = [i / 20 for i in range(21)]
    selected = {select_archetype(d, s, st) for d in grid for s in grid for st in grid}
    assert RhythmicArchetype.JUNGLE not in selected


def test_inherited_tables_are_unchanged():
    for name, (kick, snare, closed, opened, sub) in _INHERITED_TABLES.items():
        pattern = PATTERNS[RhythmicArchetype(name)]
        assert pattern.kick_steps == kick, name
        assert pattern.snare_steps == snare, name
        assert pattern.closed_hat_steps == closed, name
        assert pattern.open_hat_steps == opened, name
        assert pattern.sub_steps == sub, name


def test_a_caller_that_does_not_ask_for_jungle_gets_what_it_got_before():
    sr = _sr()
    before = generate_bank(0, _dims(), signature_rhythm=sr, heat=0.6, phrases_until_drop=8)
    asked = generate_bank(0, _dims(), signature_rhythm=sr, heat=0.6, phrases_until_drop=8,
                          archetype="amen")
    key = lambda e: (e.time, e.layer, e.note, e.velocity, e.duration)
    assert sorted(map(key, before.all_events())) == sorted(map(key, asked.all_events()))
    assert any(e.layer == "bass" for e in before.all_events())      # AMEN has a mid bass


def test_jungle_is_asked_for_by_name_or_by_member():
    key = lambda e: (e.time, e.layer, e.note, e.velocity, e.duration)
    by_name = generate_bank(0, _dims(), signature_rhythm=_sr(), archetype="jungle")
    by_member = generate_bank(0, _dims(), signature_rhythm=_sr(), archetype=RhythmicArchetype.JUNGLE)
    assert sorted(map(key, by_name.all_events())) == sorted(map(key, by_member.all_events()))
    with pytest.raises(ValueError):
        generate_bank(0, _dims(), signature_rhythm=_sr(), archetype="polka")
    with pytest.raises(ValueError):
        generate_bank(0, archetype="jungle")


def test_events_keep_the_shape_callers_read():
    events = _bank().all_events()
    assert events
    for event in events:
        bar, beat, tick = (int(x) for x in event.time.split("."))
        assert 1 <= bar <= 16 and 1 <= beat <= 4 and 0 <= tick < 24
        assert 0 <= event.note <= 127 and 1 <= event.velocity <= 127
        assert event.duration > 0 and event.active is True
        assert isinstance(event.layer, str)


# ---------------------------------------------------------------------------
# J1 - the spine
# ---------------------------------------------------------------------------

def test_spine_is_in_every_bar():
    """Kick on 1 and the "and" of 3, snares on 2 and 4: certain, in all 16 bars."""
    for index in range(4):
        events = _bank(index).all_events()
        kicks, snares = _bars(events, {"kick"}), _bars(events, {"snare"})
        for bar in range(16):
            assert {0, 10} <= kicks[bar], (index, bar)
            assert {4, 12} <= snares[bar], (index, bar)


def test_no_kick_under_the_beat_4_snare_and_no_four_on_the_floor():
    for index in range(4):
        kicks = _bars(_bank(index).all_events(), {"kick"})
        for bar in range(16):
            assert 12 not in kicks[bar] and 4 not in kicks[bar]


def test_spine_is_the_loudest_thing_in_its_lane():
    events = _bank().all_events()
    for layer, slots in (("kick", {0, 10}), ("snare", {4, 12})):
        spine = [e.velocity for e in events if e.layer == layer and _slot(e) in slots]
        rest = [e.velocity for e in events if e.layer == layer and _slot(e) not in slots]
        assert min(spine) >= 100
        assert not rest or max(rest) < min(spine)


# ---------------------------------------------------------------------------
# J5 - straight, quantised
# ---------------------------------------------------------------------------

def test_every_hit_is_on_the_sixteenth_grid():
    """52% swing is straight: no hit is moved off the grid."""
    for event in _bank().all_events():
        assert int(event.time.split(".")[2]) % 6 == 0
        assert float(event.musical_step) == int(event.musical_step)


# ---------------------------------------------------------------------------
# J6, J8 - one low voice, nothing sustained
# ---------------------------------------------------------------------------

def test_no_mid_bass_no_drones_no_call_and_response():
    layers = {e.layer for index in range(4) for e in _bank(index).all_events()}
    assert "sub" in layers
    assert "bass" not in layers
    assert not {name for name in layers if name.startswith("drone")}
    assert not layers & {"call", "response"}


def test_generation_is_reproducible():
    key = lambda e: (e.time, e.layer, e.note, e.velocity, e.duration)
    assert [key(e) for e in _bank(3).all_events()] == [key(e) for e in _bank(3).all_events()]
