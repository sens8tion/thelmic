# The grid — Tim Reaper jungle DJ set (SECTION, Aug 2026)

Source: `C:\Users\eric\Downloads\Tim_Reaper_Jungle_DJ_Set_SECTION_August_2026.wav`, 1259.727 s, 48 kHz
stereo. **Structural analysis only** — nothing was sampled, extracted or copied out of it; everything
below is derived from the cached feature frames.

Built by `scripts/reaper_grid.py`. Output: `C:\Users\eric\Downloads\reaper_cache\grid.npz`.

## Headline

**The whole 21 minutes runs at one tempo: 165.99 BPM, beat period 361.459 ms.** There is no tempo
change anywhere in the file. There is exactly **one beat-phase discontinuity, at 15:13.9**, where the
grid steps forward by +114 ms (+0.31 of a beat) with the tempo unchanged to within 0.02 BPM. That is
the signature of a mix where the incoming record is tempo-locked but not phase-locked — consistent
with a set played to a single master tempo.

**The bar grid is usable across the entire file.** Median grid salience 4.61, and the beat positions
sit within one analysis frame (10.7 ms) of the audio everywhere: phase residual median 4.5 ms, p90
9.0 ms.

The old cached grid in `meta.json` is wrong and should not be used. At 165.83 BPM it is 255 ms out at
the start and **1338 ms — 3.7 beats — out by the end**. `bars.npz` (`bar_start_s`, `grid16`,
`offs16`) was built on that grid, so its bar boundaries and 16th-note microtiming drift away from the
music; re-derive them from `grid.npz` before trusting them.

## BPM timeline

| from | to | length | BPM (fit) | line residual | beats | salience | z | beat/8th | phase resid | bar margin |
|---|---|---|---|---|---|---|---|---|---|---|
| 0:00.04 | 15:13.81 | 913.8 s | **165.994** | 10.2 ms | 2528 | 4.60 | 3.47 | 1.14 | 4.5 ms | 0.90 |
| 15:13.92 | 20:59.52 | 345.6 s | **165.974** | 12.4 ms | 956 | 4.81 | 4.33 | 1.37 | 4.5 ms | 0.61 |

The 0.020 BPM difference between the two stretches is 0.012 % and is at the edge of what a 10 ms
line residual can resolve — treat it as **one tempo, 165.99 ± 0.02 BPM**, not two. The split exists
because of the phase step, not the tempo.

Independent corroboration that the tempo is flat, from sliding least-squares fits of the raw beat
times (before any snapping):

| fit window | min | p5 | median | p95 | max |
|---|---|---|---|---|---|
| 64 beats (23 s) | 164.61 | 165.90 | 165.99 | 166.05 | 166.53 |
| 128 beats (46 s) | 165.24 | 165.92 | 165.99 | 166.02 | 166.19 |
| 256 beats (93 s) | 165.68 | 165.81 | **165.99** | 166.01 | 166.05 |

A set beatmatched by ear between records at different BPM would show ±0.5 BPM steps here. It does
not. The only excursions are at 15:02 (165.30 on the 128-beat fit) — that is the transition.

## Transitions

**Beat-phase step — 15:13.9.** The only one. The beat times drift smoothly against a single global
line for the first 14.5 minutes, then over ~25 s (14:50 → 15:14) slip forward and settle:

```
14:50.68  -72 ms     15:02.24  -23 ms     15:13.89  +68 ms     15:25.55  +46 ms     15:37.07  +35 ms
```

Net step relative to the stretch-1 line: **+114 ms = +0.31 beat**. The slip takes about 8 bars, which
is the two records overlapping.

**Bar-phase resets — 8 candidates.** Points where the 4-state bar tracker had to move the downbeat.
These are mix markers; the beat grid is continuous through all of them.

| time | bar pos | salience | beat/8th | survives pen=16 |
|---|---|---|---|---|
| 2:41.25 | 1 → 1 | 8.07 | 1.50 | |
| 3:06.92 | 3 → 1 | 6.40 | 1.20 | |
| **6:57.53** | 2 → 1 | 2.65 | 1.30 | **yes** |
| **9:17.77** | 0 → 3 | 4.76 | 1.09 | **yes** |
| 13:09.83 | 0 → 0 | 5.44 | 1.17 | |
| 14:06.22 | 3 → 1 | 3.95 | 1.01 | |
| **15:06.22** | 2 → 1 | 2.36 | 1.06 | **yes** |
| 17:07.43 | 3 → 1 | 2.86 | 1.37 | |

Robustness sweep on the tracker's switch penalty (how many z-units of evidence a reset must buy):

