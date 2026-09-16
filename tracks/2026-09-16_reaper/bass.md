# What the low end does — Tim Reaper jungle DJ set (section), 1259.7 s

Structural analysis only. No audio was sampled, extracted or copied; everything below is a
measurement. All of it is reproducible with `scripts/reaper_bass.py`
(`grid | sections | f0 | notes | spec | kick | report | bell | recipe | timbre | riff | bars`).

**Grid**: 165.97 BPM (from `grid.npz`, least-squares over 3485 beats), beat 361.5 ms,
bar 1.446 s, 871 bars. Sections are my own checkerboard-novelty split (25 sections, 22–63 bars
each) — they line up with mix points, so "section" ≈ "a record in the mix".

**Method**: 8 kHz mono band-passed 28–190 Hz, decimated to 2 kHz, YIN F0 over 30–150 Hz with a
160 ms window / 24 ms hop, median-filtered, gated at confidence > 0.70. Cross-checked against
the independent strongest 25–175 Hz spectral peak on 415 sustained notes: **92.5% agree within
1 semitone, 0.0% octave-high errors, 1.0% octave-low**. Pitch range (5–95 pct) D1–F2, i.e.
37–88 Hz.

---

## 1. The single most important finding: this bass is not a held drone

The plan in the track being built is a *held sub*. The reference does the opposite. Splitting
the F0 track into **plateaus** (|dpitch/dt| < 2 st/s) and **glides** (everything else):

| | value |
|---|---|
| Plateaus (held pitches) | 1167, **1.34 per bar** |
| Glide runs ≥ 70 ms | 2174, **2.50 per bar** |
| Time on a plateau | 29.7% of the file |
| Time gliding | 22.5% of the file |
| Transitions reached *by a glide* | 41% (59% are jumps / re-articulations) |

So for every held pitch there are ~1.9 slides. The movement is real, not tracker noise — it
survives tightening the confidence gate:

| conf gate | % of frames | % of those steady | \|slope\| p50 | p75 | p90 (st/s) |
|---|---|---|---|---|---|
| > 0.55 | 76.9 | 43.4 | 2.75 | 8.11 | 24.08 |
| > 0.70 | 60.1 | 48.0 | 2.19 | 6.42 | 13.09 |
| > 0.80 | 45.5 | 53.8 | 1.70 | 5.11 | 9.45 |
| > 0.90 | 29.9 | **58.9** | 1.39 | 4.13 | 7.41 |

Even in the cleanest 30% of frames, 41% of the time the bass is moving.

**Glide shape**: median duration **96 ms (0.27 beats)**, median span **0.76 st**, p90 span
3.17 st, median rate **6.7 st/s**. 59% fall, 41% rise. These are short portamento scoops into
and out of notes, not long risers.

## 2. Note-duration distribution (plateaus, in beats)

Percentiles: p5 0.20 · p10 0.20 · p25 0.33 · **p50 0.60** · p75 1.13 · p90 1.86 · p95 2.66 ·
p99 3.78. Mean 0.89 beats (321 ms). **Max 5.58 beats — nothing is ever held longer than
1.4 bars.**

| duration (beats) | musical value | count | % of notes | % of sounding time |
|---|---|---|---|---|
| 0.00–0.25 | < 1/16 | 134 | 11.5 | 2.6 |
| 0.25–0.50 | 1/16–1/8 | 356 | **30.5** | 12.3 |
| 0.50–0.75 | 1/8–dotted 1/8 | 211 | 18.1 | 12.7 |
| 0.75–1.00 | dotted 1/8–1/4 | 135 | 11.6 | 11.7 |
| 1.00–1.50 | 1/4–3/8 | 155 | 13.3 | **18.9** |
| 1.50–2.00 | 3/8–1/2 | 82 | 7.0 | 13.8 |
| 2.00–3.00 | 1/2–3/4 | 49 | 4.2 | 11.7 |
| 3.00–4.00 | 3/4–1 bar | 37 | 3.2 | 12.5 |
| 4.00–6.00 | 1–1.5 bar | 8 | 0.7 | 3.8 |
| > 6.00 | ≥ 1.5 bar | **0** | 0.0 | 0.0 |

Read the two right-hand columns against each other: by *count* the bass is mostly 8th-note
stabs, but by *time on the clock* the weight sits at 1–4 beats. Both states exist; neither
dominates. **Stabs and quarter-to-bar-long notes, never a drone.**

## 3. Movement: interval histogram and change rate

1023 plateau-to-plateau transitions with a gap < 1 bar. Median gap between plateaus **360 ms =
exactly 1.00 beat**. Mean |interval| 3.06 st, median 1.81 st.

Folded |interval|, % of transitions:

| st | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| % | **34.6** | 13.3 | **15.2** | 5.2 | 4.2 | 6.0 | 2.0 | **7.4** | 2.2 | 3.1 | 1.3 | 0.7 | 1.8 |

Direction is balanced: 30.7% down, 34.6% repeat, 34.7% up. Signed peaks are −2 (7.3%),
−1 (5.2%), −3 (3.3%), −7 (3.3%), +1 (8.1%), +2 (7.9%), +7 (4.1%), +5 (3.2%).

Glided and jumped transitions differ:

* **glided** (41%): median |interval| 1.05 st, p90 5.04 st, only 19% are ≥ 3 st
* **jumped** (59%): median |interval| 2.05 st, p90 9.30 st, 43% are ≥ 3 st

i.e. small moves are smeared with portamento, big moves are articulated.

**Change rate: 0.90 changes/bar over the whole file = 7.2 per 8 bars.** Per section it runs
0.03–1.72/bar; excluding the near-silent intro (S01) the range is **0.25–1.72/bar
(2.0–13.7 per 8 bars)**, and the median section sits at ~0.9/bar.

## 4. Per-section table

`chg/bar` = plateau changes ≥ 0.5 st per bar. `voiced%` = share of the section on a plateau.
Register columns are the split *within 0–250 Hz*.

