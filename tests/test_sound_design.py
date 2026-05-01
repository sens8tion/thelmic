"""Sound design module tests — no Live required.

Covers:
- Patch JSON round-trip
- Lineage flattening (parent + delta == flat)
- PatchBuilder fluent construction + alias guard
- Library save/load/list
- Knowledge loader + fuzzy resolver
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from thelmic.sound_design import (
    Patch,
    DeviceSpec,
    MacroSpec,
    MacroMapping,
    PatchBuilder,
    flatten_lineage,
    save_patch,
    load_patch,
    list_patches,
    load_device_knowledge,
    resolve_param_name,
)


# ---------------------------------------------------------------------------
# Patch round-trip
# ---------------------------------------------------------------------------


def _sample_patch() -> Patch:
    return Patch(
        name="reese_oak",
        parent="reese_root",
        target_track_hint="bass",
        territory_affinity="oak",
        chain=[DeviceSpec(kind="native", ref="Operator", alias="osc", params={})],
        macros=[
            MacroSpec(
                macro_index=0,
                name="Brightness",
                mappings=[MacroMapping("osc.Filter Freq", 200.0, 8000.0, "exp")],
            )
        ],
        overrides={"osc.Filter Freq": 800.0, "osc.Volume": -6.0},
        meta={"author": "thelmic", "vibe": "wide"},
    )


def test_patch_json_roundtrip():
    p = _sample_patch()
    js = p.to_json()
    q = Patch.from_json(js)
    assert q.to_dict() == p.to_dict()
    # fields preserved exactly
    assert q.parent == "reese_root"
    assert q.macros[0].mappings[0].curve == "exp"
    assert q.overrides["osc.Filter Freq"] == 800.0


def test_patch_dict_roundtrip():
    p = _sample_patch()
    assert Patch.from_dict(p.to_dict()).to_dict() == p.to_dict()


# ---------------------------------------------------------------------------
# Lineage
# ---------------------------------------------------------------------------


def test_lineage_parent_chain_inherited():
    parent = Patch(
        name="root",
        chain=[DeviceSpec(kind="native", ref="Operator", alias="osc")],
        overrides={"osc.Filter Freq": 1000.0, "osc.Volume": -3.0},
    )
    child = Patch(name="oak", parent="root", overrides={"osc.Filter Freq": 600.0})
    lib = {"root": parent, "oak": child}
    resolved = flatten_lineage(child, lib)
    assert len(resolved.chain) == 1
    assert resolved.chain[0].alias == "osc"
    # last-write-wins: child's Filter Freq overrides parent's
    assert resolved.overrides["osc.Filter Freq"] == 600.0
    # parent-only overrides preserved
    assert resolved.overrides["osc.Volume"] == -3.0


def test_lineage_child_replaces_chain_when_nonempty():
    parent = Patch(
        name="root",
        chain=[DeviceSpec(kind="native", ref="Operator", alias="osc")],
    )
    child = Patch(
        name="alt",
        parent="root",
        chain=[DeviceSpec(kind="native", ref="Wavetable", alias="wt")],
    )
    resolved = flatten_lineage(child, {"root": parent, "alt": child})
    assert len(resolved.chain) == 1
    assert resolved.chain[0].ref == "Wavetable"


def test_lineage_flat_equivalent_to_parent_plus_delta():
    parent = Patch(
        name="root",
        chain=[DeviceSpec(kind="native", ref="Operator", alias="osc")],
        overrides={"osc.Filter Freq": 1000.0, "osc.Volume": -3.0},
    )
    delta = Patch(name="oak", parent="root", overrides={"osc.Filter Freq": 600.0})
    flat = Patch(
        name="oak_flat",
        chain=[DeviceSpec(kind="native", ref="Operator", alias="osc")],
        overrides={"osc.Filter Freq": 600.0, "osc.Volume": -3.0},
    )
    r1 = flatten_lineage(delta, {"root": parent, "oak": delta})
    r2 = flatten_lineage(flat, {"oak_flat": flat})
    assert r1.overrides == r2.overrides
    assert [d.ref for d in r1.chain] == [d.ref for d in r2.chain]


def test_lineage_cycle_detection():
    a = Patch(name="a", parent="b")
    b = Patch(name="b", parent="a")
    with pytest.raises(ValueError, match="cycle"):
        flatten_lineage(a, {"a": a, "b": b})


def test_lineage_missing_parent():
    p = Patch(name="orphan", parent="ghost")
    with pytest.raises(ValueError, match="missing parent"):
        flatten_lineage(p, {"orphan": p})


# ---------------------------------------------------------------------------
# PatchBuilder
# ---------------------------------------------------------------------------


def test_builder_basic():
    p = (
        PatchBuilder("reese_oak")
        .target("bass")
        .affinity("oak")
        .load_native("Operator", alias="osc")
        .set("osc.Filter Freq", 800)
        .set("osc.Volume", -6)
        .macro(0, "Brightness", [("osc.Filter Freq", 200, 8000, "exp")])
        .meta(author="thelmic")
        .build()
    )
    assert p.name == "reese_oak"
    assert p.target_track_hint == "bass"
    assert p.territory_affinity == "oak"
    assert p.chain[0].alias == "osc" and p.chain[0].ref == "Operator"
    assert p.overrides["osc.Filter Freq"] == 800.0
    assert p.macros[0].name == "Brightness"
    assert p.macros[0].mappings[0].curve == "exp"
    assert p.meta["author"] == "thelmic"


def test_builder_alias_guard():
    b = PatchBuilder("p").load_native("Operator", alias="osc")
    with pytest.raises(ValueError, match="alias already used"):
        b.load_native("Wavetable", alias="osc")


def test_builder_unknown_alias_in_set():
    b = PatchBuilder("p").load_native("Operator", alias="osc")
    with pytest.raises(ValueError, match="unknown alias"):
        b.set("ghost.Volume", 0)


def test_builder_set_resolves_curated_param_name():
    """If the alias's class is curated, builder fuzzy-resolves the param name."""
    p = (
        PatchBuilder("p")
        .load_native("Operator", alias="osc")
        .set("osc.filter freq", 700)  # lowercased — should resolve to 'Filter Freq'
        .build()
    )
    assert "osc.Filter Freq" in p.overrides
    assert p.overrides["osc.Filter Freq"] == 700.0


