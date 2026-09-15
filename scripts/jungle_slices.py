"""Slice map for the jungle track's three breaks: where every slice starts, and what is in it.

Slice N of a break plays on MIDI note 36 + N. Frames are sample offsets at 44.1 kHz.

How the frames were found: onset detection, then each point moved to the TRUE attack (first
1 ms where 2.5-16 kHz, or broadband for hits with no top, rises >= 10 dB over its level 45..25 ms
earlier), then to the quietest stereo sample within 3 ms before it. A late cut leaves the attack
in the previous slice; a cut at a loud sample clicks at both this slice's start and the previous
slice's end.

How the labels were found: a rule-based pass (per-band rise at the attack), checked slice by slice
by three independent verifiers using partial tracking, waveform matching and spectrograms, which
also found the hits nobody had sliced (marked "added"). Label vocabulary:
  kick, snare (backbeat level), snare_soft (a pickup: clearly under the backbeat), ghost,
  bongo, conga, hat. "+" means two drums start together.

Things worth knowing when chopping:
  - Amen: a chopped/edited Amen, not the canonical one. Every cymbal is a short hat-like ride
    ping; no kick slice carries a cymbal. Snares 9/15/17 are within 2.4 dB of the loudest.
  - Cold Sweat: the "NoRide" edit. A closed hat sits under every kick and snare, loud on the beat
    and soft off it. Bars 3-4 of the file repeat bars 1-2.
  - Apache: resampled +6.2 st from the ~121.6 BPM original. Bar 2 is an exact copy of bar 1.
    Hand drums: bongo (718 + 1077 Hz pair) on the "a" of 2, conga (~187 Hz here, pitched up) on
    the "e" of 3 and the "a" of 4.

Low confidence, so don't lean on these as real ghost strokes: Cold Sweat 1, 3, 8, 11, 13, 18
("ghost+hat": the ghost sits 22-25 dB under the backbeat and a template decomposition hears only
the hat, or the previous kick's tail on 1 and 11) and Apache 1, 10, 15, 24 (~23 dB under, partly
the previous hit's tail). Treat them as hat slices with a whisper under them.
"""
from __future__ import annotations

SLICE_ROOT = 36

AMEN_FRAMES = [0, 7856, 16436, 24547, 28855, 32960, 37043, 41053, 49392, 56744, 65005, 69074,
               73738, 77449, 81782, 85700, 91112, 93628, 98659, 102542, 106200, 115039, 124823,
               126844, 129704, 132263]                                     # file is 160 BPM
AMEN_LABELS = [
    "kick", "kick", "snare", "hat", "snare", "hat", "snare_soft", "kick",           # 0-7
    "hat", "snare", "hat", "snare_soft", "kick", "ghost", "snare_soft", "snare",    # 8-15
    "hat", "snare", "hat", "snare_soft", "kick", "snare", "hat",                    # 16-22
    "snare_soft", "snare_soft",                                                     # 23-24 added
    "kick",                                                                         # 25 bar 3
]

CS174 = [0, 7504, 15007, 22627, 26478, 30238, 37860, 45476, 53110, 57225, 60652, 68356, 75874,
         83479, 87351, 91035, 98680, 106284, 113892, 118187, 121501]       # file is 174 BPM
CS174_LABELS = [
    "kick+hat", "ghost+hat", "snare+hat", "ghost+hat", "snare_soft", "kick+hat", "kick+hat",  # 0-6
    "snare+hat", "ghost+hat", "ghost",                                                          # 7-9 (9 added)
    "kick+hat", "ghost+hat", "snare+hat", "ghost+hat", "snare_soft", "kick+hat", "kick+hat",   # 10-16
    "snare+hat", "ghost+hat", "ghost",                                                          # 17-19 (19 added)
    "kick+hat",                                                                                 # 20 bar 3
]

AP174 = [0, 4910, 7963, 12896, 15060, 22882, 27239, 30613, 33886, 37529, 42851, 45419, 52748,
         56727, 60685, 65738, 68791, 73723, 75760, 83710, 88328, 91441, 94630, 98357, 103679,
         106247, 113576, 117554]                                           # file is 174 BPM
AP174_LABELS = [
    "kick+hat", "ghost", "hat", "ghost", "snare", "hat", "bongo", "hat", "conga",   # 0-8 (3 added)
    "kick+hat", "ghost", "snare", "hat", "conga",                                   # 9-13
    "kick+hat", "ghost", "hat", "ghost", "snare", "hat", "bongo", "hat", "conga",   # 14-22 (17 added)
    "kick+hat", "ghost", "snare", "hat", "conga",                                   # 23-27
]

BREAKS = {
    "AMEN-DMENT": (AMEN_FRAMES, AMEN_LABELS),
    "SWEAT-SHOP": (CS174, CS174_LABELS),
    "TOPSOIL": (AP174, AP174_LABELS),
}

for _name, (_frames, _labels) in BREAKS.items():
    assert len(_frames) == len(_labels), f"{_name}: {len(_frames)} frames vs {len(_labels)} labels"
    assert _frames[0] == 0 and all(b > a for a, b in zip(_frames, _frames[1:])), _name


def notes_with(track: str, drum: str, *, alone: bool = False) -> list[int]:
    """MIDI notes of the slices on `track` containing `drum` (alone=True: nothing else starts with it)."""
    _, labels = BREAKS[track]
    out = []
    for n, lab in enumerate(labels):
        parts = lab.split("+")
        if drum in parts and (not alone or len(parts) == 1):
            out.append(SLICE_ROOT + n)
    return out
