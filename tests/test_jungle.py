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


# ---------------------------------------------------------------------------
# Measurement harness for the dealt bars (J2-J5)
# ---------------------------------------------------------------------------

from functools import lru_cache
from statistics import mean, median, pstdev

from thelmic import jungle

LANE_LAYERS = (("kick",), ("snare", "ghost_snare"), ("hat", "open_hat"))   # low / mid / high


@lru_cache(maxsize=None)
def _dealt_bars(seed: int, banks: int) -> tuple:
    """The drum events of `banks` consecutive banks, one tuple of events per bar."""
    bars = []
    for index in range(banks):
        per_bar = defaultdict(list)
        for event in _bank(index, seed).all_events():
            if event.layer in DRUM_LAYERS:
                per_bar[_bar(event)].append(event)
        bars.extend(tuple(per_bar[b]) for b in range(16))
    return tuple(bars)


def _cells(bar_events) -> tuple[int, ...]:
    """A bar as rhythm.md section 3 measures it: 16 slots x 3 lanes = 48 cells."""
    cells = [0] * 48
    for event in bar_events:
        lane = next(i for i, layers in enumerate(LANE_LAYERS) if event.layer in layers)
        cells[lane * 16 + _slot(event)] = 1
    return tuple(cells)


def _is_fill(bar_events) -> bool:
    return any(event.reason == "jungle_fill" for event in bar_events)


# ---------------------------------------------------------------------------
# J2 - every bar is dealt by chance from the section's distribution
# ---------------------------------------------------------------------------

_OCCUPANCY_SEEDS = range(1, 49)     # 48 sections, 32 bars of each


def _occupancy_by_class() -> dict[str, float]:
    seen = {"spine": [], "signature": [], "eighth": [], "odd": []}
    for seed in _OCCUPANCY_SEEDS:
        signature = jungle.section_for(seed, 0).signature_slots()
        for bar_events in _dealt_bars(seed, 2):
            slots = {_slot(e) for e in bar_events}
            for slot in range(16):
                name = ("spine" if slot in (0, 4, 10, 12) else "signature" if slot in signature
                        else "odd" if slot % 2 else "eighth")
                seen[name].append(slot in slots)
    return {name: mean(hits) for name, hits in seen.items()}


def test_slot_occupancy_matches_the_research_by_class():
    """Spine 100%, signature hits 80-100%, the other 8ths about 67%, the odd 16ths about 34%."""
    occupancy = _occupancy_by_class()
    assert occupancy["spine"] == 1.0
    assert 0.80 <= occupancy["signature"] <= 1.0
    assert occupancy["eighth"] == pytest.approx(0.67, abs=0.05)
    assert occupancy["odd"] == pytest.approx(0.34, abs=0.05)


def test_each_section_has_two_to_four_signature_hits_that_land_in_most_bars():
    counts = set()
    for seed in range(1, 13):
        section = jungle.section_for(seed, 0)
        counts.add(len(section.signature))
        assert 2 <= len(section.signature) <= 4
        assert not section.signature_slots() & {0, 4, 10, 12}
        bars = _dealt_bars(seed, 16)
        for hit in section.signature:
            landed = mean(hit.slot in {_slot(e) for e in bar_events} for bar_events in bars)
            assert 0.76 <= landed <= 1.0, (seed, hit, landed)       # 80-100%, less 256 bars of noise
    assert len(counts) > 1                                          # sections differ in how many


def test_sections_differ_in_where_their_signature_hits_fall():
    assert len({jungle.section_for(seed, 0).signature_slots() for seed in range(1, 13)}) >= 8


def test_no_bar_is_read_from_a_table():
    """Within a section the bars are all dealt: nearly every bar is its own."""
    for seed in (1, 2, 3):
        patterns = {_cells(b) for b in _dealt_bars(seed, 16)}
        assert len(patterns) >= 250             # of 256


