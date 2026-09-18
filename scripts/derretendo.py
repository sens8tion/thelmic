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
- HARMONIA: the MIDI clip with her line, feeding that Auto Shift through its MIDI Input panel
  (MIDI On, External Source: HARMONIA) - which the LOM can't reach, so the user sets it once.

The lead, pitch-tracked as it plays (after the -4) and aligned with the words: every stressed
syllable - derreTENdo, MEU, coraCAO, COmo, GElo, SOL - lands on or just before a bar line at 170.

Her line comes in five versions, one per row, so the user can launch each and compare (the user: "let
her be more openly jazzy in the notes she shifts to and from. Maybe make several harmonia midi clips
which I can select for comparison"). Every row holds the lead, her, and one HARMONIA clip, so a row
plays in sync from the top. Launching only a HARMONIA clip would restart it against audio already
playing, unless its launch mode is Legato - which the bridge can't set. Where a version moves inside
one syllable, the notes overlap and Auto Shift GLIDES (Glide Time only acts on overlapping notes):
- CASCA ("shell"), as she was: shell voicings 5-9 st under - sixths, fifths and tritones, one note per
  syllable. F#m7 on DER, E7's tritone on re, F#m9 under TEN-do MEU, a sixth on coraCAO, F#7 on COmo,
  i to i7 on SOL; phrase 2 ends VI turning to iv, then an F#m7 close.
- RASTEJA ("creeps"): the same targets, every one approached by a half step - a scoop from below or
  a fall from above - and chromatic line cliches under the held notes: F#m7 to F#m6 under coraCAO,
  a G-over-C# tritone substitute on "lo" sliding into SOL, D to D# to E into the last note.
- DIABINHO ("little devil", the tritone): dominant tension on the weak syllables - tritones planing in
  parallel (E-over-A# to D-over-G#) - resolved by half steps onto the stresses; coraCAO approached from
  G above; phrase 2 ends on B-over-F, G7 - the tritone substitute for C#7 - falling to F#m7.
- QUARTAS ("fourths"): modal, "So What" - she planes a fourth under the lead, chromatically too
  (A#-over-F under COmo), with the dorian D# as the colour: F#m6 under coraCAO and SOL, B major (the
  dorian IV) under the last SOL, and an F#m6 ending. Higher than the others: fourths sit 5 st under.
- AZULADA ("bluish"): blues inflections - a minor-to-major smear (A to A# and back) under DER, whole-step
  scoops, pentatonic falls under the held notes, the E-to-E# smear on coraCAO, and a fall to C# at the end.

Her timing: the Delay's time, drawn in the clip as a step per phrase segment (changing only in the
gaps, in Fade mode): 4-8 ms on stressed syllables, where two singers lock, 25-35 ms on weak ones,
where she lays back, and 30-35 ms on the long SOLs, where a second voice arrives late. One tap,
no feedback, nothing past 35 ms - longer, and she stops being a second singer and becomes an echo. She can only
be behind: the bridge can't move a clip's start marker, so nothing puts her ahead of the lead.

Then the user: "I've concluded that the midi following is too abrupt no matter the settings I use; so
I've switched to key aware -3st quantizer". So DERRETIDA no longer follows HARMONIA: Auto Shift's
Quantizer shifts her 3 st down and snaps her to the set's scale (Scale Aware: F# minor) - a diatonic
third under, which bends with her own pitch instead of stepping at note boundaries. Her formants follow
66 % of the shift, 11 cents flat of the lead, 20 ms smoothing. USER_AUTO_SHIFT is the user's device,
read back raw; the script writes it only onto a freshly loaded Auto Shift, never over one that exists.
The user also put an EQ Eight after the Delay, by hand. The five HARMONIA lines stay in rows 22-26 as
a record, but no longer drive her.

    python scripts/derretendo.py              # everything
    python scripts/derretendo.py --harmony    # her lines and Auto Shift only: leaves the Delay's timing alone
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
LEGATO = 0.03                  # beats a move inside a syllable overlaps the note before it

# Her notes, as measured: (start beat, length, pitch as heard, syllable).
E4, D4, Cs4, B3, As3, A3, Gs3, G3, Fs3, F3, E3, Ds3, D3, Cs3 = 64, 62, 61, 59, 58, 57, 56, 55, 54, 53, 52, 51, 50, 49
LEAD_NOTES = [
    # phrase 1: "derretendo meu coracao, como gelo, ao sol"
    (0.00, 1.08, E4, "DER"), (2.12, 1.22, D4, "re"), (4.22, 0.31, E4, "TEN"), (4.56, 0.82, E4, "do"),
    (5.44, 0.68, E4, "MEU"), (6.52, 0.65, E4, "co"), (7.28, 0.71, D4, "ra"), (8.67, 1.27, Cs4, "CAO"),
    (13.63, 0.79, As3, "CO"), (14.45, 0.51, B3, "mo"), (15.89, 0.85, D4, "GE"), (19.10, 0.91, Cs4, "lo"),
    (23.71, 2.10, Cs4, "SOL"),
    # phrase 2
    (31.93, 1.27, E4, "DER"), (33.21, 0.34, D4, "re"), (33.97, 1.47, D4, "re"), (36.04, 0.37, E4, "TEN"),
    (36.47, 0.88, E4, "do"), (37.40, 0.65, E4, "MEU"), (38.48, 0.82, E4, "co"), (39.44, 0.45, D4, "ra"),
    (40.55, 1.33, Cs4, "CAO"), (45.48, 0.20, B3, "CO"), (45.73, 0.59, As3, "mo"), (46.33, 0.45, B3, "mo"),
    (47.60, 1.45, D4, "GE"), (49.07, 0.28, D4, "lo"), (54.46, 0.34, A3, "ao"), (55.51, 2.32, B3, "SOL"),
    (57.97, 1.19, A3, "(tail)"),
]

# Her lines. One entry per lead note: a pitch she holds for the syllable, or [(beats in, pitch), ...]
# for moves inside it. The same pitch on the next syllable of a phrase is held, not re-struck.
SCOOP = 0.12                    # beats spent on the approach note before she glides onto the target


def up(p, by=1):
    """scoop into p from `by` semitones under"""
    return [(0, p - by), (SCOOP, p)]


def down(p):
    """fall into p from a half step above"""
    return [(0, p + 1), (SCOOP, p)]


VARIANTS = [  # (name, what it does, [one entry per LEAD_NOTES])
    ("casca", "shells, as she was", [
        A3, Gs3, Gs3, Gs3, Gs3, A3, A3, E3, E3, E3, Fs3, Fs3, E3,
        A3, Gs3, Gs3, Gs3, Gs3, Gs3, A3, A3, E3, E3, E3, E3, Fs3, Fs3, D3, D3, E3]),
    ("rasteja", "half-step approaches, line cliches", [
        up(A3),                                  # DER   scooped onto F#m7's guide tones
        down(Gs3),                               # re    falls onto E7's tritone
        Gs3, [(0, Gs3), (0.4, A3)], As3,         # TEN-do MEU  G#, A, A#: creeping up under the held E
        A3, A3,                                  # co-ra
        [(0, F3), (SCOOP, E3), (0.7, Ds3)],      # CAO   falls onto E, then E to D#: F#m7 to F#m6
        E3, D3,                                  # CO-mo F#7 resolving to Bm: E to D under A# to B
        up(Fs3),                                 # GE
        G3,                                      # lo    C# over G: a tritone substitute...
        [(0, Fs3), (1.0, E3)],                   # SOL   ...sliding a half step to F#, then i to i7
        [(0, Gs3), (SCOOP, A3), (0.75, Gs3)],    # DER
        Gs3, [(0, Gs3), (0.8, G3)],              # re re G#, G...
        Fs3, [(0, Fs3), (0.45, G3)], up(Gs3),    # TEN-do MEU  ...F# on the stress, then back up G, G#
        A3, A3,                                  # co-ra
        [(0, F3), (SCOOP, E3), (0.75, Ds3)],     # CAO
        E3, E3, D3,                              # CO-mo
        [(0, F3), (SCOOP, Fs3), (0.8, G3)],      # GE
        G3,                                      # lo
        E3,                                      # ao
        [(0, D3), (1.3, Ds3)],                   # SOL   Bm to B major, the dorian IV...
        E3]),                                    # tail  ...D, D#, E: creeping into F#m7
    ("diabinho", "tritones planing, resolved by half steps", [
        As3, Gs3,                                # DER re    E over A#, D over G#: two dominants, planing
        A3,                                      # TEN   G# up to A: resolved on the stress
        [(0, A3), (0.45, As3)], down(A3),        # do MEU  A, A#, A
        As3, Gs3,                                # co-ra planing again
        [(0, G3), (SCOOP, Fs3)],                 # CAO   G# to G to F#: slid down onto the stress
        E3, D3,                                  # CO-mo F#7's 3 and 7, resolving to Bm
        Fs3, G3,                                 # GE lo C# over G, the tritone...
        [(0, Fs3), (1.1, E3)],                   # SOL   ...resolved a half step down
        As3, Gs3, [(0, Gs3), (0.8, G3)],         # DER re re
        up(Gs3), A3, As3, A3, Gs3,               # TEN do MEU co ra
        [(0, G3), (SCOOP, Fs3)],                 # CAO
        F3, E3, D3,                              # CO-mo B over F, A# over E: tritones sliding a half step
        Fs3, Gs3,                                # GE lo
        Ds3,                                     # ao    A over D#: B7's tritone
        [(0, D3), (1.4, F3)],                    # SOL   Bm, then B over F: G7, the substitute for C#7...
        E3]),                                    # tail  ...falling a half step into F#m7
    ("quartas", "dorian fourths, planing", [
        Gs3, Fs3,                                # DER re
        B3, [(0, B3), (0.45, Gs3)], Gs3,         # TEN do MEU  E over B: a fourth, "So What"; then the 9
        B3, A3,                                  # co-ra fourths
        [(0, Gs3), (0.65, Ds3)],                 # CAO   a fourth, then the dorian 13: F#m6
        E3, Fs3,                                 # CO-mo
        A3, Gs3,                                 # GE lo fourths
        [(0, Gs3), (0.9, E3), (1.5, Ds3)],       # SOL   fourth, sixth, the 13
        [(0, B3), (0.7, Gs3)],                   # DER
        A3, [(0, A3), (0.8, Fs3)],               # re re
        B3, [(0, B3), (0.45, Gs3)], Gs3,         # TEN do MEU
        B3, A3,                                  # co-ra
        [(0, Gs3), (0.7, Ds3)],                  # CAO
        Fs3, F3, Fs3,                            # CO-mo fourths planing chromatically: B/F#, A#/F, B/F#
        A3, A3,                                  # GE lo
        E3,                                      # ao
        [(0, Fs3), (1.2, Ds3)],                  # SOL   a fourth, then B major: the dorian IV
        [(0, E3), (0.5, Ds3)]]),                 # tail  ends on F#m6
    ("azulada", "blue smears, scoops and falls", [
        [(0, A3), (0.4, As3), (0.8, A3)],        # DER   the minor third smeared up to major and back
        up(Fs3, 2),                              # re    a whole-step scoop
        up(A3), A3, [(0, A3), (0.4, Fs3)],       # TEN do MEU  a pentatonic fall under the held E
        [(0, Fs3), (0.3, A3)],                   # co
        [(0, A3), (0.45, Fs3)],                  # ra
        [(0, E3), (0.5, F3), (0.9, E3)],         # CAO   E smeared to E# and back
        E3, [(0, E3), (0.2, Fs3)],               # CO-mo
        [(0, F3), (SCOOP, Fs3), (0.55, A3)],     # GE
        [(0, A3), (0.3, Fs3)],                   # lo
        [(0, Ds3), (SCOOP, E3), (1.2, Fs3), (1.7, E3)],  # SOL  scooped, lifted, back
        [(0, A3), (0.45, As3), (0.9, A3)],       # DER
        Fs3, [(0, Fs3), (0.8, A3)],              # re re
        up(A3), A3, [(0, A3), (0.35, Fs3)],      # TEN do MEU
        [(0, Fs3), (0.4, A3)], A3,               # co-ra
        [(0, E3), (0.5, F3), (0.95, E3)],        # CAO
        E3, E3, Fs3,                             # CO-mo
        [(0, F3), (SCOOP, Fs3), (0.8, A3)], A3,  # GE lo
        E3,                                      # ao
        [(0, E3), (0.15, Fs3), (1.4, E3)],       # SOL
        [(0, E3), (0.7, Cs3)]]),                 # tail  falls to C# as it dies
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
# The user's Auto Shift on DERRETIDA (2026-09-18), raw values as read back. Root and Scale go in before
# Scale Aware: once it is on, they are greyed out and a write raises "parameter is disabled".
USER_AUTO_SHIFT = (
    ("Root", 6.0),                   # F#
    ("Scale", 3.0),                  # Minor
    ("Scale Aware", 1.0),            # On - the set's scale
    ("Quantizer On", 1.0),
    ("Strength", 1.0),               # 100 %
    ("Pitch St.", -3.0),             # -3 st: a diatonic third under, once snapped to the scale
    ("Pitch Scale Deg.", 0.0),
    ("Pitch Fine", 0.445312),        # -11 ct
    ("Formant Shift", 0.5),          # 0 %
    ("Formant Follow", 0.664062),    # 66 %
    ("Smooth On", 1.0),
    ("Smooth Time", 0.5625),         # 20.0 ms
    ("Glide Time", 0.070312),        # 9.89 ms
    ("Attack Time", 0.117188),       # 13.7 ms
    ("Release Time", 0.304688),      # 141 ms
    ("Latch", 0.0),                  # Gate
    ("PB Range", 0.0),               # 0 st
    ("Input Gain", 0.59375),         # 4.5 dB
    ("Vibrato Amt", 0.0),            # 0 ct
    ("Vibrato Rate", 0.375816),      # 5.00 Hz
    ("Vibrato Fade-In", 0.171875),   # 59.1 ms
    ("Vibrato Natural", 1.0),        # On
    ("Dry/Wet", 1.0),                # 100 %
)
HARMONY_ONLY = "--harmony" in sys.argv


def midi_notes(entries) -> list[dict]:
    """Her line as MIDI. A change on a new syllable is a clean step: the notes meet in the middle of the
    gap, never more than EARLY before the syllable or TAIL after the last one. A change inside a
    syllable is legato - the new note overlaps the old by LEGATO - so Auto Shift glides between them."""
    if len(entries) != len(LEAD_NOTES):
        raise SystemExit(f"{len(entries)} entries for {len(LEAD_NOTES)} lead notes")
    notes, prev_end = [], None
    for (on, length, _, syl), entry in zip(LEAD_NOTES, entries):
        moves = [(0.0, entry)] if isinstance(entry, int) else entry
        for off, _ in moves[1:]:
            if not 0 < off < length - 0.05:
                raise SystemExit(f"{syl} at beat {on}: a move {off} beats in is outside the syllable")
        if not (notes and moves[0][1] == notes[-1][2] and on - prev_end < GAP_BEATS):
            if notes:
                mid = (prev_end + on) / 2
                notes[-1][1] = min(prev_end + TAIL, mid)
                start = max(on - EARLY, mid)
            else:
                start = on - EARLY
            notes.append([start, None, moves[0][1]])
        for off, pitch in moves[1:]:
            if pitch != notes[-1][2]:
                notes[-1][1] = on + off + LEGATO
                notes.append([on + off, None, pitch])
        prev_end = on + length
    notes[-1][1] = prev_end + TAIL
    return [{"pitch": pitch, "start_time": round(max(0.0, a), 3), "duration": round(min(LOOP_BEATS, b) - max(0.0, a), 3),
             "velocity": 100} for a, b, pitch in notes]


def segments() -> list[tuple[float, float]]:
    """(first onset, last end) of each run of her notes with no gap of GAP_BEATS or more."""
    runs = []
    for s, l, _, _ in LEAD_NOTES:
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
        # her voice: Auto Shift as the user set it - written only onto a freshly loaded one
        v = index_of(ch, VOICE)
        fresh = "Auto Shift" not in [d["name"] for d in devices(v)]
        shift = device(v, "Auto Shift", AUTO_SHIFT)
        if fresh:
            idx = {n: p["index"] for n, p in params(v, shift).items()}
            for pname, value in USER_AUTO_SHIFT:
                try:
                    ch.set_device_param(v, shift, idx[pname], value).result(timeout=5)
                except Exception as e:
                    print(f"    [note] Auto Shift {pname}: {e}")
        if not HARMONY_ONLY:
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
        # her lines, one row each, beside a copy of the lead and of her - each written only if it changed
        rows = [row + k for k in range(len(VARIANTS))]
        have = ch.get_scene_count().result(timeout=5)["count"]
        ours = {index_of(ch, n) for n in (LEAD, VOICE, MIDI)}
        for t in range(len(track_names(ch))):
            if t not in ours and any(c.get("slot", c.get("index")) in rows[1:] for c in clips_of(t)):
                raise SystemExit(f"track {t + 1} has clips in rows {rows[1] + 1}-{rows[-1] + 1}: they'd fire with a version")
        for _ in range(rows[-1] + 1 - have):
            ch.create_scene(-1).result(timeout=10)
        for name in (LEAD, VOICE):
            t = index_of(ch, name)
            filled = {c.get("slot", c.get("index")) for c in clips_of(t)}
            for r in rows[1:]:
                if r not in filled:
                    ch.duplicate_clip(t, row, r).result(timeout=10)
        m = index_of(ch, MIDI)
        filled = {c.get("slot", c.get("index")) for c in clips_of(m)}
        key = lambda n: (round(float(n["start_time"]), 3), int(n["pitch"]), round(float(n["duration"]), 3))
        for r, (vname, what, entries) in zip(rows, VARIANTS):
            if r not in filled:
                ch.create_clip(m, r, LOOP_BEATS).result(timeout=10)
            want = midi_notes(entries)
            got = ch.get_clip_notes(m, r).result(timeout=10)
            got = got.get("notes", got) if isinstance(got, dict) else got
            if sorted(map(key, got)) != sorted(map(key, want)):
                ch.add_notes_to_clip(m, r, want, replace=True).result(timeout=10)
                print(f"  {MIDI} row {r + 1}: wrote {vname}, {len(want)} notes")
            ch.set_clip_name(m, r, f"{vname} - {what}").result(timeout=5)
            ch.set_scene_name(r, f"DERRETIDA {vname}").result(timeout=5)
        # Auto Shift takes its MIDI through its own MIDI Input panel, which the LOM doesn't expose, and a
        # MIDI track can't route its output to an audio track's effect. The user does it once: DERRETIDA >
        # Auto Shift > MIDI In > MIDI On, External Source: HARMONIA, voice mode Mono.
        for name, db in ((LEAD, LEVEL_DB), (VOICE, LEVEL_DB - VOICE_UNDER_DB)):
            tt = index_of(ch, name)
            if "LEVEL" not in [d["name"] for d in devices(tt)]:     # a new lane: level it once, then it's the user's
                set_number(ch, tt, ensure_level(ch, tt, name), "Output", db)
        # read back
        for name in (LEAD, VOICE):
            tt = index_of(ch, name)
            pr = ch.get_clip_props(tt, row).result(timeout=5)
            print(f"  {name:<13} (track {tt + 1}) row {row + 1}: mode {pr.get('warp_mode')} transpose {int(pr['pitch_coarse']):+d} "
                  f"detune {int(pr['pitch_fine']):+d} loop {pr.get('looping')} {pr.get('length')} beats | "
                  + " > ".join(d["name"] for d in devices(tt)))
        print(f"  {MIDI:<13} (track {m + 1}) rows {rows[0] + 1}-{rows[-1] + 1}: " + ", ".join(v[0] for v in VARIANTS))
        ps = params(v, shift)
        print("  Auto Shift:", {n: ps[n]["display"] for n in ("Scale Aware", "Pitch St.", "Pitch Fine", "Formant Follow",
                                                              "Smooth Time", "Release Time")})
        if not HARMONY_ONLY:
            ps = params(v, dl)
            print("  Delay:", {n: ps[n]["display"] for n in ("Smoothing", "L Sync", "L Time", "Feedback", "Filter On", "Dry/Wet")})
            print("  lag (ms) by beat:", " ".join(f"{b:g}:{ms}" for b, ms in steps))
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
