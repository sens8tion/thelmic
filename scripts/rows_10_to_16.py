"""Add scenes 11-16 (slots 10-15) building out the arc beyond breakcore chaos.

10 BREAKCORE CHAOS (already built — slot 9)
11 BREAKDOWN: atmospheric, no drums, reversed-feel
12 FOOTWORK: triplet groove sparse
13 FOOTWORK FULL: dense vocal chops
14 JUNGLE RETURN: amen back with chaos textures
15 GABBER RECAP: 4/4 + rolls
16 OUTRO COLLAPSE: drone + final fade
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from thelmic.live_channel import LiveChannel

KICK, SNARE, HAT_C, HAT_O, RIDE, CRASH = 36, 38, 42, 46, 51, 49

T_SUB_MIDI, T_STAB_MIDI = 0, 1
T_DRUMS, T_SUB_AUDIO, T_ORGAN, T_PAD = 2, 3, 4, 5
T_VOX_YO, T_HARDKIT = 6, 7
T_AMEN_CHOPPED = 8
T_VOX_BIG, T_VOX_SEL = 9, 10


def main():
    ch = LiveChannel(lower_priority=False); ch.start()
    try:
        # ===== Pass A — Saturator on HARDKIT main + slot-9 envelope =====
        res = ch.get_browser_items_at_path("audio_effects").result(timeout=10)
        fx = {it["name"]: it["uri"] for it in res["items"] if it["uri"]}
        info = ch.get_track_info(T_HARDKIT).result(timeout=5)
        sat_idx = next((i for i, d in enumerate(info["devices"]) if d["class_name"] == "Saturator"), None)
        if sat_idx is None:
            ch.load_device(T_HARDKIT, fx["Saturator"]).result(timeout=15)
            info = ch.get_track_info(T_HARDKIT).result(timeout=5)
            sat_idx = next(i for i, d in enumerate(info["devices"]) if d["class_name"] == "Saturator")
        # Static state: bypass-ish (drive low, dry/wet 0) so other rows are clean
        di = ch.get_device_info(T_HARDKIT, sat_idx).result(timeout=5)
        sidx = {p["name"]: p["index"] for p in di["parameters"]}
        ch.set_device_param(T_HARDKIT, sat_idx, sidx["Drive"], 0.10).result(timeout=3)
        ch.set_device_param(T_HARDKIT, sat_idx, sidx["Type"], 4).result(timeout=3)   # Digital Clip
        ch.set_device_param(T_HARDKIT, sat_idx, sidx["Dry/Wet"], 0.0).result(timeout=3)
        ch.set_device_param(T_HARDKIT, sat_idx, sidx["Output"], 0.50).result(timeout=3)
        print(f"Saturator on HARDKIT idx {sat_idx} — static off")

        # Clip envelopes on HARDKIT slot 9 — drive AND wet ramp into the chaos
        ch.set_clip_envelope(T_HARDKIT, 9, T_HARDKIT, sat_idx, "Drive",
                              [(0.0, 0.20), (32.0, 0.55), (56.0, 0.85), (63.99, 0.97)]).result(timeout=10)
        ch.set_clip_envelope(T_HARDKIT, 9, T_HARDKIT, sat_idx, "Dry/Wet",
                              [(0.0, 0.30), (32.0, 0.65), (56.0, 0.95), (63.99, 1.0)]).result(timeout=10)
        print("HARDKIT slot 9 envelopes: drive 0.20→0.97, wet 0.30→1.0 (kick smash builds)")

        # ===== Pass B — Create scenes 10-15 (slots 10..15) =====
        cur = ch.get_scene_count().result(timeout=5)["count"]
        needed = 16 - cur
        for _ in range(max(0, needed)):
            ch.create_scene(-1).result(timeout=10)
        cur = ch.get_scene_count().result(timeout=5)["count"]
        print(f"scenes total: {cur}")

        def write(track, slot, name, notes):
            try: ch.clear_clip(track, slot).result(timeout=3)
            except Exception: pass
            ch.create_clip(track, slot, 64.0).result(timeout=10)
            ch.set_clip_name(track, slot, name).result(timeout=3)
            if notes:
                ch.add_notes_to_clip(track, slot, notes).result(timeout=10)

        # ----- Slot 10: BREAKDOWN — atmospheric, no drums -----
        # Pad triads (slow), single sub long notes, sparse selassie
        TRIADS = [[55,58,62],[51,55,58],[53,57,60],[55,58,62]]
        # Pad: full long held triads
        pad_notes = []
        for ci, triad in enumerate(TRIADS):
            for p in triad:
                pad_notes.append({"pitch": p, "start_time": ci*16.0, "duration": 15.5, "velocity": 70})
        # Use Splice pad clip (T_PAD has it in slot 0) — duplicate to slot 10
        try: ch.duplicate_clip(T_PAD, 0, 10).result(timeout=10)
        except Exception: pass
        # Sub long held notes
        SUB_ROOTS = [43, 39, 41, 43]
        sub_notes = [{"pitch": r, "start_time": ci*16.0, "duration": 15.5, "velocity": 95}
                     for ci, r in enumerate(SUB_ROOTS)]
        write(T_SUB_MIDI, 10, "sub_breakdown", sub_notes)
        # Sparse selassie shrieks (+12 still) at chord changes
        sel_break = [
            {"pitch": 72, "start_time": 0.0,  "duration": 1.5, "velocity":  95},
            {"pitch": 72, "start_time": 32.0, "duration": 2.0, "velocity": 100},
        ]
        write(T_VOX_SEL, 10, "sel_breakdown", sel_break)
        write(T_VOX_YO,  10, "yo_silent",     [])
        write(T_VOX_BIG, 10, "big_silent",    [])
        write(T_STAB_MIDI, 10, "stab_silent", [])
        write(T_HARDKIT, 10, "drums_silent",  [])
        print("  slot 10: BREAKDOWN — pad + sub + sparse selassie")

        # ----- Slot 11: FOOTWORK GROOVE — triplet kick, sparse vocals -----
        # Footwork at 165 → triplets ≈ 247 BPM kicks. Triplet 8th = beat / 1.5
        fw = []
        # Kick on triplet positions: 0, 2/3, 4/3, 2 = beats 0, 0.667, 1.333, 2 ...
        for bar in range(16):
            bs = bar * 4.0
            # 6 triplet 8ths per 4 beats? Actually 6 triplet 8ths = 4 beats: 0, 2/3, 4/3, 2, 8/3, 10/3
            for i in range(6):
                t = bs + i * (4.0 / 6.0)
                vel = 110 if i % 3 == 0 else 90
                fw.append({"pitch": KICK, "start_time": t, "duration": 0.15, "velocity": vel})
            # claps on 1 and 3
            for sb in [1.0, 3.0]:
                fw.append({"pitch": SNARE, "start_time": bs + sb, "duration": 0.25, "velocity": 100})
        write(T_HARDKIT, 11, "footwork_triplet", fw)
        write(T_SUB_MIDI, 11, "sub_footwork", sub_notes)  # same long sub
        # Sparse vocal chops — yo on every bar's beat 0.667 (after first triplet kick)
        yo_fw = [{"pitch": 67, "start_time": bar*4.0 + 0.667, "duration": 0.2, "velocity": 95} for bar in range(0, 16, 2)]
        write(T_VOX_YO, 11, "yo_footwork", yo_fw)
        try: ch.duplicate_clip(T_PAD, 0, 11).result(timeout=10)
        except Exception: pass
        write(T_VOX_BIG, 11, "big_silent_fw", [])
        write(T_VOX_SEL, 11, "sel_silent_fw", [])
        write(T_STAB_MIDI, 11, "stab_silent_fw", [])
        print("  slot 11: FOOTWORK — triplet kick groove")

        # ----- Slot 12: FOOTWORK FULL — dense chops -----
        fw_full = list(fw)
        write(T_HARDKIT, 12, "footwork_full", fw_full)
        write(T_SUB_MIDI, 12, "sub_fw_full", sub_notes)
        # Dense yo chops every triplet (matching kick)
        yo_dense = []
        for bar in range(16):
            bs = bar * 4.0
            for i in range(6):
                if i % 2 == 0:  # half the triplets
                    t = bs + i * (4.0 / 6.0)
                    yo_dense.append({"pitch": 67, "start_time": t, "duration": 0.18, "velocity": 90 + (i*3)})
        write(T_VOX_YO, 12, "yo_chop_dense", yo_dense)
        write(T_VOX_BIG, 12, "big_chops", [{"pitch": 60, "start_time": 16.0, "duration": 0.4, "velocity": 95},
                                              {"pitch": 60, "start_time": 48.0, "duration": 0.4, "velocity": 95}])
        write(T_VOX_SEL, 12, "sel_chops", [{"pitch": 72, "start_time": 32.0, "duration": 1.0, "velocity": 100}])
        try: ch.duplicate_clip(T_PAD, 0, 12).result(timeout=10)
        except Exception: pass
        try: ch.duplicate_clip(T_SUB_AUDIO, 0, 12).result(timeout=10)
        except Exception: pass
        print("  slot 12: FOOTWORK FULL — chop density")

        # ----- Slot 13: JUNGLE RETURN — amen + chaos textures -----
        # Just duplicate scene 4 (DROP — original jungle) for HARDKIT and others
        for ti, src in [(T_HARDKIT, 4), (T_SUB_MIDI, 4), (T_STAB_MIDI, 4)]:
            try: ch.duplicate_clip(ti, src, 13).result(timeout=10)
            except Exception as e: print(f"    {ti} dup fail: {e}")
        for ti in [T_DRUMS, T_SUB_AUDIO, T_ORGAN, T_PAD]:
            try: ch.duplicate_clip(ti, 0, 13).result(timeout=10)
            except Exception: pass
        # Layer breakcore vocal shrieks
        sel_jungle = [
            {"pitch": 72, "start_time": 14.0, "duration": 1.5, "velocity": 95},
            {"pitch": 72, "start_time": 46.0, "duration": 2.0, "velocity": 100},
        ]
        write(T_VOX_SEL, 13, "sel_shrieks_over_jungle", sel_jungle)
        big_jungle = [{"pitch": 55, "start_time": 30.0, "duration": 1.5, "velocity": 100}]  # menace at bar 8
        write(T_VOX_BIG, 13, "big_menace", big_jungle)
        write(T_VOX_YO, 13, "yo_quiet", [{"pitch": 67, "start_time": 0.0, "duration": 0.5, "velocity": 90}])
        print("  slot 13: JUNGLE RETURN with shrieks layered")

        # ----- Slot 14: GABBER RECAP — duplicate gabber slot 7 -----
        for ti in [T_HARDKIT, T_SUB_MIDI, T_STAB_MIDI, T_VOX_YO, T_VOX_BIG, T_VOX_SEL]:
            try: ch.duplicate_clip(ti, 7, 14).result(timeout=10)
            except Exception: pass
        try: ch.duplicate_clip(T_SUB_AUDIO, 0, 14).result(timeout=10)
        except Exception: pass
        try: ch.duplicate_clip(T_PAD, 0, 14).result(timeout=10)
        except Exception: pass
        print("  slot 14: GABBER RECAP")

        # ----- Slot 15: OUTRO COLLAPSE — drone + final fade -----
        # Single sustained sub root drone + pad triads + one final selassie
        outro_sub = [{"pitch": 43, "start_time": 0.0, "duration": 60.0, "velocity": 80}]   # G2 long
        write(T_SUB_MIDI, 15, "drone_outro", outro_sub)
        try: ch.duplicate_clip(T_PAD, 0, 15).result(timeout=10)
        except Exception: pass
        write(T_VOX_SEL, 15, "sel_final",
              [{"pitch": 72, "start_time": 32.0, "duration": 4.0, "velocity": 90}])
        write(T_VOX_YO, 15, "yo_silent_outro", [])
        write(T_VOX_BIG, 15, "big_silent_outro", [])
        write(T_HARDKIT, 15, "drums_silent_outro", [])
        write(T_STAB_MIDI, 15, "stab_silent_outro", [])
        print("  slot 15: OUTRO COLLAPSE — drone")

        print()
        print("ROWS 11→16 BUILT. arc:")
        print("  10 BREAKCORE CHAOS (slot 9, kick auto-overdrives across 16 bars)")
        print("  11 BREAKDOWN")
        print("  12 FOOTWORK GROOVE")
        print("  13 FOOTWORK FULL")
        print("  14 JUNGLE RETURN with chaos shrieks")
        print("  15 GABBER RECAP")
        print("  16 OUTRO COLLAPSE drone")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