| sec | start–end s | bars | notes | chg/bar | chg/8bar | med note (beats) | voiced % | med MIDI | root | <60 Hz % | 60–120 % | 120–250 % |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S01 | 0.0–49.6 | 34.3 | 4 | 0.03 | 0.2 | 0.37 | 2.2 | 33.4 | F# | 14.3 | 45.1 | 40.6 |
| S02 | 49.6–81.2 | 21.8 | 37 | 1.24 | 9.9 | 0.73 | 42.9 | 30.6 | F# | 85.2 | 7.8 | 7.0 |
| S03 | 81.2–141.4 | 41.6 | 34 | 0.53 | 4.2 | 0.73 | 20.7 | 29.2 | F | 67.0 | 14.7 | 18.3 |
| S04 | 141.4–188.0 | 32.2 | 19 | 0.56 | 4.5 | 0.40 | 10.0 | 31.3 | E | 35.9 | 35.7 | 28.4 |
| S05 | 188.0–246.7 | 40.6 | 77 | 1.33 | 10.6 | 0.66 | 44.1 | 31.1 | E | 77.7 | 15.2 | 7.2 |
| S06 | 246.7–281.2 | 23.9 | 37 | 1.30 | 10.4 | 0.53 | 31.4 | 34.6 | B | 57.9 | 29.2 | 12.9 |
| S07 | 281.2–323.4 | 29.1 | 57 | **1.72** | 13.7 | 0.40 | 31.9 | 29.4 | F | 84.8 | 6.1 | 9.2 |
| S08 | 323.4–406.1 | 57.2 | 103 | 1.57 | 12.6 | 0.53 | 30.7 | 35.3 | F# | 33.9 | 48.1 | 18.0 |
| S09 | 406.1–443.7 | 26.0 | 16 | 0.50 | 4.0 | 0.50 | 7.1 | 30.9 | F# | 31.2 | 33.7 | 35.1 |
| S10 | 443.7–487.3 | 30.2 | 41 | 0.30 | 2.4 | 1.06 | 48.9 | 30.0 | F# | 75.2 | 8.6 | 16.2 |
| S11 | 487.3–546.0 | 40.6 | 65 | 0.42 | 3.4 | 1.00 | 49.2 | 30.1 | F# | 73.2 | 10.1 | 16.6 |
| S12 | 546.0–604.6 | 40.6 | 40 | 0.67 | 5.3 | 1.03 | 34.5 | 29.4 | D# | 43.7 | 33.1 | 23.3 |
| S13 | 604.6–652.7 | 33.3 | 31 | 0.90 | 7.2 | **1.39** | 44.7 | 29.1 | D# | 82.1 | 11.5 | 6.4 |
| S14 | 652.7–697.9 | 31.2 | 52 | 1.28 | 10.3 | 0.76 | 35.2 | 31.7 | G# | 80.2 | 13.9 | 5.8 |
| S15 | 697.9–767.0 | 47.8 | 65 | 1.11 | 8.9 | 0.60 | 21.3 | 32.1 | C# | 57.2 | 31.1 | 11.7 |
| S16 | 767.0–858.8 | 63.4 | 53 | 0.54 | 4.3 | 1.19 | 38.3 | 30.0 | F# | 80.6 | 13.7 | 5.7 |
| S17 | 858.8–905.4 | 32.2 | 33 | 0.96 | 7.7 | 0.93 | 30.6 | 30.1 | F# | 83.8 | 5.7 | 10.5 |
| S18 | 905.4–937.0 | 21.8 | 24 | 0.96 | 7.7 | 0.66 | 24.4 | 33.6 | A | 56.9 | 29.8 | 13.3 |
| S19 | 937.0–983.6 | 32.2 | 23 | 0.59 | 4.7 | 0.33 | 7.3 | 27.0 | D# | 61.6 | 14.2 | 24.2 |
| S20 | 983.6–1028.7 | 31.2 | 29 | 0.87 | 6.9 | 0.46 | 13.7 | 25.4 | G | 70.4 | 7.8 | 21.8 |
| S21 | 1028.7–1075.4 | 32.2 | 57 | 0.25 | 2.0 | 0.40 | 23.4 | 27.1 | D# | **91.5** | 2.2 | 6.2 |
| S22 | 1075.4–1108.4 | 22.9 | 58 | 1.01 | 8.0 | 0.40 | 35.4 | 27.2 | D# | **95.0** | 3.2 | 1.8 |
| S23 | 1108.4–1167.1 | 40.6 | 95 | 0.91 | 7.3 | 0.40 | 32.2 | 27.2 | D# | **95.7** | 2.3 | 2.0 |
| S24 | 1167.1–1201.7 | 23.9 | 29 | 0.75 | 6.0 | 0.53 | 18.6 | 27.0 | D# | 70.3 | 11.5 | 18.3 |
| S25 | 1201.7–1259.7 | 40.1 | 88 | 1.57 | 12.6 | 0.76 | 46.4 | 33.9 | A# | 71.2 | 15.7 | 13.1 |

Note the trade-off down the `chg/bar` and `med note` columns: sections that change often
(S07, S08, S25 at 1.6–1.7/bar) hold notes for 0.40–0.76 beats; sections that change rarely
(S10, S11, S21 at 0.25–0.42/bar) hold for 0.40–1.06 beats and push the sub to 73–92% of the
low end. **Busy and deep are alternatives, not partners.**

## 5. Presence vs absence, per bar

871 bars. Bass audible (plateau or glide covering > 25% of the bar) in **76.7% of bars**.
Per-bar coverage: p10 2% · p25 28% · p50 57% · p75 76% · p90 89%.

* 90 unbroken **ON** stretches: median **3 bars**, p90 18 bars, max 40 bars
* 90 unbroken **OFF** stretches: median **1 bar**, p90 4 bars, max 34 bars

The bass drops out constantly and briefly — a one-bar hole is the normal punctuation — with a
handful of long structural absences (up to 34 bars).

## 6. Kick versus sub — there is no sidechain

5420 low-frequency transients (6.2/bar); the kick-like subset (35–120 Hz at least the median
17.1 dB above 400–2000 Hz, and loud) is **2438 hits = 2.8/bar, median IOI 280 ms**.

### 6a. The windows you asked for

Post-kick sub-band (20–60 Hz) energy vs the mean between kicks:

| band | 0–30 ms | 30–80 ms | 80–200 ms |
|---|---|---|---|
| sub 20–60 | **−0.25 dB** | **+0.32 dB** | **−0.09 dB** |
| bass 60–120 | +1.09 | +1.30 | +0.31 |
| harm 120–250 | +3.76 | +2.26 | +1.57 |
| mid 400–2k | +0.77 | +0.04 | +0.23 |

Restricted to kicks that land *inside* a sustained bass note (ref = the 110–20 ms before the
kick): sub **−0.51 / −0.32 / −0.38 dB**, bass −0.52 / −0.90 / −0.28, harm −1.07 / −1.47 / −0.24.

### 6b. The artifact-free version

Anchored on the kick's envelope *peak* (not the steepest-rise index, which sits in the trough
before the attack and fakes a dip at t=0), referenced to kick-free frames **inside the same
bass note** — 45 notes, 200 kicks, 5 ms resolution:

| ms | −120 | −80 | −40 | 0 | 40 | 80 | 120 | 160 | 200 | 240 |
|---|---|---|---|---|---|---|---|---|---|---|
| sub | +1.1 | −1.6 | +0.3 | **+2.3** | −1.6 | −0.8 | +1.2 | −1.7 | −2.0 | −0.2 |
| bass | −0.0 | −2.4 | −0.1 | +1.6 | −1.7 | −2.6 | −1.0 | −0.8 | −1.3 | −0.2 |
| harm | −1.8 | −1.6 | −0.8 | −0.6 | −2.2 | −1.9 | −1.9 | −1.8 | −1.6 | −2.1 |

The sub **rises +2.3 dB at the kick** and its deepest post-kick excursion is −3.2 dB at 115 ms —
and the oscillation is periodic, not a release curve. For scale: inside a sustained note the
sub's own p10–p90 ripple is **8.2 dB**. Every post-kick excursion is smaller than the note's
natural wobble.

Per section (sub level 30–90 ms after a kick, re the in-note kick-free baseline), across the 14
sections with enough sustained-bass-plus-kick overlap: **median +0.20 dB, worst −3.55 dB, best
+5.78 dB, zero sections below −4 dB.** No record in this mix sidechains its bass.

### 6c. What they do instead: frequency separation

Spectrum share, kick-only moments (291) vs bass-without-kick moments (787):

| band | kick-only | bass-only |
|---|---|---|
| 0–60 Hz | 50.8% | **73.8%** |
| 60–120 Hz | **23.2%** | 8.9% |
| 120–250 Hz | **19.3%** | 7.6% |
| 250–400 Hz | 4.0 | 4.8 |
| 400–1000 Hz | 2.5 | 4.5 |
| 1000–2400 Hz | 0.2 | 0.4 |

The kick's body is at 60–250 Hz (42.5% of its energy, vs 16.5% for the bass); the bass owns
below 60 Hz (73.8% vs 50.8%). They overlap in the sub but the kick puts more than twice as much
of its weight in the 60–250 Hz window where the bass has almost nothing. **They share the room
by register, not by ducking.**

## 7. Register — a clean sub, not a reese

Share of 0–2.4 kHz power over the whole file:

