"""Tests for deformation algorithms."""

import pytest
from thelmic.archetypes import Anchors, select_archetype, to_blend
from thelmic.deformations import (
    DeformationMap, deform_ghost_inject, apply_deformations, _GHOST_CEILING,
)
from thelmic.force_engine import ForceState


def _anchors_and_blend(archetype_name: str):
    arch = select_archetype(0.5, archetype_name)
    anchors = Anchors(kick=arch.kick_anchors, snare=arch.snare_anchors, hat=arch.hat_anchors)
    return anchors, to_blend(arch)


class TestGhostInject:
    def test_identity_at_zero_intensity(self):
        anchors, blend = _anchors_and_blend("two_step")
        result, dmap = deform_ghost_inject(blend, anchors, ForceState(), 0.0)
        assert result.kick_probs == blend.kick_probs
        assert result.snare_probs == blend.snare_probs
        assert result.hat_probs == blend.hat_probs
        assert all(v == 0.0 for v in dmap.kick)
        assert all(v == 0.0 for v in dmap.snare)

    def test_anchor_slots_unchanged(self):
        anchors, blend = _anchors_and_blend("two_step")
        result, _ = deform_ghost_inject(blend, anchors, ForceState(), 1.0)
        for slot in anchors.kick:
            assert result.kick_probs[slot] == blend.kick_probs[slot]
        for slot in anchors.snare:
            assert result.snare_probs[slot] == blend.snare_probs[slot]
        for slot in anchors.hat:
            assert result.hat_probs[slot] == blend.hat_probs[slot]

    def test_ghost_ceiling_respected(self):
        anchors, blend = _anchors_and_blend("two_step")
        result, _ = deform_ghost_inject(blend, anchors, ForceState(), 1.0)
        # Non-anchor slots must not exceed the ghost ceiling
        for slot, p in enumerate(result.kick_probs):
            if slot not in anchors.kick:
                assert p <= _GHOST_CEILING + 1e-9, f"kick slot {slot} exceeded ceiling: {p}"
        for slot, p in enumerate(result.snare_probs):
            if slot not in anchors.snare:
                assert p <= _GHOST_CEILING + 1e-9, f"snare slot {slot} exceeded ceiling: {p}"

    def test_neighbors_raised_at_high_intensity(self):
        anchors, blend = _anchors_and_blend("two_step")
        result, _ = deform_ghost_inject(blend, anchors, ForceState(), 1.0)
        # At intensity=1.0, neighbors of anchors should be above the 0.5 firing threshold
        for anchor in anchors.kick:
            for neighbor in ((anchor - 1) % 16, (anchor + 1) % 16):
                if neighbor not in anchors.kick:
                    assert result.kick_probs[neighbor] >= 0.5

    def test_deformation_map_nonzero_where_changed(self):
        anchors, blend = _anchors_and_blend("two_step")
        _, dmap = deform_ghost_inject(blend, anchors, ForceState(), 1.0)
        # At least some kick slots should have nonzero deformation recorded
        assert any(v > 0 for v in dmap.kick)

    def test_deformation_map_zero_at_anchor_slots(self):
        anchors, blend = _anchors_and_blend("two_step")
        _, dmap = deform_ghost_inject(blend, anchors, ForceState(), 1.0)
        # Anchor slots must not be reported as deformed (they were not changed)
        for slot in anchors.kick:
            assert dmap.kick[slot] == 0.0

    def test_higher_intensity_raises_more(self):
        anchors, blend = _anchors_and_blend("two_step")
        _, dmap_lo = deform_ghost_inject(blend, anchors, ForceState(), 0.3)
        _, dmap_hi = deform_ghost_inject(blend, anchors, ForceState(), 0.9)
        assert sum(dmap_hi.kick) >= sum(dmap_lo.kick)


class TestPipeline:
    def test_ghost_inject_active_under_instability(self):
        force = ForceState(instability=1.0, density=0.5)
        arch = select_archetype(0.5)
        anchors = Anchors(kick=arch.kick_anchors, snare=arch.snare_anchors, hat=arch.hat_anchors)
        blend = to_blend(arch)
        _, named_maps = apply_deformations(blend, anchors, force, landscape_position=0.5)
        assert "ghost_inject" in named_maps
        dmap = named_maps["ghost_inject"]
        assert any(v > 0 for v in dmap.kick) or any(v > 0 for v in dmap.snare)

    def test_no_deformation_at_oak_zero_instability(self):
        force = ForceState(instability=0.0, density=0.5)
        arch = select_archetype(0.5)
        anchors = Anchors(kick=arch.kick_anchors, snare=arch.snare_anchors, hat=arch.hat_anchors)
        blend = to_blend(arch)
        _, named_maps = apply_deformations(blend, anchors, force, landscape_position=0.0)
        # No deformations should have run — maps dict should be empty
        assert named_maps == {}

    def test_curve_override_scales_instability(self):
        force = ForceState(instability=0.5, density=0.5)
        arch = select_archetype(0.5, "two_step")
        anchors = Anchors(kick=arch.kick_anchors, snare=arch.snare_anchors, hat=arch.hat_anchors)
        blend = to_blend(arch)
        _, named_maps = apply_deformations(
            blend, anchors, force, landscape_position=0.5,
            curve_overrides={"ghost_inject": 1.0},
        )
        dmap = named_maps["ghost_inject"]
        assert max(dmap.kick) == pytest.approx(0.5)

    def test_deformation_colours_exported(self):
        from thelmic.deformations import DEFORMATION_COLOURS
        assert "ghost_inject" in DEFORMATION_COLOURS
        assert DEFORMATION_COLOURS["ghost_inject"].startswith("#")
