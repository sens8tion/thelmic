"""Full audio-engineering sweep across the jungle session.

Pass 1 — Diagnose: read meters during DROP scene
Pass 2 — Master: Glue Comp + Limiter
Pass 3 — Per-track EQ where missing (frequency carving)
Pass 4 — Level audit + trim
"""
from __future__ import annotations
import os, sys, math, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from thelmic.live_channel import LiveChannel


def hz_to_norm(hz):
    hz = max(30.0, min(22000.0, hz))
    return math.log(hz / 30.0) / math.log(22000.0 / 30.0)


def to_db(v):
    return 20 * math.log10(max(v, 1e-6))


# Filter type integers — verified: 3 = Bell. Others guessed; we'll use 0 (HP cut)
# and 5 (high shelf) cautiously. If they misbehave we disable them.
BELL = 3
HIGH_SHELF = 5
HP_12 = 1
LP_12 = 6


def find(ch, track, cn):
    info = ch.get_track_info(track).result(timeout=5)
    for i, d in enumerate(info["devices"]):
        if d["class_name"] == cn:
            return i
    return None


def ensure_eq(ch, track, eq8_uri):
    i = find(ch, track, "Eq8")
    if i is None:
        ch.load_device(track, eq8_uri).result(timeout=15)
        i = find(ch, track, "Eq8")
    return i


def set_band(ch, track, dev, band, *, ftype, hz, gain=0.0, q_norm=0.5, on=True):
    di = ch.get_device_info(track, dev).result(timeout=5)
    idx = {p["name"]: p["index"] for p in di["parameters"]}
    ch.set_device_param(track, dev, idx[f"{band} Filter On A"], 1 if on else 0).result(timeout=3)
    if on:
        ch.set_device_param(track, dev, idx[f"{band} Filter Type A"], ftype).result(timeout=3)
        ch.set_device_param(track, dev, idx[f"{band} Frequency A"], hz_to_norm(hz)).result(timeout=3)
        ch.set_device_param(track, dev, idx[f"{band} Gain A"], gain).result(timeout=3)
        ch.set_device_param(track, dev, idx[f"{band} Resonance A"], q_norm).result(timeout=3)


def disable_eq(ch, track, dev):
    di = ch.get_device_info(track, dev).result(timeout=5)
    idx = {p["name"]: p["index"] for p in di["parameters"]}
    for b in range(1, 9):
        ch.set_device_param(track, dev, idx[f"{b} Filter On A"], 0).result(timeout=3)


