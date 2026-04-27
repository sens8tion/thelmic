"""Deformation pipeline — pressure algorithms applied on top of a DrumBlend.

Architecture
------------
Each deformation is an independently-coded pure function with this signature:

    def deform_NAME(
        blend:     DrumBlend,
        anchors:   Anchors,
        force:     ForceState,
        intensity: float,          # 0.0–1.0, supplied by the pipeline
    ) -> tuple[DrumBlend, DeformationMap]:

Rules every deformation must follow:
  1. Anchor slots (anchors.kick / .snare / .hat) must survive at full probability.
     Never reduce a probability at an anchor slot.
  2. Return a new DrumBlend — do not mutate the input.
  3. Clamp all output probabilities to [0.0, 1.0].
  4. intensity=0.0 must be a no-op (identity), returning a zeroed DeformationMap.
  5. DeformationMap values represent how far each slot was moved from baseline:
     0.0 = unchanged, 1.0 = maximally deformed. Used for visualisation.

The pipeline
------------
apply_deformations() is the single entry point called by the bank generator.
It returns (DrumBlend, DeformationMap) — the modified pattern and a per-slot
record of how much each position was altered. The map drives:
  - A strip above the sequencer showing deformation intensity over time
  - Per-event colouring in the grid (blended toward a deformation colour)

Landscape position roles:
  Oak   (0.0 – 0.33) — minimal or no deformation; archetype plays close to pure
  Chaos (0.33 – 0.67) — complexity / density pressure deformations
  Nott  (0.67 – 1.0)  — tension / anticipation / withhold deformations
"""

from __future__ import annotations

from typing import NamedTuple

from thelmic.archetypes import Anchors, DrumBlend
from thelmic.force_engine import ForceState

# ---------------------------------------------------------------------------
# Per-deformation colour palette (hex strings, used by server and UI)
# ---------------------------------------------------------------------------

DEFORMATION_COLOURS: dict[str, str] = {
    "ghost_inject": "#50a0dc",   # cool blue — ghost notes
    # "stutter_pre":  "#d4804a",   # warm amber — stutter fills  (future)
    # "syncopate":    "#7cc47c",   # green — off-grid lean        (future)
    # "density_fill": "#b87ccc",   # purple — density fill        (future)
}


# ---------------------------------------------------------------------------
# DeformationMap — per-slot record of deformation intensity
# ---------------------------------------------------------------------------

class DeformationMap(NamedTuple):
    """Per-slot deformation intensity for all three layers.

    Values are 0.0 (slot unchanged from archetype) → 1.0 (maximally deformed).
    Produced by apply_deformations() and attached to each MIDIEvent for rendering.
    """
    kick:  list[float]   # 16 values
    snare: list[float]   # 16 values
    hat:   list[float]   # 16 values

    @classmethod
    def zero(cls) -> "DeformationMap":
        return cls(kick=[0.0]*16, snare=[0.0]*16, hat=[0.0]*16)

    def merge(self, other: "DeformationMap") -> "DeformationMap":
        """Combine two maps by taking the max at each slot (for sequential deformations)."""
        return DeformationMap(
            kick  = [max(a, b) for a, b in zip(self.kick,  other.kick)],
            snare = [max(a, b) for a, b in zip(self.snare, other.snare)],
            hat   = [max(a, b) for a, b in zip(self.hat,   other.hat)],
        )


# ---------------------------------------------------------------------------
# Deformation interface helpers
# ---------------------------------------------------------------------------

def _clamp_blend(blend: DrumBlend) -> DrumBlend:
    """Clamp all probabilities to [0.0, 1.0]. Call at end of every deformation."""
    return DrumBlend(
        kick_probs  = [max(0.0, min(1.0, p)) for p in blend.kick_probs],
        kick_exp    = [max(0.0, min(1.0, p)) for p in blend.kick_exp],
        snare_probs = [max(0.0, min(1.0, p)) for p in blend.snare_probs],
        snare_exp   = [max(0.0, min(1.0, p)) for p in blend.snare_exp],
        hat_probs   = [max(0.0, min(1.0, p)) for p in blend.hat_probs],
        hat_exp     = [max(0.0, min(1.0, p)) for p in blend.hat_exp],
    )


def _prob_delta_to_intensity(before: list[float], after: list[float]) -> list[float]:
    """Convert per-slot probability deltas to a normalised 0→1 intensity.

    A slot that moved by 1.0 (full swing) scores 1.0; unchanged scores 0.0.
    """
    return [min(1.0, abs(a - b)) for a, b in zip(before, after)]


# ---------------------------------------------------------------------------
# Deformation: ghost_inject
# ---------------------------------------------------------------------------

# Maximum probability a ghost slot can reach. Must be above the 0.5 firing
# threshold so ghosts actually appear, but below typical anchor values (0.8+)
# so they never compete rhythmically with the anchor.
_GHOST_CEILING = 0.72