| band | % | dB re total |
|---|---|---|
| 0–20 Hz | 0.34 | −24.6 |
| 20–30 Hz | 0.53 | −22.8 |
| 30–40 Hz | 18.93 | −7.2 |
| **40–50 Hz** | **30.10** | **−5.2** |
| 50–60 Hz | 15.71 | −8.0 |
| 60–120 Hz | 13.61 | −8.7 |
| 120–250 Hz | 11.64 | −9.3 |
| 250–400 Hz | 4.67 | −13.3 |
| 400–1000 Hz | 4.03 | −13.9 |
| 1000–2400 Hz | 0.44 | −23.5 |

**Below 60 Hz = 65.6% of all 0–2.4 kHz power.** Within the 0–250 Hz low end: **<60 Hz 72.2%,
60–120 Hz 15.0%, 120–250 Hz 12.8%.** DC/rumble is negligible (0–20 Hz is 0.34% of the total,
0.52% of the sub band) and the peak sits squarely at 40–50 Hz — this is a deliberately
high-passed, musical sub.

**Harmonic comb** over 415 sustained notes, comparing on-comb (k·F0) against an off-comb control
at (k+0.5)·F0 in the same region, which subtracts the broadband break noise:

| k | on-comb dB re k=1 | excess over off-comb |
|---|---|---|
| 1 | 0.0 | +23.3 |
| 2 | **−16.6** | +11.2 |
| 3 | **−17.7** | +6.8 |
| 4 | −20.6 | +2.3 |
| 5 | −21.7 | +3.8 |
| 6 | −25.7 | −0.2 |
| 7 | −23.5 | +3.3 |
| 8+ | −25 to −28 | +0.2 to +1.8 |

The fundamental beats the 2nd harmonic by **16.6 dB**, and above the 5th harmonic the excess over
the off-comb control collapses to ~1 dB — i.e. there is no genuine bass harmonic structure up in
the mids at all. **This is a clean sine-ish sub, not a reese.** A reese would show h2–h8 within
6–10 dB of the fundamental and a large comb excess out past 500 Hz.

## 8. Key

Whole-file bass pitch-class weight, by sounding time:

| C | C# | D | D# | E | F | F# | G | G# | A | A# | B |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.7 | 7.3 | 2.3 | **17.0** | 5.6 | 8.3 | **33.5** | 4.5 | 9.9 | 2.3 | 5.3 | 3.4 |

Best single 7-note collection for the whole file: **D# minor / F# major — 84.6% of all bass
sounding time lies inside it.** Only C (0.7%), D (2.3%), E (5.6%), G (4.5%) and A (2.3%) fall
outside.

Section roots: F# ×8, D# ×7, E ×2, F ×2, and one each of A, A#, B, C#, G, G# — 10 distinct roots
over 25 sections, but **16/25 sections sit ≥ 80% inside D# minor and 20/25 sit ≥ 60%, median fit
89%.** The outliers are a contiguous run in the first half (S04, S05 rooted on E; S18–S20 on A/G,
19–48% fit). So: **the set is key-mixed around D# minor / F# major for roughly three quarters of
its length, with two deliberate excursions.** The DJ is not ignoring key, but is also not
policing it — the excursions are whole records, not accidents.

---

## 9. The bell in the attack

The plateau comb in §7 averaged over sustains, so it could not see an attack. This section looks
at note onsets only (`reaper_bass.py bell` and `recipe`).

**Onsets.** A voiced run after ≥ 96 ms unvoiced, a stable settled pitch, a ≥ 9 dB rise in the
25–400 Hz envelope, refined to 2.5 ms: **334 onsets**, **172** lasting ≥ 420 ms (needed for the
200–400 ms reference), **98 clean** (no ≥ 9 dB 2–4 kHz drum transient at the onset; 43% of onsets
land on one). Median pitch of the clean set **47.4 Hz**.

**Method.** Each partial k·f0 is read by Gaussian demodulation with σ = f0/4, which puts the
neighbouring harmonics 35 dB down, with a time resolution σ_t ≈ 13 ms. Every note is normalised to
*its own* sustained fundamental (200–400 ms), so pitch cannot pass for timbre. **Control:** the
identical pipeline run on a clean sine note with the same pitch and attack time. Pitch is measured
period by period from zero crossings, band-passed 0.6–1.9 × f0 (narrow) and 0.6–3.5 × f0 (wide).

### 9.1 Partial levels per window (clean notes, n = 98), dB re sustained fundamental

| k | 0–20 ms | 20–50 | 50–100 | 100–200 | 200–400 | background (−150…−90) |
|---|---|---|---|---|---|---|
| 1 | −7.5 | −0.7 | +1.8 | +2.0 | 0.0 | −14.2 |
| 2 | **−8.5** | **−13.1** | −25.0 | −24.1 | −25.5 | −29.5 |
| 3 | −14.8 | −19.1 | −17.8 | −15.8 | **−17.7** | −28.3 |
| 4 | −14.6 | −18.2 | −23.3 | −22.0 | −20.4 | −22.0 |
| 5 | −16.4 | −21.5 | −23.2 | −25.0 | −23.0 | −25.6 |
| 6 | −18.2 | −22.1 | −25.1 | −24.1 | −23.3 | −24.3 |
| 7 | −20.2 | −23.0 | −25.3 | −25.4 | −22.4 | −25.3 |
| 8 | −22.5 | −26.4 | −26.9 | −24.0 | −24.5 | −25.2 |

Excess over the clean-sine control (floored at the background), dB:

| k | 0–20 ms | 20–50 | 50–100 | 100–200 | 200–400 |
|---|---|---|---|---|---|
| 2 | **+21.0** | **+16.3** | +4.5 | +5.4 | +4.0 |
| 3 | +13.5 | +9.2 | +10.5 | +12.5 | +10.6 |
| 4 | +7.4 | +3.8 | −1.3 | 0.0 | +1.6 |
| 5 | +9.2 | +4.0 | +2.4 | +0.6 | +2.5 |
| 6 | +6.2 | +2.3 | −0.7 | +0.2 | +1.0 |
| 7 | +5.1 | +2.3 | 0.0 | −0.1 | +2.9 |
| 8 | +2.7 | −1.1 | −1.6 | +1.2 | +0.8 |

Two different things are in this table. **h2 is an attack event:** −8.5 dB in the first 20 ms, back
down to −25 dB by 50–100 ms. **h3 is static:** about −15 to −19 dB from start to finish (+10 to
+13 dB over a sine throughout), i.e. odd-harmonic saturation that belongs to the sustain, not the
attack. h4–h8 carry +3 to +9 dB in the first 20 ms and are back at the background by 20–50 ms.

### 9.2 Harmonic or inharmonic? Harmonic — the energy between the harmonics is a swept fundamental

Ratio scan with σ = 0.1 × f0 (resolution ±0.1 in ratio), 0–80 ms vs 200–400 ms:

| ratio | 1 | 1.5 | 2 | 2.5 | 3 | 3.5 | 4 | 4.5 | 5 | 5.5 | 6 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| attack − sustain, dB | −2.3 | **+17.0** | +12.6 | +9.9 | −0.5 | +5.7 | +2.8 | +2.1 | +5.4 | +3.4 | +0.9 |
| attack level, dB re fund. | −2.3 | −12.3 | −16.9 | −22.5 | −21.0 | −21.2 | −21.5 | −24.1 | −22.6 | −24.9 | −26.1 |

* The **only local peak** of the attack curve is at **1.05 × f0** — the fundamental, still a little
  sharp. There is **no peak** at the classic FM/bell ratios: 2.76× reads −22.1 dB, 3.5× −21.2 dB,
  5.4× −25.3 dB, all at or below the neighbouring levels.
* The attack excess sits **just above the fundamental and shrinks steadily with ratio** (1.5×
  +17 dB → 2.5× +10 dB → 3.5× +6 dB), and it fills the half-integer gaps as much as the integers.
  A fixed partial can't do that; a fundamental sweeping *down* through 2×, 1.5× and 1× in the
  first tens of milliseconds does exactly that.