def test_the_deal_is_seeded():
    assert _cells(_dealt_bars(1, 1)[5]) != _cells(_dealt_bars(2, 1)[5])
    fresh = generate_bank(3, _dims(), signature_rhythm=_sr(7), heat=0.6, archetype="jungle")
    again = generate_bank(3, _dims(), signature_rhythm=_sr(7), heat=0.6, archetype="jungle")
    key = lambda e: (e.time, e.layer, e.note, e.velocity, e.duration)
    assert [key(e) for e in fresh.all_events()] == [key(e) for e in again.all_events()]


def test_kicks_stay_break_kick_sparse():
    """About 2-3.5 kicks a bar (rhythm.md 10.3, break-kick sections), never beside a spine kick."""
    per_bar = [sum(e.layer == "kick" for e in b) for seed in range(1, 13) for b in _dealt_bars(seed, 16)]
    assert 2.0 <= mean(per_bar) <= 3.5
    for seed in range(1, 13):
        for bar_events in _dealt_bars(seed, 16):
            assert not {_slot(e) for e in bar_events if e.layer == "kick"} & {1, 4, 9, 11, 12, 15}


# ---------------------------------------------------------------------------
# J3 - neighbouring bars do not match; the 4-bar group returns
# ---------------------------------------------------------------------------

_LAG_SEEDS = range(1, 13)           # 12 sections, 256 bars of each


@lru_cache(maxsize=None)
def _lag_profile() -> dict:
    lags = {1: [], 2: [], 3: [], 4: [], 8: []}
    baseline, changed, near_copies, identical = [], [], 0, 0
    for seed in _LAG_SEEDS:
        cells = [_cells(b) for b in _dealt_bars(seed, 16)]
        for lag, values in lags.items():
            values.extend(jungle.similarity(cells[i], cells[i + lag]) for i in range(len(cells) - lag))
        # two bars from the same section, far apart and at unrelated places in their groups
        baseline.extend(jungle.similarity(cells[i], cells[(i * 7 + 37) % len(cells)])
                        for i in range(0, len(cells), 3))
        for a, b in zip(cells, cells[1:]):
            changed.append(sum(x != y for x, y in zip(a, b)))
            near_copies += jungle.similarity(a, b) > 0.8
            identical += a == b
    pairs = len(changed)
    return {"lag": {k: mean(v) for k, v in lags.items()}, "baseline": mean(baseline),
            "changed": median(changed), "near_copies": near_copies / pairs, "identical": identical}


def test_neighbouring_bars_are_as_unalike_as_random_ones():
    """Reference: lag 1 0.355 against a same-section random baseline of 0.356."""
    profile = _lag_profile()
    assert profile["lag"][1] == pytest.approx(profile["baseline"], abs=0.03)
    assert profile["lag"][3] == pytest.approx(profile["baseline"], abs=0.03)


def test_the_four_bar_group_returns():
    """Reference: lag 4 is 0.131 above lag 1 (0.486 against 0.355), lag 2 is 0.081 above (0.436)."""
    lag = _lag_profile()["lag"]
    assert lag[4] - lag[1] == pytest.approx(0.131, abs=0.04)
    assert lag[2] - lag[1] == pytest.approx(0.081, abs=0.04)
    assert lag[1] < lag[2] < lag[4]
    assert lag[8] > lag[1] + 0.08               # reference: lag 8 0.465


def test_the_group_returns_similar_not_identical():
    """Reference: 2% of bars are near-copies (r > 0.8) of the bar before; no bar repeats exactly."""
    profile = _lag_profile()
    assert profile["near_copies"] <= 0.04
    assert profile["identical"] == 0
    for seed in (1, 2, 3):
        cells = [_cells(b) for b in _dealt_bars(seed, 16)]
        same_four_bars_later = mean(cells[i] == cells[i + 4] for i in range(len(cells) - 4))
        assert same_four_bars_later <= 0.02


def test_bars_change_about_a_third_of_what_they_hold():
    """Reference: a median 15 of 48 band cells change from bar to bar, of about 26 onsets.
    The engine deals drum hits, not band onsets - about 16 a bar - so fewer cells can change;
    the share is the same order: more than half as many cells change as there are hits."""
    profile = _lag_profile()
    hits = mean(len(b) for seed in _LAG_SEEDS for b in _dealt_bars(seed, 16))
    assert 8 <= profile["changed"] <= 15
    assert profile["changed"] / hits >= 0.5     # reference: 15 / 26 = 0.58


