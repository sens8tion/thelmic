"""Deformation pipeline — pressure algorithms applied on top of a DrumBlend.

Architecture
------------
Each deformation is an independently-coded pure function with this signature:

    def deform_NAME(
        blend:     DrumBlend,
        anchors:   Anchors,
        force:     ForceState,
        intensity: float,          # 0.0–1.0, supplied by the pipeline
    ) -> DrumBlend:

Rules every deformation must follow:
  1. Anchor slots (anchors.kick / .snare / .hat) must survive at full probability.
     Never reduce a probability at an anchor slot.
  2. Return a new DrumBlend — do not mutate the input.
  3. Clamp all output probabilities to [0.0, 1.0].
  4. intensity=0.0 must be a no-op (identity).

The pipeline
------------
apply_deformations() is the single entry point called by the bank generator.
It decides which deformations are active based on landscape_position and force
state, then folds them in sequence over the blend.

Landscape position roles:
  Oak  (0.0 – 0.33) — minimal or no deformation; archetype plays close to pure
  Chaos (0.33 – 0.67) — complexity / density pressure deformations
  Nott  (0.67 – 1.0)  — tension / anticipation / withhold deformations

Deformations are added to this module as separate named functions and registered
in the _DEFORMATION_SCHEDULE table inside apply_deformations(). The stub below
returns the blend unchanged until algorithms are developed on feature branches.
"""

from __future__ import annotations

from thelmic.archetypes import Anchors, DrumBlend
from thelmic.force_engine import ForceState


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


# ---------------------------------------------------------------------------
# Deformation functions (stubs — algorithms developed on feature branches)
# ---------------------------------------------------------------------------

# Each function below will be a complete, independently-coded pressure algorithm.
# Stubs return the blend unchanged (identity at any intensity).

# def deform_ghost_inject(blend, anchors, force, intensity) -> DrumBlend:
#     """Add low-velocity ghost hits in the 16ths surrounding anchor slots.
#     Increases felt anticipation without displacing the anchor."""
#     ...

# def deform_stutter_pre(blend, anchors, force, intensity) -> DrumBlend:
#     """Insert a tight 16th-note double-hit immediately before kick anchor slots.
#     Creates urgency while preserving the landing beat."""
#     ...

# def deform_syncopate(blend, anchors, force, intensity) -> DrumBlend:
#     """Raise probability on 16th-note off-positions (slots 1, 3, 5, 7, 9, 11, 13, 15).
#     Pushes non-anchor hits earlier or later, creating rhythmic lean."""
#     ...

# def deform_anticipation_withhold(blend, anchors, force, intensity) -> DrumBlend:
#     """Suppress a high-expectation non-anchor slot. The absence is heard as tension
#     because the listener expected a hit that didn't arrive."""
#     ...

# def deform_density_fill(blend, anchors, force, intensity) -> DrumBlend:
#     """Uniformly raise probability of currently-quiet slots. Adds density
#     without disturbing existing hits or anchor positions."""
#     ...


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def apply_deformations(
    blend: DrumBlend,
    anchors: Anchors,
    force: ForceState,
    landscape_position: float,
) -> DrumBlend:
    """Apply the active deformation pipeline to blend and return the result.

    Currently a stub — returns blend unchanged. As deformation algorithms are
    implemented on feature branches they are registered in _active() below and
    folded over the blend in sequence.

    Contract: no deformation registered here may reduce the probability of any
    slot in anchors.kick, anchors.snare, or anchors.hat.
    """

    def _active() -> list[tuple]:
        """Return list of (deform_fn, intensity) pairs to apply, in order.

        Landscape position and force state determine which deformations are
        active and at what intensity. Oak = sparse/none; Chaos/Nott = various.
        """
        # TODO: populate as algorithms are developed
        # Example structure (not active):
        #   steps = []
        #   if landscape_position > 0.33:
        #       steps.append((deform_ghost_inject, force.instability))
        #   if landscape_position > 0.67:
        #       steps.append((deform_anticipation_withhold, force.anticipation * 0.8))
        #   return steps
        return []

    result = blend
    for deform_fn, intensity in _active():
        result = deform_fn(result, anchors, force, intensity)
        result = _clamp_blend(result)   # enforce bounds after each step
    return result