* Locked to the note, not to a frequency: the 0–80 ms excess is **41.1 dB** above its median on a
  ratio axis (at 1.50 × f0) against **31.8 dB** on an absolute-Hz axis. It is not a fixed resonance.

### 9.3 Decay of each partial

Median onset-aligned envelopes. Resolution floor: the clean-sine control itself takes 32–60 ms to
fall 20 dB, so faster decays read as ~30 ms.

| k | attack peak dB | at ms | sustain / background dB | T-10 from peak | back at background |
|---|---|---|---|---|---|
| 2 | −8.1 | 12.5 | −25.5 | **30 ms** | by 50–100 ms (~17 dB drop) |
| 3 | −14.4 | 10.0 | −17.7 (sustains) | — (only 3 dB of attack) | static |
| 4 | −13.9 | 17.5 | −20.4 | 25 ms | by 50–100 ms |
| 5 | −16.4 | 12.5 | −23.0 | — (7 dB range) | by 20–50 ms |
| 6 | −17.8 | 10.0 | −23.3 | 37.5 ms | by 20–50 ms |
| 7 | −19.7 | 7.5 | −22.4 | — (3 dB range) | by 20–50 ms |
| 8 | −21.4 | 2.5 | −24.5 | — (3 dB range) | by 20–50 ms |

Every non-fundamental attack component is gone in **≈ 30–40 ms** (h2 is the slowest, falling
~17 dB by 50–100 ms). That is the time course of the pitch sweep in 9.4, not of independent partials.

### 9.4 Pitch envelope at the onset — a large, fast drop ("ping")

Period-by-period pitch, semitones above the note's 200–400 ms pitch (clean notes):

| ms after onset | 0–10 | 10–20 | 20–30 | 30–45 | 45–60 | 60–80 | 80–100 | 100–130 | 130–170 | 170–220 | 220–300 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| narrow band, p50 | +10.3 | +7.6 | +5.6 | +1.5 | +1.4 | +1.1 | +0.6 | +0.5 | +0.3 | +0.2 | 0.0 |
| wide band, p50 | **+17.1** | +10.4 | +7.0 | +2.3 | +1.5 | +1.5 | +0.7 | +0.5 | +0.3 | +0.3 | +0.1 |
| narrow p25 | +6.5 | +6.0 | −0.4 | +1.0 | +1.0 | +0.3 | +0.2 | −0.1 | 0.0 | 0.0 | −0.1 |
| narrow p75 | +11.3 | +9.4 | +7.0 | +3.4 | +2.6 | +1.7 | +1.3 | +0.9 | +0.6 | +0.7 | +0.2 |
| notes with a period in the bin | 50 | 56 | 61 | 76 | 64 | 86 | 92 | 98 | 98 | 98 | 98 |

The narrow band cannot see pitches above ~1.9 × f0 (+11 st), so it under-reads the start. The wide
band reads **+17 st in the first 10 ms**, and the recipe fit (9.7) puts the true start at about
**+30 st**.

* **Start offset** (mean over 0–35 ms): median **+6.8 st** narrow / **+11.0 st** wide; p25 +3.7,
  p75 +8.7, p90 +9.7 (narrow).
* **Share of notes that start sharp**, against a control measured mid-note (250–285 ms):

  | threshold | ≥ +1 st | ≥ +3 st | ≥ +5 st |
  |---|---|---|---|
  | onsets | **79%** | **76%** | **63%** |
  | mid-note control | 3% | 1% | 0% |

  Only 4–6% of onsets start *flat*, so this is a directed drop, not jitter.
* **Shape:** two stages — a fast drop to within ~+1.5 st by **30–45 ms**, then a slow tail of
  +1 → 0 st over ~150 ms. Settle time (last period ≥ 0.7 st off): median **157 ms** for the notes
  that ping.
* **The glides of §1 are half this.** **48%** of the 2174 glide runs begin within 100 ms of a
  voiced start, and **71%** of those fall; the rest are split 47% falling. The YIN window (160 ms)
  smeared a +10 st, 30 ms drop into what looked like a −0.6 st, 120 ms "glide". The pitch drop at
  note start is real and large; the portamento between notes is the smaller half of §1b.

### 9.5 Click or tone? A pitched transient — no click

Band power, dB re sustained fundamental, **reference / clean sine**:

| band Hz | −60…−10 ms | 0–5 ms | 5–20 ms | 20–50 ms | 200–400 ms |
|---|---|---|---|---|---|
| 20–60 | −17.9 / — | −9.6 / −29.1 | −5.2 / −13.9 | −1.2 / −3.5 | 0.0 / 0.0 |
| 60–120 | −23.8 / — | −7.1 / −28.1 | −2.9 / −13.8 | −3.2 / −7.4 | −21.8 / −40.9 |
| 120–250 | −20.4 / — | **−3.9** / −27.5 | −4.8 / −23.0 | −9.8 / −37.4 | −13.2 / −79.8 |
| 250–500 | −15.9 / — | **−4.9** / −34.6 | −9.5 / −52.7 | −11.8 / −61.3 | −12.8 / −101 |
| 500–1000 | −19.6 / — | −12.4 / −54.9 | −14.3 / −70.9 | −15.6 / −77.1 | −16.9 / −118 |
| 1000–2000 | −26.5 / — | −24.5 / −71.5 | −22.5 / −86.6 | −23.8 / −92.0 | −25.6 / −133 |
| 2000–3900 | −51.7 / — | **−51.4** / −87.6 | −50.0 / −102 | −51.2 / −107 | −52.1 / −150 |

* **No broadband click:** 2–3.9 kHz does not move at the onset (−51.7 dB before, −51.4 dB in the
  first 5 ms), and 1–2 kHz rises only 2 dB.
* **Pitched transient:** the 0–20 ms excess over a clean sine peaks at **101 Hz**, centroid
  **230 Hz**, spectral flatness **0.001** (1 = white click). Over 0–80 ms the excess peaks at
  **136 Hz = 2.87 × f0** — the sweep passing through the low hundreds of Hz.
* **Loudness:** in the first 5 ms, 120–500 Hz sits only **4–5 dB below the sustained
  fundamental**, where a clean sine sits 27–35 dB below. Over 0–20 ms the energy above 150 Hz
  (beyond a sine) is **−3.9 dB** re sustained fundamental. On small speakers that is the part you
  hear.

### 9.6 Consistency — per record, not universal

**Strict set** (clean onsets, n = 98): **76%** start ≥ +3 st sharp. The "bell index" — partials
2–8 over 0–50 ms, dB above the loudest of their own sustain, the background, and the clean-sine
splatter — has median **+5.0 dB** (p10 −4.2, p90 +10.7); **67%** of notes are ≥ 3 dB and **36%**
are ≥ 6 dB.

**Broad set** (every voiced start after ≥ 48 ms with a ≥ 6 dB rise, pitch re YIN; 651 onsets):
**52%** start ≥ +3 st — 49% of the 391 clean onsets, 57% of the 260 on a drum hit. The broad set
includes short and near-legato notes, which read lower. Per section:

| sec | onsets | start ≥ +3 st | median start st | | sec | onsets | start ≥ +3 st | median start st |
|---|---|---|---|---|---|---|---|---|
| S02 | 30 | 57% | +4.9 | | S14 | 51 | **88%** | +6.3 |
| S03 | 42 | 55% | +3.4 | | S15 | 63 | 52% | +3.6 |
| S04 | 26 | 58% | +4.3 | | S16 | 47 | 62% | +6.6 |
| S05 | 23 | 52% | +3.6 | | S17 | 17 | **94%** | +11.2 |
| S06 | 24 | 42% | +2.2 | | S18 | 8 | 62% | +3.0 |
| S07 | 36 | 75% | +4.8 | | S19 | 19 | 32% | +0.4 |
| S08 | 69 | 36% | +1.4 | | S20 | 30 | 70% | +6.7 |
| S09 | 17 | **12%** | +0.5 | | S21 | 5 | 20% | +0.2 |
| S10 | 6 | 50% | +2.1 | | S22 | 7 | **0%** | −0.6 |
| S11 | 11 | 36% | +0.3 | | S24 | 11 | 55% | +4.6 |
| S12 | 34 | 50% | +3.1 | | S25 | 46 | **7%** | −0.1 |
| S13 | 24 | 79% | +4.8 | | | | | |

