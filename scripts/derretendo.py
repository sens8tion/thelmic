"""DERRETENDO - "derretendo meu coracao, como gelo ao sol", with a written harmony.

The user: "go look at the samples notes; then you create a great midi harmony for the notes to follow
- get it emphasis aligned to work beautifully against the lead."

Four lanes after MOUTHFUL, one row at the bottom of the grid, so launching that row plays these alone:
- DERRETENDO: the lead, native - the untouched original in Complex Pro, transposed -4 into A major
  (F# minor's relative; it sings in C# major) and detuned +12 c for her flat tuning, looped as a
  16-bar bed (auto-warp reads the 85 bpm loop as 64 beats at 170: half-time).
- DERRETENDO+3: the same clip through Live's Auto Shift, which retunes it to whatever MIDI it is
  sent, formants kept, 6 dB under the lead.
- HARMONIA: a MIDI clip with the harmony line below, feeding that Auto Shift through its sidechain
  "MIDI From" - the one setting the LOM can't reach, so the user picks it once.

The lead, pitch-tracked as it plays (after the -4) and aligned with the words: every stressed
syllable - derreTENdo, MEU, coraCAO, COmo, GElo, SOL - lands on or just before a bar line at 170.
The harmony changes exactly on her note onsets (a hair early, so Auto Shift is on the pitch when
the syllable starts), holds one note where she repeats one, and is built on diatonic thirds above
with four departures, each placed on a stress:
- coraCAO: the lead falls D->C#, the harmony rises F#->A - contrary motion onto an F# minor sixth
- COmo: the harmony holds D4 while she moves through the chromatic A#3 to B3 - it resolves under it
- GE-lo ... SOL, the first time: a 4-3 suspension - F#4 held against C#4 on "lo", resolving to E4
  exactly on the stressed SOL
- the last SOL: D4 (B minor, iv) moving to F#4 as she falls B3->A3 - a plagal close on F# minor

    python scripts/derretendo.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

BROWSER = "user_library/Samples/Splice/saudade_originals"
FILE = "RP_JV_85_vocal_vibe_Gb.wav"
LEAD, VOICE, MIDI, AFTER = "DERRETENDO", "DERRETENDO+3", "HARMONIA", "MOUTHFUL"
TRANSPOSE, DETUNE = -4, +12
COMPLEX_PRO = 6
LOOP_BEATS = 64.0
LEVEL_DB, VOICE_UNDER_DB = -8.0, 6.0
EARLY, TAIL = 0.06, 0.08      # beats: MIDI starts a hair before the syllable, ends just after it

# (start beat, length) of her notes, as measured - and the harmony note over each group of them.
G4s, F4s, A4, D4, E4, C4s = 68, 66, 69, 62, 64, 61
HARMONY = [
    # phrase 1: "derretendo meu coracao, como gelo, ao sol"
    ([(0.00, 1.08)], G4s),                                         # DER        E4  -> third above
    ([(2.12, 1.22)], F4s),                                         # re         D4
    ([(4.22, 0.31), (4.56, 0.82), (5.44, 0.68), (6.52, 0.65)], G4s),   # TEN-do MEU co   E4 x4: one held note
    ([(7.28, 0.71)], F4s),                                         # ra         D4
    ([(8.67, 1.27)], A4),                                          # CAO        C#4 - contrary, F#m sixth
    ([(13.63, 0.79), (14.45, 0.51)], D4),                          # CO-mo      A#3->B3 under a held D4
    ([(15.89, 0.85), (19.10, 0.91)], F4s),                         # GE-lo      D4, then C#4: the 4 of a 4-3
    ([(23.71, 2.10)], E4),                                         # SOL        C#4 - the 3, on the stress
    # phrase 2
    ([(31.93, 1.27)], G4s),                                        # DER
    ([(33.21, 0.34), (33.97, 1.47)], F4s),                         # re
    ([(36.04, 0.37), (36.47, 0.88), (37.40, 0.65), (38.48, 0.82)], G4s),  # TEN-do MEU co
    ([(39.44, 0.45)], F4s),                                        # ra
    ([(40.55, 1.33)], A4),                                         # CAO
    ([(45.48, 0.20), (45.73, 0.59), (46.33, 0.45)], D4),           # CO-mo      B3 A#3 B3
    ([(47.60, 1.45), (49.07, 0.28)], F4s),                         # GE-lo      D4 D4
    ([(54.46, 0.34)], C4s),                                        # ao         A3
    ([(55.51, 2.32)], D4),                                         # SOL        B3 - B minor, iv
    ([(57.97, 1.19)], F4s),                                        # (tail)     A3 - F# minor, home
]


def midi_notes() -> list[dict]:
    notes = []
    for lead, pitch in HARMONY:
        start = max(0.0, lead[0][0] - EARLY)
        end = min(LOOP_BEATS, lead[-1][0] + lead[-1][1] + TAIL)
        notes.append({"pitch": pitch, "start_time": round(start, 3), "duration": round(end - start, 3), "velocity": 100})
    return notes


def main() -> None:
    os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
    from thelmic.live_channel import LiveChannel
    from jungle_reset import index_of, track_names
    from jungle_space import set_number
    from jungle_levels_native import ensure_level
    ch = LiveChannel(lower_priority=False)
    ch.start()

    def clips_of(t):
        c = ch.get_track_clips(t).result(timeout=10)
        return c.get("clips", c) if isinstance(c, dict) else c

    try:
        prev = AFTER
        for name in (LEAD, VOICE, MIDI):
            if name not in track_names(ch):
                make = ch.create_midi_track if name == MIDI else ch.create_audio_track
                t = make(index_of(ch, prev) + 1).result(timeout=10)["index"]
                ch.set_track_name(t, name).result(timeout=5)
            prev = name
        # their own row at the bottom of the grid
        rows = [c.get("slot", c.get("index")) for name in (LEAD, VOICE) for c in clips_of(index_of(ch, name))]
        row = min(rows) if rows else ch.get_scene_count().result(timeout=5)["count"]
        if row >= ch.get_scene_count().result(timeout=5)["count"]:
            ch.create_scene(-1).result(timeout=10)
        for name in (LEAD, VOICE):
            t = index_of(ch, name)
            if row not in {c.get("slot", c.get("index")) for c in clips_of(t)}:
                ch.load_audio_to_slot(t, row, BROWSER, FILE).result(timeout=30)
            for _ in range(40):
                try:
                    ch.set_clip_warp(t, row, warping=True, warp_mode=COMPLEX_PRO).result(timeout=5)
                    break
                except Exception:
                    time.sleep(0.25)
            ch.set_clip_pitch(t, row, coarse=TRANSPOSE, fine=DETUNE).result(timeout=5)
            ch.set_clip_name(t, row, "derretendo" + (" (harmony voice)" if name == VOICE else "")).result(timeout=5)
            if abs(float(ch.get_clip_props(t, row).result(timeout=5).get("length", 0)) - LOOP_BEATS) < 0.01:
                ch.set_clip_loop(t, row, True).result(timeout=5)
        # the harmony voice: Auto Shift, following MIDI, formants kept
        v = index_of(ch, VOICE)
        if "Auto Shift" not in [d["name"] for d in ch.get_track_info(v).result(timeout=5)["devices"]]:
            ch.load_device(v, "query:AudioFx#Auto%20Shift").result(timeout=30)
            time.sleep(1.0)
        shift = next(d["index"] for d in ch.get_track_info(v).result(timeout=5)["devices"] if d["name"] == "Auto Shift")
        idx = {p["name"]: p["index"] for p in ch.get_device_info(v, shift).result(timeout=10)["parameters"]}
        for pname, value in (("Scale Aware", 0.0), ("Quantizer On", 1.0), ("Strength", 1.0), ("Pitch St.", 0.0),
                             ("Pitch Scale Deg.", 0.0), ("Formant Follow", 0.0), ("Formant Shift", 0.5), ("Dry/Wet", 1.0)):
            try:
                ch.set_device_param(v, shift, idx[pname], value).result(timeout=5)
            except Exception as e:
                print(f"    [note] Auto Shift {pname}: {e}")
        # the harmony line, into that Auto Shift
        m = index_of(ch, MIDI)
        if row not in {c.get("slot", c.get("index")) for c in clips_of(m)}:
            ch.create_clip(m, row, LOOP_BEATS).result(timeout=10)
        ch.add_notes_to_clip(m, row, midi_notes(), replace=True).result(timeout=10)
        ch.set_clip_name(m, row, "harmonia - thirds, a 4-3, a plagal close").result(timeout=5)
        # Auto Shift takes its MIDI through its own sidechain input ("MIDI From"), which the LOM doesn't
        # expose on the device, and a MIDI track can't route its output to an audio track's effect.
        # One dropdown for the user: DERRETENDO+3 > Auto Shift > sidechain > MIDI From: HARMONIA.
        for name, db in ((LEAD, LEVEL_DB), (VOICE, LEVEL_DB - VOICE_UNDER_DB)):
            tt = index_of(ch, name)
            set_number(ch, tt, ensure_level(ch, tt, name), "Output", db)
        # read back
        for name in (LEAD, VOICE):
            tt = index_of(ch, name)
            pr = ch.get_clip_props(tt, row).result(timeout=5)
            print(f"  {name:<13} (track {tt + 1}) row {row + 1}: mode {pr.get('warp_mode')} transpose {int(pr['pitch_coarse']):+d} "
                  f"detune {int(pr['pitch_fine']):+d} loop {pr.get('looping')} {pr.get('length')} beats | "
                  + " > ".join(d["name"] for d in ch.get_track_info(tt).result(timeout=5)["devices"]))
        print(f"  {MIDI:<13} (track {m + 1}) row {row + 1}: {len(midi_notes())} notes - set Auto Shift's MIDI From to it")
        vals = {p["name"]: round(p["value"], 2) for p in ch.get_device_info(v, shift).result(timeout=10)["parameters"]
                if p["name"] in ("Scale Aware", "Quantizer On", "Strength", "Formant Follow", "Latch", "Glide Time")}
        print("  Auto Shift:", vals)
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