# ---------------------------------------------------------------------------
# Library
# ---------------------------------------------------------------------------


def test_library_save_load_list(tmp_path):
    p = _sample_patch()
    path = save_patch(p, directory=tmp_path)
    assert path.exists()
    loaded = load_patch(p.name, directory=tmp_path)
    assert loaded.to_dict() == p.to_dict()
    names = list_patches(directory=tmp_path)
    assert p.name in names


def test_library_safe_filename(tmp_path):
    p = Patch(name="weird/name with spaces!?")
    path = save_patch(p, directory=tmp_path)
    assert "/" not in path.stem
    assert path.suffix == ".json"


# ---------------------------------------------------------------------------
# Device knowledge
# ---------------------------------------------------------------------------


def test_load_curated_devices_present():
    for cls in ["Operator", "Wavetable", "DrumBus", "Saturator", "GlueCompressor"]:
        k = load_device_knowledge(cls)
        assert k is not None, f"missing {cls}.json"
        assert "params" in k
        assert len(k["params"]) > 0


def test_resolve_param_exact_match():
    assert resolve_param_name("Operator", "Filter Freq") == "Filter Freq"


def test_resolve_param_case_insensitive():
    assert resolve_param_name("Operator", "filter freq") == "Filter Freq"


def test_resolve_param_fuzzy():
    # "Filter Frequency" should resolve to "Filter Freq"
    assert resolve_param_name("Operator", "Filter Frequenc") == "Filter Freq"


def test_resolve_param_no_match_returns_none():
    assert resolve_param_name("Operator", "totallyfakeparam") is None


def test_resolve_param_unknown_class():
    # No curated knowledge → returns None unless live_param_names supplied.
    assert resolve_param_name("UnknownDevice", "Volume") is None
    assert (
        resolve_param_name("UnknownDevice", "volume", live_param_names=["Volume", "Gain"])
        == "Volume"
    )


def test_resolve_param_prefers_live_when_curated_misses():
    # Curated 'Operator' has no 'Sub Gain'; live list does — should match it.
    assert (
        resolve_param_name(
            "Operator", "Sub Gain", live_param_names=["Volume", "Sub Gain"]
        )
        == "Sub Gain"
    )