Some records ping on almost every note (S14, S17, S13, S07: 75–94%). Others essentially never do
(S25, S22, S09: 0–12%). S25, the most odd-harmonic, saturated sub in the set (§10), has no ping at all:
**the bell and the grit are alternative characters, chosen per record.**

### 9.7 Synthesis recipe — fitted through the same measurement code

Candidate synths built from formulas (never from the reference) were pushed through the identical
pipeline and grid-searched against the clean-note medians. The objective combines partial levels
(8 partials × 5 windows), period pitch (narrow + wide bins) and the 0–50 ms click bands, with the
measured background power-added to the synth.

| model | rms dB partials | rms st pitch | rms dB click bands | misfit J |
|---|---|---|---|---|
| sine (+ attack, static ratio-1 modulation) | 5.98 | 2.83 | 7.13 | 44.2 |
| + pitch envelope (+30 st, τ 12 ms) | 4.26 | 0.76 | 6.43 | 9.5 |
| + pitch envelope, two-stage | 4.20 | 0.51 | 6.31 | 7.9 |
| + decaying FM modulator only (2.76×, index 6, τ 18 ms) | 4.29 | 0.83 | 6.04 | 9.6 |
| + decaying 1/k harmonic layer only | 4.56 | 3.00 | 6.80 | 44.1 |
| two FM modulators, **no** pitch envelope (best) | 3.19 | 0.86 | 5.62 | 7.5 |
| **pitch envelope + static ratio-2 modulator** | **1.68** | **0.50** | **2.81** | **2.2** |
| … + decaying ratio-2 modulator (index 1.5, τ 18 ms) | 1.44 | 0.50 | 2.38 | 1.9 (15% better, not kept) |

**Sweep vs sideband.** A decaying modulator at 2.76× puts a folded sideband at 1.76× into the
narrow band and fakes a sharp start. The two differ once you add the wide band, which only a real
sweep from high up can light:

| | narrow start | wide start | wide − narrow |
|---|---|---|---|
| reference (median) | +6.45 st | +10.81 st | **+3.05** |
| pitch envelope + static modulator | +8.40 | +14.01 | +5.61 |
| two FM modulators, no pitch env | +5.80 | +6.54 | +0.74 |

The reference behaves like the sweep. The best pitch-free FM model also stalls at 3.4× the misfit.

**The recipe, on a sine sub:**

1. **Pitch envelope — the single component that matters most.** Start **+30 st** (2.5 octaves;
   the median 47 Hz note begins at **284 Hz**), falling exponentially with **τ = 12 ms**: +14 st at
   10 ms, +6.6 at 20, +3.3 at 30, +1.5 at 45, +0.9 at 60 ms. Add a small tail of **+1 st decaying
   over τ = 200 ms** (still +0.4 st at 200 ms). On its own the pitch envelope removes **82%** of the
   misfit, a harmonic layer removes 0%, and no model without it gets below J 7.5.
2. **Static odd-harmonic colour:** a modulator at **ratio 2** (which makes odd harmonics) plus a
   touch at ratio 1 — fitted indices 0.5 and 0.3 — set so the sustained **h3 sits about −15 to
   −18 dB and h2 about −24 dB** re the fundamental. Calibrate on a meter, not by index: synth
   index-to-level mappings differ. This is a per-record choice (§10).
3. **Hard amplitude attack, ~1 ms.** No click layer, no noise, no inharmonic ratio.
4. Optional: a decaying ratio-2 modulator (index 1.5, τ 18 ms) adds a slightly brighter first
   20 ms (a 15% better fit).

In Operator terms: oscillator A sine; B at coarse ratio 2 feeding A at a fixed low level for the
h3 target; the pitch envelope set to +30 st with a ~12 ms exponential decay (reaching +1.5 st by
~45 ms); no filter needed. Check the result against the tables above: h2 −8 dB in the first
20 ms, −25 dB by 50 ms; wide-band pitch +17 st in the first 10 ms, +2 st by 40 ms.

---

## 10. Timbre per section

Claim tested: *the sub changes tone and harmonics (distortion) per section but keeps its nature
within a section.* (`reaper_bass.py timbre`, `bars`)

**Fingerprint, per held note** (513 plateaus ≥ 250 ms, conf > 0.7, sustain from +60 ms for up to
400 ms, zero-padded Hann FFT): each harmonic h2–h8 is read as the on-comb peak **minus the off-comb
background** at (k ± 0.5) × f0, in dB re the note's **own** fundamental and clamped at −45 dB
(= not above the background). **odd − even** = (h3+h5+h7) vs (h2+h4+h6). **THD** = sum of h2–h8.
A pooled within-section slope against pitch is removed ("pitch-adjusted").

**Octave check:** the fundamental stands a median **28.5 dB** above its half-integer neighbours
(p10 19.4 dB), and only 0.6% of notes fail to clear 6 dB. Strong h2 values are real harmonics, not
octave errors.

### 10.1 Is it constant within and different between? ANOVA over 20 sections (494 notes)

| feature | F | η² | η² pitch-adj | perm p | within-sec SD dB | between-sec SD of medians dB | first-half vs second-half r |
|---|---|---|---|---|---|---|---|
| **h2** | 26.3 | 0.51 | **0.50** | ≤ 0.002 | 10.9 | 10.3 | **+0.89** |
| **h3** | 16.8 | 0.40 | **0.41** | ≤ 0.002 | 10.1 | 10.7 | **+0.77** |
| h4 | 2.9 | 0.11 | 0.10 | ≤ 0.002 | 10.3 | 7.7 | +0.30 |
| h5 | 10.2 | 0.29 | 0.31 | ≤ 0.002 | 9.8 | 8.2 | +0.39 |
| h6 | 2.5 | 0.09 | 0.10 | ≤ 0.002 | 9.0 | 2.6 | +0.07 |
| h7 | 7.7 | 0.24 | 0.24 | ≤ 0.002 | 8.3 | 7.8 | +0.66 |
| h8 | 6.1 | 0.20 | 0.22 | ≤ 0.002 | 8.6 | 7.4 | +0.65 |
| **odd − even** | 16.6 | 0.40 | **0.42** | ≤ 0.002 | 11.3 | 9.7 | **+0.71** |
| **THD** | 19.6 | 0.44 | **0.42** | ≤ 0.002 | 7.6 | 6.3 | **+0.78** |
| background @h2 (the break) | 9.9 | 0.28 | 0.28 | ≤ 0.002 | 7.6 | 4.8 | +0.68 |

*perm p ≤ 0.002 is the floor of a 500-shuffle permutation test.*

* **Between-section differences are large and stable.** Section explains **~40–50%** of the variance
  in h2, h3, odd/even and THD, well above the background's 28%. The median of a section's first
  half predicts its second half at **r = 0.71–0.89**.
* A single note's fingerprint picks its section **33.4%** of the time (leave-one-out nearest
  centroid; chance 5.0%), and 39.7% within ±1 section.
* **But single notes scatter.** Within-section SD (8–11 dB) is as large as the spread between
  sections. About half of it is measurement noise from the breaks: note-to-note noise is h2 5.1,
  h3 5.2, THD 3.8 dB. Read the tone off a handful of notes, never one.

