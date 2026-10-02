"""Jungle - bars dealt by chance from a section's distribution.

Rules: musical_rules.md, "Jungle - Measured Rules" (J2-J5).

The other archetypes read a bar from a step table. A jungle bar is dealt: a
section holds a chance for every 16th slot in each of three lanes, and every
bar is a fresh deal from it. The spine is certain, a few signature hits are
nearly so, the other 8th positions land about two times in three and the odd
16ths about one time in three.

A deal is seeded. The same seed and the same bar number always give the same
bar, so "chance" here is the Determinism Contract's kind: no state, no clock,
nothing drawn at run time.

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

# Tags that keep the separate draws apart.
_T_SIGNATURE, _T_LEAN, _T_TIE, _T_DEAL, _T_FILL, _T_VELOCITY = range(1, 7)

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
    kind:     str    # "spine" | "signature" | "between" | "fill"
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


@lru_cache(maxsize=4096)
def deal_bar(seed: int, global_bar: int) -> BarDeal:
    """Deal one bar. global_bar counts from the start of the piece."""
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
