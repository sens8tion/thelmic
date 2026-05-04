"""Apply CHANNEL_AUDIO meta — gain-stage every processing element.

Two modes:
- apply_channel_audio(metered=False): static unity. Sets every device's
  output param to 0 dB and pad volumes to unity. Fast, approximate —
  doesn't account for Drive / Saturator harmonics / Compressor makeup
  that change a device's actual output level.
- apply_channel_audio(metered=True): true unity. For each device, bypass
  everything downstream, fire a representative clip, sample the track
  output meter (= this device's output), correct the device's gain param
  so peaks land at 0 dB, then re-enable downstream. Slow but accurate.


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
import math, time

from thelmic.meta import ChannelAudio
from .discovery import ensure_device
from .eq import set_eq_band, EQ8_HP_48_GUESS, EQ8_LP_48_GUESS

# Live's per-track meter — 0.85 ≈ 0 dBFS (unity), 1.0 ≈ +6 dBFS.
UNITY_METER = 0.85
SAMPLE_INTERVAL_S = 0.05
SAMPLE_WINDOW_S   = 1.2
WARMUP_S          = 0.6


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


def _gainstage_chain_metered(ch, ti: int, role: str) -> int:
    """For each gain-bearing device on this track, bypass everything
    downstream, fire a clip, sample track output meter (= this device's
    output), correct the device's gain param so peaks land at unity.
    Restore original device-on states afterward.

    Returns count of devices corrected.
    """
    info = ch.get_track_info(ti).result(timeout=3)
    devs = info.get("devices", [])
    gain_devs = [(i, d.get("class_name")) for i, d in enumerate(devs)
                 if DEVICE_GAIN_RULE.get(d.get("class_name")) is not None]
    if not gain_devs:
        return 0

    # Find a clip to fire — prefer a populated audio clip on slot 0,
    # else any clip the track has.
    clips = ch.get_track_clips(ti).result(timeout=3).get("clips", [])
    if not clips:
        return 0
    play_slot = clips[0]["slot"]

    # Snapshot Device On state for every device so we can restore.
    on_state: list[tuple[int, int, float]] = []   # (di, on_param_idx, was_on)
    for di in range(len(devs)):
        try:
            pinfo = ch.get_device_info(ti, di).result(timeout=3)
            on_param = next((p for p in pinfo["parameters"]
                             if p["name"] == "Device On"), None)
            if on_param is None:
                continue
            on_state.append((di, on_param["index"], on_param["value"]))
        except Exception:
            continue

    corrected = 0
    try:
        for gain_di, cls in gain_devs:
            # Bypass every device strictly after gain_di
            for di, on_idx, _ in on_state:
                want = 1.0 if di <= gain_di else 0.0
                ch.set_device_param(ti, di, on_idx, want).result(timeout=3)

            # Read current gain param value
            param_name, unit = DEVICE_GAIN_RULE[cls]
            pinfo = ch.get_device_info(ti, gain_di).result(timeout=3)
            gp = next((p for p in pinfo["parameters"]
                       if p["name"] == param_name), None)
            if gp is None:
                continue

            # Fire + sample
            peak = _measure_track_peak(ch, ti, play_slot)
            if peak <= 0:
                continue

            # Compute correction in dB so peak → UNITY_METER
            correction_db = 20 * math.log10(UNITY_METER / peak)

            # Apply correction in the param's native unit
            new_value = _apply_correction(unit, gp["value"], correction_db)
            new_value = max(gp.get("min", 0.0), min(gp.get("max", 1.0), new_value))
            ch.set_device_param(ti, gain_di, gp["index"], new_value).result(timeout=3)
            corrected += 1
    finally:
        # Stop playback + restore device-on states
        try:
            ch.stop_clip(ti, play_slot).result(timeout=3)
        except Exception:
            pass
        for di, on_idx, was_on in on_state:
            try:
                ch.set_device_param(ti, di, on_idx, was_on).result(timeout=3)
            except Exception:
                pass

    return corrected


def _measure_track_peak(ch, ti: int, play_slot: int) -> float:
    ch.fire_clip(ti, play_slot).result(timeout=3)
    time.sleep(WARMUP_S)
    peak = 0.0
    steps = int(SAMPLE_WINDOW_S / SAMPLE_INTERVAL_S)
    for _ in range(steps):
        meters = ch.get_all_meters().result(timeout=2).get("meters", [])
        m = next((mm for mm in meters if mm.get("track_index") == ti), None)
        if m:
            p = max(float(m.get("left", 0)), float(m.get("right", 0)))
            if p > peak:
                peak = p
        time.sleep(SAMPLE_INTERVAL_S)
    return peak


def _apply_correction(unit: str, current_value: float, correction_db: float) -> float:
    """Translate a dB correction into the param's native value space."""
    if unit == "db_direct":
        return current_value + correction_db
    if unit == "live_norm":
        # Convert current normalized → dB, add correction, convert back.
        # Inverse of _db_to_live_norm (approximate).
        cur_db = _live_norm_to_db(current_value)
        return _db_to_live_norm(cur_db + correction_db)
    if unit == "utility":
        cur_db = (current_value - 0.5) * 70.0
        new_db = max(-35.0, min(35.0, cur_db + correction_db))
        return 0.5 + (new_db / 70.0)
    raise ValueError("unknown gain unit: " + unit)


def _live_norm_to_db(v: float) -> float:
    """Inverse of _db_to_live_norm (approximate)."""
    if v >= 1.0:  return 6.0
    if v >= 0.85: return ((v - 0.85) / 0.15) * 6.0
    if v >= 0.70: return -6 + ((v - 0.70) / 0.15) * 6.0
    if v >= 0.55: return -12 + ((v - 0.55) / 0.15) * 6.0
    if v >= 0.35: return -24 + ((v - 0.35) / 0.20) * 12.0
    if v >= 0.13: return -48 + ((v - 0.13) / 0.22) * 24.0
    return -70 + (v / 0.13) * 22.0 if v > 0 else float("-inf")


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
                        channel_audio: dict[str, ChannelAudio],
                        metered: bool = False) -> dict:
    counts = {"device_gain_set": 0, "clip_gain_set": 0, "eq_set": 0,
              "missing_role": 0, "no_gain_target": 0, "metered_corrections": 0}
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

        # 2b. Metered correction: drive each device's actual output to unity
        if metered:
            try:
                corrected = _gainstage_chain_metered(ch, ti, role)
                counts["metered_corrections"] += corrected
            except Exception as e:
                print(f"  {role} metered: {e}")

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