### 10.2 Per section (pitch-adjusted medians, dB re own fundamental; −45 = not above background)

| sec | notes | med MIDI | h2 | h3 | h4 | h5 | odd−even | THD | ping share (§9.6) |
|---|---|---|---|---|---|---|---|---|---|
| S02 | 20 | 30.6 | −44.7 | −27.0 | −44.8 | −26.9 | +14.1 | −20.3 | 57% |
| S03 | 17 | 29.3 | −42.9 | −45.1 | −26.6 | −28.3 | +1.6 | −14.1 | 55% |
| S05 | 31 | 28.3 | −42.4 | −20.1 | −43.9 | −37.4 | +11.0 | −16.7 | 52% |
| S06 | 14 | 34.7 | −21.1 | −43.1 | −33.3 | −40.7 | −13.9 | −12.9 | 42% |
| S07 | 17 | 30.9 | −41.7 | −17.1 | −34.9 | −31.5 | +5.2 | −12.9 | 75% |
| S08 | 39 | 37.2 | −24.7 | −23.5 | −42.8 | −32.0 | −0.4 | −14.7 | 36% |
| S10 | 33 | 30.0 | −44.1 | −21.2 | −31.1 | −25.0 | +12.5 | −17.4 | 50% |
| S11 | 49 | 30.1 | −44.2 | −30.4 | −36.8 | −45.3 | +5.2 | −21.7 | 36% |
| S12 | 24 | 27.4 | **−2.1** | −21.6 | −41.4 | −40.8 | **−18.4** | **−3.5** | 50% |
| S13 | 25 | 29.1 | −32.2 | −25.8 | −42.4 | −35.9 | +4.7 | −15.7 | 79% |
| S14 | 28 | 28.4 | −39.0 | −44.9 | −31.9 | −44.7 | −10.4 | −18.7 | 88% |
| S15 | 23 | 32.1 | −40.0 | −44.4 | −27.0 | −42.6 | −5.3 | −20.0 | 52% |
| S16 | 33 | 29.9 | −44.1 | −27.0 | −44.6 | −45.4 | +12.1 | −25.7 | 62% |
| S17 | 23 | 30.0 | −39.1 | −25.9 | −44.6 | −45.3 | +6.0 | −21.7 | 94% |
| S18 | 11 | 33.0 | −37.7 | −24.8 | −45.9 | −44.1 | +11.0 | −24.1 | 62% |
| S20 | 10 | 28.4 | −38.9 | −21.9 | −21.6 | −28.1 | −2.9 | −8.1 | 70% |
| S21 | 10 | 27.1 | −41.1 | −45.3 | −25.6 | −46.5 | −9.1 | −19.4 | 20% |
| S22 | 13 | 29.1 | −43.2 | −45.1 | −44.2 | −43.9 | +1.9 | **−31.4** | 0% |
| S23 | 19 | 29.1 | −43.2 | −38.1 | −44.2 | −39.7 | +12.4 | −22.8 | — |
| S25 | 55 | 33.9 | −46.1 | **−11.6** | −31.7 | −17.8 | **+15.8** | −10.4 | 7% |

**Range of distortion across sections:**

* **Cleanest: S22**, THD −31.4 dB with no harmonic above the background, then S16 (−25.7) and S18
  (−24.1).
* **Dirtiest and even-dominant: S12**, h2 **−2.1 dB** (nearly as loud as the fundamental),
  odd−even −18.4, THD −3.5 — an octave-doubled sub. S06 is also even-leaning (h2 −21, odd−even −14).
* **Dirtiest and odd-dominant: S25**, h3 **−11.6 dB**, h5 −17.8, odd−even **+15.8**, THD −10.4 —
  clipped/saturated. S07 (h3 −17) and S05 (h3 −20) sit in the same family.
* **Typical record:** h2 below the background, h3 around −20 to −27 dB, odd-leaning — a lightly
  saturated sine.

### 10.3 Bar-level timbre change points

A bar's evidence is the notes that *start* in it (608 notes ≥ 210 ms; 67% of bass bars have one),
standardised by the note-to-note noise and winsorised at ±2.5σ. Optimal segmentation uses a
weighted mean-shift cost and a BIC penalty, minimum 2 bars.

| penalty | change points | segment median | p25 | p75 | p90 |
|---|---|---|---|---|---|
| 0.5 × BIC | 93 | 6 bars | 2 | 12 | 19 |
| **1.0 × BIC** | **36** | **17 bars** | **13** | **38** | **48** |
| 2.0 × BIC | 14 | 52 bars | 35 | 72 | 105 |

At 1.0 × BIC, share of bars by timbre-segment length: 2–7 bars 2%, 8–15 bars 13%, 16–31 bars 21%,
**32–63 bars 55%**, 64+ bars 8%.

* **44%** of timbre change points fall within 4 bars of a section boundary (chance 25%), and **58%**
  of section boundaries have a timbre change within 4 bars.
* **20 of 36 change points fall inside sections** (> 4 bars from a boundary).

**Verdict:** the user's claim is **mostly right at record scale**. The tone is a per-record choice,
held for **16–40 bars at a time** (median segment 17 bars, 55% of bars in 32–63-bar segments). It
is not frozen for a whole record, though: about half the changes happen inside one. Those changes
sit on the 16-bar grid more than chance allows (§12).

---

## 11. Riff repetition

Claim tested: *the bassline notes are repeated for 8–16 bars.* (`reaper_bass.py riff`, `bars`)

**Sequence.** Every bar of `grid.npz` is cut into 16 slots; each slot gets the rounded MIDI note of
the voiced F0 frames inside it (≥ 50% voiced), else rest. 756 of 870 bars (87%) have ≥ 3 pitched
16ths; 59% of all 16ths are pitched.

**Agreement.** Share of slots, among those pitched in either bar, where both bars agree within
±1 st, with rest = rest. The ±1 st tolerance absorbs the ping and glide smear across 16th edges.
Between bars of *different* sections, agreement is mean **11%**, p90 38%, p99 80% (held roots in a
shared key match easily). The threshold for "the same riff" is **50%**.

### 11.1 Riff period per section (mean agreement between bar b and b + L)

| sec | L1 | L2 | L4 | L8 | period | notes / riff | runs | median run | max run |
|---|---|---|---|---|---|---|---|---|---|
| S02 | 29 | 62 | 61 | 54 | **2** | 5 | 2 | 5 | 7 |
| S03 | 27 | 57 | 42 | 17 | **2** | 6 | 5 | 6 | 8 |
| S04 | 4 | 20 | 44 | 36 | none (4) | 12 | 5 | 6 | 8 |
| S05 | 18 | 44 | 63 | **82** | **8** | 20 | 2 | 22 | 32 |
| S06 | 13 | 50 | 45 | 19 | **2** | 5 | 3 | 9 | 15 |
| S07 | 43 | 11 | 64 | **94** | **8** | 16 | 3 | 11 | 14 |
| S08 | 2 | 45 | 45 | 41 | none (2) | 6 | 6 | 10 | 15 |
| S09 | 1 | 29 | 41 | 26 | none (4) | 10 | 2 | 8 | 10 |
| S10 | 39 | 33 | 51 | 51 | **4** | 8.5 | 3 | 5 | 11 |
| S11 | 41 | 48 | **73** | 67 | **4** | 11 | 1 | 40 | 40 |
| S12 | 16 | 23 | 7 | 62 | **8** | 15.5 | 5 | 13 | 23 |
| S13 | 17 | 21 | 26 | 66 | **8** | 14 | 5 | 12 | 46 |
| S14 | 6 | 35 | 60 | **86** | **8** | 16 | 0 † | — | — |
| S15 | 1 | 35 | **72** | 71 | **4** | 9 | 4 | 14 | 19 |
| S16 | 9 | 61 | **77** | 72 | **4** | 7 | 5 | 6 | 30 |
| S17 | 6 | 49 | **79** | 79 | **4** | 8 | 1 | 28 | 28 |
| S18 | 14 | 37 | 39 | 26 | none (2) | 8 | 2 | 10 | 11 |
| S19 | 10 | 16 | 27 | 48 | none (8) | 20 | 4 | 12 | 28 |
| S20 | 20 | 27 | **76** | 76 | **4** | 10 | 1 | 12 | 12 |
| S21 | **82** | 81 | 70 | 62 | **1** | 1 (held root) | 2 | 20 | 31 |
| S22 | 34 | 62 | 69 | **81** | **8** | 11 | 0 † | — | — |
| S23 | 39 | 69 | 77 | **91** | **8** | 9 | 3 | 15 | 21 |
| S24 | 36 | 21 | 27 | 37 | none (1) | 3 | 1 | 15 | 15 |
| S25 | 23 | 59 | 63 | 65 | **2** | 6 | 2 | 16 | 17 |