# ---------------------------------------------------------------------------
# J4 - fills
# ---------------------------------------------------------------------------

def _fill_census():
    bars = [(i, b) for seed in range(1, 25) for i, b in enumerate(_dealt_bars(seed, 16))]
    return bars, [(i, b) for i, b in bars if _is_fill(b)], [(i, b) for i, b in bars if not _is_fill(b)]


def test_a_fill_lands_on_the_four_bar_line_about_one_time_in_four():
    """Reference: 6.5% of bars are fills, one every 15.5 bars: 1 opportunity in 4."""
    bars, fills, _ = _fill_census()
    assert all(i % 4 == 3 for i, _ in fills)
    assert len(fills) / len(bars) == pytest.approx(0.065, abs=0.015)
    assert len(fills) / (len(bars) / 4) == pytest.approx(0.25, abs=0.06)


def test_a_fill_is_a_slightly_busier_brighter_bar_not_a_roll():
    """Reference: 1.23x the onsets of a normal bar; high band 1.30x, low band 1.06x."""
    _, fills, normal = _fill_census()
    count = lambda rows, layers: mean(sum(e.layer in layers for e in b) for _, b in rows)
    assert count(fills, DRUM_LAYERS) / count(normal, DRUM_LAYERS) == pytest.approx(1.23, abs=0.10)
    assert count(fills, {"kick"}) / count(normal, {"kick"}) == pytest.approx(1.0, abs=0.12)
    top = {"hat", "open_hat", "snare", "ghost_snare"}
    assert count(fills, top) / count(normal, top) > 1.2
    for _, bar_events in fills:
        assert all(_slot(e) >= 8 for e in bar_events if e.reason == "jungle_fill")
        assert {0, 10} <= {_slot(e) for e in bar_events if e.layer == "kick"}
        assert {4, 12} <= {_slot(e) for e in bar_events if e.layer == "snare"}
        snare_lane = {_slot(e) for e in bar_events if e.layer in ("snare", "ghost_snare")}
        assert len(snare_lane & set(range(8, 16))) < 8          # not a roll of 16ths
    assert mean(len({_slot(e) for e in b}) for _, b in fills) < 14      # nor a wall of them


# ---------------------------------------------------------------------------
# J5 - ghosts and dynamics
# ---------------------------------------------------------------------------

def test_ghost_snares_are_quiet_varied_and_off_the_spine():
    ghosts = [e for seed in range(1, 13) for b in _dealt_bars(seed, 16) for e in b
              if e.layer == "ghost_snare"]
    bars = 12 * 256
    assert 1.0 <= len(ghosts) / bars <= 3.0                     # a ghost line, not a roll
    velocities = [e.velocity for e in ghosts]
    assert max(velocities) < 60                                 # the spine snare is 118
    assert len(set(velocities)) >= 12 and pstdev(velocities) > 4
    assert not {_slot(e) for e in ghosts} & {0, 4, 10, 12}
    assert all(e.structural_authority is False for e in ghosts)


def test_the_odd_sixteenths_sit_under_the_eighths():
    hats = [e for seed in range(1, 13) for b in _dealt_bars(seed, 16) for e in b if e.layer == "hat"]
    odd = mean(e.velocity for e in hats if _slot(e) % 2)
    even = mean(e.velocity for e in hats if _slot(e) % 2 == 0)
    assert even - odd >= 8                                      # "off-16ths 12 softer"


# ---------------------------------------------------------------------------
# J6 - the sub riff
# ---------------------------------------------------------------------------

BEAT = 60.0 / 174.0                 # durations are seconds at 174 BPM
_SUB_SEEDS, _SUB_BANKS = range(1, 13), 16
_ROOT = 30
_FUNDAMENTAL = _ROOT - 12


@lru_cache(maxsize=None)
def _layer_notes(seed: int, banks: int, layer: str) -> tuple:
    """(global 16th, note, length in beats, reason) for one layer, in time order."""
    notes = []
    for index in range(banks):
        for event in _bank(index, seed).all_events():
            if event.layer == layer:
                notes.append((index * 256 + int(event.musical_step), event.note,
                              event.duration / BEAT, event.reason))
    return tuple(sorted(notes))


