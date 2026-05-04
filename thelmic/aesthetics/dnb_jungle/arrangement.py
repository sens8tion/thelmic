"""dnb_jungle arrangement — translates the existing ARRANGEMENT into a
generic Timeline using bridge primitives.

Reflects the full ragga → Rotterdam arc with all its anticipation moves,
filter sweeps, saturator drives, and tempo modulation, expressed in the
genre-neutral event vocabulary so the bridge engine can walk it.
"""
from __future__ import annotations
from thelmic.bridge.timeline import Timeline, RampSpec
from thelmic.bridge.helpers  import SemanticParam


def build_timeline() -> Timeline:
    tl = Timeline()

    # ── INTRO + PATIENT BUILD ────────────────────────────
    tl.add_scene(0, 16, tag="INTRO — pad alone, sub-free open")
    tl.add_ramp(RampSpec(track="TECTONIC", device_substring="saturator",
                          param_name="Drive", from_value=0.0, to_value=0.15,
                          duration_bars=16, steps=32, curve="log",
                          tag="TECTONIC saturator nudge in"))
    tl.add_ramp(RampSpec(track="TECTONIC", device_substring="eq8",
                          param_name="1 Frequency A", from_value=0.55, to_value=0.20,
                          duration_bars=32, steps=64, curve="log",
                          tag="TECTONIC HP open over STIRRING+BUILD"))
    tl.add_ramp(RampSpec(track="ORGAN", device_idx=1,
                          param_name="Frequency", from_value=0.20, to_value=0.55,
                          duration_bars=32, steps=32, curve="linear",
                          tag="ORGAN auto-pan rate building"))
    tl.add_scene(1, 16, tag="STIRRING")
    tl.add_scene(2, 16, tag="BUILD")
    tl.add_ramp(RampSpec(track="HARDKIT", device_substring="eq8",
                          param_name="1 Frequency A", from_value=0.10, to_value=0.05,
                          duration_bars=16, steps=32, curve="linear",
                          tag="HARDKIT HP relaxes into D1"))
    tl.add_scene(3, 16, tag="RISER (anticipation)")

    # ── FALSE D1 SEQUENCE ────────────────────────────────
    tl.add_silence(2, "tiny void — false-drop setup")
    tl.add_scene(4, 4, tag="FAKE D1 (4 bars only)")
    tl.add_silence(4, "FAKE-OUT void")
    tl.add_scene(1, 4, tag="STIRRING callback (fakeout)")
    tl.add_silence(4, "real void before D1")
    tl.add_ramp(RampSpec(track="SUBBONK", device_substring="compressor",
                          param_name="Threshold", from_value=0.55, to_value=0.30,
                          duration_bars=24, steps=24, curve="linear",
                          tag="SUBBONK comp tightening during D1"))
    tl.add_ramp(RampSpec(track="TECTONIC", device_substring="saturator",
                          param_name="Drive", from_value=0.15, to_value=0.45,
                          duration_bars=24, steps=24, curve="exp",
                          tag="TECTONIC drive grits up over D1"))
    tl.add_scene(4, 24, tag="⚡ DROP 1 (real, ragga jungle)")

    # ── PIVOT ─────────────────────────────────────────────
    tl.add_ramp(RampSpec(track="COLD MIST", device_substring="eq8",
                          param_name="8 Frequency A", from_value=0.85, to_value=0.45,
                          duration_bars=8, steps=24, curve="exp",
                          tag="COLD MIST LP close over BREAKDOWN"))
    tl.add_ramp(RampSpec(track="TECTONIC", device_substring="eq8",
                          param_name="1 Frequency A", from_value=0.20, to_value=0.55,
                          duration_bars=16, steps=32, curve="exp",
                          tag="TECTONIC HP rises (anti-build during pivot)"))
    tl.add_scene(12, 8, tag="FOOTWORK pivot")
    tl.add_scene(5, 8, tag="BREAKDOWN")
    tl.add_scene(13, 8, tag="JUNGLE RETURN")

    # ── REBUILD INTO D2 ──────────────────────────────────
    tl.add_ramp(RampSpec(track="MASTER", device_substring="eq8",
                          param_name="1 Frequency A", from_value=0.20, to_value=0.55,
                          duration_bars=8, steps=24, curve="exp",
                          tag="MASTER global thinning for D2"))
    tl.add_ramp(RampSpec(track="TECTONIC", device_substring="eq8",
                          param_name="1 Frequency A", from_value=0.55, to_value=0.10,
                          duration_bars=8, steps=24, curve="linear",
                          tag="TECTONIC HP collapses for D2"))
    tl.add_ramp(RampSpec(track="TECTONIC", device_substring="operator",
                          param_name="Transpose", from_value=0.0, to_value=-12.0,
                          duration_bars=8, steps=24, curve="exp",
                          tag="TECTONIC pitch slide DOWN to sub for D2"))
    tl.add_ramp(RampSpec(track="ORGAN", device_idx=2, param_name="Amount",
                          from_value=0.0, to_value=1.0, duration_bars=8,
                          steps=32, curve="exp", tag="Chopper1 amount surge"))
    tl.add_ramp(RampSpec(track="ORGAN", device_idx=3, param_name="Amount",
                          from_value=0.0, to_value=1.0, duration_bars=8,
                          steps=32, curve="exp", tag="Chopper2 amount surge"))
    tl.add_ramp(RampSpec(track="ORGAN", device_idx=4, param_name="Amount",
                          from_value=0.0, to_value=1.0, duration_bars=8,
                          steps=32, curve="exp", tag="Chopper3 amount surge"))
    tl.add_ramp(RampSpec(track="ORGAN", device_idx=2, param_name="Sync Rate",
                          from_value=10.0, to_value=19.0, duration_bars=8,
                          steps=18, curve="linear", tag="Chopper1 rate tighten"))
    tl.add_scene(6, 8, tag="REBUILD (anticipation)")

    # ── PRE-D2 TEMPO PULL-BACK + VOID ────────────────────
    tl.add_tempo(145.0, "DRAMATIC pull-back")
    tl.add_silence(6, "void before Rotterdam")
    tl.add_tempo(165.0, "snap back at D2")

    # ── ⚡⚡ DROP 2: ROTTERDAM ────────────────────────────
    tl.add_ramp(RampSpec(track="MASTER", device_substring="eq8",
                          param_name="1 Frequency A", from_value=0.55, to_value=0.10,
                          duration_bars=1, steps=8, curve="exp",
                          tag="MASTER slams open at D2"))
    tl.add_ramp(RampSpec(track="MASTER", device_substring="saturator",
                          param_name="Drive", from_value=0.10, to_value=0.45,
                          duration_bars=16, steps=24, curve="exp",
                          tag="MASTER drive intensifies in gabber"))
    tl.add_ramp(RampSpec(track="MASTER", device_substring="glue",
                          param_name="Threshold", from_value=-10.0, to_value=-16.0,
                          duration_bars=16, steps=24, curve="linear",
                          tag="MASTER glue tightens"))
    tl.add_ramp(RampSpec(track="SUBBONK", device_substring="compressor",
                          param_name="Threshold", from_value=0.30, to_value=0.15,
                          duration_bars=16, steps=24, curve="exp",
                          tag="SUBBONK comp peak during gabber"))
    tl.add_ramp(RampSpec(track="TECTONIC", device_substring="saturator",
                          param_name="Drive", from_value=0.45, to_value=0.85,
                          duration_bars=16, steps=24, curve="exp",
                          tag="TECTONIC drive peak gabber"))
    tl.add_scene(7, 16, tag="GABBER 1 — drop hits")

    tl.add_ramp(RampSpec(track="HARDKIT", device_substring="saturator",
                          param_name="Drive", from_value=0.20, to_value=0.65,
                          duration_bars=16, steps=24, curve="exp",
                          tag="HARDKIT saturator drive up"))
    tl.add_scene(9, 16, tag="BREAKCORE chaos peak")
    tl.add_scene(7, 24, tag="GABBER sustained max density")

    # ── DESCENT + REPRISE + OUTRO ────────────────────────
    tl.add_ramp(RampSpec(track="MASTER", device_substring="saturator",
                          param_name="Drive", from_value=0.45, to_value=0.10,
                          duration_bars=4, steps=16, curve="linear",
                          tag="MASTER drive release"))
    tl.add_ramp(RampSpec(track="MASTER", device_substring="glue",
                          param_name="Threshold", from_value=-16.0, to_value=-10.0,
                          duration_bars=4, steps=16, curve="linear",
                          tag="MASTER glue release"))
    tl.add_ramp(RampSpec(track="TECTONIC", device_substring="operator",
                          param_name="Transpose", from_value=-12.0, to_value=0.0,
                          duration_bars=4, steps=16, curve="linear",
                          tag="TECTONIC pitch returns to root"))
    tl.add_ramp(RampSpec(track="HARDKIT", device_substring="saturator",
                          param_name="Drive", from_value=0.65, to_value=0.10,
                          duration_bars=4, steps=16, curve="linear",
                          tag="HARDKIT saturator pull back"))
    tl.add_ramp(RampSpec(track="TECTONIC", device_substring="saturator",
                          param_name="Drive", from_value=0.85, to_value=0.10,
                          duration_bars=4, steps=16, curve="linear",
                          tag="TECTONIC saturator pull back"))
    tl.add_ramp(RampSpec(track="SUBBONK", device_substring="compressor",
                          param_name="Threshold", from_value=0.15, to_value=0.55,
                          duration_bars=4, steps=16, curve="linear",
                          tag="SUBBONK comp release"))
    tl.add_scene(5, 4, tag="BREAKDOWN cut to air")
    tl.add_scene(1, 8, tag="STIRRING reprise (emotional callback)")

    tl.add_ramp(RampSpec(track="COLD MIST", device_substring="eq8",
                          param_name="1 Frequency A", from_value=0.30, to_value=0.65,
                          duration_bars=16, steps=32, curve="log",
                          tag="COLD MIST HP rises into close"))
    tl.add_ramp(RampSpec(track="TECTONIC", device_substring="eq8",
                          param_name="8 Frequency A", from_value=0.60, to_value=0.30,
                          duration_bars=16, steps=32, curve="exp",
                          tag="TECTONIC LP closes outro"))
    tl.add_ramp(RampSpec(track="ORGAN", device_idx=1, param_name="Frequency",
                          from_value=0.55, to_value=0.15, duration_bars=16,
                          steps=32, curve="log", tag="ORGAN auto-pan slows"))
    tl.add_scene(11, 16, tag="OUTRO quiet close")

    return tl
