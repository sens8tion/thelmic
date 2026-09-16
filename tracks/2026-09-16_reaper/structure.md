# Macro shape of the Tim Reaper jungle DJ set (SECTION, Aug 2026)

Structural analysis only. Nothing was sampled, extracted or copied from the reference — every
number below comes from cached frame features (band energies, spectral flux, centroid, stereo
width, crest) and from a beat grid measured on the onset envelope.

Source: `Tim_Reaper_Jungle_DJ_Set_SECTION_August_2026.wav`, 1259.727 s, 48 kHz stereo.
All code: `scripts/reaper_structure.py`. Working data: `frames.npz` at 93.723 fps.

---

## 0. The grid (measured, not assumed)

The cached single global tempo is 165.831 BPM. It is close but not good enough to count 871 bars
with: a 0.1 BPM error accumulates to 0.76 beats over 21 minutes. I re-measured three ways.

| method | beat period | BPM |
|:--|---:|---:|
| ACF peak at lag = 8 beats | 361.526 ms | 165.963 |
| ACF peak at lag = 128 beats | 361.561 ms | 165.947 |
| ACF peak at lag = 1024 beats (370 s span, ACF still 0.26) | 361.558 ms | 165.948 |
| whole-file comb fit, period + phase | 361.561 ms | 165.947 |

**Adopted grid: beat = 361.561 ms, bar = 1.44624 s, 165.947 BPM, first downbeat at 0.042 s.**
1259.727 s / 1.44624 = **871.0 bars** — the file is cut almost exactly on a bar line.

Stability check: the best beat phase in rolling 12 s windows (half-beat hops folded out) sits at
+36…+52 ms for the first 15 minutes — drift under ±10 ms against a 90.4 ms sixteenth. At
**15:30 there is a single real phase step of ~+30 ms** and the grid then creeps to +108 ms by
20:36, i.e. the record after 15:30 runs about 0.02 BPM slow against the earlier grid. That is the
only place one global grid fails, and it fails by a third of a sixteenth. Everything else in this
document is bar-exact.

Downbeat-of-four is only weakly determined (the low-band vote wins by a ratio of 1.03–1.87, and
beats 0 and 2 split 10/6 across twenty 60 s chunks) — normal for jungle, where the kick is on 1
*and* 3. Bar *numbering* is therefore arbitrary up to a half bar; bar *durations* are not.

**Cross-check against `reaper_cache/grid.npz`** (built independently by the grid agent, which
allows the phase to be re-anchored rather than holding one rigid grid):

| | this analysis | grid.npz |
|:--|---:|---:|
| first downbeat | 0.0421 s | 0.04083 s (agree to **1.3 ms**) |
| beat | 361.561 ms | 361.46 ms |
| BPM | 165.947 | 165.994 (two segments: 165.9939 / 165.9743, split at 913.8 s = 15:13.8) |
| bar | 1.44624 s | 1.44584 s median, sd 85.9 ms (it stretches) |
| bars | 871 | 869 downbeats + 8 phase resets |

The 0.047 BPM disagreement is 0.4 ms per bar — 0.35 s accumulated over the whole file, a quarter
of a bar. It does not move any boundary in this document. More useful: grid.npz's two tempo
segments split at **15:13.8**, within 20 s of the single phase step I measured at 15:30, and
**five of its eight bar-phase resets land within 2.3 s of a section boundary found here**
(3:06.9 ↔ my 3:08.05 track cut; 9:17.8 ↔ 9:18.29; 13:09.8 ↔ 13:09.69; 15:06.2 ↔ 15:05.39;
17:07.4 ↔ 17:09.77). Two methods that share no code agree on where the music turns over.

## 1. Method

- **Features, per bar** (871 rows): log energy in sub 20–60, bass 60–120, lowmid 120–400,
  mid 400–2k, high 2–8k, air 8–16k, each with the overall level divided out (so a fader move is
  not read as a new section), plus log centroid, stereo width and crest. Z-scored, bands weighted
  1.0, the three support features 0.6/0.6/0.4.
- **SSM**: cosine similarity of that matrix, in two versions — smoothed over 4 bars (texture) and
  unsmoothed (literal repeat).
