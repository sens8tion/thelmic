"""Jungle - bars dealt by chance from a section's distribution, the sub's
riff, and where the hooks go.

Rules: musical_rules.md, "Jungle - Measured Rules" (J2-J10).

The other archetypes read a bar from a step table. A jungle bar is dealt: a
section holds a chance for every 16th slot in each of three lanes, and every
bar is a fresh deal from it. The spine is certain, a few signature hits are
nearly so, the other 8th positions land about two times in three and the odd
16ths about one time in three.

A deal is seeded. The same seed and the same bar number always give the same
bar, so "chance" here is the Determinism Contract's kind: no state, no clock,
nothing drawn at run time.

The sub is the opposite case: a riff is written once, from the seed, and
repeats as written. Hooks are short shapes that come back about three times.

This module decides which slots sound, and how hard. It makes no events; the
voices in thelmic/voices/jungle.py do that.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache


STEPS_PER_BAR = 16
GROUP_BARS    = 4                       # the unit that returns (J3)
LANES         = ("low", "mid", "high")  # kick / snare and ghost snare / hat

# J1 - the spine: certain in every bar.
SPINE: dict[str, tuple[int, ...]] = {"low": (0, 10), "mid": (4, 12)}
SPINE_SLOTS = frozenset(s for slots in SPINE.values() for s in slots)

# J2 - chance per lane on a slot that is neither spine nor signature, as
# (8th position, odd 16th). The lanes are dealt independently, so the chance
# that the slot carries anything is 1 - (1-high)(1-mid)(1-low):
#   8th position: 1 - 0.50 * 0.78 * 0.85 = 0.67   (reference: 0.67)
#   odd 16th:     1 - 0.78 * 0.88 * 0.96 = 0.34   (reference: 0.34)
_BETWEEN: dict[str, tuple[float, float]] = {
    "high": (0.50, 0.22),
    "mid":  (0.22, 0.12),
    "low":  (0.15, 0.04),
}
# No kick a 16th either side of a spine kick: fast double kicks are one of the
# brief's top mistakes at this tempo. The hat takes up the slack so the slot's
# chance is still 0.34: 1 - 0.75 * 0.88.
_BESIDE_SPINE_KICK      = frozenset({1, 9, 11, 15})
_HAT_BESIDE_SPINE_KICK  = 0.25
_BESIDE_SPINE_SNARE     = frozenset({3, 5, 11, 13})
# The carrier over a spine hit. Reference high-band occupancy on the beats: 0.74-0.87.
_HAT_ON_SPINE           = 0.80

# J2 - signature hits: 2-4 positions a section lands in 80-100% of its bars.
_SIGNATURE_SLOTS  = (2, 3, 5, 6, 7, 8, 11, 13, 14, 15)
_SIGNATURE_CHANCE = (0.80, 1.00)

# J3 - how hard each position in the 4-bar group leans the section's chances
# its own way. 0 = four bars from one distribution (no group, lag 4 = lag 1);
# 1 = four fixed bars (a loop). Tuned against the reference's lag profile,
# where lag 4 sits 0.131 above lag 1 (0.486 against 0.355) and lag 2 sits
# 0.081 above it (0.436): these two values give 0.130 and 0.082.
_GROUP_LEAN     = 0.55
# Chance that bar 3 of the group leans the way bar 1 does, and bar 4 the way
# bar 2 does: the 2-bar sub-period under the 4-bar one.
_HALF_GROUP_TIE = 0.70

# J4 - fills: the last bar of a group, about 1 group in 4, busier in the top
# two lanes in the second half of the bar.
FILL_CHANCE = 0.25
_FILL_LIFT  = 0.45
_FILL_FROM  = 8

# J9 - drops are subtraction. Before a drop the low end is out for this many
# 16ths while the break runs on: 1.25 bars (reference: a median 1.2 bars).
LOW_END_OUT_STEPS = 20
# A roll before 27% of drops, a gap before 27% - and then one 16th of it.
ROLL_CHANCE = 0.27
GAP_CHANCE  = 0.27
_ROLL_FROM  = 8              # a roll is the last half bar, not a build
_GAP_SLOT   = 15             # the last 16th before the drop; never a spine slot
# The first bar of a drop has fewer onsets than a groove bar (21 band-onsets
# against 32): everything that is neither spine nor signature is dealt at half
# its chance.
_DROP_BAR_THIN = 0.50
# The sub's first bar of a drop: one held note on the fundamental, the
# bassline proper from bar 2 (drops.md section 4).
DROP_NOTE_BEATS = 3.0
# J10 - a breakdown is busier on top, not thinner: onset density up about 0.6
# a bar. With the sub out, every possible hit in the top two lanes moves this
# far towards certain.
_BREAKDOWN_LIFT = 0.04

# Tags that keep the separate draws apart.
_T_SIGNATURE, _T_LEAN, _T_TIE, _T_DEAL, _T_FILL, _T_VELOCITY, _T_DROP = range(1, 8)

_MASK = 0xFFFFFFFFFFFFFFFF


def _unit(*keys: int) -> float:
    """A reproducible number in [0, 1) from integer keys (splitmix64 mixing)."""
    h = 0x9E3779B97F4A7C15
    for key in keys:
        h = (h + (int(key) & _MASK) + 0x9E3779B97F4A7C15) & _MASK
        h ^= h >> 30
        h = (h * 0xBF58476D1CE4E5B9) & _MASK
        h ^= h >> 27
        h = (h * 0x94D049BB133111EB) & _MASK
        h ^= h >> 31
    return (h >> 11) / float(1 << 53)


@dataclass(frozen=True)
class SignatureHit:
    lane:   str
    slot:   int
    chance: float


@dataclass(frozen=True)
class JungleSection:
    """What a section holds still while its bars are re-dealt (scene rules)."""
    seed:      int
    index:     int
    signature: tuple[SignatureHit, ...]
    # chance[lane index][slot]: the section's distribution.
    chance:    tuple[tuple[float, ...], ...]
    # lean[position in group][lane index][slot]: the same, as each of the four
    # bars of the group sees it.
    lean:      tuple[tuple[tuple[float, ...], ...], ...]

    def signature_slots(self) -> frozenset[int]:
        return frozenset(hit.slot for hit in self.signature)


@dataclass(frozen=True)
class Hit:
    lane:     str
    slot:     int
    kind:     str    # "spine" | "signature" | "between" | "fill" | "roll"
    velocity: int


@dataclass(frozen=True)
class BarDeal:
    global_bar: int
    is_fill:    bool
    hits:       tuple[Hit, ...]

    def cells(self) -> tuple[int, ...]:
        """The bar as the 48-cell vector of rhythm.md section 3 (16 slots x 3 lanes)."""
        out = [0] * (len(LANES) * STEPS_PER_BAR)
        for hit in self.hits:
            out[LANES.index(hit.lane) * STEPS_PER_BAR + hit.slot] = 1
        return tuple(out)


# ---------------------------------------------------------------------------
# The section's distribution
# ---------------------------------------------------------------------------

def _base_chance(lane: str, slot: int) -> float:
    if slot in SPINE.get(lane, ()):
        return 1.0
    if slot in SPINE_SLOTS:
        return _HAT_ON_SPINE if lane == "high" else 0.0
    odd = slot % 2 == 1
    if odd and slot in _BESIDE_SPINE_KICK:
        if lane == "low":
            return 0.0
        if lane == "high":
            return _HAT_BESIDE_SPINE_KICK
    return _BETWEEN[lane][1 if odd else 0]


def _signature_for(seed: int, index: int) -> tuple[SignatureHit, ...]:
    count = 2 + int(_unit(seed, index, _T_SIGNATURE, 0) * 3)          # 2, 3 or 4
    ranked = sorted(_SIGNATURE_SLOTS, key=lambda s: _unit(seed, index, _T_SIGNATURE, 1, s))
    hits: list[SignatureHit] = []
    for slot in ranked:
        if len(hits) == count:
            break
        u = _unit(seed, index, _T_SIGNATURE, 2, slot)
        if slot == 8:                               # beat 3: a kick or a snare
            lane = "low" if u < 0.5 else "mid"
        elif slot % 2 == 0:                         # an "and": snare, kick or open hat
            lane = "mid" if u < 0.40 else "low" if u < 0.70 else "high"
        elif slot in _BESIDE_SPINE_KICK:            # no kick beside a spine kick
            lane = "mid" if u < 0.75 else "high"
        else:                                       # an "e" or "a": a drag or a pickup
            lane = "mid" if u < 0.55 else "low" if u < 0.85 else "high"
        if any(hit.lane == lane and abs(hit.slot - slot) == 1 for hit in hits):
            continue                                # two in a row in one lane is a roll, not a signature
        if lane == "mid" and any(hit.lane == "mid" and abs(hit.slot - slot) == 2
                                 and (hit.slot + slot) // 2 in SPINE["mid"] for hit in hits):
            continue                                # one drag to a backbeat, not one each side
        low, high = _SIGNATURE_CHANCE
        chance = low + (high - low) * _unit(seed, index, _T_SIGNATURE, 3, slot)
        hits.append(SignatureHit(lane, slot, round(chance, 3)))
    return tuple(sorted(hits, key=lambda hit: hit.slot))


@lru_cache(maxsize=256)
def section_for(seed: int, index: int = 0) -> JungleSection:
    """The section with this index: its signature hits and its chances."""
    signature = _signature_for(seed, index)
    signed = {(hit.lane, hit.slot): hit.chance for hit in signature}
    chance = tuple(
        tuple(signed.get((lane, slot), _base_chance(lane, slot)) for slot in range(STEPS_PER_BAR))
        for lane in LANES
    )

    def leaned(position: int, lane_i: int, slot: int) -> float:
        p = chance[lane_i][slot]
        if p <= 0.0 or p >= 1.0 or (LANES[lane_i], slot) in signed:
            return p            # spine, silence and signature hits do not lean
        source = position
        if position >= 2 and _unit(seed, index, _T_TIE, position, lane_i, slot) < _HALF_GROUP_TIE:
            source = position - 2
        towards = 1.0 if _unit(seed, index, _T_LEAN, source, lane_i, slot) < p else 0.0
        return p + _GROUP_LEAN * (towards - p)

    lean = tuple(
        tuple(tuple(leaned(position, lane_i, slot) for slot in range(STEPS_PER_BAR))
              for lane_i in range(len(LANES)))
        for position in range(GROUP_BARS)
    )
    return JungleSection(seed=seed, index=index, signature=signature, chance=chance, lean=lean)


def section_index(seed: int, global_bar: int) -> int:
    """Which section a bar belongs to. One section, until the clocks turn it over."""
    return 0


# ---------------------------------------------------------------------------
# The deal
# ---------------------------------------------------------------------------

def is_fill_bar(seed: int, global_bar: int) -> bool:
    """A fill takes the last bar of its 4-bar group, about 1 group in 4."""
    if global_bar % GROUP_BARS != GROUP_BARS - 1:
        return False
    return _unit(seed, _T_FILL, global_bar // GROUP_BARS) < FILL_CHANCE


def drop_has_roll(seed: int, drop_bar: int) -> bool:
    """Whether the drop landing on this bar is one of the 27% with a roll before it."""
    return _unit(seed, _T_DROP, 0, drop_bar) < ROLL_CHANCE


def drop_has_gap(seed: int, drop_bar: int) -> bool:
    """Whether the drop landing on this bar is one of the 27% with a 16th of gap before it."""
    return _unit(seed, _T_DROP, 1, drop_bar) < GAP_CHANCE


@lru_cache(maxsize=4096)
def deal_bar(
    seed: int,
    global_bar: int,
    under_hook: bool = False,
    state: str = "groove",
    roll: bool = False,
    gap: bool = False,
) -> BarDeal:
    """Deal one bar. global_bar counts from the start of the piece.

    under_hook: a hook sounds in this bar, so the kick's in-between hits thin (J7).
    state:      "groove"; "drop" for the first bar of a drop, which is thinner
                (J9); "breakdown" when the sub is out, which is busier on top (J10).
    roll, gap:  the bar before a drop that has one (J9).
    """
    section = section_for(seed, section_index(seed, global_bar))
    signed = {(hit.lane, hit.slot) for hit in section.signature}
    lean = section.lean[global_bar % GROUP_BARS]
    fill = is_fill_bar(seed, global_bar)

    hits: list[Hit] = []
    for lane_i, lane in enumerate(LANES):
        for slot in range(STEPS_PER_BAR):
            p = lean[lane_i][slot]
            if p <= 0.0:
                continue
            dealt = p < 1.0 and (lane, slot) not in signed       # neither spine nor signature
            if under_hook and lane == "low" and dealt:
                p *= _LOW_UNDER_HOOK
            if state == "drop" and dealt:
                p *= _DROP_BAR_THIN
            elif state == "breakdown" and dealt and lane != "low":
                p += (1.0 - p) * _BREAKDOWN_LIFT
            u = _unit(seed, _T_DEAL, global_bar, lane_i, slot)
            if slot in SPINE.get(lane, ()):
                kind = "spine"
            elif u < p:
                kind = "signature" if (lane, slot) in signed else "between"
            elif (fill and lane != "low" and slot >= _FILL_FROM
                    and u < p + (1.0 - p) * _FILL_LIFT):
                kind = "fill"
            else:
                continue
            hits.append(Hit(lane, slot, kind, _velocity(seed, global_bar, lane, slot, kind)))
    if roll:
        # 16th snares through the last half bar, growing; the spine snare stays what it is.
        hits = [h for h in hits if not (h.lane == "mid" and h.slot >= _ROLL_FROM and h.kind != "spine")]
        for slot in range(_ROLL_FROM, STEPS_PER_BAR):
            if slot not in SPINE["mid"]:
                ramp = (slot - _ROLL_FROM) / (STEPS_PER_BAR - 1 - _ROLL_FROM)
                hits.append(Hit("mid", slot, "roll", 58 + int(ramp * 42)))
    if gap:
        hits = [h for h in hits if h.slot != _GAP_SLOT]
    return BarDeal(global_bar=global_bar, is_fill=fill, hits=tuple(hits))


def _velocity(seed: int, global_bar: int, lane: str, slot: int, kind: str) -> int:
    """Dynamics carry the feel (J5): the spine leads, the 8ths sit under it,
    the odd 16ths under those, and the ghost snares are quiet and never level."""
    u = _unit(seed, _T_VELOCITY, global_bar, LANES.index(lane), slot)
    odd = slot % 2 == 1
    if kind == "spine":
        return {0: 122, 10: 112}.get(slot, 118)
    if kind == "fill":
        # A fill grows through its half bar: 62 at the "3" to about 92 at the "a" of 4.
        ramp = (slot - _FILL_FROM) / (STEPS_PER_BAR - 1 - _FILL_FROM)
        base = (70 if lane == "high" else 62) + int(ramp * 24)
        return base + int(u * 7)
    if lane == "low":
        if kind == "signature":
            return 100 + int(u * 7)                 # 100-106
        return (80 if odd else 88) + int(u * 9)     # 80-88 / 88-96
    if lane == "mid":
        if kind == "signature":
            if slot in _BESIDE_SPINE_SNARE:
                return 64 + int(u * 15)             # 64-78: a drag, "louder than a ghost
                                                    # but softer than the backbeat" (brief)
            return 88 + int(u * 13)                 # 88-100: a real snare hit
        return (28 if odd else 38) + int(u * 19)    # ghosts: 28-46 / 38-56
    if kind == "signature":
        return 88 + int(u * 9)                      # open hat accent
    if slot in SPINE_SLOTS:
        return 84 + int(u * 9)
    return (60 if odd else 74) + int(u * 13)        # 60-72 / 74-86


# ---------------------------------------------------------------------------
# Measurement, as the research measured it
# ---------------------------------------------------------------------------

def similarity(a: tuple[int, ...], b: tuple[int, ...]) -> float:
    """Pearson correlation of two bars' cell vectors (rhythm.md section 3)."""
    n = len(a)
    mean_a, mean_b = sum(a) / n, sum(b) / n
    cov = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b))
    var_a = sum((x - mean_a) ** 2 for x in a)
    var_b = sum((y - mean_b) ** 2 for y in b)
    if var_a == 0 or var_b == 0:
        return 0.0
    return cov / (var_a * var_b) ** 0.5