def main():
    ch = LiveChannel(lower_priority=False); ch.start()
    try:
        print("=== AUDIO ENGINEERING SWEEP ===\n")

        sess = ch.get_session_info().result(timeout=5)
        print(f"tempo {sess['tempo']}, tracks {sess['track_count']}\n")

        # Identify roles by name
        roles = {}
        audio_tracks = []
        for i in range(sess["track_count"]):
            info = ch.get_track_info(i).result(timeout=5)
            roles[i] = (info["name"], info["is_midi_track"])
            if not info["is_midi_track"]:
                audio_tracks.append(i)

        for i, (name, midi) in roles.items():
            print(f"  T{i} {name:<14s} {'MIDI' if midi else 'AUDIO'}")
        print()

        res = ch.get_browser_items_at_path("audio_effects").result(timeout=10)
        fx = {it["name"]: it["uri"] for it in res["items"] if it["uri"]}
        EQ8 = fx["EQ Eight"]

        # ---- PASS 1: DIAGNOSE — meter during DROP ----
        print("--- PASS 1: meter audit during DROP scene ---")
        ch.fire_scene(4).result(timeout=5)
        time.sleep(2)
        peaks = {ti: 0.0 for ti in audio_tracks}
        for _ in range(20):
            for ti in audio_tracks:
                try:
                    r = ch.get_track_meter(ti).result(timeout=2)
                    peaks[ti] = max(peaks[ti], max(r["left"], r["right"]))
                except Exception:
                    pass
            time.sleep(0.15)
        for ti, peak in sorted(peaks.items()):
            name = roles[ti][0]
            flag = ""
            if peak >= 0.95: flag = "  *** HOT ***"
            elif peak >= 0.85: flag = "  hot"
            elif peak <= 0.15: flag = "  quiet"
            print(f"  T{ti} {name:<14s} peak={peak:.3f} ({to_db(peak):+.1f} dB){flag}")
        print()

        # ---- PASS 2: MASTER glue + limiter ----
        print("--- PASS 2: master bus ---")
        m_info = ch.get_master_track().result(timeout=5)
        # current device count via get_master_device_info on idx 0..N
        # Simpler: just attempt to load and check duplicate; if Glue Comp not present add it.
        # We don't have a direct "master devices list" — use get_master_device_info iteratively.
        existing = []
        for di in range(8):
            try:
                info = ch.get_master_device_info(di).result(timeout=3)
                existing.append((di, info["class_name"], info["name"]))
            except Exception:
                break
        print(f"  master devices currently: {[(d, c) for d, c, n in existing]}")

        # Add Glue Compressor if not present
        if not any(c == "GlueCompressor" for _, c, _ in existing):
            ch.load_master_device(uri=fx["Glue Compressor"]).result(timeout=20)
            print("  + Glue Compressor on master")
            existing = []
            for di in range(8):
                try: info = ch.get_master_device_info(di).result(timeout=3); existing.append((di, info["class_name"], info["name"]))
                except Exception: break

        glue_idx = next((d for d, c, n in existing if c == "GlueCompressor"), None)
        if glue_idx is not None:
            di = ch.get_master_device_info(glue_idx).result(timeout=3)
            idx_by_name = {p["name"]: p["index"] for p in di["parameters"]}
            # Gentle bus glue: ratio 4:1 (q_idx 1), threshold -8, attack 4, release auto
            for k, v in [("Threshold", -6), ("Ratio", 1), ("Attack", 4),
                         ("Release", 6), ("Makeup", 1), ("Dry/Wet", 1.0)]:
                if k in idx_by_name:
                    ch.set_master_device_param(glue_idx, idx_by_name[k], v).result(timeout=3)
            print(f"  Glue Comp configured: thresh -6, ratio 4:1, attack 4, release auto")

        # Add Limiter for true-peak safety
        if not any(c == "Limiter" for _, c, _ in existing):
            ch.load_master_device(uri=fx["Limiter"]).result(timeout=20)
            print("  + Limiter on master")
            existing = []
            for di in range(8):
                try: info = ch.get_master_device_info(di).result(timeout=3); existing.append((di, info["class_name"], info["name"]))
                except Exception: break

        lim_idx = next((d for d, c, n in existing if c == "Limiter"), None)
        if lim_idx is not None:
            di = ch.get_master_device_info(lim_idx).result(timeout=3)
            idx_by_name = {p["name"]: p["index"] for p in di["parameters"]}
            # Set ceiling -1 dB true peak — leave headroom
            for k, v in [("Ceiling", -1.0), ("Gain", 0.0), ("Lookahead", 1)]:
                if k in idx_by_name:
                    ch.set_master_device_param(lim_idx, idx_by_name[k], v).result(timeout=3)
            print(f"  Limiter ceiling -1 dB true peak")
        print()

        # ---- PASS 3: PER-TRACK EQ ----
        print("--- PASS 3: EQ pass per track ---")
        # Mapping track name → EQ recipe
        # Using verified bell (type 3); HP and high shelf attempts.
        recipes = {
            "BREAKBEAST": [(BELL, 60, 1.0, 0.5), (BELL, 350, -1.0, 0.55), (BELL, 8000, 1.0, 0.5)],
            "SUBBONK":    [(BELL, 50, 0.5, 0.4), (BELL, 200, -0.8, 0.4)],
            "ORGAN":      [(BELL, 250, -1.5, 0.5), (BELL, 2500, 1.0, 0.5)],
            "COLD MIST":  [(BELL, 400, -1.0, 0.4), (BELL, 6000, 0.5, 0.5)],
            "TOASTER":    [(BELL, 200, -2.0, 0.4), (BELL, 2500, 1.5, 0.45)],
            "HARDKIT":    [(BELL, 60, 1.5, 0.45), (BELL, 350, -1.0, 0.55), (BELL, 9000, 1.0, 0.5)],
            "TECTONIC":   [(BELL, 50, 1.0, 0.4)],
            "STAB":       [(BELL, 500, -1.0, 0.5), (BELL, 2500, 1.0, 0.45)],
        }

        for ti, (name, midi) in roles.items():
            recipe = recipes.get(name)
            if recipe is None:
                continue
            eq = ensure_eq(ch, ti, EQ8)
            # disable all bands first
            disable_eq(ch, ti, eq)
            for bi, (ftype, hz, gain, q) in enumerate(recipe, start=1):
                set_band(ch, ti, eq, bi, ftype=ftype, hz=hz, gain=gain, q_norm=q)
            print(f"  T{ti} {name}: EQ {len(recipe)} bands (gentle)")
        print()

        # ---- PASS 4: re-meter post-EQ + glue + limiter ----
        print("--- PASS 4: post-sweep meter check ---")
        time.sleep(2)
        new_peaks = {ti: 0.0 for ti in audio_tracks}
        for _ in range(20):
            for ti in audio_tracks:
                try:
                    r = ch.get_track_meter(ti).result(timeout=2)
                    new_peaks[ti] = max(new_peaks[ti], max(r["left"], r["right"]))
                except Exception:
                    pass
            time.sleep(0.15)
        for ti, peak in sorted(new_peaks.items()):
            name = roles[ti][0]
            print(f"  T{ti} {name:<14s} peak={peak:.3f} ({to_db(peak):+.1f} dB)")
        print()

        print("=== SWEEP COMPLETE ===")
        print("Master: Glue Comp (-6 thresh, 4:1, makeup +1) + Limiter (-1 dB ceiling)")
        print("Per-track EQ carving applied (gentle bell-only; type 3 verified)")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
