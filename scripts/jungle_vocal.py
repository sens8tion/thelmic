"""JUNGLE VOCAL - the hook, sung locally, at the session's tempo.

The user's words: hop, bump, lick, bubble. Three that hit and one that holds - a word held
on a long note has to end open, and of these only "bubble" does (the others end in plosives,
which die on a sustain: 1 in 5 survive).

Shape from the reference (tracks/2026-09-16_reaper/hooks.md): hooks are short - median 1.2
beats - sit in the low mids, and leave gaps for the sub to answer. So: chat on the offbeats
in F# minor, land on "bubble", and leave the last beat of the phrase to the 808.

Two versions of the same phrase, because "bubble" is two syllables:
  one-note   the whole word on one note, the renderer fitting both syllables into it
  split      "bub" and "ble" on their own notes, the second one held
  phrases    each word made a phrase of its own: "<word> like this" / "<word> like that"

CPU only. The GPU is shared with Live and is asked for, never taken (sources/vocal.py).
Takes are kept: there is no seed, so a take you like cannot be rendered again.

    python scripts/jungle_vocal.py              # render both, keep them in tracks/vocals/
    python scripts/jungle_vocal.py one-note     # just one
"""
from __future__ import annotations

import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = Path(SCRIPTS_DIR).parent
sys.path.insert(0, str(REPO))

KEPT = REPO / "tracks" / "vocals"
SPEAKER = "tiger_electric"          # the brightest mode: it cuts a dense mix

CS4, E4, A3, FS3 = 61, 64, 57, 54
# Every stop-final word comes back from the dictionary with a trailing "cl", the stop closure, and
# the renderer gives it ~46 ms: at the end of a phrase that closure sounds as a voiced "uh" (heard
# by the user, then found in bench/diag_durations.py). These are the same pronunciations without it.
NO_CLOSURE = {"hop": ["hh", "ao", "p"], "bump": ["b", "ah", "m", "p"], "lick": ["l", "ih", "k"],
              "that": ["dh", "ae", "t"], "it": ["ih", "t"]}   # C#, E, A, F# - all in F# minor, in the hook's register


def hit(word, midi, beats=0.5, scoop=-1.2):
    return {"lyric": word, "midi": midi, "beats": beats, "scoop": scoop, "scoop_beats": 0.2}


def rest(beats=0.5):
    return {"rest": True, "beats": beats}


def chat():
    """hop . bump . lick . — the three short words, twice."""
    return [hit("hop", CS4), rest(), hit("bump", CS4, scoop=-1.0), rest(),
            hit("lick", E4, scoop=-1.6), rest()]


def phrase(word, midi, tail, tail_midi=None, *, word_phonemes=None, scoop=-1.2,
           lead_beats=1.25, like_lift=0.0):
    """One bar on the track's grid: the lead word from beat 1, "like <tail>" landing on beat 3,
    then a beat of air for the sub and break to answer.

    Sized by measurement (scripts/jungle_vocal_takes.py, 6 takes a phrase, word by word):
      * a short lead word starved its consonants - "hop" was heard as "hope", "lick" as "night" -
        so the lead gets 0.75 beats, and a word the model under-sings gets more.
      * "like" landed 60-115 cents FLAT when the phrase was rushed, so it was written sharp to
        compensate (`like_lift`, fractional MIDI). Rendering unhurried and warping to the grid
        fixed the cause, and the compensation then overshot to +68 cents, so it is back to 0.
      * the tag sat 12-16 dB under the peak and was heard as "it" or "a sir"; it now gets the
        beat that the lead gave up.
      * the scoop is 0.15 beats: on a 176 ms note a 0.2-beat scoop was most of the note.
    """
    tags = 3.0 - lead_beats            # the phrase lands on beat 4, and is warped to fit
    lead = {"midi": midi, "beats": lead_beats, "scoop": scoop, "scoop_beats": 0.15, "word": word}
    lead.update({"phonemes": list(word_phonemes or NO_CLOSURE.get(word) or [])} if (word_phonemes or word in NO_CLOSURE)
                else {"lyric": word})
    tail_note = {"midi": (tail_midi if tail_midi is not None else midi - 3), "word": tail,
                 "beats": round(tags * 0.52, 3), "fall": -1.0, "fall_beats": 0.3}
    tail_note.update({"phonemes": list(NO_CLOSURE[tail])} if tail in NO_CLOSURE else {"lyric": tail})
    return [lead,
            {"lyric": "like", "midi": midi + like_lift, "beats": round(tags * 0.48, 3), "word": "like"},
            tail_note,
            rest(1.0)]


HOOKS = {
    # bar 1 lands on A, bar 2 falls to F# and holds - the phrase ends where the sub does
    "one-note": chat() + [{"lyric": "bubble", "midi": A3, "beats": 1.0, "scoop": -2.0}]
                + chat() + [{"lyric": "bubble", "midi": FS3, "beats": 1.5, "scoop": -2.2,
                             "fall": -1.4, "fall_beats": 0.3,
                             "vibrato": {"rate": 5.6, "depth": 0.35, "delay": 0.5, "fade": 0.25}}],
    # b-ah / b-ah-l: the held syllable is the open one
    "split": chat() + [{"phonemes": ["b", "ah"], "midi": A3, "beats": 0.5, "scoop": -2.0},
                       {"phonemes": ["b", "ah", "l"], "midi": A3, "beats": 0.5}]
             + chat() + [{"phonemes": ["b", "ah"], "midi": FS3, "beats": 0.5, "scoop": -2.2},
                         {"phonemes": ["b", "ah", "l"], "midi": FS3, "beats": 1.0,
                          "fall": -1.4, "fall_beats": 0.3,
                          "vibrato": {"rate": 5.6, "depth": 0.35, "delay": 0.5, "fade": 0.25}}],
    # one phrase a bar: the word, "like this" or "like that", then two beats of air
    "phrases": (phrase("hop", CS4, "this", CS4)
                + phrase("bump", CS4, "that", A3)
                + phrase("lick", E4, "this", E4, scoop=-1.8)
                + phrase("bubble", A3, "that", FS3)),
}


def session_bpm() -> float:
    from thelmic.live_channel import LiveChannel
    ch = LiveChannel(lower_priority=False)
    ch.start()
    try:
        return float(ch.get_session_info().result(timeout=5)["tempo"])
    finally:
        ch.stop()


def main(argv=None):
    from thelmic.sources import vocal
    names = argv or sys.argv[1:] or list(HOOKS)
    bpm = session_bpm()
    KEPT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%H%M%S")
    print(f"bpm {bpm:g} from the session, speaker {SPEAKER}, provider cpu")
    for name in names:
        spec = vocal.VocalSpec(notes=HOOKS[name], bpm=bpm, speaker=SPEAKER)
        t0 = time.monotonic()
        sound = vocal.render(spec)
        kept = KEPT / f"hook-{name}-{stamp}.wav"
        shutil.copy2(vocal.fetch(sound), kept)
        print(f"  {name:<9} {sound.duration:.2f}s in {time.monotonic() - t0:.1f}s -> {kept.relative_to(REPO)}")
        if sound.extra["inferred_pronunciations"]:
            print("    pronounced from CMUdict, not the bank (check these):")
            for word, phones in sound.extra["inferred_pronunciations"].items():
                print(f"      {word:<10} {phones}")


if __name__ == "__main__":
    main()
