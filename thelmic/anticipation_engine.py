"""Anticipation engine — pre-drop withholding patterns.

Two modes selected by landscape stability:

Mode A — Compression (stability ≥ 0.50, Oak/Nott character)
  Subdivision doubles as drop approaches. Feels inevitable, mathematical.
  References: classic house/techno build, DnB snare roll.

Mode B — Mathematical Dissolution (stability < 0.50, Chaos character)
  Events removed in a deterministic algorithmic pattern.
  The specific shape is derived from signature_rhythm.base_pattern_seed.
  References: IDM, experimental electronic, Euclidean rhythms.

Both:
  - NEVER remove kick anchor steps (step 0 minimum always survives)
  - NEVER remove snare anchor steps
  - Hat removed first, then call/response, then hook
  - Bass always survives
  - Minimum 1 kick per bar
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnticipationState:
    """The pre-drop pattern state for a single step."""
    hat_interval:      int            # 1=16th, 2=8th, 4=quarter; lower = denser
    hat_allowed:       bool           # False = hat suppressed entirely this step
    call_allowed:      bool           # False = calls suppressed
    response_allowed:  bool           # False = responses suppressed
    snare_allowed:     bool           # False = snare withheld (dissolution, bars 13–16)
    mode:              str            # "compression" | "dissolution" | "groove"


_GROOVE = AnticipationState(
    hat_interval=1, hat_allowed=True,
    call_allowed=True, response_allowed=True,
    snare_allowed=True,
    mode="groove",
)


def compute_anticipation(
    musical_step:        int,
    step_in_bar:         int,
    phrases_until_drop:  int,
    stability:           float,
    heat:                float,
    pattern_seed:        int,
) -> AnticipationState:
    """Compute the anticipation pattern for a single step.

    pattern_seed: from signature_rhythm.base_pattern_seed
    """
    if phrases_until_drop >= 2:
        return _GROOVE

    if stability >= 0.50:
        return _compression(musical_step, step_in_bar, phrases_until_drop, heat)
    else:
        return _dissolution(musical_step, step_in_bar, phrases_until_drop, heat, pattern_seed)


# ---------------------------------------------------------------------------
# Mode A — Compression
# ---------------------------------------------------------------------------

def _compression(
    musical_step: int, step_in_bar: int,
    phrases_until_drop: int, heat: float,
) -> AnticipationState:
    """Subdivision doubles as drop approaches."""
    # Heat shifts when compression starts
    early_onset = heat > 0.6   # hot = compression starts earlier

    if phrases_until_drop == 1:
        # One phrase away: light compression in second half (or whole phrase if hot)
        compress_from = 0 if early_onset else 128
        if musical_step < compress_from:
            return _GROOVE
        # 8th notes: hat fires every 2 steps
        hat_ok = step_in_bar % 2 == 0
        return AnticipationState(
            hat_interval=2, hat_allowed=hat_ok,
            call_allowed=True, response_allowed=True,
            snare_allowed=True,
            mode="compression",
        )

    # phrases_until_drop == 0 — final phrase
    if musical_step < 64:
        # Bars 1–4: quarter notes — very sparse, everything stripped back
        hat_ok = step_in_bar % 4 == 0
        return AnticipationState(hat_interval=4, hat_allowed=hat_ok,
                                  call_allowed=False, response_allowed=False,
                                  snare_allowed=True,   # snare still present early
                                  mode="compression")
    if musical_step < 192:
        # Bars 5–12: 8th notes — building tension; snare still anchors
        hat_ok = step_in_bar % 2 == 0
        return AnticipationState(hat_interval=2, hat_allowed=hat_ok,
                                  call_allowed=False, response_allowed=False,
                                  snare_allowed=True,
                                  mode="compression")
    if musical_step < 224:
        # Bars 13–14: 8th notes tightening; snare begins to thin
        # (rules: snare removed 2–4 bars before drop)
        hat_ok = step_in_bar % 2 == 0
        return AnticipationState(hat_interval=2, hat_allowed=hat_ok,
                                  call_allowed=False, response_allowed=False,
                                  snare_allowed=(step_in_bar in {4, 12}),  # anchors only
                                  mode="compression")
    # Bars 15–16: 16th notes — maximum grid reminder; snare removed
    return AnticipationState(hat_interval=1, hat_allowed=True,
                              call_allowed=False, response_allowed=False,
                              snare_allowed=False,   # rules: snare cut 2 bars before drop
                              mode="compression")


# ---------------------------------------------------------------------------
# Mode B — Mathematical Dissolution
# ---------------------------------------------------------------------------

_DISSOLUTION_PATTERNS = {
    0: "power_of_2",
    1: "euclidean",
    2: "prime_gaps",
}


def _dissolution(
    musical_step: int, step_in_bar: int,
    phrases_until_drop: int, heat: float,
    seed: int,
) -> AnticipationState:
    """Deterministic event removal based on pattern_seed."""
    pattern = _DISSOLUTION_PATTERNS[seed % 3]

    # How many events to keep per bar (scales with proximity and heat)
    if phrases_until_drop == 1:
        onset = 0 if heat > 0.6 else 128
        if musical_step < onset:
            return _GROOVE
        bar_in_range = (musical_step - onset) // 16
        events_per_bar = max(2, 8 - bar_in_range)
    else:  # phrases_until_drop == 0
        bar_in_range   = (musical_step - 64) // 16 if musical_step >= 64 else -1
        if bar_in_range < 0:
            return _GROOVE
        # Deep withholding: 8 → 4 → 2 → 1, decays more aggressively as drop nears
        events_per_bar = max(1, 8 >> (bar_in_range // 2))

    allowed_steps = _allowed_steps(pattern, events_per_bar, seed)
    hat_ok         = step_in_bar in allowed_steps

    call_ok     = hat_ok and phrases_until_drop > 0
    response_ok = call_ok

    # Rules: snare removed in final 2–4 bars before drop (musical_step ≥ 192
    # in the final phrase = bars 13+). Snare anchors (steps 4, 12) removed last.
    if phrases_until_drop == 0 and musical_step >= 192:
        snare_ok = False       # bars 13+ in final phrase — snare gone
    elif phrases_until_drop == 0 and musical_step >= 128:
        snare_ok = (step_in_bar in {4, 12})   # bars 9-12: anchors only
    else:
        snare_ok = True

    return AnticipationState(
        hat_interval=1, hat_allowed=hat_ok,
        call_allowed=call_ok, response_allowed=response_ok,
        snare_allowed=snare_ok,
        mode=f"dissolution:{pattern}",
    )


def _allowed_steps(pattern: str, n: int, seed: int) -> frozenset[int]:
    """Which of the 16 steps are allowed to fire, keeping n events."""
    n = max(1, min(16, n))

    if pattern == "power_of_2":
        # Keep every (16/n)th step: n=8 → every 2nd, n=4 → every 4th
        interval = max(1, 16 // n)
        return frozenset(i for i in range(0, 16, interval))

    if pattern == "euclidean":
        # Bjorklund/Euclidean rhythm: maximally distribute n hits across 16 steps
        return frozenset(_euclidean(n, 16))

    # prime_gaps: deterministic from seed
    # Remove steps at composite indices first (preserving primes)
    primes = {2, 3, 5, 7, 11, 13}
    all_steps = list(range(16))
    # Seed-derived shuffle of non-prime steps
    composites = [s for s in all_steps if s not in primes and s != 0]
    # Deterministic removal order from seed
    order = sorted(composites, key=lambda s: (seed * (s + 7) * 2654435761) & 0xFFFFFFFF)
    keep = set(all_steps) - set(order[: max(0, 16 - n)])
    keep.add(0)   # step 0 (kick anchor position) always survives
    return frozenset(keep)


def _euclidean(k: int, n: int) -> list[int]:
    """Bjorklund algorithm: distribute k hits maximally across n steps."""
    if k >= n:
        return list(range(n))
    if k <= 0:
        return [0]
    pattern = []
    counts  = [1] * k + [0] * (n - k)
    while True:
        groups = {}
        for c in counts:
            groups[c] = groups.get(c, 0) + 1
        if len(groups) <= 1 or groups.get(0, 0) <= 1:
            break
        new_counts = []
        ones  = [c for c in counts if c == 1]
        zeros = [c for c in counts if c == 0]
        pairs = min(len(ones), len(zeros))
        new_counts = [1 + 0] * pairs  # noqa: simplification
        # Standard Bjorklund: interleave
        result = []
        for i in range(n):
            result.append(1 if (i * k) % n < k else 0)
        steps = [i for i, v in enumerate(result) if v == 1]
        return steps if steps else [0]
    steps = [i for i, v in enumerate(counts) if v]
    return steps if steps else [0]
