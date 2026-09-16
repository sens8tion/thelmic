# The Reaper reference, measured — and what it says about our track

Seven analyses of `Tim_Reaper_Jungle_DJ_Set_SECTION_August_2026.wav` (1259.7 s, 48 kHz stereo),
run 2026-09-16. **Structural analysis only: nothing was sampled, extracted or copied from the file.**
Everything below is a number about arrangement, rhythm or balance.

| report | question | code |
|---|---|---|
| [grid.md](grid.md) | tempo, beat phase, downbeats, mix points | `scripts/reaper_grid.py` |
| [structure.md](structure.md) | sections, records, seams, phrase lengths | `scripts/reaper_structure.py` |
| [drops.md](drops.md) | every drop and breakdown, before vs after | `scripts/reaper_drops.py` |
| [rhythm.md](rhythm.md) | inside the bar, and bar to bar | `scripts/reaper_rhythm.py` |
| [bass.md](bass.md) | what the low end actually does | `scripts/reaper_bass.py` |
| [hooks.md](hooks.md) | melodic material: how often, how long, how high | `scripts/reaper_hooks.py` |
| [mix-space.md](mix-space.md) | spectral balance, stereo, tails, density | `scripts/reaper_mix.py` |

Shared feature cache: `scripts/reaper_features.py` → `<Downloads>/reaper_cache/` (frames at 93.75 fps,
per-bar aggregates, 8 kHz mono). Only numpy and torch were available, so every estimator —  RIFF
reader, STFT, onset detection, tempo, F0, HPSS — was written for this.

## How much to trust it

Four agents derived the tempo independently and agree to 0.03 BPM: **165.96 / 165.97 / 165.99 /
166.00**. That is the strongest result in the set, and it means the whole 21 minutes is played to one
master clock, not beatmatched by ear (which would show ±0.5 BPM steps).

The first cached grid was **wrong** — 165.83 BPM drifts 3.7 beats by the end, and its "confidence 1.0"
was an autocorrelation lag-lattice artifact. Two agents caught it independently and rebuilt their own.
The rhythm agent went further and rejected the shared `grid.npz` too, because its beats are snapped to
the 10.67 ms frame hop, which is coarser than the microtiming it was measuring. Its tracked grid puts
76.6% of onsets within 10 ms where a rigid grid manages 35.1%.

Where a result was inconclusive it is reported as inconclusive: the chop-detection test failed its own
selection-bias control and is not counted as evidence.

## What the reference does

**Tempo and shape.** 166 BPM throughout. 871 bars, 38 sections, 9 records. Track blocks of
130/46/130/72/40/192/133/64/64 bars, five of them exact multiples of 8. Phrasing is strictly 4-bar
(100% of sections within 2 bars of a multiple of 4) and loosely 8-bar (84%). Seams are either **hard
cuts of 1–5 bars** (5 of them, prepared by 1–7 bars of bass removal) or **real blends of 8–32 bars**
(3 of them, 12–46 s). Nothing in between: there are no 8-second transitions. The median section is 9%
literal recall and 20% new material — newness is spent at the seam, then the loop returns 40–84%
verbatim. No record ever comes back.

**Drops are subtraction, not addition.** 22 drops and 22 breakdowns. **82% of drops are set up by
subtraction alone**: the break keeps running at full onset density while the low end is pulled a median
**19 dB** down. Rolls appear in 27%, filter sweeps 23%, stabs 18%. **Zero risers in 22 drops.** The
median drop is approached by *falling* level.

The drop itself is a **re-weighting, not a lift**: sub +10 dB, bass +5 dB, but mid −0.9 dB, high
−1.1 dB, centroid −394 Hz, and RMS up only **2.6 dB**. Width narrows and crest falls. There is no
layered build-in — bar 2 is within 0.5 dB of bar 1 and onset counts are flat; only the sub stages in,
at +2.1 dB. Gaps before a drop are rare (27%) and tiny: median **80 ms, one 16th**. The set is "full"
86% of its runtime.

**Breakdowns get brighter and busier**, not quieter: −1.3 dB RMS, but centroid +277 Hz and onset
density up in 64% of them.

**Inside the bar.** Occupancy: beat slots 0.83–0.87, other even 16ths 0.67, odd 16ths 0.34. Kick owns
slot 0 (0.91) and slot 10 (0.66); snare slots 4 (0.94) and 12 (0.89). Timing is **straight** — 51.5%
raw swing, 52.4% after correcting a level-dependent detection bias — with 7.5 ms spread on 8ths against
13.5 ms on odd 16ths: quantised placement, human content. **Nothing is looped**: even the most
pattern-identical bars differ by 4.6 ms of microtiming, where a loop would give 0–1 ms.

**Bar to bar: A-B-C-D, not three-then-disturb.** Lag-4 similarity is 0.486 while **lag-1 is 0.355, the
lowest in the profile and level with the random baseline**. Consecutive bars are the *least* alike;
bar N resembles bar N+4. The explicit test of "three bars repeat, the fourth disturbs" gives a 4-bar
position spread of 0.042 at p = 0.20 — not supported.

**The low end.** No sidechain: the duck under the kick measures −0.5 dB, and anchored against a
kick-free baseline the sub *rises* +2.3 dB at the kick. Zero of 14 measurable sections duck past 4 dB.
Kick and bass separate by **register** — the kick puts 42.5% of its energy in 60–250 Hz against the
bass's 16.5%, and the bass owns below 60 Hz (73.8% vs 50.8%). It is a **clean sub, not a reese**:
fundamental 16.6 dB above the second harmonic, 65.6% of its power below 60 Hz, peaking 40–50 Hz.