- **Novelty**: Foote checkerboard with a Gaussian taper at half-widths of 8, 16 and 32 bars
  (11.6 / 23.1 / 46.3 s). 8 bars is the shortest phrase a jungle record commits to; 32 bars is
  about the length of a whole section, so it responds to record changes and not to drum edits.
- **Boundaries**: I did **not** use novelty peak-picking for the final cut. Peak-picking needs a
  threshold and gives ±2 bar boundaries. Instead a dynamic-programming partition maximising
  within-block similarity mass minus λ per boundary (integral image, O(n²)); λ controls the block
  count directly. λ = 4 → 38 blocks (section level), λ = 20 → 9 blocks (track level). Each cut is
  then moved to the nearby bar with the sharpest ±8-bar contrast on the **unsmoothed** SSM,
  because the 4-bar smoothing used for the DP blurs a cut by ±2 bars.
- **Onsets**: local maxima of spectral flux above a 0.46 s moving average × 1.3, counted per bar.

---

## 2. TIMELINE

38 sections, 9 track-level blocks. `low%` = share of the spectrum below 120 Hz — the single most
diagnostic number in this set. `lit.rep` = literal per-bar self-similarity at lags of 4 / 8 / 16
bars. `recalls` = share of bars whose best 8-bar match, at least 16 bars earlier, exceeds 0.85.

