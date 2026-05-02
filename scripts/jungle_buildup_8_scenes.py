"""8-scene modern jungle buildup using existing Splice audio + MIDI variations.

Scene layout:
  0 INTRO       — pad only
  1 STIRRING    — pad + organ
  2 BUILD       — pad + organ + sub (MIDI)
  3 RISER       — pad + organ + audio drums + MIDI sub + sparse vocals
  4 DROP        — full mix: all audio + all MIDI + chop vocals
  5 BREAKDOWN   — pad + sub + selassie_i vocals (drums out)
  6 REBUILD     — drums back + organ + sub + sparse stabs + sparse vocals
  7 FINAL DROP  — everything full, vocal chops max density
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from thelmic.live_channel import LiveChannel

# Track indices (verify against your set; adjust if different)
T_SUB_MIDI   = 0   # TECTONIC (Operator sub)
T_STAB_MIDI  = 1   # STAB (Operator FM stab)
T_DRUMS      = 2   # BREAKBEAST (audio Splice)
T_SUB_AUDIO  = 3   # SUBBONK (audio Splice)
T_ORGAN      = 4   # ORGAN (audio Splice)
T_PAD        = 5   # COLD MIST (audio Splice)
T_VOX        = 6   # TOASTER (MIDI drum rack)

# Vocal MIDI notes
VOX_YO       = 36
VOX_BIG      = 37
VOX_SEL      = 38

# G minor chord progression: Gm Eb F Gm — 4 bars each
SUB_ROOTS = [43, 39, 41, 43]                        # G2, Eb2, F2, G2
TRIADS    = [[55, 58, 62], [51, 55, 58], [53, 57, 60], [55, 58, 62]]


def sub_notes(density="full"):
    out = []
    for ci, root in enumerate(SUB_ROOTS):
        cs = ci * 16.0
        for bar in range(4):
            if density == "sparse" and bar % 2: continue
            out.append({"pitch": root, "start_time": cs + bar * 4.0,
                        "duration": 3.95, "velocity": 105})
    return out


def stab_notes(density="full"):
    out = []
    for ci, triad in enumerate(TRIADS):
        cs = ci * 16.0
        for bar in range(4):
            bs = cs + bar * 4.0
            offsets = [0.5, 1.5, 2.5, 3.5] if density == "full" else [0.5, 2.5]
            for off in offsets:
                t = bs + off
                vel = 95 if off == 0.5 else 85
                for p in triad:
                    out.append({"pitch": p, "start_time": t, "duration": 0.18, "velocity": vel})
    return out


def vox_sparse_notes():
    """Single 'selassie i' anchor + occasional 'big up' tail."""
    return [
        {"pitch": VOX_SEL, "start_time": 0.0,  "duration": 1.5, "velocity": 100},
        {"pitch": VOX_BIG, "start_time": 30.0, "duration": 0.4, "velocity": 90},
        {"pitch": VOX_SEL, "start_time": 32.0, "duration": 1.5, "velocity": 100},
        {"pitch": VOX_BIG, "start_time": 62.0, "duration": 0.4, "velocity": 90},
    ]


def vox_drop_notes():
    """Yo chargie anchor + bar-8 stutter chop + selassie at bar 9 + bar-16 chop."""
    out = []
    out.append({"pitch": VOX_YO, "start_time": 0.0,  "duration": 0.5, "velocity": 100})
    out.append({"pitch": VOX_BIG, "start_time": 14.0, "duration": 0.3, "velocity": 95})
    # bar 8 stutter (16ths) on yo
    for i in range(8):
        out.append({"pitch": VOX_YO, "start_time": 28.0 + i * 0.5,
                    "duration": 0.18, "velocity": 75 + (i % 2) * 15})
    out.append({"pitch": VOX_SEL, "start_time": 32.0, "duration": 1.5, "velocity": 105})
    # bar 14 alternation
    for i in range(4):
        out.append({"pitch": VOX_YO if i % 2 == 0 else VOX_BIG,
                    "start_time": 52.0 + i * 1.0,
                    "duration": 0.3, "velocity": 90 + i * 3})
    # bar 16 stutter into next loop
    for i in range(8):
        out.append({"pitch": VOX_YO, "start_time": 60.0 + i * 0.5,
                    "duration": 0.18, "velocity": 80 + i * 4})
    out.append({"pitch": VOX_SEL, "start_time": 63.0, "duration": 1.0, "velocity": 110})
    out.append({"pitch": VOX_BIG, "start_time": 63.5, "duration": 0.5, "velocity": 95})
    return out


def vox_max_notes():
    """Final-drop max density: chops every bar, all 3 stabs alternating."""
    out = []
    samples = [VOX_YO, VOX_BIG, VOX_SEL]
    # 16 bars × hits at offbeats + stutters every 4 bars
    for bar in range(16):
        bs = bar * 4.0
        # offbeat hits
        for off, p in [(0.5, samples[bar % 3]), (2.5, samples[(bar + 1) % 3])]:
            out.append({"pitch": p, "start_time": bs + off, "duration": 0.28, "velocity": 90})
        # stutter every 4 bars on the and-of-3
        if bar % 4 == 3:
            for i in range(8):
                out.append({"pitch": VOX_YO, "start_time": bs + 3.0 + i * 0.125,
                            "duration": 0.08, "velocity": 75 + i * 5})
    return out


def main():
    ch = LiveChannel(lower_priority=False); ch.start()
    try:
        print("ping:", ch.ping().result(timeout=5))

        # ---- 1) duplicate audio clips into target slots ----
        print("--- duplicating audio clips ---")
        # T_PAD (T5): slot 0 -> 1,2,3,4,5,6,7  (pad plays in every scene)
        for s in range(1, 8):
            ch.duplicate_clip(T_PAD, 0, s).result(timeout=10)
        # T_ORGAN (T4): slot 0 -> 1,2,3,4,6,7 (organ in scenes 1-4, 6-7; out in 0,5)
        for s in [1, 2, 3, 4, 6, 7]:
            ch.duplicate_clip(T_ORGAN, 0, s).result(timeout=10)
        # T_DRUMS (T2): slot 0 -> 3,4,6,7
        for s in [3, 4, 6, 7]:
            ch.duplicate_clip(T_DRUMS, 0, s).result(timeout=10)
        # T_SUB_AUDIO (T3): slot 0 -> 4,7
        for s in [4, 7]:
            ch.duplicate_clip(T_SUB_AUDIO, 0, s).result(timeout=10)
        # Now empty out slot 0 of audio tracks 2,3,4 so scene 0 plays only the pad
        ch.clear_clip(T_DRUMS, 0).result(timeout=5)
        ch.clear_clip(T_SUB_AUDIO, 0).result(timeout=5)
        ch.clear_clip(T_ORGAN, 0).result(timeout=5)
        # T_PAD slot 0 stays — scene 0 = pad only
        print("  audio clips replicated")

        # ---- 2) MIDI clips per scene ----
        def write(track, slot, name, notes):
            ch.create_clip(track, slot, 64.0).result(timeout=10)
            ch.set_clip_name(track, slot, name).result(timeout=5)
            ch.add_notes_to_clip(track, slot, notes).result(timeout=10)
            print(f"  T{track} S{slot}: {name} ({len(notes)} notes)")

        # T0 SUB MIDI — present in scenes 2-7
        for s in [2, 6]:
            write(T_SUB_MIDI, s, f"sub_sparse_s{s}", sub_notes("sparse"))
        for s in [3, 4, 5, 7]:
            write(T_SUB_MIDI, s, f"sub_full_s{s}", sub_notes("full"))

        # T1 STAB MIDI — only in 4 (drop) and 7 (final), sparse in 6
        write(T_STAB_MIDI, 4, "stab_drop", stab_notes("full"))
        write(T_STAB_MIDI, 6, "stab_rebuild", stab_notes("sparse"))
        write(T_STAB_MIDI, 7, "stab_FINAL", stab_notes("full"))

        # T6 TOASTER vocals — sparse in 3, drop in 4, selassie-anchor in 5, sparse in 6, max in 7
        write(T_VOX, 3, "vox_sparse_riser", vox_sparse_notes())
        write(T_VOX, 4, "vox_DROP_chops", vox_drop_notes())
        write(T_VOX, 5, "vox_breakdown_selassie", vox_sparse_notes())
        write(T_VOX, 6, "vox_rebuild_sparse", vox_sparse_notes())
        write(T_VOX, 7, "vox_FINAL_max", vox_max_notes())

        # ---- 3) Mix levels — fixed across scenes ----
        ch.set_track_volume(T_SUB_MIDI, 0.65).result(timeout=3)
        ch.set_track_volume(T_STAB_MIDI, 0.55).result(timeout=3)
        ch.set_track_volume(T_DRUMS, 0.80).result(timeout=3)
        ch.set_track_volume(T_SUB_AUDIO, 0.78).result(timeout=3)
        ch.set_track_volume(T_ORGAN, 0.70).result(timeout=3)
        ch.set_track_volume(T_PAD, 0.55).result(timeout=3)
        ch.set_track_volume(T_VOX, 0.60).result(timeout=3)

        # Set launch quant to 8 bars for tight transitions
        ch.set_launch_quantization(8).result(timeout=5)

        # Fire scene 0 to start the build
        ch.fire_scene(0).result(timeout=5)
        print()
        print("FIRED scene 0 (INTRO). Click scene 1 → 7 in sequence to build.")
        print("Layout: 0=intro pad / 1=stir +organ / 2=build +sub / 3=riser +drums+vox /")
        print("        4=DROP full / 5=breakdown / 6=rebuild / 7=FINAL DROP")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
