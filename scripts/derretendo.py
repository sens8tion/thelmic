"""DERRETENDO - "derretendo meu coracao, como gelo ao sol", with a written harmony under it.

The user: "go look at the samples notes; then you create a great midi harmony for the notes to follow
- get it emphasis aligned to work beautifully against the lead." Then: "how can we make the
follower's onset points more natural, slightly ahead / delayed?" and "I'd like her pitched down too
as though she's a subtly jazzier feel".

Three lanes after MOUTHFUL, one row at the bottom of the grid, so launching that row plays these alone:
- DERRETENDO: the lead, native - the untouched original in Complex Pro, transposed -4 into A major
  (F# minor's relative; it sings in C# major) and detuned +12 c for her flat tuning, looped as a
  16-bar bed (auto-warp reads the 85 bpm loop as 64 beats at 170: half-time).
- DERRETIDA ("melted", the second her): the same clip through Live's Auto Shift, which retunes it to
  the MIDI it is sent and gates it to those notes, 6 dB under the lead. Then a Delay, whose time the
  clip draws per syllable, so she sings behind the lead the way a second singer does.
- HARMONIA: the MIDI clip with her line, feeding that Auto Shift through its sidechain "MIDI From" -
  the one setting the LOM can't reach, so the user picks it once.

The lead, pitch-tracked as it plays (after the -4) and aligned with the words: every stressed
syllable - derreTENdo, MEU, coraCAO, COmo, GElo, SOL - lands on or just before a bar line at 170.

Her line sits 2-7 semitones UNDER the lead, and changes on the lead's note onsets. Where the first
version was thirds above, this one walks down: C#-B-A#-A-G#-F# across the first four bars, 5 to 1 of
F# minor, while the lead falls more slowly, so the interval between them opens and closes - a minor
third, the fourths of an F#m11, a passing tritone, the fifth that spells F#m7. The colours:
- derreTENdo: E over B, a fourth - F#m11, open, on the stress
- MEU: E over A#, the tritone of F#7, one weak syllable - the A# the lead sings herself at COmo
- coraCAO: C# over G#, the 9 of F#m9, on the stress
- COmo: A# over F# - F# major for a beat, the V of the B minor it moves to
- GE-lo: B held under D (B minor, on the stress), then under C# - the 9, a rub on the weak "lo"...
- ...SOL: which resolves down a step, B to A, under the held C# - 11 to 3, on the stress
- the last "ao SOL": A over F#, B over G# - the 9 and 11 of F#m9 - then E under her final A: the
  close is F#m7, the jazz ending, not the triad

Her timing: the Delay's time, drawn in the clip as a step per phrase segment (changing only in the
gaps, in Fade mode): 4-8 ms on stressed syllables, where two singers lock, 25-35 ms on weak ones,
where she lays back, and 30-35 ms on the long SOLs, where a second voice arrives late. One tap,
no feedback, nothing past 35 ms - longer, and she stops being a second singer and becomes an echo. She can only
be behind: the bridge can't move a clip's start marker, so nothing puts her ahead of the lead.

Her voice: Formant Follow 25 %, so the further she's pitched down the darker she gets - a lower
singer, not the same one tuned down - and a light vibrato (12 ct, 5 Hz, "Natural") that fades in over
450 ms, so it only blooms on the held notes.

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
LEAD, VOICE, MIDI, AFTER = "DERRETENDO", "DERRETIDA", "HARMONIA", "MOUTHFUL"
OLD_VOICE = "DERRETENDO+3"      # the lane's name while she sang thirds above
TRANSPOSE, DETUNE = -4, +12
COMPLEX_PRO = 6
LOOP_BEATS = 64.0
LEVEL_DB, VOICE_UNDER_DB = -8.0, 6.0
# beats: Auto Shift GATES the voice to its MIDI notes (20 ms attack), so a note opens before the
# syllable's consonant and closes after its tail - never past the middle of the gap to the next one
EARLY, TAIL = 0.10, 0.12

# (start beat, length) of her notes, as measured - and the harmony note under each group of them.
E4, D4, C4s, B3, As3, A3, Gs3, Fs3, E3 = 64, 62, 61, 59, 58, 57, 56, 54, 52
HARMONY = [
    # phrase 1: "derretendo meu coracao, como gelo, ao sol"
    ([(0.00, 1.08)], C4s),                                        # DER        E4 over C#: F#m7, a minor third
    ([(2.12, 1.22)], B3),                                         # re         D4 over B: B minor
    ([(4.22, 0.31), (4.56, 0.82)], B3),                           # TEN-do     E4 over B: a fourth, F#m11
    ([(5.44, 0.68)], As3),                                        # MEU        E4 over A#: the tritone of F#7
    ([(6.52, 0.65), (7.28, 0.71)], A3),                           # co-ra      E4, D4 over A: F#m7's guide tones
    ([(8.67, 1.27)], Gs3),                                        # CAO        C#4 over G#: the 9
    ([(13.63, 0.79), (14.45, 0.51)], Fs3),                        # CO-mo      A#3, B3 over F#: F# major, V of Bm
    ([(15.89, 0.85), (19.10, 0.91)], B3),                         # GE-lo      D4 then C#4 over B: Bm, then the 9
    ([(23.71, 2.10)], A3),                                        # SOL        C#4 over A: the rub resolves, 11 to 3
    # phrase 2
    ([(31.93, 1.27)], C4s),                                       # DER        E4
    ([(33.21, 0.34), (33.97, 1.47)], B3),                         # re         D4 D4
    ([(36.04, 0.37), (36.47, 0.88)], B3),                         # TEN-do     E4
    ([(37.40, 0.65)], As3),                                       # MEU        E4
    ([(38.48, 0.82), (39.44, 0.45)], A3),                         # co-ra      E4, D4
    ([(40.55, 1.33)], Gs3),                                       # CAO        C#4
    ([(45.48, 0.20), (45.73, 0.59), (46.33, 0.45)], Fs3),         # CO-mo      B3 A#3 B3
    ([(47.60, 1.45), (49.07, 0.28)], B3),                         # GE-lo      D4 D4
    ([(54.46, 0.34)], Fs3),                                       # ao         A3 over F#: F# minor
    ([(55.51, 2.32)], Gs3),                                       # SOL        B3 over G#: the 9 and 11 of F#m9
    ([(57.97, 1.19)], E3),                                        # (tail)     A3 over E: the close is F#m7
]

# How far behind the lead she sings, per phrase segment (a run of her notes with no gap of GAP_BEATS
# or more - too short to change a delay cleanly). Keyed by the segment's first note.
GAP_BEATS = 0.3
LAG_MS = {
    0.00: 12,    # DER            a hair behind as she comes in
    2.12: 30,    # re             weak: laid back
    4.22: 6,     # TEN-do MEU     the stress: locked with the lead
    6.52: 28,    # co-ra          weak
    8.67: 8,     # CAO            the stress
    13.63: 32,   # CO-mo          a late entry after the rest
    15.89: 5,    # GE             the stress
    19.10: 24,   # lo             weak
    23.71: 35,   # SOL            she leans in late to the long note
    31.93: 18,   # DER-re
    33.97: 30,   # re
    36.04: 6,    # TEN-do MEU
    38.48: 30,   # co-ra
    40.55: 8,    # CAO
    45.48: 30,   # CO-mo
    47.60: 6,    # GE-lo
    54.46: 26,   # ao
    55.51: 35,   # SOL, the tail  the latest of all, on the last note
}

AUTO_SHIFT = "query:AudioFx#Auto%20Shift"
DELAY = "query:AudioFx#Delay"
FORMANT_FOLLOW = 0.25
VIBRATO = (("Vibrato Amt", 12.0), ("Vibrato Rate", 5.0), ("Vibrato Fade-In", 450.0))


def midi_notes() -> list[dict]:
    spans = [(lead[0][0], lead[-1][0] + lead[-1][1], pitch) for lead, pitch in HARMONY]
    notes = []
    for i, (on, off, pitch) in enumerate(spans):
        start = on - EARLY if i == 0 else max(on - EARLY, (spans[i - 1][1] + on) / 2)
        end = off + TAIL if i + 1 == len(spans) else min(off + TAIL, (off + spans[i + 1][0]) / 2)
        start, end = max(0.0, start), min(LOOP_BEATS, end)
        notes.append({"pitch": pitch, "start_time": round(start, 3), "duration": round(end - start, 3), "velocity": 100})
    return notes


def segments() -> list[tuple[float, float]]:
    """(first onset, last end) of each run of her notes with no gap of GAP_BEATS or more."""
    runs = []
    for s, l in sorted(n for lead, _ in HARMONY for n in lead):
        if runs and s - runs[-1][1] < GAP_BEATS:
            runs[-1][1] = max(runs[-1][1], s + l)
        else:
            runs.append([s, s + l])
    return [(a, b) for a, b in runs]


def lag_steps() -> list[tuple[float, int]]:
    """(beat, ms): each segment's lag, switched in the middle of the gap before it. The first one is
    also switched in the gap before the loop comes round."""
    segs = segments()
    if [round(a, 2) for a, _ in segs] != sorted(LAG_MS):
        raise SystemExit(f"LAG_MS keys don't match her phrase segments: {[round(a, 2) for a, _ in segs]}")
    steps = [(0.0, LAG_MS[round(segs[0][0], 2)])]
    for (_, prev_end), (on, _) in zip(segs, segs[1:]):
        steps.append((round((prev_end + on) / 2, 3), LAG_MS[round(on, 2)]))
    steps.append((round((segs[-1][1] + LOOP_BEATS + segs[0][0]) / 2, 3), LAG_MS[round(segs[0][0], 2)]))
    return steps


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

    def devices(t):
        return ch.get_track_info(t).result(timeout=5)["devices"]

    def device(t, name, query):
        if name not in [d["name"] for d in devices(t)]:
            ch.load_device(t, query).result(timeout=30)
            time.sleep(1.0)
        return next(d["index"] for d in devices(t) if d["name"] == name)

    def params(t, d):
        return {p["name"]: p for p in ch.get_device_info(t, d).result(timeout=10)["parameters"]}

    try:
        if OLD_VOICE in track_names(ch) and VOICE not in track_names(ch):
            ch.set_track_name(index_of(ch, OLD_VOICE), VOICE).result(timeout=5)
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
            ch.set_clip_name(t, row, "derretendo" + (" (her, under)" if name == VOICE else "")).result(timeout=5)
            if abs(float(ch.get_clip_props(t, row).result(timeout=5).get("length", 0)) - LOOP_BEATS) < 0.01:
                ch.set_clip_loop(t, row, True).result(timeout=5)
        # her voice: Auto Shift, following MIDI, formants following a quarter of the shift down
        v = index_of(ch, VOICE)
        shift = device(v, "Auto Shift", AUTO_SHIFT)
        idx = {n: p["index"] for n, p in params(v, shift).items()}
        for pname, value in (("Scale Aware", 0.0), ("Quantizer On", 1.0), ("Strength", 1.0), ("Pitch St.", 0.0),
                             ("Pitch Scale Deg.", 0.0), ("Formant Follow", FORMANT_FOLLOW), ("Formant Shift", 0.5),
                             ("Vibrato Natural", 1.0), ("Dry/Wet", 1.0)):
            try:
                ch.set_device_param(v, shift, idx[pname], value).result(timeout=5)
            except Exception as e:
                print(f"    [note] Auto Shift {pname}: {e}")
        for pname, value in VIBRATO:
            set_number(ch, v, shift, pname, value)
        # her timing: a Delay, all wet, one tap, no filter, its time crossfading when it changes
        dl = device(v, "Delay", DELAY)
        idx = {n: p["index"] for n, p in params(v, dl).items()}
        for pname, value in (("Smoothing", 1.0), ("Link", 1.0), ("Ping Pong", 0.0), ("L Sync", 0.0), ("R Sync", 0.0),
                             ("Feedback", 0.0), ("Freeze", 0.0), ("Filter On", 0.0), ("LFO > Delay", 0.0),
                             ("Dry/Wet", 1.0)):
            ch.set_device_param(v, dl, idx[pname], value).result(timeout=5)
        steps = lag_steps()
        raw = {}
        # finding each time's raw value swings the knob from 1 ms to 5 s: bypass the Delay meanwhile,
        # or a playing voice gets thrown seconds late
        ch.set_device_param(v, dl, idx["Device On"], 0.0).result(timeout=5)
        for ms in sorted({ms for _, ms in steps}):
            set_number(ch, v, dl, "L Time", float(ms))
            raw[ms] = params(v, dl)["L Time"]["value"]
        set_number(ch, v, dl, "L Time", float(steps[0][1]))
        ch.set_device_param(v, dl, idx["Device On"], 1.0).result(timeout=5)
        ch.set_clip_envelope(v, row, v, dl, "L Time", [[b, raw[ms]] for b, ms in steps] + [[LOOP_BEATS - 0.01, raw[steps[0][1]]]]).result(timeout=10)
        # her line, into that Auto Shift - written only if it changed
        m = index_of(ch, MIDI)
        if row not in {c.get("slot", c.get("index")) for c in clips_of(m)}:
            ch.create_clip(m, row, LOOP_BEATS).result(timeout=10)
        want = midi_notes()
        have = ch.get_clip_notes(m, row).result(timeout=10)
        have = have.get("notes", have) if isinstance(have, dict) else have
        key = lambda n: (round(float(n["start_time"]), 3), int(n["pitch"]), round(float(n["duration"]), 3))
        if sorted(map(key, have)) != sorted(map(key, want)):
            ch.add_notes_to_clip(m, row, want, replace=True).result(timeout=10)
            print(f"  {MIDI}: wrote {len(want)} notes")
        ch.set_clip_name(m, row, "harmonia - down under her: F#m7, a 9, an 11 that falls to 3").result(timeout=5)
        # Auto Shift takes its MIDI through its own sidechain input ("MIDI From"), which the LOM doesn't
        # expose on the device, and a MIDI track can't route its output to an audio track's effect.
        # One dropdown for the user: DERRETIDA > Auto Shift > sidechain > MIDI From: HARMONIA.
        for name, db in ((LEAD, LEVEL_DB), (VOICE, LEVEL_DB - VOICE_UNDER_DB)):
            tt = index_of(ch, name)
            set_number(ch, tt, ensure_level(ch, tt, name), "Output", db)
        # read back
        for name in (LEAD, VOICE):
            tt = index_of(ch, name)
            pr = ch.get_clip_props(tt, row).result(timeout=5)
            print(f"  {name:<13} (track {tt + 1}) row {row + 1}: mode {pr.get('warp_mode')} transpose {int(pr['pitch_coarse']):+d} "
                  f"detune {int(pr['pitch_fine']):+d} loop {pr.get('looping')} {pr.get('length')} beats | "
                  + " > ".join(d["name"] for d in devices(tt)))
        print(f"  {MIDI:<13} (track {m + 1}) row {row + 1}: {len(want)} notes - set Auto Shift's MIDI From to it")
        ps = params(v, shift)
        print("  Auto Shift:", {n: ps[n]["display"] for n in ("Quantizer On", "Strength", "Formant Follow", "Smooth Time",
                                                              "Vibrato Amt", "Vibrato Rate", "Vibrato Fade-In", "Vibrato Natural", "Latch")})
        ps = params(v, dl)
        print("  Delay:", {n: ps[n]["display"] for n in ("Smoothing", "L Sync", "L Time", "Feedback", "Filter On", "Dry/Wet")})
        print("  lag (ms) by beat:", " ".join(f"{b:g}:{ms}" for b, ms in steps))
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