# ===========================================================================
# The sub riff (J6)
# ===========================================================================
#
# Unlike the break, a riff is written once and repeats as written: "the bass
# lands regularly and gives the track its structure" (bass.md section 11).

BEATS_PER_BAR = 4
SUB_MAX_BEATS = 4.0          # nothing in the reference is held past 1.4 bars; the rule caps at a bar

# What the instrument has to do to a sub note; the engine can only say so.
# bass.md sections 6, 7 and 9.4; archetypes.md, "Bass".
SUB_VOICE = {
    "waveform":              "sine",    # fundamental 16.6 dB over its 2nd harmonic
    "pitch_drop_semitones":  30,        # every note starts this far above its pitch...
    "pitch_drop_tau_ms":     12,        # ...and falls with this time constant
    "pitch_tail_semitones":  1,         # then a slow tail of about a semitone
    "pitch_tail_settle_ms":  175,       # settling over 150-200 ms
    "amp_attack_ms":         1,         # hard attack, no click layer
    "sidechain_db":          0.0,       # not ducked under the kick (measured: -0.5 dB)
    "kick_body_hz":          (60, 250), # kick and sub share the room by register:
    "sub_below_hz":          60,        # 65.6% of the sub's power is below this
}

_T_RIFF, _T_FALL = 10, 11

