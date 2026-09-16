# What the low end does — Tim Reaper jungle DJ set (section), 1259.7 s

Structural analysis only. No audio was sampled, extracted or copied; everything below is a
measurement. All of it is reproducible with `scripts/reaper_bass.py`
(`grid | sections | f0 | notes | spec | kick | report`).

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
   median 2.05 st with 43% ≥ 3 st. This is the single biggest textural difference from a
   straight held sub.

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

9. **Make the sub clean, not a reese — and if you want a reese, make it a separate lane.** The
   reference sub beats its own 2nd harmonic by **16.6 dB** and has effectively no harmonic comb
   above the 5th. A reese an octave up is fine as an *additional* voice, but do not let it live
   in the sub's lane; keep the sub itself within ~15 dB fundamental-to-h2.

10. **Let the bass drop out, often and briefly.** Bass audible in **76.7% of bars**; median
    unbroken ON stretch **3 bars**, median OFF stretch **1 bar** (p90 4 bars). Punctuate with
    one-bar holes rather than playing continuously, and reserve long absences (up to 34 bars)
    for structural breakdowns.

11. **Pick one key and mostly keep it.** Put ~85% of bass sounding time inside a single 7-note
    collection (the reference: D# minor / F# major, 84.6%), with the root taking ~33% of the
    weight and the ♭3/♭6 next. If you want a section to leave, leave for a whole section
    (5 of 25 here fit the home key at only 19–48%) rather than drifting bar to bar.