*Period = the smallest of 1/2/4/8 bars within 8 points of the best lag, if that lag reaches 50%.
Runs are attributed to the section they start in. † No run starts in S14 or S22. S13's 46-bar run
is longer than S13 itself (33 bars), so it carries on into S14. S01 is near-silent.*

**Periods:** 8 bars × 7 sections, 4 bars × 6, 2 bars × 4, 1 bar × 1, **no stable riff in 7**.
Notes per riff: **9–20** for 8-bar riffs, **7–11** for 4-bar, **5–6** for 2-bar. The odd lag L3
(not shown) always scores about the same as L1 and never like L4 — the repetition is locked to
2/4/8-bar units.

### 11.2 How long a riff runs before it changes

A run is a stretch where every bar agrees ≥ 50% with the bar one period back, tolerating one odd bar.

* **68 runs**, run length **p10 5, p25 7, median 11, p75 15, p90 25, max 46 bars**.

  | run length | 2–3 bars | 4–7 | **8–15** | 16–31 | 32+ |
  |---|---|---|---|---|---|
  | % of runs | 3% | 26% | **54%** | 12% | 4% |
  | % of riff bars | 1% | 12% | **50%** | 23% | 14% |

* 91% of bass bars are inside a run. **80%** of bass bars are in runs of ≥ 8 bars, 45% in runs of
  8–16 bars, and only 12% in runs shorter than 8.
* The threshold barely matters: at 40% the median run is 11 bars (p90 26); at 60% it is 10 (p90 21).

**The user's "8–16 bars" is right:** median 11 bars, interquartile 7–15.

**What follows the end of a run** (67 changes):

| next | share | across a section boundary | after an absence |
|---|---|---|---|
| **new riff** | **39%** | 12% | 23% |
| **the same riff again**, after a fill or dropout | **36%** | 0% | 54% |
| partial variation (30–50% agreement) | 21% | 7% | 36% |
| transposition (−5 st, +6 st) | 3% | 0% | 50% |
| same notes, new rhythm | 1% | 0% | 0% |
| same rhythm, new notes | 0% | — | — |

About a third of "changes" are only interruptions: the riff stops for a bar or a fill and comes
straight back. Real changes are mostly **new riffs** or **partial rewrites**. Transposing a riff
is rare (2 of 67).

---

## 12. Bar-level state, phrase grid, and `bass_bars.npz`

Every layer as a state per bar, so it can be lined up against the kick and 16th-carrier data
(`reaper_bass.py bars`).

### 12.1 Sub-section lengths

**Riff segments** are contiguous bars with the same `riff_id`. Riff ids match across rotations
and 1/2/4/8-bar tilings; bars without bass get id −1; minimum segment 2 bars, so one-bar dropouts
are absorbed. That gives 65 segments and 74 riff ids, of which 8 recur in more than one segment.

| | p10 | p25 | median | p75 | p90 | max |
|---|---|---|---|---|---|---|
| riff segment, bars | 4 | 6 | **10** | 20 | 32 | 62 |
| timbre segment, bars (1 × BIC) | — | 13 | **17** | 38 | 48 | — |

Share of bass bars by riff-segment length: 2–3 bars 1%, 4–7 bars 8%, 8–15 bars 25%, 16–31 bars 29%,
32+ bars 36%. Only 39% of riff change points fall within 4 bars of a section boundary: riffs change
*inside* records, timbre mostly at their edges (§10.3).

### 12.2 Do change points land on the phrase grid?

Share of change points on a 4/8/16/32-bar grid, against a Monte-Carlo null with the same number of
change points per section and ≥ 2-bar spacing (1000 draws). Two columns fit one grid phase for
the whole file, exactly or within ±1 bar. The segment-length column asks how often a segment is a
whole multiple of M bars.

| layer | grid | on grid, one phase for the file (null, p) | within ±1 bar (null, p) | segment length a multiple (null, p) |
|---|---|---|---|---|
| riff | 4 | 39.1% (31.6%, 0.03) | 82.8% (81.2%, 0.36) | 30.2% (23.7%, 0.15) |
| riff | **8** | **32.8%** (18.9%, **<0.001**) | **65.6%** (45.4%, **<0.001**) | **20.6%** (9.6%, 0.01) |
| riff | **16** | **25.0%** (12.1%, **<0.001**) | **53.1%** (26.6%, **<0.001**) | **9.5%** (3.0%, 0.006) |
| riff | **32** | **15.6%** (8.2%, **<0.001**) | **32.8%** (16.4%, **<0.001**) | 4.8% (0.5%, 0.003) |
| timbre | 4 | 33.3% (33.7%, 0.62) | 80.6% (83.3%, 0.89) | 20.0% (24.1%, 0.78) |
| timbre | 8 | 22.2% (21.3%, 0.50) | 58.3% (48.6%, 0.06) | 17.1% (11.0%, 0.18) |
| timbre | **16** | 19.4% (14.4%, 0.10) | **47.2%** (29.9%, **0.001**) | 11.4% (4.6%, 0.07) |
| timbre | 32 | 11.1% (10.2%, 0.55) | **27.8%** (19.4%, 0.02) | 2.9% (1.7%, 0.47) |

Letting each section choose its own best phase helps little once that freedom is priced into the
null: riff 8-bar 51.6% vs 43.8% (p 0.02), 16-bar 42.2% vs 37.0% (p 0.03), timbre never. The file
is mixed phrase-aligned, so one global phase is the right frame.

* **Riff changes are phrase-aligned.** On a single global grid they hit the 8-bar line **1.7×**
  chance and the 16- and 32-bar lines about **2×** chance. Within ±1 bar, **53%** of riff changes
  are on a 16-bar line (chance 27%).
* **Timbre changes align only loosely,** to 16 and 32 bars within ±1 bar (47% vs 30%). The timbre
  change points are also less precise: a bar has a reading only when a long enough note starts
  in it.
* Neither layer is locked to the grid. Roughly half of all changes land off the 16-bar lines.

### 12.3 `C:\Users\eric\Downloads\reaper_cache\bass_bars.npz`

One row per bar of `grid.npz` (870 bars). Numbers derived from the analysis only — no audio.