# Riff lengths: 4 bars 39% of the time, 8 bars 31% (scene rules) -> 56 : 44.
_RIFF_PERIODS = ((4, 0.56), (8, 1.0))
# How long a riff is held before it changes, in bars. Reference: median 11,
# interquartile 7-15, changes on the phrase grid.
_RIFF_HOLD = {
    4: ((8, 0.50), (12, 0.80), (16, 1.0)),
    8: ((8, 0.25), (16, 1.0)),
}
# About one phrase in two or three ends on the fundamental and a gap.
FALL_CHANCE = 0.40

# One-bar figures on the 8th grid: (slot, "S" short or "H" held). Attacks sit
# at the front of the bar, on the 1 and the 2&; shorts come in pairs and lead
# somewhere ("da-da-DUM"); pushes into beat 4 come from the 3&.
_FIGURES = {
    "anchors":         ((0, "H"), (6, "H")),                         # 1 and 2&
    "anchors+4":       ((0, "H"), (6, "H"), (12, "H")),
    "da-da-dum+3&":    ((0, "S"), (2, "S"), (4, "H"), (10, "H")),
    "da-da-dum+4":     ((0, "S"), (2, "S"), (4, "H"), (12, "H")),
    "push":            ((0, "H"), (6, "H"), (10, "S"), (12, "H")),   # 3& into 4
    "one-two-push":    ((0, "H"), (4, "H"), (10, "S"), (12, "H")),
    "pickup":          ((2, "S"), (4, "H"), (10, "H")),              # 1& into 2
    "one-two-three":   ((0, "H"), (4, "H"), (8, "H")),
    "one-two-four":    ((0, "H"), (4, "H"), (12, "H")),
    "one-two-3&":      ((0, "H"), (4, "H"), (10, "H")),
    "one-three-four":  ((0, "H"), (8, "H"), (12, "H")),
    "one-two":         ((0, "H"), (4, "H")),
    "one-four":        ((0, "H"), (12, "H")),
    "one":             ((0, "H"),),
    "rest":            (),                                           # a one-bar hole
}
# Bar 1 of a phrase is the busiest, bar 4 the thinnest (bass.md 13.3). Notes
# start about a beat apart, with holes: most gaps are a beat or less, a few
# are most of a bar.
_FIGURES_FIRST  = (("da-da-dum+4", 0.30), ("one-two-push", 0.55), ("push", 0.75),
                   ("da-da-dum+3&", 1.0))