def deform_ghost_inject(
    blend: DrumBlend,
    anchors: Anchors,
    force: ForceState,
    intensity: float,
) -> tuple[DrumBlend, DeformationMap]:
    """Raise probability on the 16th-note slots immediately surrounding each
    anchor hit, adding ghost notes that set up and shadow the anchor.

    Mechanics:
    - For each anchor slot, the slots at (anchor-1)%16 and (anchor+1)%16 are
      candidates, provided they are not themselves anchors.
    - Candidate probability is raised by intensity × _GHOST_CEILING, capped at
      _GHOST_CEILING (0.72). At intensity ≥ ~0.70 the ghost crosses the 0.5
      firing threshold and appears in the pattern.
    - Anchor slots are never touched (anchor constraint satisfied by construction).
    - intensity=0 → no change, zeroed DeformationMap (identity).

    Deformation map: each affected slot records how far it moved relative to
    the ghost ceiling, normalised to 0→1.
    """
    if intensity <= 0.0:
        return blend, DeformationMap.zero()

    def _inject_layer(
        probs: list[float],
        anchor_slots: frozenset[int],
    ) -> tuple[list[float], list[float]]:
        out = list(probs)
        dmap = [0.0] * 16
        for anchor in anchor_slots:
            for neighbor in ((anchor - 1) % 16, (anchor + 1) % 16):
                if neighbor in anchor_slots:
                    continue  # never touch another anchor
                addition = intensity * _GHOST_CEILING
                before   = out[neighbor]
                out[neighbor] = min(_GHOST_CEILING, before + addition)
                delta = out[neighbor] - before
                dmap[neighbor] = min(1.0, dmap[neighbor] + delta / _GHOST_CEILING)
        return out, dmap

    kick_probs,  dk = _inject_layer(blend.kick_probs,  anchors.kick)
    snare_probs, ds = _inject_layer(blend.snare_probs, anchors.snare)
    hat_probs,   dh = _inject_layer(blend.hat_probs,   anchors.hat)

    new_blend = DrumBlend(
        kick_probs  = kick_probs,
        kick_exp    = list(blend.kick_exp),
        snare_probs = snare_probs,
        snare_exp   = list(blend.snare_exp),
        hat_probs   = hat_probs,
        hat_exp     = list(blend.hat_exp),
    )
    return new_blend, DeformationMap(kick=dk, snare=ds, hat=dh)


# ---------------------------------------------------------------------------
# Deformation stubs (algorithms on future feature branches)
# ---------------------------------------------------------------------------

# def deform_stutter_pre(blend, anchors, force, intensity) -> tuple[DrumBlend, DeformationMap]:
#     """Tight 16th-note double-hit immediately before kick anchor slots."""
#     ...

# def deform_syncopate(blend, anchors, force, intensity) -> tuple[DrumBlend, DeformationMap]:
#     """Raise probability on off-grid 16th positions to create rhythmic lean."""
#     ...

# def deform_anticipation_withhold(blend, anchors, force, intensity) -> tuple[DrumBlend, DeformationMap]:
#     """Suppress a high-expectation non-anchor slot — tension through absence."""
#     ...

# def deform_density_fill(blend, anchors, force, intensity) -> tuple[DrumBlend, DeformationMap]:
#     """Raise probability of quiet slots without disturbing anchors."""
#     ...


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def apply_deformations(
    blend: DrumBlend,
    anchors: Anchors,
    force: ForceState,
    landscape_position: float,
    curve_overrides: dict[str, float] | None = None,
) -> tuple[DrumBlend, dict[str, DeformationMap]]:
    """Apply the active deformation pipeline and return (blend, named_maps).

    Returns:
        blend   — the modified DrumBlend after all deformations
        maps    — dict keyed by deformation name (e.g. "ghost_inject") mapping
                  to a DeformationMap for that deformation only.  Keys are only
                  present when that deformation actually ran (intensity > 0).
                  Used by the UI to render one colour-coded strip per type.

    Contract: no deformation may reduce the probability of any slot in
    anchors.kick, anchors.snare, or anchors.hat.
    """

    def _active() -> list[tuple[str, object, float]]:
        """Return ordered list of (name, deform_fn, intensity) triples.

        Territory and force state determine which deformations are active.
        Ghost inject is driven by instability across all territories.
        Oak (pos < 0.33): scaled down so pure Oak stays clean.
        """
        steps: list[tuple[str, object, float]] = []
        overrides = curve_overrides or {}
        ghost_intensity = overrides.get("ghost_inject", 0.0)
        ghost_clustering = overrides.get("ghost_clustering", 0.0)
        ghost_intensity = min(1.0, max(ghost_intensity, ghost_clustering))
        if ghost_intensity > 0.0:
            steps.append(("ghost_inject", deform_ghost_inject, ghost_intensity))
        return steps

    result = blend
    named_maps: dict[str, DeformationMap] = {}

    for name, deform_fn, intensity in _active():
        deformed, step_map = deform_fn(result, anchors, force, intensity)
        result = _clamp_blend(deformed)
        named_maps[name] = step_map

    return result, named_maps