It **moves**: nothing held longer than 1.4 bars, only 0.7% of notes over a bar, median note 0.60 beats,
**0.90 changes per bar**. 41% of transitions are portamento — 2.5 glide runs per bar, median 96 ms over
0.76 semitones, 59% falling. Intervals: 34.6% repeats, 28.5% 1–2 semitones, 7.4% fifths, 1.8% octaves.
Bass is present in 76.7% of bars, median run 3 bars on and 1 bar off. Key: 84.6% of bass time inside
E♭ minor.

**Hooks are frequent but short.** 287 events, 12% of runtime; **39% of bars carry one — 3.1 bars in
every 8**. Median event **1.2 beats** (81% under 2 beats), median gap 1.5 bars. Only 50 of 128 shapes
recur, typically three times at 4–8 bar spacing. Fundamentals **233–392 Hz**, harmonics to ~1.6 kHz.
The separation from the bass is a **10 dB valley at 233 Hz** — bass stops at 174 Hz, hooks start at
233. Hook placement is uncorrelated with sub level (r ≈ 0): the mix thins the low-end *pattern*
(flux −2.1 dB), it does not duck the bass. "Light against dark" is register and tonality, not treble —
the hook centre sits 3.1 octaves above the low band while the full-mix centroid gets *darker*.

**Space.** Nothing below 150 Hz is in the sides (side is 33 dB under mid there). The image opens at
250–500 Hz, and 53% of all side energy sits between 400 Hz and 2 kHz; in drops the highs actually
narrow. The movement is **event-driven, not cyclic** — bar-locked autocorrelation is only 0.13–0.21,
so there is no auto-panner; mid width swings 0.03→0.26 with its strongest periodicity at 8–12 s.
Delays are **short**: 1/8 triplet ~120 ms (primary), 1/8 ~181 ms, and a 45 ms slapback. **Nothing at
1/4 or longer.** Tails are not long but *constant*: 2–8 kHz sits above −20 dB of its peak 96% of the
time, T20 median 299 ms. Limited to 0.0 dBFS, loudness range inside a drop only 1.8 dB, but
breakdown-to-drop RMS steps 6.4 dB; 50 ms crest 7.5 dB median, so transients survive.

**Density.** A drop bar has **fewer** events than a groove bar — 21 band-onsets against 32 — using 11
of 16 sixteenths, 1.8 bands per sixteenth. Drop spectral flatness 0.010 versus 0.027 in a breakdown.
The drop is a spike at the bottom, not a wall.

## Where our track disagrees

Ours is 170 BPM in F minor; the reference is 166 in E♭ minor. That difference is deliberate and not
a fault. These are:

**1. Bar-to-bar repetition (biggest).** Our composer repeats a 2-bar unit verbatim three times and
disturbs the fourth. The reference makes consecutive bars the least similar thing in the track and
carries identity at 4 bars. This contradicts the stated listening theory, so it is a question of taste
rather than a defect — but the measurement is unambiguous.

**2. Drops add; the reference re-weights.** Our builds use accelerating snare rolls and a climbing
bell, then the drop brings lanes back in. The reference: no risers, no layering, the break never stops,
and the event is +10 dB of sub against a *falling* centroid. Our 1.5-beat gap before a drop is ~10×
the reference's median 80 ms.

**3. The bass.** We hold notes and duck them 8 dB off a kick-keyed compressor, with a reese doubling an
octave up. The reference has no duck at all, separates by register, keeps a clean sub with 65% of its
power under 60 Hz, and moves it ~0.9 times a bar with glides. Note the user's own instinct — "it should
drone; change perhaps every other bar" — points the opposite way from the reference too.

**4. Hook register.** Our bell sits at 800–2000 Hz and the lead at 520–1100. The reference's hooks live
at 233–392 Hz with a deliberate 10 dB notch at 233 Hz doing the separating. We are an octave or more
too high, which is likely why the highs read as "saccharine".

**5. Sustained versus punctuated.** Our pad holds whole rows. The reference has no sustained voice in
that register at all: 81% of its melodic events are under two beats. The stabs lane is the right
instinct; the pad may be the wrong one.

**6. Delay times.** Ours: dotted 8th (~529 ms) on the bell, dotted quarter on the lead. The reference
uses nothing at or above a 1/4 — 120 ms, 181 ms and a 45 ms slapback.

**7. Stereo mechanism.** Ours: synced 2-bar and 1.5-bar auto-pans. The reference: no cyclic panning at
all, movement arrives with events, and the highs *narrow* in drops.

**8. Breakdowns.** Ours drops to 0.62 on the master and thins out. The reference's breakdowns are
brighter and busier than the drops around them, only 1.3 dB quieter.

## If we act on it

Cheap and low-risk, in order:

1. Shorten the delays — bell to 1/8 triplet, lead to 1/8, and add a 45 ms slapback to the stabs.
2. Drop the hooks an octave: move the bell's motifs and the lead's themes into 233–392 Hz, and cut a
   narrow ~10 dB notch at 233 Hz on the bass lanes rather than shelving everything.
3. Swap the auto-pans for event-driven width (short stereo delays and the throws), keeping the highs
   narrow in drops.
4. Make the builds subtract instead of rise: keep the break running, pull the low end 19 dB, and cut
   the gap from 1.5 beats to one 16th.
5. Turn the pad into punctuation (1–2 beat chord hits) or drop it from the drops entirely.
6. Try one drop row with A-B-C-D bars instead of three-plus-disturb, and compare by ear.

Not recommended without the user's say-so: removing the bass sidechain, which was an explicit
instruction and is the one place where their taste and the reference clearly part company.