| array | shape, dtype | meaning |
|---|---|---|
| `bar_start_s`, `bar_end_s` | (870,) float64 | bar edges in seconds, from `grid.npz` beats / downbeats |
| `section` | (870,) int16 | novelty section index, 0-based (S01 = 0) |
| `bass_present` | (870,) bool | ≥ 3 of the bar's 16ths carry a voiced bass pitch |
| `root_pc` | (870,) int8 | pitch class (0 = C … 11 = B) of the most-sounded bass note; −1 = no bass |
| `seq16` | (870, 16) int8 | per-16th rounded MIDI note of the bass, −1 = rest |
| `riff_id` | (870,) int16 | same id when the same riff comes back (±1 st, ≥ 50% agreement, any rotation / 1-2-4-8-bar tiling); −1 = no bass |
| `riff_period_bars` | (870,) int8 | the section's riff period (1/2/4/8; best lag where none passed) |
| `riff_segment_id` | (870,) int16 | contiguous riff state, minimum 2 bars (dropouts ≤ 1 bar absorbed) |
| `timbre` | (870, 6) float32 | pitch-adjusted median over notes overlapping the bar: `timbre_cols` = h2, h3, h4, h5 (dB re own fundamental, background-subtracted, clamped −45), odd−even (dB), THD (dB); NaN = no note ≥ 210 ms |
| `timbre_cols` | (6,) str | column names for `timbre` |
| `timbre_segment_id` | (870,) int16 | weighted-BIC timbre segment, minimum 2 bars (37 segments) |
| `has_bell_attack` | (870,) float32 | share of the bar's measured note onsets that start ≥ +3 st sharp (the §9 ping); NaN = no measured onset (452 bars have one) |
| `n_onsets_measured` | (870,) int8 | how many onsets that share is over |

---

# What this means for building a jungle track

Numbers to build against. Where the reference contradicts the current plan I say so.

1. **Drop the held drone.** Nothing in 871 bars is held longer than **5.58 beats (1.4 bars)**,
   and only 0.7% of notes exceed one bar. Cap sub note length at **4 beats**, and make the
   *modal* note **0.25–0.5 beats** (30.5% of notes) with the time-weight centre at **1–1.5 beats**.
   Target median **0.60 beats**.

2. **Let the bass change 0.9 times per bar — about 7 changes per 8 bars.** Stay inside
   **0.25–1.7 changes/bar (2–14 per 8 bars)** section to section. A section under 0.25/bar reads
   as a dead pad; over 1.7/bar it stops being a bass part.

3. **Trade density against depth, never stack them.** In the reference, sections at 1.6–1.7
   changes/bar keep only 34–85% of the low end below 60 Hz, while the 0.25–0.42/bar sections push
   it to **73–96%**. Pick one per section: busy mid-weighted bass, or sparse deep sub.

4. **Add portamento — 2.5 glide runs per bar.** Median glide **96 ms (0.27 beats)**, span
   **0.76 st** (p90 3.17 st), rate **~6.7 st/s**, 59% falling. Put a glide on **~40% of note
   transitions**, preferentially the small ones: glided moves are median 1.05 st, jumped moves
   median 2.05 st with 43% ≥ 3 st. Nearly half the glide runs (48%) are really the note-start
   pitch drop of rule 12, which the 160 ms tracker smeared; the between-note portamento is the
   rest.

5. **Interval budget: 35% repeats, 28% steps, 7% fifths.** Repeat the same pitch **34.6%** of the
   time, move by 1–2 st **28.5%**, by a fifth (7 st) **7.4%**, by a fourth (5 st) 6.0%, by an
   octave only **1.8%**. Keep up and down balanced (30.7% down / 34.7% up). Space changes about
   **one beat apart** (median gap 360 ms).

6. **Do not sidechain the sub to the kick.** Measured duck across the whole set is
   **−0.5 dB at 0–30 ms, −0.3 dB at 30–80 ms, −0.4 dB at 80–200 ms**; the properly-anchored
   in-note measurement shows the sub *rising* **+2.3 dB** at the kick, with a worst-case
   excursion of −3.2 dB inside an 8.2 dB natural ripple. Zero of 14 measurable sections duck
   more than 4 dB. If you keep a duck at all, keep it **≤ 2 dB and under 60 ms** — anything
   deeper is a different genre.

7. **Separate by register instead.** Give the kick its body at **60–250 Hz** (the reference kick
   puts **42.5%** of its energy there vs the bass's **16.5%**) and give the bass **73–74% of its
   energy below 60 Hz**. High-pass the kick's own sub or shelve it so the two are not fighting
   for 30–60 Hz. That, not a compressor, is what buys the coexistence.

8. **Put 65% of the mix's 0–2.4 kHz power below 60 Hz, peaking at 40–50 Hz.** Within the
   0–250 Hz low end aim for **72% / 15% / 13%** across <60 / 60–120 / 120–250 Hz. High-pass
   everything below ~25 Hz: the reference has only **0.34%** of its energy under 20 Hz.

9. **Make the sub a sine with a chosen amount of saturation, not a reese — and if you want a
   reese, make it a separate lane.** On average the reference sub beats its own 2nd harmonic by
   **16.6 dB** and has no harmonic comb above the 5th. How much grit it gets is a per-record
   decision (§10): the typical record is odd-leaning, with h3 at −20 to −27 dB; the extremes are
   a clean sine (THD −31 dB), a clipped one (h3 −12 dB, odd/even +16 dB) and an octave-doubled
   one (h2 −2 dB). A reese an octave up is fine as an *additional* voice, but not in the sub's
   lane.

10. **Let the bass drop out, often and briefly.** Bass audible in **76.7% of bars**; median
    unbroken ON stretch **3 bars**, median OFF stretch **1 bar** (p90 4 bars). Punctuate with
    one-bar holes rather than playing continuously, and reserve long absences (up to 34 bars)
    for structural breakdowns.

11. **Pick one key and mostly keep it.** Put ~85% of bass sounding time inside a single 7-note
    collection (the reference: D# minor / F# major, 84.6%), with the root taking ~33% of the
    weight and the ♭3/♭6 next. If you want a section to leave, leave for a whole section
    (5 of 25 here fit the home key at only 19–48%) rather than drifting bar to bar.

12. **Give the sub a pitch-drop attack: that is the "bell".** Start each note **+30 st** above
    its pitch (a 47 Hz note starts at ~284 Hz) and fall exponentially with **τ ≈ 12 ms**: +14 st
    at 10 ms, +3 st at 30 ms, +1.5 st at 45 ms. Leave a **+1 st tail that settles over ~150–200 ms**.
    Use a hard ~1 ms amplitude attack and no click layer, noise or inharmonic ratio. The attack
    alone puts 120–500 Hz energy **4–5 dB below the sustained fundamental in the first 5 ms**,
    which is what small speakers hear. It is gone in 30–40 ms. Of all the components tried, this
    one does the work (82% of the fit on its own).

13. **Decide the attack per record, not per note.** In the pinging records, **75–94%** of notes
    start ≥ +3 st sharp; in others **0–12%** do. Pair it or trade it against grit: the most
    saturated sub in the set (S25) never pings. Within a record, keep the choice on almost every
    note.

14. **Hold the sub's tone for 16–40 bars, and change it at record-scale joins.** Timbre segments
    have a median of **17 bars** (p25 13, p75 38), with 55% of bars in 32–63-bar segments. 44% of
    tone changes sit within 4 bars of a record boundary (chance 25%). The ones inside a record
    favour 16- and 32-bar lines (47% within ±1 bar of a 16-bar line, chance 30%). Don't morph the
    sub's distortion bar to bar.

15. **Write 4- or 8-bar riffs and let them run ~8–16 bars.** Periods are 8 bars (7 sections),
    4 bars (6) or 2 bars (4), with **9–20 notes** in an 8-bar riff, **7–11** in a 4-bar and **5–6**
    in a 2-bar. Unbroken runs have a median of **11 bars** (IQR 7–15), and 80% of bass bars sit in
    runs of ≥ 8 bars. **Put riff changes on the phrase grid:** on one global phase 33% land on an
    8-bar line and 25% on a 16-bar line, 1.7–2× chance; within ±1 bar, 53% are on a 16-bar line.
    When a run ends, bring back the *same* riff after a one-bar fill or dropout about a third of
    the time (36%). Otherwise write a new riff (39%) or a partial rewrite (21%). Transpose rarely
    (3%).
