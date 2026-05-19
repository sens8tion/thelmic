"""Master chain setup for ROTTERDAM_CHAIN.

Builds the master output chain: Glue Compressor (bus glue) -> EQ Eight
(tonal shaping) -> Limiter (digital ceiling). Run once after the rest
of the session is built; idempotent — reuses existing devices if found.

Chain order:
  [0] Glue Compressor   gentle bus glue, ~1-2 dB GR on peaks
  [1] EQ Eight          HP 30 Hz, low-mid scoop, presence bump, LP 18 kHz
  [2] Limiter           threshold -3 dB, ceiling -0.3 dB, lookahead 1.5 ms

Tonal philosophy for gabber master:
  - HP @ 30 Hz removes sub-rumble below human hearing that just eats
    headroom. Frees the limiter to work on audible peaks.
  - Low-mid scoop @ 350 Hz keeps the wall of distorted sound from
    turning to mud. Gentle (-2 dB) — not a notch.
  - Presence bump @ 2.5 kHz emphasizes kick/snare attack and hoover
    edge. The frequency where gabber's aggression lives.
  - LP @ 18 kHz tapers the harshest top octave so the saturator stack
    doesn't pierce.
  - Limiter ceiling -0.3 dB stays safely below 0 dBFS digital clipping;
    threshold -3 dB so it engages on peaks but doesn't pump the mix.
"""
from __future__ import annotations
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")

from thelmic.live_channel import LiveChannel


GLUE_URI    = "query:AudioFx#Glue%20Compressor"
EQ8_URI     = "query:AudioFx#EQ%20Eight"
LIMITER_URI = "query:AudioFx#Limiter"


def hz_norm(hz: float, lo: float = 30.0, hi: float = 22000.0) -> float:
    hz = max(lo, min(hi, hz))
    return math.log(hz / lo) / math.log(hi / lo)


def main():
    ch = LiveChannel(enabled=True); ch.start()
    try:
        # Discover current chain
        master = ch._enqueue("get_master_track", {}).result(timeout=5)
        n_dev = master.get("device_count") or 0
        existing = {}
        for di in range(n_dev):
            info = ch._enqueue("get_master_device_info", {"device_index": di}).result(timeout=5)
            existing[info.get("class_name") or ""] = di

        # Ensure Glue Compressor present
        if "GlueCompressor" not in existing:
            ch._enqueue("load_master_device", {"uri": GLUE_URI}).result(timeout=20)
            time.sleep(0.4)
            print("  loaded Glue Compressor")
        # Ensure EQ Eight present
        if "Eq8" not in existing:
            ch._enqueue("load_master_device", {"uri": EQ8_URI}).result(timeout=20)
            time.sleep(0.4)
            print("  loaded EQ Eight")
        # Ensure Limiter present
        if "Limiter" not in existing:
            ch._enqueue("load_master_device", {"uri": LIMITER_URI}).result(timeout=20)
            time.sleep(0.4)
            print("  loaded Limiter")

        # Re-resolve indices after additions
        master = ch._enqueue("get_master_track", {}).result(timeout=5)
        idx = {}
        for di in range(master.get("device_count") or 0):
            info = ch._enqueue("get_master_device_info", {"device_index": di}).result(timeout=5)
            idx[info.get("class_name") or ""] = di

        def set_m(di: int, name: str, val: float) -> None:
            try:
                ch._enqueue("set_master_device_param", {
                    "device_index": di, "param_name": name, "value": val,
                }).result(timeout=5)
            except Exception as e:
                print(f"    set {name}={val} failed: {e}")

        # === Glue Compressor — gentle bus glue ===
        if "GlueCompressor" in idx:
            di = idx["GlueCompressor"]
            set_m(di, "Threshold", -10.0)   # dB
            set_m(di, "Ratio",      1.0)    # indexed — middle setting
            set_m(di, "Attack",     4.0)    # indexed — slow (~10 ms, pass transients)
            set_m(di, "Release",    5.0)    # indexed — Auto
            set_m(di, "Output",     0.0)    # no makeup boost
            set_m(di, "S/C On",     0.0)    # no master sidechain
            print(f"  [{di}] Glue Compressor: Threshold -10 dB, Ratio mid, Attack slow, Auto release")

        # === EQ Eight — tonal shaping ===
        if "Eq8" in idx:
            di = idx["Eq8"]
            # Band 1 — HP 30 Hz, 48 dB/oct
            set_m(di, "1 Filter On A", 1.0)
            set_m(di, "1 Filter Type A", 0.0)
            set_m(di, "1 Frequency A", hz_norm(30.0))
            set_m(di, "1 Q A", 0.5)
            # Band 4 — low-mid scoop @ 350 Hz, -2 dB bell
            set_m(di, "4 Filter On A", 1.0)
            set_m(di, "4 Filter Type A", 3.0)
            set_m(di, "4 Frequency A", hz_norm(350.0))
            set_m(di, "4 Gain A", -2.0)
            set_m(di, "4 Q A", 0.4)
            # Band 6 — presence bump @ 2.5 kHz, +1.5 dB bell
            set_m(di, "6 Filter On A", 1.0)
            set_m(di, "6 Filter Type A", 3.0)
            set_m(di, "6 Frequency A", hz_norm(2500.0))
            set_m(di, "6 Gain A", 1.5)
            set_m(di, "6 Q A", 0.35)
            # Band 8 — LP 18 kHz, 48 dB/oct
            set_m(di, "8 Filter On A", 1.0)
            set_m(di, "8 Filter Type A", 7.0)
            set_m(di, "8 Frequency A", hz_norm(18000.0))
            set_m(di, "8 Q A", 0.5)
            print(f"  [{di}] EQ Eight: HP 30 / scoop 350 -2dB / bell 2.5k +1.5dB / LP 18k")

        # === Limiter — digital ceiling ===
        if "Limiter" in idx:
            di = idx["Limiter"]
            set_m(di, "Threshold", 0.85)   # ~-3 dB trigger
            set_m(di, "Ceiling",   0.965)  # ~-0.3 dB ceiling
            set_m(di, "Lookahead", 1.0)    # mid (1.5 ms)
            set_m(di, "Auto",      1.0)    # auto release
            print(f"  [{di}] Limiter: Threshold -3 dB, Ceiling -0.3 dB, Lookahead 1.5 ms, Auto")

        print("\nMaster chain configured.")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