_FIGURES_MIDDLE = (("one-two-four", 0.22), ("one-two-three", 0.40), ("one-three-four", 0.55),
                   ("anchors+4", 0.70), ("one-two-3&", 0.82), ("pickup", 0.90), ("anchors", 1.0))
# The bass drops out often and briefly: a one-bar hole is the reference's
# normal punctuation (bass.md section 5).
_FIGURES_LAST   = (("rest", 0.15), ("one", 0.40), ("one-four", 0.65), ("one-two", 0.85),
                   ("anchors", 1.0))

# Lengths in beats. Median 0.60; shorts are a 16th to an 8th; the time-weight
# sits at 1-1.5 beats. A note is also cut by the next one.
_SHORT_BEATS = ((0.25, 0.30), (0.40, 0.70), (0.50, 1.0))
_HELD_BEATS  = ((0.50, 0.15), (0.60, 0.45), (0.75, 0.60), (1.00, 0.78), (1.50, 0.92), (2.00, 1.0))

# Semitones above the fundamental. A riff lives on a home note - the minor
# third, the fourth or the fifth - and a neighbour one scale step away, so its
# moves are repeats and 1-2 semitone steps; it falls to the fundamental.
_RIFF_HOMES = ((7, 0.40), (5, 0.70), (3, 1.0))
_NEIGHBOURS = {7: (5, 8), 5: (3, 7), 3: (2, 5)}
_BAR_MOVE_CHANCE  = 0.50     # the bar's note differs from the bar before's
_LATE_MOVE_CHANCE = 0.22     # the bar's last held note steps to the other note