| penalty | resets | agreement with the published bar phase |
|---|---|---|
| 4 | 9 | 96.8 % |
| 8 (published) | 8 | 100 % |
| 16 | 3 | 83.8 % |
| 32 | 1 | 72.7 % |
| ∞ (one global bar phase) | 0 | 54.3 % |

Read that bottom row carefully: forbidding resets entirely still only reproduces the published bar
phase on 54 % of beats, so the bar phase genuinely moves during the file — a single global downbeat
offset is wrong. **Three resets are solid** (6:57.5, 9:17.8, 15:06.2 — they survive a doubled
penalty). The other five are softer; treat a downbeat within ±8 bars of them as provisional.
15:06.2 is the strongest of all (the only one surviving penalty 32) and sits 8 s before the beat-phase
step, so **15:06–15:14 is the one unambiguous mix point in this file**.

## Downbeat confidence

The bar phase is carried by the kick band, and two independent features agree with it:

| feature | pos 0 | pos 1 | pos 2 | pos 3 | argmax | pos0 / pos2 |
|---|---|---|---|---|---|---|
| kick-band onset (20–120 Hz) | **3.383** | 2.133 | 1.898 | 2.408 | pos 0 | **1.78** |
| broadband onset | **3.311** | 3.114 | 2.779 | 3.120 | pos 0 | 1.19 |
| per-beat spectral change (band energies) | **0.648** | 0.462 | 0.496 | 0.527 | pos 0 | 1.31 |

The rival hypothesis for a downbeat is always "it is actually beat 3", i.e. pos 2. The kick beats it
by 78 %, and spectral change — a different measurement entirely (energy level, not attack) — beats it
by 31 % independently. **I am confident in the downbeat phase.** Per stretch the local z-margin of
pos 0 over its best rival is 0.90 (0:00–15:14) and 0.61 (15:14–end): the second half is weaker,
because it is denser and the kick is less exposed there.

869 downbeats / 869 bars over the file; the histogram of bar positions is [869, 873, 872, 870], i.e.
near-perfectly balanced, as it must be if the tracker is not thrashing.

## Beat phase — is it on the beat or on the off-beat 8th?

This is the question that actually matters in jungle, because every 16th is populated and onset
density alone barely distinguishes a beat from an 8th. Beat-synchronous onset profile, 32 bins per
beat, measured against the final beats:

```
bin  0 (  0 ms)  2.735  ##########################   <- the grid
bin  4 ( 45 ms)  0.412  ###
bin  8 ( 90 ms)  0.638  ######                       <- the 16th
bin 16 (181 ms)  2.298  #####################        <- the off-beat 8th
bin 24 (271 ms)  0.765  #######
bin 31 (350 ms)  2.168  ####################         <- the previous beat
```

- A 16th-note offset is rejected outright: 0.64 vs 2.74, a factor of 4.3.
- The beat beats the off-beat 8th by 1.19× broadband and **1.47× in the kick band**. That is a real
  but modest margin, and it is the honest limit of what this file supports.
- Half-tempo and double-tempo grids score below this one on both envelopes, so 165.99 is the beat
  level, not an octave error.

11.2 % of 8 s windows have a beat/8th ratio below 1.0 — scattered ambiguous windows, mostly in
breakdowns where the kick drops out. **No whole minute falls below 1.0**, so anything measured over a
bar or longer is safe.

## Per-minute reliability

`salience` = broadband onset on the beat ÷ the same measure at 12 offsets spread across the beat
(a guessed grid scores ~1.0). `z` = the same contrast in standard deviations of the offset
distribution. `beat/8th` = beat vs off-beat-8th, kick + broadband. `resid` = median |local phase
offset| of the audio against the grid, searched over ±¼ beat.