| # | start | end | dur s | bars | bar# | trk | label | rms dB | low% | on/bar | crest | lit.rep 4/8/16 | recalls | evidence |
|---:|---:|---:|---:|---:|---:|:--|:--|---:|---:|---:|---:|:--|---:|:--|
| 0 | 0:00.04 | 0:49.21 | 49.2 | 34 | 0 | T0 | intro / mix-in | -15.4 | 2.5 | 13.1 | 3.16 | .86/.83/.77 | 18% | bass gone (2.5% vs 12.5% set median), highest crest in the set, full drum density — a high-passed breaks-only mix-in |
| 1 | 0:49.21 | 1:12.35 | 23.1 | 16 | 34 | T0 | drop | **-7.4** | 17.0 | 15.8 | 1.97 | .45/-.03/-.51 | 0% | loudest section in the set; low% ×6.8 across the bar-34 line; crest collapses 3.16→1.97; onsets +21% |
| 2 | 1:12.35 | 1:32.60 | 20.2 | 14 | 50 | T0 | groove | -11.0 | 8.8 | 12.6 | 2.64 | .63/.53/.06 | 0% | −3.6 dB off the drop, bass halved |
| 3 | 1:32.60 | 2:20.33 | 47.7 | 33 | 64 | T0 | groove | -11.1 | 7.5 | 14.8 | 2.73 | .49/.34/.45 | 33% | busiest drum edits of T0 |
| 4 | 2:20.33 | 3:08.05 | 47.7 | 33 | 97 | T0 | groove (draining) | -13.6 | 8.9 | 9.7 | 2.71 | .42/.29/.18 | 0% | −2.5 dB and onsets down a third (14.8→9.7): the deck being emptied before the cut |
| 5 | 3:08.05 | 4:14.58 | 66.5 | 46 | 130 | T1 | drop | -10.2 | **23.0** | 10.4 | 2.13 | .81/.75/.56 | 48% | hard cut in; the most internally cohesive block in the set (within-similarity 0.84) |
| 6 | 4:14.58 | 4:29.04 | 14.5 | 10 | 176 | T2 | transition | -14.0 | 11.7 | 9.2 | 2.72 | .35/.14/.19 | 0% | grid legibility 5.84→4.25 through here: two records running |
| 7 | 4:29.04 | 4:40.61 | 11.6 | 8 | 186 | T2 | build | -14.4 | 5.0 | 10.1 | 2.89 | .51/.17/-.16 | 0% | +0.53 dB/bar, bass at 40% of set norm |
| 8 | 4:40.61 | 5:26.89 | 46.3 | 32 | 194 | T2 | drop/groove | **-9.5** | 15.5 | 11.2 | 2.39 | .33/.59/.43 | 38% | +4.9 dB over the build; 32 bars exactly |
| 9 | 5:26.89 | 5:54.37 | 27.5 | 19 | 226 | T2 | groove | -12.9 | 9.2 | 10.2 | 2.81 | .49/.43/.15 | 26% | −3.4 dB step down |
| 10 | 5:54.37 | 6:33.42 | 39.0 | 27 | 245 | T2 | groove | -11.6 | 8.2 | 11.3 | 2.79 | .70/.70/.50 | 0% | narrowest image of the set (width 0.030) |
| 11 | 6:33.42 | 6:46.44 | 13.0 | 9 | 272 | T2 | groove | -11.7 | 12.4 | 11.4 | 2.62 | .65/.37/.25 | 0% | short bass return |
| 12 | 6:46.44 | 7:22.59 | 36.2 | 25 | 281 | T2 | groove → bass fade | -11.3 | 7.0 | 10.8 | 2.72 | .66/.52/.45 | 20% | last 8 bars: low% ramps 5.2→1.7, the EQ handover |
| 13 | 7:22.59 | 8:01.64 | 39.0 | 27 | 306 | T3 | drop (cut in) | **-8.4** | 14.6 | 10.6 | 2.24 | .52/.46/.40 | 0% | +3.7 dB in one bar |
| 14 | 8:01.64 | 9:06.72 | 65.1 | 45 | 333 | T3 | groove | -8.4 | 15.3 | 9.7 | 2.18 | .75/.72/.73 | 40% | joint-loudest sustained stretch (45 bars at −8.4 dB); lit.rep at 16 bars = 0.73 — near-literal 16-bar loop |
| 15 | 9:06.72 | 9:18.29 | 11.6 | 8 | 378 | T4 | breakdown / build | -13.3 | **1.9** | 11.6 | 3.01 | .23/-.54/-.17 | 50% | 8 bars belonging to neither record; +0.29 dB/bar |
| 16 | 9:18.29 | 10:04.57 | 46.3 | 32 | 386 | T4 | groove | -11.1 | 11.1 | 11.0 | 2.56 | .54/.50/.51 | 38% | 32 bars exactly |
| 17 | 10:04.57 | 10:26.27 | 21.7 | 15 | 418 | T5 | drop | -11.7 | **25.3** | 11.8 | 2.04 | .66/.42/-.01 | 47% | preceded by 2 bars of doubled drums (22 and 19 onsets vs 11 norm) with the bass at 0.3% |
| 18 | 10:26.27 | 10:46.51 | 20.2 | 14 | 433 | T5 | build | -12.8 | 18.2 | 11.7 | 2.41 | .56/.58/.73 | 0% | +0.16 dB/bar |
| 19 | 10:46.51 | 11:40.02 | 53.5 | 37 | 447 | T5 | groove | -11.6 | 14.1 | 11.2 | 2.51 | .45/.60/.52 | 5% | longest single groove |
| 20 | 11:40.02 | 12:00.27 | 20.2 | 14 | 484 | T5 | groove (falling) | -12.6 | 12.5 | 10.4 | 2.56 | .50/.71/.53 | 0% | −0.48 dB/bar: the steepest sustained fall in the set |
| 21 | 12:00.27 | 12:46.55 | 46.3 | 32 | 498 | T5 | groove | -11.8 | 12.5 | 11.4 | 2.53 | .53/.53/.54 | 41% | 32 bars exactly |
| 22 | 12:46.55 | 13:09.69 | 23.1 | 16 | 530 | T5 | groove | -13.5 | 16.5 | 11.6 | 2.29 | .77/.76/.80 | 12% | strongest literal 16-bar loop in the set (0.80) |
| 23 | 13:09.69 | 13:53.08 | 43.4 | 30 | 546 | T5 | groove | -11.3 | 20.7 | 11.3 | 2.18 | **.89/.85/.77** | 57% | the most literally repetitive section anywhere here |
| 24 | 13:53.08 | 14:19.11 | 26.0 | 18 | 576 | T5 | groove | -13.2 | 11.6 | 12.7 | 2.50 | .47/.43/.67 | 0% | variation pass over the same loop |
| 25 | 14:19.11 | 14:42.25 | 23.1 | 16 | 594 | T5 | groove | -11.6 | 16.8 | 13.1 | 2.30 | .76/.69/.52 | 6% | onsets climbing into the seam |
| 26 | 14:42.25 | 15:05.39 | 23.1 | 16 | 610 | T6 | transition | -11.5 | 8.2 | 12.9 | 2.71 | .62/.49/.21 | 0% | see §3: the long double-play |
| 27 | 15:05.39 | 15:19.85 | 14.5 | 10 | 626 | T6 | groove | -12.9 | 17.1 | 14.2 | 2.35 | .27/-.17/-.15 | **70%** | densest drums after the opening drop (14.2 onsets/bar) |
| 28 | 15:19.85 | 15:37.21 | 17.4 | 12 | 636 | T6 | build | -16.3 | **3.7** | 10.6 | 2.93 | .55/.12/.19 | 0% | −4.8 dB below track norm, +0.48 dB/bar, second-widest image (0.265) |
| 29 | 15:37.21 | 16:23.49 | 46.3 | 32 | 648 | T6 | drop | -10.7 | 13.4 | 12.1 | 2.53 | .66/.61/.44 | 34% | +5.6 dB over the build; 32 bars exactly |
| 30 | 16:23.49 | 17:09.77 | 46.3 | 32 | 680 | T6 | groove | -11.3 | 9.6 | 11.8 | 2.68 | .79/.74/.58 | 22% | 32 bars exactly |
| 31 | 17:09.77 | 17:43.03 | 33.3 | 23 | 712 | T6 | groove | -10.1 | 15.8 | 10.4 | 2.38 | .56/.36/.55 | 0% | +1.4 dB, the track's last statement |
| 32 | 17:43.03 | 17:54.60 | 11.6 | 8 | 735 | T6 | breakdown / mix-out | **-18.6** | **2.2** | 11.1 | 3.04 | .39/-.22/.10 | 0% | quietest section in the set, −7.1 dB below its own track's median; bass at 0.9–1.8% |
| 33 | 17:54.60 | 18:39.43 | 44.8 | 31 | 743 | T7 | drop | -10.4 | **26.2** | 10.4 | 2.06 | .72/.48/.39 | **84%** | slam out of silence: +7.0 dB and ×22 the bass across the single bar line 742→743 |
| 34 | 18:39.43 | 19:27.16 | 47.7 | 33 | 774 | T7 | groove | -12.7 | 14.0 | 11.4 | 2.43 | .66/.70/.60 | 30% | −2.3 dB |
| 35 | 19:27.16 | 19:50.30 | 23.1 | 16 | 807 | T8 | breakdown (new record's intro) | -17.0 | **3.1** | 12.2 | 3.04 | .63/.30/-.40 | 0% | hard switch straight into 16 bass-less bars at −17 dB |
| 36 | 19:50.30 | 20:03.32 | 13.0 | 9 | 823 | T8 | drop | -13.5 | 20.5 | 9.6 | 2.29 | .38/-.20/-.36 | 0% | widest image of the set (0.320); low% ×6.6 across the bar-823 line |
| 37 | 20:03.32 | 20:59.73 | 56.4 | 39 | 832 | T8 | outro / mix-out | -13.4 | 8.1 | 11.2 | 2.82 | .79/.62/.40 | 18% | file ends mid-record |

**Time by label:** groove 589 bars (67.6%), drop 117 (13.4%), build 42 (4.8%), intro 34 (3.9%),
outro 39 (4.5%), transition 26 (3.0%), breakdown 24 (2.8%).

---

## 3. THE DJ-MIX SEAMS

**Nine records in 21 minutes.** The DP partition at λ = 20 gives 9 blocks; every internal cut is
independently corroborated by at least two of {long-kernel novelty, low-band handover, doubled
percussion, beat-comb legibility dip}. Block lengths, in bars:

`130, 46, 130, 72, 40, 192, 133, 64, 64` → `188, 67, 188, 104, 58, 278, 192, 93, 93` seconds.
Median 72 bars (104 s), mean 97 bars (140 s). **Five of nine are exact multiples of 8 bars; the
other four are within 3 bars**, which is boundary uncertainty, not musical fact.

Track-block cross-similarity shows a family, not a repeat: T1↔T3 +0.51, T1↔T5 +0.39,
T1↔T7 +0.34, T3↔T7 +0.28 — the bassy records resemble each other. No record returns literally.

| cut | time | device | handover | bass-out before | min low% | doubled drums | grid legibility (before / min / after) | level dip before |
|---:|---:|:--|---:|---:|---:|---:|:--|---:|
| bar 130 | 3:08.05 | **hard cut** | 1 bar (1.4 s) | 3 bars | 0.8% | — | 5.40 / 6.13 / 5.78 (no dip) | −4.0 dB |
| bar 176 | 4:14.58 | **long blend, two loops running** | 8–18 bars (11.6–26 s) | 0 | 15.3% | — | 6.94 / **4.24** / 4.99 (−39%) | −5.1 dB |
| bar 306 | 7:22.59 | **EQ bass handover then cut** | 2 bars | 5 bars (low% 5.2→1.7) | 1.7% | — | 5.10 / 4.94 / 5.45 | −0.6 dB |
| bar 378 | 9:06.72 | **8-bar airlock** (drums only, belongs to neither record: cos to A −0.35, to B −0.40) | 16 bars (23 s) | 0 | 8.5% | — | 5.45 / 5.64 / 5.64 | −0.3 dB |
| bar 418 | 10:04.57 | **doubled drum fill then drop** | 5 bars (7.2 s) | 4 bars | 0.3% | **2 bars at 22 and 19 onsets vs an 11 norm (1.9×)** | 5.87 / 5.35 / 6.58 | −5.4 dB |
| bar 610 | 14:42.25 | **long double-play** — bars 592–630 alternate bar-by-bar between the two records | 2 bars nominal, ~32 bars real (46 s) | 1 bar | 1.8% | 6 bars flagged both-audible | 6.76 / **4.16** / 4.92 (−38%) | −8.3 dB |
| bar 743 | 17:54.60 | **drop out, then slam** | 2 bars | 7 bars at −19.3 dB | 0.9% | — | 4.33 / 3.72 / 6.32 | **−9.8 dB** |
| bar 807 | 19:27.16 | **cut straight into the new record's breakdown** (16 bass-less bars before its drop) | 5 bars (7.2 s) | 1 bar | 5.6% | — | 5.59 / 5.10 / 6.50 | −2.3 dB |

**How long is a blend?** Two populations, and nothing in between:

- **Cuts: 5 of 8** (bars 130, 306, 418, 743, 807) — the texture flips in **1–5 bars (1.4–7.2 s)**,
  with the beat-comb legibility *unaffected or improving* (it rises at four of the five). Prepared
  by 1–7 bars of bass removal (median 4) and a 0.6–9.8 dB level dip on the outgoing record.
- **Blends: 3 of 8** (bars 176, 378, 610) — **8–32 bars (12–46 s)** with both records audible.
  The tell is not loudness, it is the beat-comb legibility falling 38–39% at bars 176 and 610,
  plus the low-band fraction lurching bar to bar (0.4% → 21% → 1.0% across three bars at 610).

**Bass is the handover channel.** 17.0% of all bars (148 of 871) sit below 5% low-band energy.
Nine runs of ≥4 such bars; **five of the nine sit on a track cut**, and they are 34, 5, 8, 7 and
15 bars long. Outside the seams, the set never goes more than 5 bars without sub.

---

## 4. PHRASE ARITHMETIC

Two independent measurements, neither of which depends on boundary detection.

**(a) Lag profile of the unsmoothed per-bar SSM** — mean similarity of bar *i* to bar *i−L*,
averaged over the whole set. Excess over the average of the two neighbouring lags:

| lag (bars) | 2 | 4 | 8 | 12 | 16 | 24 | 32 | 48 | 64 | 96 | 112 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| similarity | .615 | .616 | .518 | .401 | .415 | .290 | .291 | .204 | .158 | .103 | .141 |
| **excess** | **+.061** | **+.160** | **+.181** | +.117 | **+.159** | +.120 | **+.112** | +.084 | +.060 | +.053 | +.050 |

Every even lag is a local maximum; the powers of two stand well above the multiples of four.
**The 8-bar phrase is the single strongest structural period in the set.**

**(b) Per-bar best-repeat lag** (4–64 bars, 8-bar path). Histogram of the winning lag:
4 bars 39.0%, 8 bars 8.7%, 16 bars 9.3%, 32 bars 3.3%, 64 bars 2.5%, 48 bars 2.4%, 24 bars 2.2%,
12 bars 1.6%. Every other lag is under 2%.

**Section lengths against the phrase grid** (38 sections, refined to bar accuracy):

| unit | exact | within 1 bar | within 2 bars |
|:--|---:|---:|---:|
| multiple of 4 | 37% | 76% | **100%** |
| multiple of 8 | 34% | 61% | 84% |
| multiple of 16 | 26% | 39% | 58% |

Lengths in bars: 34, 16, 14, 33, 33, 46, 10, 8, 32, 19, 27, 9, 25, 27, 45, 8, 32, 15, 14, 37, 14,
32, 16, 30, 18, 16, 16, 10, 12, 32, 32, 23, 8, 31, 33, 16, 9, 39.
Median 21 bars (30.4 s), mean 22.9, min 8, max 46. **32 bars and 16 bars are the two modes**;
32-bar sections appear seven times exactly, 16-bar four times, 8-bar three times.

**Is it strictly 8-bar?** No — **strictly 4-bar, loosely 8-bar.** Every section length is within
2 bars of a multiple of 4; only 84% are within 2 bars of a multiple of 8. Two distinct ways it
breaks the 8:

- **Odd counts of 4-bar units.** Six sections (16%) are ≥3 bars off a multiple of 8, and every one
  of them is an odd number of four-bar units: 19 bars ≈ 5×4 (5:26), 27 ≈ 7×4 (5:54 and 7:22),
  45 ≈ 11×4 (8:01), 37 ≈ 9×4 (10:46), 12 = 3×4 (15:19). Nothing lands between the 4-bar lines —
  the set simply does not insist that the 4-bar unit count be even.
- **Short sections at the seams.** Eight sections are ≤12 bars. Three sit *exactly* on a track cut
  (10 bars at 4:14, 8 at 9:06, 8 at 17:43) and three more are within 16 bars of one (8 at 4:29,
  10 at 15:05, 9 at 19:50). The 8–12 bar section is a mix device, not a musical one: **the
  records run in 16s and 32s; the mix cuts 8s and 12s out of them.**
- Novelty peaks (±8-bar kernel, 41 of them) have a **median spacing of exactly 16 bars** with a
  mode of 8 — the surface changes every 8–16 bars even where the section runs 32.

---

## 5. REPETITION

Literal per-bar self-similarity, median across the 38 sections: lag 4 bars **0.56**, lag 8
**0.50**, lag 16 **0.44**, lag 32 **0.31**. The material does not decorrelate — a jungle bar is
recognisably the same bar 32 bars later.

**Repeat vs new, section by section** (`recalls` = share of bars matching material ≥16 bars
earlier at >0.85; `new` = share below 0.70):

- **Median section is 9% recall, 20% new** — i.e. 70%+ of a typical section is neither a literal
  callback nor new material: it is the *current* loop, varied.
- **Most literal sections:** #33 (17:54, 84% recall), #27 (15:05, 70%), #23 (13:09, 57% recall
  with the highest internal repetition anywhere: 0.89/0.85/0.77 at 4/8/16 bars), #15 (9:06, 50%),
  #5 (3:08, 48%), #17 (10:04, 47%).
