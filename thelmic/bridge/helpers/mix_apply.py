"""Apply CHANNEL_AUDIO meta — gain-stage every processing element.

For each role:
  1. Walk the device chain. For every device whose class is in
     DEVICE_GAIN_RULE, attenuate its own gain/output/volume param so that
     stage's output doesn't exceed the channel cap. Catches the case where
     a Saturator adds drive, a Compressor adds makeup, or a synth amp
     pushes past unity — which a single pre-chain Utility would miss.
  2. For pure audio tracks (no chain device with a gain rule), set
     clip_gain on the slot-0 source clip — that's where their level lives.
  3. Ensure EQ8 with HP / LP bands per FreqRegion.

No metering — meta is the source of truth. One-shot, fast.
"""
from __future__ import annotations

from thelmic.meta import ChannelAudio
from .discovery import ensure_device
from .eq import set_eq_band, EQ8_HP_48_GUESS, EQ8_LP_48_GUESS


EQ8_URI = "query:AudioFx#EQ%20Eight"


# Per-device gain rule: (param_name, unit).
# unit values:
#   "db_direct"   — param.value is in dB, set directly
#   "live_norm"   — Operator-style 0..1 normalized; 0.85 ≈ 0 dB
#   "utility"     — Utility's Gain param (linear 0..1 with 0.5 = 0 dB)
DEVICE_GAIN_RULE = {
    "Saturator":             ("Output",       "db_direct"),
    "Compressor":            ("Output Gain",  "db_direct"),
    "Compressor2":           ("Output Gain",  "db_direct"),
    "MultibandDynamics":     ("Output",       "db_direct"),
    "Eq8":                   ("Output Gain",  "db_direct"),
    "OriginalSimpler":       ("Volume",       "db_direct"),
    "Operator":              ("Volume",       "live_norm"),
    "StereoGain":            ("Gain",         "utility"),
}


def _db_to_live_norm(db: float) -> float:
    """Approximate Operator/Simpler-style normalized volume curve.
    Anchors: 0 dB ≈ 0.85, +6 dB = 1.0, -inf = 0.0."""
    if db >= 6:   return 1.0
    if db >= 0:   return 0.85 + (db / 6.0) * 0.15
    if db >= -6:  return 0.70 + ((db + 6) / 6.0) * 0.15
    if db >= -12: return 0.55 + ((db + 12) / 6.0) * 0.15
    if db >= -24: return 0.35 + ((db + 24) / 12.0) * 0.20
    if db >= -48: return 0.13 + ((db + 48) / 24.0) * 0.22
    return max(0.0, (db + 70.0) / 22.0 * 0.13)


def _utility_gain_to_param(db: float) -> float:
    db = max(-35.0, min(35.0, db))
    return 0.5 + (db / 70.0)


def _convert(db: float, unit: str) -> float:
    if unit == "db_direct":  return db
    if unit == "live_norm":  return _db_to_live_norm(db)
    if unit == "utility":    return _utility_gain_to_param(db)
    raise ValueError("unknown gain unit: " + unit)


def remove_utilities(ch, roles: dict[str, int]) -> int:
    """Delete every StereoGain (Utility) device on the role tracks."""
    deleted = 0
    for role, ti in roles.items():
        info = ch.get_track_info(ti).result(timeout=3)
        # Iterate from end so indices don't shift
        for di in reversed(range(len(info.get("devices", [])))):
            if info["devices"][di].get("class_name") == "StereoGain":
                try:
                    ch.delete_device(ti, di).result(timeout=5)
                    deleted += 1
                except Exception as e:
                    print(f"  {role}: delete utility T{ti} D{di} fail: {e}")
    return deleted


def apply_channel_audio(ch, roles: dict[str, int],
                        channel_audio: dict[str, ChannelAudio]) -> dict:
    counts = {"device_gain_set": 0, "clip_gain_set": 0, "eq_set": 0,
              "missing_role": 0, "no_gain_target": 0}
    for role, ca in channel_audio.items():
        ti = roles.get(role)
        if ti is None:
            counts["missing_role"] += 1
            continue

        # Rule: every device aims for UNITY (0 dB) at its output, and the
        # chain as a whole lands at unity. We don't rely on the master
        # slider to clean up. No stacking attenuation, no per-channel
        # peak_db cap at the device layer — peak_db is descriptive
        # metadata, not where staging is enforced.

        # 1. EQ8 — ensure + HP/LP bands; Output Gain held at 0 dB
        eq_idx = ensure_device(ch, ti, "Eq8", EQ8_URI)
        if ca.freq.hp_hz is not None:
            set_eq_band(ch, ti, eq_idx, band=1,
                        ftype=EQ8_HP_48_GUESS, hz=ca.freq.hp_hz, on=True)
        if ca.freq.lp_hz is not None:
            set_eq_band(ch, ti, eq_idx, band=8,
                        ftype=EQ8_LP_48_GUESS, hz=ca.freq.lp_hz, on=True)
        counts["eq_set"] += 1

        # 2. Every gain-bearing device → output at unity (0 dB)
        info = ch.get_track_info(ti).result(timeout=3)
        for di, d in enumerate(info.get("devices", [])):
            cls = d.get("class_name")
            rule = DEVICE_GAIN_RULE.get(cls)
            if rule is None:
                continue
            param_name, unit = rule
            try:
                pinfo = ch.get_device_info(ti, di).result(timeout=3)
                idx_map = {p["name"]: p["index"] for p in pinfo["parameters"]}
                if param_name not in idx_map:
                    continue
                ch.set_device_param(ti, di, idx_map[param_name],
                                     _convert(0.0, unit)).result(timeout=3)
                counts["device_gain_set"] += 1
            except Exception as e:
                print(f"  {role} {cls}.{param_name}: {e}")

        # 3. Drum Rack — every populated pad and its inner chain at unity
        for di, d in enumerate(info.get("devices", [])):
            if d.get("class_name") != "DrumGroupDevice":
                continue
            try:
                pads = ch.get_drum_pads(ti, di).result(timeout=3).get("pads", [])
                unity_norm = _db_to_live_norm(0.0)
                for p in pads:
                    if p.get("chain_count", 0) > 0:
                        ch.set_drum_pad_volume(ti, di, p["note"], unity_norm).result(timeout=3)
                        counts["device_gain_set"] += 1
            except Exception as e:
                print(f"  {role} drum-pad-volume: {e}")

    return counts


def _per_stage_cap(ca: ChannelAudio, device_class: str, default_db: float) -> float:
    """If chain_caps declares a checkpoint matching this device class, use
    its peak_db; else fall back to channel-level peak_db."""
    needle = device_class.lower()
    for sc in ca.level.chain_caps:
        if sc.after_device.lower() in (needle, needle.replace("device", "")):
            return sc.peak_db
    return default_db