| min | BPM | salience | z | beat/8th | resid | resets | verdict |
|---|---|---|---|---|---|---|---|
| 0 | 165.99 | 4.35 | 2.39 | 1.26 | 4.5 ms | 0 | solid |
| 1 | 165.99 | 3.65 | 2.25 | 1.05 | 4.5 ms | 0 | solid |
| 2 | 165.99 | 6.40 | 4.58 | 1.32 | 0.0 ms | 1 | ok |
| 3 | 165.99 | 5.93 | 4.52 | 1.18 | 0.0 ms | 1 | ok |
| 4 | 165.99 | 4.66 | 3.95 | 1.16 | 0.0 ms | 0 | solid |
| 5 | 165.99 | 4.15 | 3.59 | 1.20 | 0.0 ms | 0 | solid |
| 6 | 165.99 | 3.24 | 3.00 | 1.11 | 9.0 ms | 1 | ok |
| 7 | 165.99 | 3.16 | 2.58 | 1.14 | 9.0 ms | 0 | solid |
| 8 | 165.99 | 4.58 | 5.00 | 1.15 | 4.5 ms | 0 | solid |
| 9 | 165.99 | 4.85 | 5.09 | 1.10 | 0.0 ms | 1 | ok |
| 10 | 165.99 | 5.04 | 3.68 | 1.18 | 4.5 ms | 0 | solid |
| 11 | 165.99 | 4.94 | 2.86 | 1.01 | 4.5 ms | 0 | ok |
| 12 | 165.99 | 5.66 | 3.31 | 1.17 | 4.5 ms | 0 | solid |
| 13 | 165.99 | 5.64 | 3.53 | 1.10 | 4.5 ms | 1 | ok |
| 14 | 165.99 | 4.15 | 3.27 | 1.25 | 4.5 ms | 1 | ok |
| 15 | 165.97 | 2.63 | 2.17 | 1.15 | 4.5 ms | 1 | ok |
| 16 | 165.97 | 3.18 | 2.62 | 1.41 | 4.5 ms | 0 | solid |
| 17 | 165.97 | 3.69 | 3.47 | 1.45 | 4.5 ms | 1 | ok |
| 18 | 165.97 | 5.51 | 5.00 | 1.43 | 0.0 ms | 0 | solid |
| 19 | 165.97 | 6.68 | 5.35 | 1.41 | 0.0 ms | 0 | solid |
| 20 | 165.97 | 6.32 | 5.13 | 1.29 | 4.5 ms | 0 | solid |

## Which parts have a reliable bar grid

- **Beat grid: the entire file, 0:00–20:59.5.** Salience never drops below 2.6 in any minute and the
  phase residual is ≤ 9 ms (one frame) everywhere. Use it anywhere.
- **Bar grid: reliable everywhere except within ±8 bars of a bar-phase reset.** The three strong
  resets (6:57.5, 9:17.8, 15:06.2) are genuine downbeat moves; the five weaker ones (2:41.3, 3:06.9,
  13:09.8, 14:06.2, 17:07.4) are the places where the bar phase is least certain.
- **Softest minute: 15.** Salience 2.63, a reset, and the beat-phase step at 15:13.9 all land in
  15:00–15:15. Anything bar-aligned across that window is suspect; everything either side is fine.
- **Strongest stretches: 2:00–6:00 and 18:00–21:00.** Salience 4–6.7 with 0 resets in most minutes
  and beat/8th up to 1.45.
- **Not resolved here:** how many tracks are in the set and where they start. The grid shows exactly
  one phase discontinuity and eight bar-phase moves; a beatmatched, phrase-matched transition between
  two records at the same master tempo leaves no trace in the grid at all. Track boundaries have to
  come from timbre/structure analysis, not from this file.

## Method

1. **Onset envelopes** from the cached spectral flux at 93.75 fps: log-compressed, a 1.5 s running
   mean removed, half-wave rectified, unit variance. Three of them — broadband, kick band (sub+bass,
   20–120 Hz) and high (2–16 kHz). The tracker runs on `1.0·broadband + 0.7·kick + 0.5·high`.
2. **Tempogram**: 8 s windows, 1 s hop, FFT autocorrelation, comb over lag multiples 1–4 with weights
   1 / 0.6 / 0.4 / 0.3, BPM 140–200. *Gotcha worth knowing:* the autocorrelation only exists at
   integer lags, so interpolating it linearly makes the comb score piecewise linear and its maximum
   snaps to whichever BPM puts all four teeth on integer lags — the same BPM in every window,
   forever. That is what a "confidence 1.0" flat phase search looks like from the inside. The AC is
   now tapered and sinc-upsampled ×8 before the comb, which makes the score a genuinely smooth
   function of BPM.
3. **Tempo Viterbi** over the BPM grid with an L1 penalty on BPM change → a piecewise-constant path,
   used only to give the beat tracker a per-frame period.
4. **Beat DP** (Ellis-style): `cum[t] = onset[t] + max over τ∈[0.5P, 2P] of (cum[t−τ] − 80·log(τ/P)²)`
   with P taken per frame from the tempo path, then backtrace. Phase is continuous by construction
   and the penalty is loose enough (0.0007 at a 0.5 BPM deviation) that the DP is free to follow a
   different tempo if one exists. It didn't.
5. **Stable stretches**: bottom-up piecewise-**linear** fit of beat time vs beat index. A constant
   tempo is a straight line in that space, so each surviving piece is a stable-tempo stretch and its
   slope gives the period to better than 0.01 BPM — far finer than an 8 s window can resolve.
   Merging stops at 12 ms RMS. Then a second beat-DP pass with the refined periods, the beats snapped
   onto their stretch's line (killing the DP's ±10 ms integer-frame jitter), and a sub-frame phase
   polish per stretch (−5.4 ms and −4.5 ms).