@dataclass(frozen=True)
class SubNote:
    slot:     int
    offset:   int      # semitones above the fundamental
    beats:    float
    velocity: int
    kind:     str      # "riff" | "fall"


@dataclass(frozen=True)
class Riff:
    index:     int
    start_bar: int
    held_bars: int
    period:    int                                  # 4 or 8 bars
    fall_slot: int
    bars:      tuple[tuple[SubNote, ...], ...]      # one tuple of notes per bar of the period


def _pick(table, u: float):
    for value, ceiling in table:
        if u < ceiling:
            return value
    return table[-1][0]


_RIFF_STARTS: dict[int, list[tuple[int, int, int]]] = {}   # seed -> [(start_bar, held, period)]


def _riff_span(seed: int, global_bar: int) -> tuple[int, int, int, int]:
    """(index, start_bar, held_bars, period) of the riff sounding in this bar.

    Spans are laid end to end from bar 0. The list is only a memo: it is a pure
    function of the seed.
    """
    spans = _RIFF_STARTS.setdefault(seed, [])
    while not spans or spans[-1][0] + spans[-1][1] <= global_bar:
        index = len(spans)
        start = spans[-1][0] + spans[-1][1] if spans else 0
        period = _pick(_RIFF_PERIODS, _unit(seed, _T_RIFF, index, 0))
        held = _pick(_RIFF_HOLD[period], _unit(seed, _T_RIFF, index, 1))
        spans.append((start, held, period))
    low, high = 0, len(spans) - 1
    while low < high:                                # the span holding global_bar
        mid = (low + high + 1) // 2
        if spans[mid][0] <= global_bar:
            low = mid
        else:
            high = mid - 1
    return (low, *spans[low])