@lru_cache(maxsize=None)
def _sub_census() -> dict:
    gaps, lengths, intervals, per_bar, slots = [], [], [], [], []
    bars = falls = phrases = 0
    for seed in _SUB_SEEDS:
        notes = _layer_notes(seed, _SUB_BANKS, "sub")
        count = defaultdict(int)
        for step, _, beats, _ in notes:
            count[step // 16] += 1
            lengths.append(beats)
            slots.append(step % 16)
        for a, b in zip(notes, notes[1:]):
            gaps.append((b[0] - a[0]) / 4.0)
            intervals.append(abs(b[1] - a[1]))
        total = _SUB_BANKS * 16
        bars += total
        per_bar.extend(count[b] for b in range(total))
        fall_bars = {step // 16 for step, _, _, reason in notes if reason == "jungle_fall"}
        phrases += total // 4
        falls += len(fall_bars)
    return {"gaps": gaps, "lengths": lengths, "intervals": intervals, "per_bar": per_bar,
            "slots": slots, "bars": bars, "falls": falls, "phrases": phrases}


def test_sub_notes_start_about_a_beat_apart_and_last_about_0_6_beats():
    """Reference: median gap 1.00 beat, median note 0.60 beats, nothing held past 1.4 bars."""
    census = _sub_census()
    assert median(census["gaps"]) == pytest.approx(1.0, abs=0.25)
    assert median(census["lengths"]) == pytest.approx(0.60, abs=0.12)
    assert max(census["lengths"]) <= 4.0
    assert min(census["lengths"]) >= 0.15       # reference: no short note under about 0.15 beats


def test_sub_changes_pitch_about_0_9_times_a_bar_by_repeats_and_steps():
    """Reference: 0.90 changes a bar; repeats and 1-2 semitone steps are the two largest classes."""
    census = _sub_census()
    intervals = census["intervals"]
    changes = sum(i != 0 for i in intervals)
    assert changes / census["bars"] == pytest.approx(0.90, abs=0.25)
    repeats = mean(i == 0 for i in intervals)
    steps = mean(i in (1, 2) for i in intervals)
    leaps = 1.0 - repeats - steps
    assert repeats + steps >= 0.80
    assert repeats > leaps and steps > leaps
    assert 0 < mean(i == 12 for i in intervals) + 0.02 <= 0.04      # octaves stay rare (1.8%)


def test_sub_is_a_riff_of_struck_notes_not_a_drone_and_not_a_run():
    census = _sub_census()
    assert 2.0 <= mean(census["per_bar"]) <= 3.5        # reference: about 2-3 a bar, median 4 detected
    assert max(census["per_bar"]) < 8                   # 8+ onsets in 1.6% of reference bars
    assert all(slot % 2 == 0 for slot in census["slots"])       # on the 8th grid
    # attacks at the front of the bar (reference: 57% of sub onsets in the first half)
    assert mean(slot < 8 for slot in census["slots"]) == pytest.approx(0.60, abs=0.10)
    first = max(set(census["slots"]), key=census["slots"].count)
    assert first == 0


def test_sub_lives_above_its_fundamental_and_below_the_hooks():
    for seed in _SUB_SEEDS:
        notes = [n for _, n, _, _ in _layer_notes(seed, _SUB_BANKS, "sub")]
        assert min(notes) == _FUNDAMENTAL               # it does fall to the fundamental
        assert max(notes) <= _FUNDAMENTAL + 10          # and stays within a seventh of it
        assert max(notes) < 58                          # hooks start at 233 Hz


def test_about_one_phrase_in_two_or_three_falls_to_the_fundamental_and_leaves_a_gap():
    census = _sub_census()
    assert 1 / 3 - 0.06 <= census["falls"] / census["phrases"] <= 1 / 2 + 0.06
    for seed in (1, 2, 3):
        notes = _layer_notes(seed, _SUB_BANKS, "sub")
        for bar in {step // 16 for step, _, _, reason in notes if reason == "jungle_fall"}:
            assert bar % 4 == 3                                         # the phrase's last bar
            in_bar = [n for n in notes if n[0] // 16 == bar]
            step, note, beats, reason = in_bar[-1]
            assert reason == "jungle_fall" and note == _FUNDAMENTAL     # the low "dum"
            assert all(n[1] > _FUNDAMENTAL for n in in_bar[:-1])        # reached from above
            assert (step % 16) / 4.0 + beats <= 3.0 + 0.01             # then at least a beat of gap


def _bar_signature(notes, bar):
    return tuple((s % 16, n, round(b, 3)) for s, n, b, r in notes if s // 16 == bar and r != "jungle_fall")


def test_riffs_are_4_or_8_bars_and_are_held_about_11_bars():
    """Reference: 4-bar or 8-bar riffs; runs of median 11 bars, interquartile 7-15."""
    held, periods = [], []
    for seed in _SUB_SEEDS:
        riff, bar = jungle.riff_at(seed, 0), 0
        while bar < 2000:
            riff = jungle.riff_at(seed, bar)
            assert riff.start_bar == bar and riff.start_bar % 4 == 0    # changes on the phrase grid
            held.append(riff.held_bars)
            periods.append(riff.period)
            bar += riff.held_bars
    assert set(periods) == {4, 8}
    assert mean(p == 4 for p in periods) == pytest.approx(0.56, abs=0.08)    # 39% : 31%
    assert 8 <= median(held) <= 12 and mean(held) == pytest.approx(11.0, abs=1.5)
    assert min(held) >= 7 and max(held) <= 16


def test_a_riff_repeats_as_written_then_changes():
    """Inside a riff the bar one period back is the same bar; across a change it is not."""
    for seed in (1, 2, 3, 4):
        notes = _layer_notes(seed, _SUB_BANKS, "sub")
        fall_bars = {s // 16 for s, _, _, r in notes if r == "jungle_fall"}
        same = changed = different = 0
        for bar in range(_SUB_BANKS * 16):
            riff = jungle.riff_at(seed, bar)
            back = bar - riff.period
            if bar in fall_bars or back in fall_bars or bar + 1 in fall_bars or back + 1 in fall_bars:
                continue        # a fall rewrites its bar and trims the bar before's last note
            if back >= riff.start_bar:
                assert _bar_signature(notes, bar) == _bar_signature(notes, back), (seed, bar)
                same += 1
            elif back >= 0 and bar - riff.start_bar < 4 and bar % 4 == 0:
                changed += 1
                different += _bar_signature(notes, bar) != _bar_signature(notes, back)
        assert same > 60
        assert different / changed >= 0.7       # a new riff is nearly always a different first bar


def test_the_engine_says_what_the_sub_instrument_must_do():
    """Sound the engine cannot make: published for the instrument, numbers from bass.md."""
    voice = jungle.SUB_VOICE
    assert voice["waveform"] == "sine"
    assert voice["pitch_drop_semitones"] == 30 and voice["pitch_drop_tau_ms"] == 12
    assert voice["sidechain_db"] == 0.0


# ---------------------------------------------------------------------------
# J7 - hooks
# ---------------------------------------------------------------------------

_HOOK_SEEDS, _HOOK_BANKS = range(1, 13), 16


@lru_cache(maxsize=None)
def _hook_events(seed: int) -> dict:
    """bar -> ((slot, note, beats), ...): one hook event per bar that has one."""
    events = defaultdict(list)
    for step, note, beats, _ in _layer_notes(seed, _HOOK_BANKS, "hook"):
        events[step // 16].append((step % 16, note, round(beats, 3)))
    return {bar: tuple(sorted(notes)) for bar, notes in events.items()}


def _hook_length(notes) -> float:
    return max(slot / 4.0 + beats for slot, _, beats in notes) - min(slot for slot, _, _ in notes) / 4.0


def test_a_hook_sounds_in_about_3_bars_of_every_8():
    """Reference: 39% of bars, 3.1 in every 8; per section 21% to 58%."""
    share = mean(len(_hook_events(seed)) / (_HOOK_BANKS * 16) for seed in _HOOK_SEEDS)
    assert share == pytest.approx(0.39, abs=0.05)
    for seed in _HOOK_SEEDS:
        assert 0.21 <= len(_hook_events(seed)) / (_HOOK_BANKS * 16) <= 0.58
    # and the old window (bars 1, 2, 5, 13 of 16) is gone: hooks reach most positions
    positions = {bar % 16 for seed in _HOOK_SEEDS for bar in _hook_events(seed)}
    assert len(positions) >= 12


def test_hooks_are_fragments():
    """Reference: median 1.2 beats, 81% under 2 beats, 3% as long as a bar."""
    lengths = [_hook_length(notes) for seed in _HOOK_SEEDS for notes in _hook_events(seed).values()]
    assert median(lengths) == pytest.approx(1.2, abs=0.3)
    assert mean(length < 2.0 for length in lengths) == pytest.approx(0.81, abs=0.08)
    assert max(lengths) <= 4.0


def test_hooks_sit_at_233_to_392_hz_above_the_sub():
    notes = [n for seed in _HOOK_SEEDS for event in _hook_events(seed).values() for _, n, _ in event]
    assert min(notes) >= 58 and max(notes) <= 67            # A#3 233 Hz .. G4 392 Hz
    for root in (24, 29, 30, 35, 41, 47):                   # whatever the key
        bank = generate_bank(0, _dims(), signature_rhythm=_sr(1, root), archetype="jungle")
        hook = [e.note for e in bank.all_events() if e.layer == "hook"]
        assert hook and min(hook) >= 58 and max(hook) <= 67
        # the 5th, the minor 3rd, the root and the 4th of the key
        assert {(n - root) % 12 for n in hook} <= {7, 3, 0, 5}


def test_a_hook_shape_comes_back_about_three_times_at_4_or_8_bars_then_is_replaced():
    """Reference: recurring shapes return a median of 3 times, at 4-8 bar spacing; most never return."""
    appearances, spacings, one_offs, shapes = [], [], 0, 0
    for seed in _HOOK_SEEDS:
        seen = defaultdict(list)
        for bar, notes in sorted(_hook_events(seed).items()):
            seen[notes].append(bar)
        for bars in seen.values():
            shapes += 1
            if len(bars) == 1:
                one_offs += 1
                continue
            appearances.append(len(bars))
            spacings.extend(b - a for a, b in zip(bars, bars[1:]))
    assert median(appearances) == 3
    assert mean(count <= 4 for count in appearances) >= 0.90    # nothing plays every bar for 16
    assert mean(s in (4, 8) for s in spacings) >= 0.80
    assert one_offs / shapes >= 0.25                # reference: 61% of shapes never return


def test_the_kick_pattern_thins_under_a_hook():
    """Reference: low-band flux -2.1 dB while a hook sounds; the sub is not turned down."""
    under, clear, sub_under, sub_clear = [], [], [], []
    for seed in _HOOK_SEEDS:
        hook_bars = set(_hook_events(seed))
        sub = _layer_notes(seed, _HOOK_BANKS, "sub")
        velocity = defaultdict(list)
        for index in range(_HOOK_BANKS):
            for e in _bank(index, seed).all_events():
                if e.layer == "sub":
                    velocity[index * 16 + _bar(e)].append(e.velocity)
        for bar, bar_events in enumerate(_dealt_bars(seed, _HOOK_BANKS)):
            if _is_fill(bar_events):
                continue
            kicks = sum(e.layer == "kick" for e in bar_events)
            (under if bar in hook_bars else clear).append(kicks)
            (sub_under if bar in hook_bars else sub_clear).extend(velocity[bar])
        assert sub
    assert mean(under) < mean(clear) - 0.1
    assert min(under) >= 2                                      # the spine kicks stay
    assert mean(sub_under) == pytest.approx(mean(sub_clear), abs=3)


def test_no_hook_and_no_sub_when_sparsity_takes_them_out():
    layers = lambda sparsity: {e.layer for e in _bank(0, 1, sparsity).all_events()}
    assert {"hook", "sub"} <= layers(0.2)
    assert "hook" not in layers(0.55) and "sub" in layers(0.55)         # the hook leaves first
    assert not {"hook", "sub"} & layers(0.70)
