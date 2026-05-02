"""Add dub/ragga scene at slot 5 of jungle session."""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from thelmic.live_channel import LiveChannel

KICK, SNARE, RIM, HAT_C, HAT_O, RIDE, CRASH = 36, 38, 37, 42, 46, 51, 49


def find(ch, track, cn):
    info = ch.get_track_info(track).result(timeout=5)
    for i, d in enumerate(info["devices"]):
        if d["class_name"] == cn:
            return i
    return None


def main():
    ch = LiveChannel(lower_priority=False); ch.start()
    try:
        # ---- Drums: amen w/ dub echo-tail snares ----
        # The "echo" is faked in MIDI: each main snare gets a ghost hit 0.375 beats later
        # (3/16, dotted-eighth-like) at progressively lower velocity, simulating tape delay
        def dub_4bar():
            notes = []
            # base amen (same as before)
            base = [
                (KICK, 0.0, 0.4, 110), (SNARE, 1.0, 0.35, 100),
                (KICK, 1.5, 0.4, 95),  (SNARE, 3.0, 0.35, 105),
                (KICK, 4.0, 0.4, 110), (SNARE, 5.0, 0.35, 100),
                (SNARE, 5.5, 0.2, 75), (SNARE, 6.5, 0.3, 95),
                (KICK, 7.5, 0.35, 90),
                (KICK, 8.0, 0.4, 110), (SNARE, 9.0, 0.35, 100),
                (KICK, 10.5, 0.35, 95),(SNARE, 11.0, 0.35, 105),
                (KICK, 12.0, 0.4, 110),(SNARE, 13.0, 0.3, 95),
                (SNARE, 13.5, 0.2, 75),(SNARE, 14.0, 0.35, 100),
                (KICK, 14.5, 0.35, 90),(SNARE, 15.0, 0.3, 95),
                (SNARE, 15.5, 0.25, 80),
            ]
            notes.extend(base)
            # echo tails on every accented snare (vel >= 95)
            for p, t, dur, vel in base:
                if p == SNARE and vel >= 95:
                    # 3 echoes at 3/8 spacing, each -25% velocity
                    for echo_idx in range(1, 4):
                        notes.append((SNARE, t + echo_idx * 0.375, 0.18,
                                      max(35, int(vel * (0.55 ** echo_idx)))))
            # 16th hats with subtle pulse
            for i in range(64):
                t = i * 0.25
                slot = i % 4
                vel = {0: 88, 1: 60, 2: 75, 3: 60}[slot]
                notes.append((HAT_C, t, 0.18, vel))
            # rim shots on the and-of-1 every 2 bars
            for bar in [1, 3]:
                notes.append((RIM, bar * 4.0 + 0.5, 0.2, 90))
            return notes

        drums = []
        pat = dub_4bar()
        for rep in range(4):
            offset = rep * 16.0
            for p, t, dur, vel in pat:
                drums.append({"pitch": p, "start_time": t + offset, "duration": dur, "velocity": vel})

        # ---- Bubbly bass on T1 (replaces held sub) ----
        # Ragga-style short bass stabs on offbeats, walking around chord roots
        SUB_ROOTS = [43, 39, 41, 43]  # G2, Eb2, F2, G2
        bubble_notes = []
        for chord_idx, root in enumerate(SUB_ROOTS):
            chord_start = chord_idx * 16.0
            for bar in range(4):
                bs = chord_start + bar * 4.0
                # offbeat bass bubbles — short 16th stabs
                pattern = [
                    (0.0, root, 0.3, 100),       # downbeat root
                    (1.5, root + 7, 0.25, 85),   # 5th, offbeat
                    (2.0, root, 0.4, 95),        # back to root
                    (3.5, root + 5, 0.25, 80),   # 4th passing
                    (3.75, root, 0.2, 90),       # quick root before next bar
                ]
                for t, p, dur, vel in pattern:
                    bubble_notes.append({"pitch": p, "start_time": bs + t,
                                         "duration": dur, "velocity": vel})

        # ---- Stab: more sustained dub skank with echo tails ----
        # Same triads but each stab has a 3/8 echo at lower velocity
        TRIADS = [[55, 58, 62], [51, 55, 58], [53, 57, 60], [55, 58, 62]]
        stab_notes = []
        for chord_idx, triad in enumerate(TRIADS):
            chord_start = chord_idx * 16.0
            for bar in range(4):
                bar_start = chord_start + bar * 4.0
                for off in [0.5, 1.5, 2.5, 3.5]:
                    t = bar_start + off
                    vel_main = 95 if off == 0.5 else 88
                    for pitch in triad:
                        # main hit
                        stab_notes.append({"pitch": pitch, "start_time": t,
                                           "duration": 0.25, "velocity": vel_main})
                        # dub echo at +3/8 (single tail)
                        stab_notes.append({"pitch": pitch, "start_time": t + 0.375,
                                           "duration": 0.18,
                                           "velocity": max(45, int(vel_main * 0.55))})

        # ---- Pad: thinner and more spectral for dub atmosphere ----
        # Just one note (root + 5th of each chord) held — leave space
        DUB_PAD = [
            (55, 58),    # G3 + Bb3 (Gm root + b3 only)
            (51, 55),    # Eb root + 5
            (53, 57),    # F root + 3
            (55, 58),
        ]
        pad_notes = []
        for chord_idx, pair in enumerate(DUB_PAD):
            chord_start = chord_idx * 16.0
            for pitch in pair:
                pad_notes.append({"pitch": pitch, "start_time": chord_start,
                                  "duration": 15.5, "velocity": 70})

        # ---- write clips ----
        def write(track, slot, name, notes):
            ch.create_clip(track, slot, 64.0).result(timeout=10)
            ch.set_clip_name(track, slot, name).result(timeout=5)
            ch.add_notes_to_clip(track, slot, notes).result(timeout=10)
            print(f"  T{track} S{slot}: {name} ({len(notes)} notes)")

        print("DUB DROP scene 5:")
        write(0, 5, "dub_TAILS", drums)
        write(1, 5, "ragga_BUBBLES", bubble_notes)
        write(4, 5, "skank_DUBWISE", stab_notes)
        write(5, 5, "ghost_HOLDOUT", pad_notes)

        # Add an Echo to GHOSTKEY for actual dub delay (in addition to the MIDI ghost notes)
        res = ch.get_browser_items_at_path("audio_effects").result(timeout=10)
        fx = {it["name"]: it["uri"] for it in res["items"] if it["uri"]}
        if find(ch, 4, "Echo") is None:
            ch.load_device(4, fx["Echo"]).result(timeout=15)
            print("  + Echo on GHOSTKEY")
        echo_idx = find(ch, 4, "Echo")
        di = ch.get_device_info(4, echo_idx).result(timeout=5)
        pidx = {p["name"]: p["index"] for p in di["parameters"]}
        # Probe ranges first, then set sensibly
        # Echo's Dry Wet, Feedback, L/R Sync, L/R 16th
        for k in ("L Sync", "R Sync", "Feedback", "Dry Wet", "Dry/Wet", "L 16th", "R 16th"):
            if k in pidx:
                p = next(p for p in di["parameters"] if p["name"] == k)
                rng = (p["min"], p["max"])
                # heuristic for normalized vs raw
                if rng == (0.0, 1.0):
                    val = {"L Sync": 1, "R Sync": 1, "Feedback": 0.55,
                           "Dry Wet": 0.32, "Dry/Wet": 0.32}.get(k, 0.5)
                else:
                    val = {"L 16th": 6, "R 16th": 4, "L Sync": 1, "R Sync": 1}.get(k, 0)
                try:
                    ch.set_device_param(4, echo_idx, pidx[k], val).result(timeout=3)
                except Exception:
                    pass
        print("  Echo configured: dotted-eighth feel, 32% wet")

        # Use clip envelope to AUTOMATE Echo Dry/Wet just for THIS scene (slot 5)
        # so other GHOSTKEY clips don't get the same wet level
        for k in ("Dry Wet", "Dry/Wet"):
            if k in pidx:
                try:
                    ch.set_clip_envelope(4, 5, 4, echo_idx, k, [
                        (0.0, 0.45),
                        (32.0, 0.55),
                        (60.0, 0.45),
                    ]).result(timeout=10)
                    print(f"  envelope: {k} 0.45 -> 0.55 -> 0.45 (dub wet ride)")
                except Exception as e:
                    print(f"  envelope failed for {k}: {e}")

        ch.fire_scene(5).result(timeout=5)
        print("\nFIRED scene 5 (DUB DROP)")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