@lru_cache(maxsize=512)
def _write_riff(seed: int, index: int, start_bar: int, held_bars: int, period: int) -> Riff:
    def u(*keys: int) -> float:
        return _unit(seed, _T_RIFF, index, 2, *keys)

    home = _pick(_RIFF_HOMES, u(0))
    near = _NEIGHBOURS[home][0 if u(1) < 0.6 else 1]
    fall_slot = _pick(((6, 0.40), (8, 0.70), (0, 1.0)), u(2))

    bars: list[tuple[SubNote, ...]] = []
    pitch = home
    for bar in range(period):
        if bar >= 4 and u(3, bar) < 0.6:
            bars.append(bars[bar - 4])               # an 8-bar riff's second half mostly restates its first
            if bars[-1]:
                pitch = bars[-1][0].offset
            continue
        if bar > 0 and u(4, bar) < _BAR_MOVE_CHANCE:
            pitch = near if pitch == home else home
        position = bar % GROUP_BARS
        table = (_FIGURES_FIRST if position == 0 else _FIGURES_LAST if position == GROUP_BARS - 1
                 else _FIGURES_MIDDLE)
        figure = _FIGURES[_pick(table, u(5, bar))]
        other = near if pitch == home else home
        late = len(figure) >= 2 and u(6, bar) < _LATE_MOVE_CHANCE
        notes = []
        for n, (slot, length) in enumerate(figure):
            last_held = late and n == len(figure) - 1 and length == "H"
            beats = _pick(_SHORT_BEATS if length == "S" else _HELD_BEATS, u(7, bar, slot))
            velocity = (88 if length == "S" else 104) + int(u(8, bar, slot) * (11 if length == "S" else 9))
            notes.append(SubNote(slot, other if last_held else pitch, beats, velocity, "riff"))
        bars.append(tuple(notes))
    return Riff(index=index, start_bar=start_bar, held_bars=held_bars, period=period,
                fall_slot=fall_slot, bars=tuple(bars))