6. **Downbeats**: beat-synchronous kick-band onset, locally z-scored, into a 4-state Viterbi over bar
   position with forced 0→1→2→3→0 transitions and a penalty for any other jump. Validated against
   broadband onset and per-beat spectral change, and stress-tested by sweeping the penalty.
7. **Confidence**: two separate measures, because they answer different questions. *Salience*
   (is there a pulse here at all) compares onset energy on the beat against 12 offsets spread over
   the beat — a guessed grid scores 1.0. *beat/8th* (is the pulse on the beat rather than an 8th off)
   compares the beat against beat+P/2 in the kick and broadband envelopes, because in jungle the
   off-beat 8th is the only realistic rival and a generic baseline barely notices the difference.
   Phase residual is searched over ±¼ beat only: over a full beat, an ambiguous window flips to the
   off-beat 8th and reports half a beat of "error" that is not an error of the grid.

Reproduce: `python scripts/reaper_grid.py` (rebuild + tables), `--report` (tables from the saved
npz), `--diag` (tempo/phase/profile diagnostics). A cached intermediate is written next to the repo;
`--force` rebuilds it.

## How to use grid.npz

```python
import numpy as np
g = np.load(r"C:\Users\eric\Downloads\reaper_cache\grid.npz")
```

| key | shape | meaning |
|---|---|---|
| `beats_s` | (3484,) f8 | beat times in seconds, 0.0408 → 1259.158, ascending |
| `downbeats_s` | (869,) f8 | bar-one times; identical to `beats_s[beat_bar_pos == 0]` |
| `beat_bar_pos` | (3484,) i1 | 0–3, position of each beat in its bar (0 = downbeat) |
| `bpm_timeline` | (1249, 2) f8 | column 0 = window-centre time s, column 1 = BPM. The published one |
| `bpm_tempogram` | (1249, 2) f8 | same shape, the raw windowed tempogram estimate before the beat-time refit. Diagnostic only — noisier |
| `confidence` | (1258, 2) f8 | t, salience. 8 s windows, 1 s hop. ~1 = no grid, ≥3 = solid |
| `confidence_z` | (1258, 2) f8 | t, the same contrast as a z-score |
| `confidence_phase` | (1258, 2) f8 | t, beat ÷ off-beat-8th. >1 means the phase is on the beat |
| `phase_residual_ms` | (1258, 2) f8 | t, local offset of the audio from the grid in ms (±¼ beat search) |
| `segments` | (2, 3) f8 | rows of `(start_s, end_s, bpm)` — the stable stretches |
| `segment_fit` | (2, 2) f8 | rows of `(line_residual_ms, n_beats)` for the same rows |
| `segment_stats` | (2, 5) f8 | rows of `(salience, z, beat_per_8th, phase_resid_ms, bar_margin)` |
| `bar_phase_resets_s` | (8,) f8 | times where the bar phase moved — candidate mix markers |
| `meta` | (4,) f8 | `[fps, duration_s, n_beats, n_downbeats]` = `[93.75, 1259.727, 3484, 869]` |

Common jobs:

```python
beats, downs, pos = g["beats_s"], g["downbeats_s"], g["beat_bar_pos"]

# bar n spans downs[n] .. downs[n+1]  (869 bars; a bar is 1.4458 s at 165.99 BPM)
bar_edges = downs

# the 16th-note grid inside bar n, as times
b0, b1 = downs[n], downs[n + 1]
sixteenths = b0 + (b1 - b0) * np.arange(16) / 16

# frame index in frames.npz for any time t (fps = 93.75, hop 512 @ 48 kHz)
frame = np.round(t * 93.75).astype(int)

# is this stretch trustworthy?
c = g["confidence"]; p = g["confidence_phase"]
ok = np.interp(t, c[:, 0], c[:, 1]) > 3.0 and np.interp(t, p[:, 0], p[:, 1]) > 1.05

# stay clear of the mix at 15:06-15:14 if you need bar alignment across it
```

Two gotchas: bars either side of a `bar_phase_resets_s` entry are **not** 4 beats apart (bar length
ranges 0.36–2.53 s across a reset — that is the reset absorbing 1–3 beats, by design), so always
take bar edges from `downbeats_s` rather than assuming `beats_s[::4]`. And do not mix this grid with
`bar_start_s` / `grid16` / `offs16` from `bars.npz`: those were built on the old 165.83 BPM grid,
which is up to 3.7 beats out.
