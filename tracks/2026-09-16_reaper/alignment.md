# Do the layers change together?

The user's model of the reference: every layer holds its state inside a **sub-section** and only
changes at its boundaries. The bass analysis ([bass.md](bass.md) §10-12) found change points in the
**riff** and the **sub tone**; the rhythm analysis ([rhythm.md](rhythm.md) §9-10) found them in the
**kick pattern** and the **16th carrier**. This lines the four up on one bar timeline.
Code: `scripts/reaper_alignment.py`. Structural analysis only.

Rhythm bars were mapped onto the bass table's bars by nearest start time (median offset 17 ms; 97 of
852 bars sit more than half a bar out, around the grid's phase resets, so a ±1 bar tolerance is used
throughout). Chance comes from 2000 circular shifts of the other layer's change sequence.

## Each layer keeps its own clock

| layer | changes | sub-section length, median | IQR |
|---|---|---|---|
| bass riff | 64 | **8 bars** | 5-16 |
| sub tone | 36 | **17 bars** | 13-38 |
| kick pattern | 22 | **28 bars** | 19-46 |
| 16th carrier | 22 | **32 bars** | 15-60 |

A hierarchy: the riff turns over about every 8 bars, the sub's tone about every 16, and the drums
about every 32.

## The slow layers change where the riff changes

Share of the row layer's changes that land within ±1 bar of a change in the column layer:

| | riff | sub tone | kick | carrier |
|---|---|---|---|---|
| **riff** | - | 23% vs 12%, p 0.021 | 27% vs 8%, p < 0.001 | 16% vs 8%, p 0.054 |
| **sub tone** | **42% vs 21%**, p 0.009 | - | 17% vs 7%, p 0.042 | 3% vs 8%, p 0.91 |
| **kick** | **77% vs 21%**, p < 0.001 | 27% vs 12%, p 0.040 | - | **32% vs 8%**, p < 0.001 |
| **carrier** | **45% vs 20%**, p 0.029 | 5% vs 12%, p 0.91 | **32% vs 8%**, p < 0.001 | - |

Read down the riff column: **three quarters of kick changes, and nearly half of sub-tone and carrier
changes, happen on a bar where the riff also changes.** The reverse is weaker, because the riff
changes far more often than anything else — most riff changes happen alone.

Kick and carrier move together (32% against 8%). The **sub tone and the carrier are unrelated**
(3-5%, below chance): the bass's colour and the break's filter are not switched together.

## Big turnovers

74 boundary events (changes within 2 bars merged): 45 involve one layer, 17 two, 11 three, and 1 all
four. **Three or more layers turning over together happens in 16% of events against 2% by chance
(p 0.002).**

| bar | time | layers | where |
|---|---|---|---|
| 34 | 0:49.2 | 3 | |
| 94 | 2:15.9 | 3 | |
| 113 | 2:43.8 | **4** | beside the 8th-note drum run the rhythm analysis flagged at 2:44 |
| 127 | 3:04.0 | 3 | |
| 170 | 4:07.3 | 3 | |
| 192 | 4:39.1 | 3 | |
| 223 | 5:23.9 | 3 | |
| 240 | 5:48.5 | 3 | |
| 415 | 10:00.1 | 3 | |
| 496 | 11:57.2 | 3 | |
| 544 | 13:06.6 | 3 | |
| 646 | 15:33.4 | 3 | |

Only 5 of these 12 sit within 2 bars of a record seam. **The big turnovers are mostly the records'
own section changes, not the DJ's mixes.**

## What it says about the model

- **Holding state per sub-section is right**, but there is no single sub-section length. Each layer
  has its own period: riff ~8 bars, tone ~17, drums ~28-32.
- **The layers are nested, not independent.** When a slow layer changes, the riff almost always
  changes with it; the riff also moves on its own in between.
- **A real section change is several layers at once** — 3 or 4 turning over on the same bar, about
  eight times more often than chance.
- **What does not follow the phrase grid:** the rhythm analysis found kick and carrier changes do not
  prefer 4/8/16/32-bar lines (p ≥ 0.11), while riff changes do (33% on 8-bar lines against 19%).
  The riff keeps the phrase grid; the drums change when the music does.

## Call and response - three readings tested

The user hears "a high call at the front, a longer sub response at the back". Three readings:

1. **Hooks call, sub answers** ([hooks.md](hooks.md), *Call and response*): **null.** No front/back
   split at 1, 2, 4 or 8 bars, no answering lag, no pitch relationship beyond chance. The opposite
   placement does show: sub notes start at the FRONT of the bar (57%) and high percussion accents fall
   at the BACK (58%).
2. **Across the bar line** - an accent on the back of bar N calls, and the sub on the front of bar N+1
   answers (hooks.md, *Call across the bar line*): **null.** After an accent the sub starts on the next
   downbeat 22.4% of the time, against 21.5% without one; no cross-correlation peak; same duration.
3. **Inside the bassline itself** - the riff's own first half calls, and its second half answers.
   Measured on `bass_bars.npz` (`seq16`), comparing each riff cycle's second half with its first,
   inside segments with that riff period (95% bootstrap intervals):

| riff cycle | cycles | pitch, back minus front | back half lower | note length, back minus front | back half longer |
|---|---|---|---|---|---|
| 1 bar | 43 | +1.19 st [+0.21, +2.25] | 35% | -0.006 beats [-0.047, +0.039] | 21% |
| **2 bars** | **89** | **-1.02 st [-1.94, -0.14]** | **66%** | +0.057 beats [-0.020, +0.131] | 49% |
| 4 bars | 66 | +0.05 st [-0.89, +0.98] | 45% | +0.077 beats [-0.008, +0.165] | 58% |
| 8 bars | 26 | +0.83 st [+0.35, +1.29] | 23% | +0.107 beats [-0.004, +0.241] | 46% |

   **Partial support.** In 2-bar riffs the second bar sits about a semitone lower in two cycles out of
   three - a higher call, a lower answer, inside the bassline. Notes in the back half run slightly
   longer at 2, 4 and 8 bars (+0.06 to +0.11 beats), but no single interval clears zero. At 1 and 8
   bars the back half is *higher*, so this is a 2-bar habit, not a rule at every scale.
