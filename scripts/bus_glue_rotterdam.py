"""Compressor + bus glue pass — REAL gabber punch via sidechain pumping.

The professional move that gives gabber its physical impact is the
sidechain pump: every lane EXCEPT the kicks ducks ~3-6 dB on each kick
hit and recovers between kicks. The ducked surrounding wash makes the
transient peak feel ENORMOUS — punch is the gap between peak and
surroundings, not the absolute level.

Architecture:
  - Add Compressor at end of chain on every non-kick lane.
  - Sidechain source = KICK_ROTTERDAM (track-name routing).
  - Fast attack (~1 ms) so the kick transient cuts through before
    ducking starts. Medium release (~150 ms) so the duck recovers
    halfway between kicks at 190 BPM (kick spacing = 316 ms).
  - Aggressive ratio (~6:1) and threshold dialed for 4-8 dB GR on
    each hit. That's the audible pump.
  - PERC_INDUSTRIAL is excluded — snare lands on 2/4 and is part of
    the kick wall. Ducking it would create a hole.

Master gets a Glue Compressor for final bus glue (gentle 2:1 with
slow attack — just hugs the mix together).

Per the gain-staging memory: ideally key from the PERC BUS rather than
raw kick. We don't have a perc bus track set up (would need grouping
which the LOM doesn't expose). KICK_ROTTERDAM as a single-track key
is the next-best primitive available.
"""
from __future__ import annotations
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")

from thelmic.live_channel import LiveChannel


COMP_URI = "query:AudioFx#Compressor"
GLUE_URI = "query:AudioFx#Glue%20Compressor"
SIDECHAIN_KEY = "KICK_ROTTERDAM"   # sidechain source for all ducked lanes

# Lanes to sidechain-compress (everything except kicks and snare-stack
# perc). Order doesn't matter — we look up by name.
SIDECHAIN_LANES = [
    "SUB_PUNCH",
    "HOOVER_LEAD",
    "STAB_HARDCORE",
    "SIREN_FX",
    "VOX_SHOUT",
    "ACID_TONGUE",
    "DRONE_CRYPT",
    "REVERSE_VOID",
    "CHOIR_NECRO",
    "SCREAM_BLEACH",
    "STAB_BWAAH",
    "NOISE_OSSUARY",
]

# Pump settings — Live's Compressor uses normalized 0-1 for most params.
# At 190 BPM kicks fire every 316 ms and ghost notes are tighter still,
# so release MUST recover within ~80-100 ms or the comp pins to the
# floor and the duck just sits there permanently.
#   Threshold 0.30 (~-13 dB):  only peaks trigger, not every note
#   Ratio     0.50 (~3:1):     light enough to release cleanly
#   Attack    0.02 (~1 ms):    transient passes first
#   Release   0.08 (~60-80ms): snaps back between kicks — the audible pump
PUMP_SETTINGS = {
    "S/C On":      1.0,
    "Threshold":   0.30,
    "Ratio":       0.50,
    "Attack":      0.02,
    "Release":     0.08,
    "Auto Release On/Off": 0.0,
    "Knee":        0.0,
    "S/C Listen":  0.0,
    "S/C EQ On":   0.0,
    "Dry/Wet":     1.0,
}

# Master Glue Compressor — gentle final bus glue. 2:1, slow attack,
# auto release, threshold to grab ~1-2 dB GR on peaks.
MASTER_GLUE = {
    "Threshold":   -10.0,    # dB
    "Ratio":       1.0,      # indexed 1 = 4:1
    "Attack":      4.0,      # indexed 4 = 10 ms (slow — pass transients)
    "Release":     5.0,      # indexed 5 = "Auto"
    "Output":      0.0,      # dB makeup (no boost)
    "S/C On":      0.0,      # no master sidechain
    "Dry/Wet":     1.0,
}


def main():
    ch = LiveChannel(enabled=True); ch.start()
    try:
        info = ch.get_session_info().result(timeout=5)
        tc = info.get("track_count") or 0
        # Single-pass name -> idx
        futs = [ch.get_track_info(t) for t in range(tc)]
        name_to_idx: dict[str, int] = {}
        for t, f in enumerate(futs):
            try:
                ti = f.result(timeout=5)
                if ti.get("name"):
                    name_to_idx[ti.get("name")] = t
            except Exception:
                pass

        print("=== Sidechain pump setup ===\n")
        for lane in SIDECHAIN_LANES:
            t = name_to_idx.get(lane)
            if t is None:
                print(f"  {lane}: NOT FOUND")
                continue
            # Check if a Compressor's already at the end of the chain
            ti = ch.get_track_info(t).result(timeout=3)
            devs = ti.get("devices") or []
            comp_idx = None
            for di, d in enumerate(devs):
                if (d.get("class_name") or "") in ("Compressor2", "Compressor"):
                    comp_idx = di
            if comp_idx is None:
                ch.load_device(t, COMP_URI).result(timeout=20)
                time.sleep(0.2)
                ti = ch.get_track_info(t).result(timeout=3)
                comp_idx = len(ti.get("devices") or []) - 1
                print(f"  T{t:2d} {lane:17s}  added Compressor at [{comp_idx}]")
            else:
                print(f"  T{t:2d} {lane:17s}  reused Compressor at [{comp_idx}]")

            # Configure pump settings
            for pname, pval in PUMP_SETTINGS.items():
                try:
                    ch.set_device_param(t, comp_idx, pname, pval).result(timeout=5)
                except Exception as e:
                    print(f"      {pname} fail: {e}")
            # Wire sidechain to KICK_ROTTERDAM (by track index)
            key_idx = name_to_idx.get(SIDECHAIN_KEY)
            if key_idx is None:
                print(f"      sidechain skip: {SIDECHAIN_KEY} not found")
            else:
                try:
                    ch._enqueue("set_device_sidechain_source", {
                        "track_index": t,
                        "device_index": comp_idx,
                        "source_track_index": key_idx,
                    }).result(timeout=5)
                    print(f"      sidechain <- T{key_idx} {SIDECHAIN_KEY}")
                except Exception as e:
                    print(f"      sidechain fail: {e}")

        # ============== Master Glue Compressor ==============
        print("\n=== Master Glue Compressor ===")
        minfo = None
        try:
            minfo = ch._enqueue("get_master_device_info", {"device_index": 0}).result(timeout=5)
        except Exception:
            pass
        if not minfo or minfo.get("class_name") != "GlueCompressor":
            ch._enqueue("load_master_device", {"uri": GLUE_URI}).result(timeout=20)
            time.sleep(0.4)
            print("  loaded Glue Compressor on master")
        else:
            print("  reusing existing master Glue Compressor")
        for pname, pval in MASTER_GLUE.items():
            try:
                ch._enqueue("set_master_device_param", {
                    "device_index": 0, "param_name": pname, "value": pval,
                }).result(timeout=5)
            except Exception as e:
                print(f"  master {pname} fail: {e}")
        print(f"  master Glue -> Threshold -10 dB, Ratio 4:1, Attack 10 ms, Release Auto")

        print("\nDone. Fire S15 NUCLEAR_TERMINAL — every non-kick lane should now")
        print("breathe with the kick. The wash recedes on each hit; the kick punches")
        print("through the resulting gap. Master Glue ties the bus together gently.")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