def riff_at(seed: int, global_bar: int) -> Riff:
    """The riff sounding in this bar."""
    return _write_riff(seed, *_riff_span(seed, global_bar))


def is_fall_bar(seed: int, global_bar: int) -> bool:
    """The last bar of a 4-bar phrase, about one phrase in two or three."""
    if global_bar % GROUP_BARS != GROUP_BARS - 1:
        return False
    return _unit(seed, _T_FALL, global_bar // GROUP_BARS) < FALL_CHANCE


def _written_sub_bar(seed: int, global_bar: int) -> tuple[SubNote, ...]:
    riff = riff_at(seed, global_bar)
    notes = riff.bars[(global_bar - riff.start_bar) % riff.period]
    if not is_fall_bar(seed, global_bar):
        return notes
    # The phrase drops to a low "dum" on the fundamental and leaves a gap.
    fall_beats = {0: 2.0, 6: 1.5, 8: 1.0}[riff.fall_slot]
    kept = tuple(note for note in notes if note.slot < riff.fall_slot)
    return kept + (SubNote(riff.fall_slot, 0, fall_beats, 116, "fall"),)


@lru_cache(maxsize=4096)
def sub_bar(seed: int, global_bar: int) -> tuple[SubNote, ...]:
    """The sub's notes in this bar, each cut where the next note starts."""
    notes = _written_sub_bar(seed, global_bar)
    following = _written_sub_bar(seed, global_bar + 1)
    onsets = [note.slot for note in notes]
    if following:
        onsets.append(STEPS_PER_BAR + following[0].slot)
    out = []
    for n, note in enumerate(notes):
        beats = min(note.beats, SUB_MAX_BEATS)
        if n + 1 < len(onsets):
            beats = min(beats, (onsets[n + 1] - note.slot) / 4.0)
        out.append(SubNote(note.slot, note.offset, beats, note.velocity, note.kind))
    return tuple(out)


# ===========================================================================
# Hooks (J7)
# ===========================================================================

HOOK_LOW_NOTE, HOOK_HIGH_NOTE = 58, 67     # 233 Hz to 392 Hz
# Under a hook the low-end pattern thins (low-band flux -2.1 dB): the kick's
# in-between hits are dealt at this share of their chance. The sub is untouched.
_LOW_UNDER_HOOK = 0.60

_T_HOOK = 12

# Where hooks sit in an 8-bar phrase: bars 4, 5 and 8 are the busiest
# (hooks.md, "Call and response" verdict 2). Bars 4 and 8 share a shape that
# returns every 4 bars; bar 5 has one that returns every 8. Each comes back
# three times and is replaced. A fourth, one-off hook lands elsewhere about
# 6 phrases in 10: most shapes in the reference never come back.
#   expected bars with a hook in 8: 0.85 + 0.85 + 0.80 + 0.60 = 3.1  (39%)
_HOOK_PHRASE          = 8
_HOOK_FOUR_BAR_SLOTS  = (3, 7)
_HOOK_EIGHT_BAR_SLOT  = 4
_HOOK_ONE_OFF_BARS    = (0, 1, 2, 5, 6)
_HOOK_FOUR_BAR_CHANCE = 0.85
_HOOK_EIGHT_BAR_CHANCE = 0.80
_HOOK_ONE_OFF_CHANCE  = 0.60
_HOOK_RETURNS         = 3

# Length of a hook in 16ths. Reference: median 1.2 beats, 81% under 2 beats;
# 44% of events 0.5-1 beat, 38% 1-2, 11% 2-3, 5% 3-4, 3% longer.
_HOOK_LENGTHS = ((3, 0.22), (4, 0.44), (5, 0.62), (6, 0.76), (7, 0.82),
                 (9, 0.92), (12, 0.97), (16, 1.0))
# Where it starts: towards the back of the bar, answering the drums.
_HOOK_STARTS = ((2, 0.10), (4, 0.30), (6, 0.50), (8, 0.75), (10, 0.90), (12, 1.0))
# Pitch classes above the root, by weight: 5th, minor 3rd, root, 4th.
_HOOK_DEGREES = ((7, 0.30), (3, 0.55), (0, 0.80), (5, 1.0))
_HOOK_DYAD_CHANCE = 0.35       # median 2 pitch classes sounding: dyads, not stacks


@dataclass(frozen=True)
class HookNote:
    slot:     int
    note:     int      # MIDI note
    steps:    int      # length in 16ths
    velocity: int


def _hook_shape_id(seed: int, global_bar: int) -> tuple[int, int] | None:
    """(family, number) of the shape sounding in this bar, or None for no hook."""
    phrase, bar = divmod(global_bar, _HOOK_PHRASE)
    if bar in _HOOK_FOUR_BAR_SLOTS:
        if _unit(seed, _T_HOOK, 0, global_bar) >= _HOOK_FOUR_BAR_CHANCE:
            return None
        appearance = phrase * len(_HOOK_FOUR_BAR_SLOTS) + _HOOK_FOUR_BAR_SLOTS.index(bar)
        return (0, appearance // _HOOK_RETURNS)
    if bar == _HOOK_EIGHT_BAR_SLOT:
        if _unit(seed, _T_HOOK, 0, global_bar) >= _HOOK_EIGHT_BAR_CHANCE:
            return None
        return (1, phrase // _HOOK_RETURNS)
    one_off = _HOOK_ONE_OFF_BARS[int(_unit(seed, _T_HOOK, 1, phrase) * len(_HOOK_ONE_OFF_BARS))]
    if bar == one_off and _unit(seed, _T_HOOK, 2, phrase) < _HOOK_ONE_OFF_CHANCE:
        return (2, phrase)
    return None


def has_hook(seed: int, global_bar: int) -> bool:
    return _hook_shape_id(seed, global_bar) is not None


@lru_cache(maxsize=1024)
def _hook_shape(seed: int, family: int, number: int, root_class: int) -> tuple[HookNote, ...]:
    def u(*keys: int) -> float:
        return _unit(seed, _T_HOOK, 3, family, number, *keys)

    length = _pick(_HOOK_LENGTHS, u(0))
    start = min(_pick(_HOOK_STARTS, u(1)), STEPS_PER_BAR - length)
    if length <= 3:
        pieces = [length]
    elif length <= 7:
        first = 2 if u(2) < 0.6 else 3
        pieces = [first, length - first]
    else:
        pieces = [2, 2, length - 4] if u(2) < 0.5 else [3, length - 6, 3]

    def pitch(*keys: int) -> int:
        degree = _pick(_HOOK_DEGREES, u(*keys))
        for _ in range(4):                          # walk on if this degree has no note in the register
            fits = [n for n in range(HOOK_LOW_NOTE, HOOK_HIGH_NOTE + 1) if n % 12 == (root_class + degree) % 12]
            if fits:
                return fits[0]
            degree = {7: 3, 3: 0, 0: 5, 5: 7}[degree]
        return HOOK_LOW_NOTE

    notes, slot = [], start
    for n, steps in enumerate(pieces):
        velocity = 96 + int(u(4, n) * 13) - (6 if slot % 2 else 0)
        first = pitch(3, n)
        notes.append(HookNote(slot, first, steps, velocity))
        if n == len(pieces) - 1 and u(5) < _HOOK_DYAD_CHANCE:
            second = pitch(6, n)
            if second != first:
                notes.append(HookNote(slot, second, steps, velocity - 6))
        slot += steps
    return tuple(notes)


def hook_bar(seed: int, global_bar: int, root_note: int) -> tuple[HookNote, ...]:
    """The hook's notes in this bar; empty in about 5 bars of every 8."""
    shape = _hook_shape_id(seed, global_bar)
    if shape is None:
        return ()
    return _hook_shape(seed, shape[0], shape[1], root_note % 12)