- **Most new:** the sections around a seam. #1 (0:49, 100% new), #2 (1:12, 100%), #6 (4:14,
  100%), #4 (2:20, 97%), #20 (11:40, 79%), #11 (6:33, 78%), #26 (14:42, 75%), #28 (15:19, 75%),
  #7 (4:29, 75%).
- **The pattern:** newness is spent at the seam and never again inside the record. Within a
  record, the second and third sections run 0–40% recall (variation), and the fourth or later
  section jumps to 40–84% (the record's main loop returning verbatim).
- **Breakdowns and builds are new material** — 0% recall at #7, #18, #28, #32 and #35. The one
  exception is the 8-bar airlock at 9:06 (50% recall), and that is drums shared by *both* records
  across the seam, not a callback.
- **Nothing comes back across records.** Best cross-record block similarity is +0.51 (T1↔T3), an
  "these are the same kind of record" number, not a "this is the same record" number.

---

## 6. LOUDNESS AND DENSITY ARC

Per minute, RMS / low-band share / onsets per bar:

```
00  -13.9   5.0%  13.7      07   -9.5  11.6%  10.8      14  -11.8  13.1%  12.9
01  -10.1  10.1%  14.1      08   -8.4  15.0%   9.7      15  -13.1  10.6%  12.5
02  -12.9   8.7%  11.4      09  -11.2  10.5%  10.5      16  -10.9  11.6%  11.9
03  -10.5  22.0%  10.5      10  -12.3  18.7%  12.1      17  -12.2  12.8%  10.3
04  -11.4  14.1%   9.9      11  -11.5  13.7%  10.9      18  -11.4  22.0%  11.0
05  -11.5  11.5%  11.1      12  -12.0  13.7%  11.6      19  -14.3  10.8%  11.4
06  -11.6   8.8%  11.0      13  -12.3  18.8%  11.3      20  -13.3   8.5%  11.1
```

Total range across 21 minutes: **11.2 dB** at the section level (−7.4 at 0:49 to −18.6 at 17:43),
but only **5.9 dB** at the per-minute level (−8.4 at minute 8 to −14.3 at minute 19). The set does
not get louder; it swaps which 10 dB it is using. Bass share swings 2.2%–26.2% at section level
and 5.0%–22.0% per minute — **the low band is the dynamic, not the fader.** Onset density is
almost flat (9.2–15.8 per bar at section level, 9.7–14.1 per minute): the drums never thin out,
even in the breakdowns (11.1 onsets/bar at −18.6 dB in #32).

---

## What this means for building a jungle track

1. **Lock one tempo to sub-millisecond precision and never move it.** 165.947 BPM, bar 1.44624 s,
   across 871 bars. The only phase change in the whole 21 minutes is 30 ms, a third of a
   sixteenth. Do not use a "roughly 170" grid; measure the period over ≥128 bars.
2. **Build in 32s and 16s, land on 4s.** Section lengths: 100% within 2 bars of a multiple of 4,
   84% within 2 of a multiple of 8, and 32/16 bars are the two modes. Median section 21 bars
   (30 s). Do not write a section shorter than 8 bars or longer than 46.
3. **Give a section 30 seconds, and change something every 16 bars.** Median section 21 bars
   (30.4 s), mean 22.9. The 41 novelty peaks have a **median spacing of exactly 16 bars**, mode 8 —
   so the surface moves twice inside a 32-bar section.
4. **Keep 65–70% of the runtime on groove.** Groove 67.6%, drop 13.4%, build 4.8%, breakdown
   2.8%, transition 3.0%. Breakdowns and builds together are under 8% — jungle does not spend its
   time announcing things.
5. **Move the bass, not the fader.** Low-band share swings 2%→26% (a 12× range) while per-minute
   RMS moves only 5.9 dB. Set the low band to 12–13% of the spectrum in a groove, 20–26% in a
   drop, under 4% in a breakdown, and leave the level roughly alone.
6. **Keep the drums on through the breakdown.** Onsets per bar stay in a 9.2–15.8 band everywhere
   including the −18.6 dB breakdown (11.1/bar). Strip the sub, not the break. Crest is the tell:
   2.0–2.4 in a drop, 2.9–3.2 in a breakdown.
7. **Prepare a section change with 3–7 bars of bass removal, then change on the bar line.**
   Four of the eight seams do exactly this: the low band falls to 0.3–1.7% for 3–7 bars, the level
   drops up to 9.8 dB, and then the new material arrives inside one bar. Bar 743 is the template:
   7 bars at −19.3 dB, then **+7.0 dB and 22× the bass across a single bar line.**
8. **Two transition lengths, and a gap between them: 1–5 bars, or 8–32 bars.** Cuts take
   1.4–7.2 s (5 of 8 seams); blends take 12–46 s (3 of 8). Nothing in the set takes 8 seconds.
9. **Make a build 8–14 bars and ramp 0.16–0.53 dB per bar.** Four builds, lengths 8, 8, 12 and 14
   bars, slopes +0.53 / +0.29 / +0.48 / +0.16 dB/bar, each landing 1.2–5.6 dB (median 3.6) below
   whatever follows it.
10. **Spend all your new material in the first 16 bars of a record, then repeat almost verbatim.**
    Opening sections run 75–100% new; later sections in the same record run 40–84% literal recall,
    with per-bar self-similarity of 0.89 at 4 bars and 0.77 at 16 bars. The listener gets one
    surprise per record, not one per section.
11. **Signal a double-drop with drum density, not with a riser.** The only doubled-percussion
    event in the set is 2 bars at 22 and 19 onsets against an 11 norm (1.9×), with the bass cut to
    0.3%, immediately before the biggest bass entry of the section (low% 25.3%).
