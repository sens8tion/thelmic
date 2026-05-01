"""Hook voice — melodic identity.

A 2–5 note motif derived deterministically from the active SignatureRhythm.
Loopable across 1–2 bars and repeated throughout the phrase.
Subordinate to bass: hook notes avoid the bass root on beat 1.

Character scales with Dimensions:
  - stability → tightness/coherence of the motif
  - density   → how many notes fire per bar
"""

from __future__ import annotations

from thelmic.dimensions import Dimensions, PhraseContext
from thelmic.landscape_map import SignatureRhythm
from thelmic.stream_engine import Intent, StructureFrame
from thelmic.voices import make_intent

# MIDI note for hook layer (no dedicated constant yet — use a melodic range)
_HOOK_BASE = 60   # C4; motif notes are derived as offsets above bass root


class HookIntentStream:
    def intents_for_frame(
        self,
        frame: StructureFrame,
        context: PhraseContext,
        dims: Dimensions,
        sr: SignatureRhythm | None = None,
    ) -> tuple[Intent, ...]:
        if sr is None:
            return ()

        # Derive motif steps and pitches once per phrase using hook_motif_seed
        motif = _derive_motif(sr.hook_motif_seed, sr.density_bias, dims.stability)

        if frame.step_in_bar not in motif:
            return ()

        # Skip hook on drop phrase beat 1 — bass asserts there
        if context.is_drop_phrase and frame.step_in_bar == 0:
            return ()

        note     = _hook_note(sr, frame.step_in_bar, motif, dims.stability)
        velocity = _velocity(dims.stability, dims.sparsity, frame.step_in_bar)
        return (make_intent(frame, "hook", "hook", velocity, 0.18,
                            "signature_hook", note, 7),)


def _derive_motif(seed: int, density_bias: float, stability: float) -> tuple[int, ...]:
    """Derive which steps in a 16-step bar the hook fires on.

    Higher density_bias (from SignatureRhythm) → more notes.
    Higher stability → more on-grid placement.
    Result is deterministic from seed + biases.
    """
    # Number of notes: 2–5 based on density_bias
    n = 2 + min(3, int(density_bias * 4))

    # Generate candidate steps using seed-derived LCG
    rng = seed
    candidates = []
    seen: set[int] = set()
    while len(candidates) < n:
        rng = (rng * 1664525 + 1013904223) & 0xFFFFFFFF
        step = rng % 16
        # Stable: prefer even steps (on-grid); unstable: allow any
        if stability > 0.5 and step % 2 != 0:
            continue
        if step not in seen:
            seen.add(step)
            candidates.append(step)

    return tuple(sorted(candidates))


def _hook_note(sr, step: int, motif: tuple[int, ...], stability: float = 0.5) -> int:
    """Derive a MIDI note from the SignatureRhythm.

    Rules (musical_rules.md — Melodic Note Alignment):
    Default: natural minor palette (root, b3, 5th, b7, octave, b10).
    At high heat (low stability): allow harmonic minor peak (raised 7th = maj7).
    Never major — the target genres are minor/Phrygian/Dorian.
    """
    if stability < 0.35:
        # Low stability (Chaos / high heat): harmonic minor peak colour
        # root, b3, 5th, maj7 (tension leading tone), octave, b10
        intervals = (0, 3, 7, 11, 12, 15)
    else:
        # Default: natural minor — root, b3, 5th, b7, octave, b10
        intervals = (0, 3, 7, 10, 12, 15)
    idx = motif.index(step) % len(intervals)
    return sr.root_note + 12 + intervals[idx]   # +12 = one octave above bass root


def _velocity(stability: float, sparsity: float, step: int) -> int:
    """Rules (musical_rules.md, Velocity Dynamics):
    High stability: anchor 95–112, fill 55–75.
    Low stability:  anchor 110–127, fill 40–65.

    Hook is a melodic anchor voice — step 0 = peak energy.
    """
    heat_proxy = 1.0 - stability
    if step == 0:
        # Anchor hit: cold=95, hot=122
        base = int(95 + heat_proxy * 27)
    else:
        # Fill hit: cold=65, hot=48 (recede at high energy, let other voices dominate)
        base = int(65 - heat_proxy * 17)
    # Sparsity thinning reduces velocity slightly
    v = int(base - sparsity * 8)
    return max(35, min(122, v))
