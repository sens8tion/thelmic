"""Dual-modal intra-bar call/response system.

Every bar contains a clear call (beats 1–2, steps 0–7) and a response
(beats 3–4, steps 8–15). The leader generates in the call window; the
responder derives from the leader in the response window.

Two modes
---------
  STAB_LEADS  — stab calls in beats 1–2; bass responds in beats 3–4
  BASS_LEADS  — bass calls in beats 1–2; stab responds in beats 3–4

Mode persists for 4–16 bars. Flips happen only at phrase boundaries
(abs_bar % 4 == 0) when the mode has been held long enough.

Hard rule
---------
No responder event may fire before step 8.
derive_response_steps() enforces this by construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Window constants — the only place bar windows are defined
# ---------------------------------------------------------------------------

CALL_WINDOW      = frozenset(range(0, 8))    # steps 0–7,  beats 1–2 (leader)
RESPONSE_WINDOW  = frozenset(range(8, 16))   # steps 8–15, beats 3–4 (responder)
RESPONSE_WINDOW_MIN = 8
RESPONSE_WINDOW_MAX = 15


# ---------------------------------------------------------------------------
# Mode
# ---------------------------------------------------------------------------

class Mode(Enum):
    STAB_LEADS = "STAB_LEADS"
    BASS_LEADS = "BASS_LEADS"


@dataclass
class CallResponseState:
    """Mutable mode state — persists across banks as a server singleton."""
    mode:               Mode
    bars_in_mode:       int     # how many bars in the current mode
    mode_duration_bars: int     # when to consider flipping (4–16)
    force_mode: Optional[Mode] = None   # debug override; bypasses flip logic


def default_state() -> CallResponseState:
    return CallResponseState(
        mode=Mode.STAB_LEADS,
        bars_in_mode=0,
        mode_duration_bars=8,
        force_mode=None,
    )


# ---------------------------------------------------------------------------
# Deterministic gate helpers (no random() anywhere)
# ---------------------------------------------------------------------------

def _gate_hash(abs_bar: int, salt: int = 0) -> float:
    """Deterministic pseudo-random float in [0.0, 1.0) from bar + salt."""
    return ((abs_bar * 37 + salt * 29 + 7) % 100) / 100.0


def _next_duration(abs_bar: int) -> int:
    """Deterministic mode duration 4–16 bars."""
    return 4 + (abs_bar * 13 + 11) % 13


# ---------------------------------------------------------------------------
# Step derivation
# ---------------------------------------------------------------------------

def derive_response_steps(leader_steps: list[int]) -> list[int]:
    """Map call-window steps (0–7) to response-window steps (8–15).

    Primary mapping: response_step = leader_step + 8
    (mirrors the call window to the response window exactly).

    If that slot is occupied by an already-assigned response step,
    the next slot (+9, +10, …) is tried, clamped to RESPONSE_WINDOW_MAX.

    Steps outside CALL_WINDOW (0–7) are silently ignored.

    Hard guarantee: all returned steps are in {8..15}.
    """
    occupied: set[int] = set()
    result: list[int] = []

    for ls in sorted(set(leader_steps)):
        if ls not in CALL_WINDOW:
            continue
        base = ls + 8   # primary mapping
        for candidate in range(base, RESPONSE_WINDOW_MAX + 1):
            if candidate not in occupied:
                occupied.add(candidate)
                result.append(candidate)
                break

    return sorted(result)


# ---------------------------------------------------------------------------
# Mode advancement
# ---------------------------------------------------------------------------

def should_flip(state: CallResponseState, abs_bar: int) -> bool:
    """True if mode should flip at this phrase boundary.

    Flip probabilities (biased toward returning to STAB_LEADS):
      STAB_LEADS → BASS_LEADS: 0.20
      BASS_LEADS → STAB_LEADS: 0.35
    """
    if state.force_mode is not None:
        return False
    threshold = 0.20 if state.mode == Mode.STAB_LEADS else 0.35
    return _gate_hash(abs_bar, salt=42) < threshold


def advance_mode(state: CallResponseState, abs_bar: int) -> CallResponseState:
    """Return new CallResponseState after one bar.

    Rules:
    - Always increments bars_in_mode.
    - Flip only at phrase boundaries (abs_bar % 4 == 0).
    - Flip only when bars_in_mode (after increment) >= max(4, mode_duration_bars).
    - force_mode overrides: mode is always force_mode, no flipping.
    """
    if state.force_mode is not None:
        return CallResponseState(
            mode=state.force_mode,
            bars_in_mode=state.bars_in_mode + 1,
            mode_duration_bars=state.mode_duration_bars,
            force_mode=state.force_mode,
        )

    new_bars = state.bars_in_mode + 1
    at_boundary = (abs_bar % 4 == 0)
    eligible    = new_bars >= max(4, state.mode_duration_bars)

    if at_boundary and eligible and should_flip(state, abs_bar):
        new_mode = Mode.BASS_LEADS if state.mode == Mode.STAB_LEADS else Mode.STAB_LEADS
        return CallResponseState(
            mode=new_mode,
            bars_in_mode=0,
            mode_duration_bars=_next_duration(abs_bar),
            force_mode=None,
        )

    return CallResponseState(
        mode=state.mode,
        bars_in_mode=new_bars,
        mode_duration_bars=state.mode_duration_bars,
        force_mode=None,
    )
