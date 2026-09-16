# Tim Reaper jungle set - why it reads as spacious and legible

Source `Tim_Reaper_Jungle_DJ_Set_SECTION_August_2026.wav` - 1259.7 s, 48 kHz stereo. **Structural analysis only**: no audio, loop or riff was extracted or reused; every line below is a measurement.

Measured by `scripts/reaper_mix.py` (numpy + torch only). Tempo is stable across the whole section at **165.7-166.4 BPM**, so one grid holds throughout: beat 361.8 ms, bar 1447 ms, 16th 90.4 ms. Sections were cut by what the drums and the low end are doing, not by loudness alone, then the longest five of each kind were measured at full rate in stereo (60 s cap each).

Bands: sub 20-60, bass 60-120, lowmid 120-400, mid 400-2k, high 2k-8k, air 8k-16k Hz.

## Sections measured

| id | kind | start s | end s | dur s | RMS dBFS | BPM |
| --- | --- | --- | --- | --- | --- | --- |
| S00 | breakdown | 0.0 | 50.1 | 50.1 | -14.29 | 165.85 |
| S02 | groove | 73.1 | 105.6 | 32.6 | -10.99 | 165.83 |
| S04 | groove | 115.3 | 152.1 | 36.8 | -11.78 | 165.84 |
| S05 | breakdown | 152.2 | 165.2 | 13.0 | -15.30 | 165.86 |
| S07 | drop | 188.6 | 248.6 | 60.0 | -10.09 | 165.92 |
| S10 | drop | 280.9 | 304.0 | 23.0 | -8.52 | 165.84 |
| S13 | groove | 324.0 | 384.0 | 60.0 | -11.65 | 165.89 |
| S15 | drop | 443.0 | 503.0 | 60.0 | -8.08 | 165.78 |
| S21 | groove | 558.2 | 618.2 | 60.0 | -11.42 | 165.82 |
| S25 | breakdown | 920.2 | 936.2 | 16.0 | -15.47 | 165.90 |
| S30 | drop | 1008.3 | 1063.2 | 54.9 | -10.29 | 165.57 |
| S31 | breakdown | 1063.3 | 1075.8 | 12.6 | -16.93 | 165.80 |
| S32 | drop | 1075.9 | 1101.0 | 25.2 | -10.03 | 165.90 |
| S33 | groove | 1101.0 | 1145.4 | 44.4 | -11.47 | 165.81 |
| S36 | breakdown | 1167.6 | 1190.4 | 22.8 | -17.13 | 165.86 |

`S00` and `S36` are DJ mix-in regions with two records running; they behave like breakdowns harmonically but carry two sets of drums, so they inflate the breakdown onset counts. `S25`, `S31` are the cleanest true breakdowns.

## 1. Spectral balance per section

Energy in each band in dB relative to that section's own total (so the rows are level-independent and sum to the whole mix). `tilt` is a least-squares fit through the six band centres, in dB per octave.

| id | kind | sub | bass | lowmid | mid | high | air | tilt dB/oct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S00 | breakdown | -11.2 | -7.7 | -7.0 | -7.1 | -6.0 | -9.7 | 0.18 |
| S02 | groove | -6.2 | -7.6 | -7.7 | -8.7 | -6.8 | -11.4 | -0.39 |
| S04 | groove | -5.8 | -7.3 | -7.5 | -9.1 | -7.6 | -11.2 | -0.47 |
| S05 | breakdown | -7.3 | -4.5 | -8.3 | -9.0 | -8.4 | -13.8 | -0.74 |
| S07 | drop | -2.3 | -6.1 | -11.3 | -13.9 | -13.6 | -19.3 | -1.76 |
| S10 | drop | -2.3 | -7.8 | -10.7 | -11.9 | -11.1 | -17.7 | -1.41 |
| S13 | groove | -7.9 | -5.4 | -8.9 | -7.7 | -7.0 | -13.2 | -0.49 |
| S15 | drop | -3.0 | -7.7 | -8.2 | -11.6 | -11.5 | -14.5 | -1.17 |
| S21 | groove | -5.1 | -6.2 | -7.4 | -9.8 | -9.9 | -12.5 | -0.84 |
| S25 | breakdown | -12.4 | -13.7 | -8.8 | -4.1 | -4.4 | -18.4 | 0.03 |
| S30 | drop | -2.5 | -12.1 | -9.1 | -10.0 | -8.8 | -18.0 | -1.08 |
| S31 | breakdown | -4.1 | -15.4 | -9.5 | -5.8 | -7.6 | -14.4 | -0.36 |
| S32 | drop | -0.8 | -10.2 | -16.8 | -16.4 | -17.1 | -22.4 | -2.02 |
| S33 | groove | -1.1 | -11.6 | -13.9 | -15.2 | -11.2 | -18.9 | -1.37 |
| S36 | breakdown | -24.9 | -9.7 | -5.5 | -8.8 | -3.8 | -12.5 | 1.15 |

| **mean** | kind | sub | bass | lowmid | mid | high | air | tilt dB/oct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  | **breakdown** | -12.0 | -10.2 | -7.8 | -7.0 | -6.0 | -13.8 | 0.05 |
|  | **groove** | -5.2 | -7.6 | -9.1 | -10.1 | -8.5 | -13.4 | -0.71 |
|  | **drop** | -2.2 | -8.8 | -11.2 | -12.8 | -12.4 | -18.4 | -1.49 |

**Breakdown -> drop, what actually moves:**

| band | breakdown | groove | drop | drop - breakdown |
| --- | --- | --- | --- | --- |
| sub | -12.0 | -5.2 | -2.2 | **+9.8** |
| bass | -10.2 | -7.6 | -8.8 | **+1.4** |
| lowmid | -7.8 | -9.1 | -11.2 | **-3.4** |
| mid | -7.0 | -10.1 | -12.8 | **-5.8** |
| high | -6.0 | -8.5 | -12.4 | **-6.4** |
| air | -13.8 | -13.4 | -18.4 | **-4.6** |
| tilt dB/oct | 0.05 | -0.71 | -1.49 | **-1.54** |

The drop is not brighter - it is heavier. Sub gains **+9.8 dB** of relative share while high *loses* **-6.4 dB** and air **-4.6 dB**. The breakdown is spectrally flat (tilt ~0 dB/oct, top-weighted); the drop tilts to **-1.49 dB/oct**. Every section keeps air 12-19 dB under the total - the top octave is never a large share of the energy, it is a thin, always-present layer.

## 2. Dynamics

`crest 50 ms` and `crest 3 s` are peak-to-RMS measured on non-overlapping windows of that length, median over the section (near-silent blocks gated out). `LRA` is the 95th-10th percentile spread of gated K-weighted short-term loudness.

| id | kind | peak dBFS | RMS dBFS | crest 50 ms | crest 50 ms p90 | crest 3 s | LRA 3 s | LRA 400 ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S00 | breakdown | 0.00 | -14.29 | 11.7 | 14.8 | 13.5 | 7.84 | 10.07 |
| S02 | groove | 0.00 | -10.99 | 10.3 | 12.9 | 10.9 | 1.46 | 3.29 |
| S04 | groove | 0.00 | -11.78 | 10.2 | 12.9 | 11.6 | 2.67 | 3.76 |
| S05 | breakdown | -0.22 | -15.30 | 10.6 | 13.7 | 14.3 | 2.15 | 6.63 |
| S07 | drop | 0.00 | -10.14 | 7.7 | 9.3 | 10.1 | 1.99 | 2.98 |
| S10 | drop | 0.00 | -8.52 | 7.3 | 11.2 | 7.8 | 1.33 | 3.30 |
| S13 | groove | 0.00 | -11.93 | 10.4 | 12.5 | 12.0 | 1.94 | 4.21 |
| S15 | drop | 0.00 | -8.11 | 7.3 | 11.2 | 8.1 | 1.46 | 2.97 |
| S21 | groove | 0.00 | -10.97 | 9.0 | 11.1 | 10.4 | 4.90 | 6.45 |
| S25 | breakdown | -0.00 | -15.48 | 10.9 | 13.2 | 15.9 | 5.26 | 8.68 |
| S30 | drop | 0.00 | -10.29 | 8.8 | 11.0 | 10.0 | 3.47 | 4.07 |
| S31 | breakdown | -1.63 | -16.94 | 11.0 | 12.6 | 15.3 | 2.11 | 3.86 |
| S32 | drop | 0.00 | -10.03 | 6.3 | 7.6 | 8.3 | 0.56 | 1.81 |
| S33 | groove | 0.00 | -11.47 | 8.3 | 11.5 | 11.0 | 3.21 | 4.11 |
| S36 | breakdown | -0.53 | -17.13 | 11.6 | 13.4 | 16.3 | 0.82 | 2.69 |

| **mean** | kind | peak dBFS | RMS dBFS | crest 50 ms | crest 50 ms p90 | crest 3 s | LRA 3 s | LRA 400 ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  | **breakdown** | -0.48 | -15.83 | 11.2 | 13.5 | 15.1 | 3.64 | 6.39 |
|  | **groove** | 0.00 | -11.43 | 9.6 | 12.2 | 11.2 | 2.84 | 4.36 |
|  | **drop** | 0.00 | -9.42 | 7.5 | 10.1 | 8.9 | 1.76 | 3.03 |

The master is limited - peak sits at 0.0 dBFS in every drop and groove. Inside a section almost nothing moves: the drop's short-term loudness range is **1.76 dB** over a full minute. All the macro-dynamic contrast is *between* sections: mean RMS -15.8 dBFS in a breakdown against -9.4 dBFS in a drop, a **6.4 dB** step.

The transients survive it. A drop still shows **7.45 dB** of median 50 ms crest (p90 10.07 dB) against **8.85 dB** on a 3 s window - the 50 ms figure is **84%** of the 3 s figure, meaning nearly all of the remaining crest is genuine drum attack rather than slow level movement. In the breakdowns that ratio is 74% (more of the crest is arrangement, less is transient).

## 3. Stereo

Width = side / (mid + side) energy in that band, from an independent mid/side STFT on each section slice. 0 = mono, 0.5 = uncorrelated. Computed only on frames where the band is actually playing (above its own 40th percentile).

### 3a. Width per band

| id | kind | sub | bass | lowmid | mid | high | air |
| --- | --- | --- | --- | --- | --- | --- | --- |
| S00 | breakdown | 0.0378 | 0.0662 | 0.0465 | 0.0732 | 0.0733 | 0.1147 |
| S02 | groove | 0.0002 | 0.0006 | 0.0043 | 0.0400 | 0.0380 | 0.1162 |
| S04 | groove | 0.0007 | 0.0009 | 0.0303 | 0.0667 | 0.0562 | 0.0720 |
| S05 | breakdown | 0.0089 | 0.0040 | 0.1083 | 0.1028 | 0.3064 | 0.0088 |
| S07 | drop | 0.0004 | 0.0010 | 0.0164 | 0.1426 | 0.0319 | 0.0187 |
| S10 | drop | 0.0001 | 0.0002 | 0.0004 | 0.0023 | 0.0040 | 0.0043 |
| S13 | groove | 0.0020 | 0.0013 | 0.0009 | 0.0020 | 0.0045 | 0.0249 |
| S15 | drop | 0.0001 | 0.0002 | 0.0125 | 0.0511 | 0.0192 | 0.0193 |
| S21 | groove | 0.0003 | 0.0005 | 0.0302 | 0.0741 | 0.0551 | 0.0688 |
| S25 | breakdown | 0.0058 | 0.0087 | 0.0549 | 0.1643 | 0.1803 | 0.1775 |
| S30 | drop | 0.0005 | 0.0137 | 0.1187 | 0.1806 | 0.0339 | 0.0081 |
| S31 | breakdown | 0.0080 | 0.0303 | 0.1945 | 0.2257 | 0.0751 | 0.0285 |
| S32 | drop | 0.0001 | 0.0023 | 0.0946 | 0.2538 | 0.0460 | 0.0398 |
| S33 | groove | 0.0001 | 0.0028 | 0.1205 | 0.1514 | 0.0197 | 0.0191 |
| S36 | breakdown | 0.2481 | 0.0956 | 0.1483 | 0.1687 | 0.0562 | 0.0509 |

| **mean** | kind | sub | bass | lowmid | mid | high | air |
| --- | --- | --- | --- | --- | --- | --- | --- |
|  | **breakdown** | 0.0617 | 0.0410 | 0.1105 | 0.1469 | 0.1383 | 0.0761 |
|  | **groove** | 0.0007 | 0.0012 | 0.0372 | 0.0668 | 0.0347 | 0.0602 |
|  | **drop** | 0.0002 | 0.0035 | 0.0485 | 0.1261 | 0.0270 | 0.0180 |

Same thing as side-minus-mid in dB, which is the number to dial a mix to:

| kind | sub S/M dB | bass S/M dB | lowmid S/M dB | mid S/M dB | high S/M dB | air S/M dB |
| --- | --- | --- | --- | --- | --- | --- |
| **breakdown** | -27.1 | -21.6 | -12.4 | -8.3 | -8.7 | -12.5 |
| **groove** | -35.7 | -30.7 | -20.4 | -14.9 | -15.6 | -13.2 |
| **drop** | -37.2 | -30.0 | -19.3 | -12.0 | -16.9 | -18.8 |

### 3b. Where the bass is

| id | kind | side <150 Hz vs mid <150 Hz | side <150 Hz vs whole mid |
| --- | --- | --- | --- |
| S00 | breakdown | -24.4 | -30.1 |
| S02 | groove | -35.8 | -39.4 |
| S04 | groove | -33.0 | -36.2 |
| S05 | breakdown | -27.6 | -29.9 |
| S07 | drop | -32.0 | -32.8 |
| S10 | drop | -38.5 | -39.5 |
| S13 | groove | -28.8 | -32.1 |
| S15 | drop | -37.7 | -39.3 |
| S21 | groove | -31.9 | -34.3 |
| S25 | breakdown | -24.4 | -33.7 |
| S30 | drop | -23.5 | -25.4 |
| S31 | breakdown | -23.4 | -27.1 |
| S32 | drop | -34.0 | -34.3 |
| S33 | groove | -34.0 | -34.7 |
| S36 | breakdown | -10.6 | -18.4 |

**Nothing below 150 Hz is in the sides.** Across grooves and drops the side channel below 150 Hz sits **-32.9 dB** under the mid channel in the same range - that is bleed, not width. The two apparent exceptions are the mix-in regions where two records overlap.

Octave-band width locates the crossover exactly:

| kind | 31 Hz | 63 Hz | 125 Hz | 250 Hz | 500 Hz | 1000 Hz | 2000 Hz | 4000 Hz | 8000 Hz | 16000 Hz |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **breakdown** width | 0.0828 | 0.0176 | 0.0582 | 0.0678 | 0.1453 | 0.1398 | 0.1536 | 0.1564 | 0.0664 | 0.0893 |
| S/M dB | -24.7 | -27.4 | -16.4 | -12.9 | -8.3 | -8.4 | -8.1 | -8.7 | -13.1 | -12.2 |
| **groove** width | 0.0006 | 0.0004 | 0.0045 | 0.0278 | 0.0556 | 0.0670 | 0.0473 | 0.0309 | 0.0417 | 0.0820 |
| S/M dB | -34.2 | -35.4 | -26.4 | -20.2 | -16.1 | -14.3 | -14.7 | -16.2 | -15.0 | -11.7 |
| **drop** width | 0.0003 | 0.0004 | 0.0230 | 0.0345 | 0.1142 | 0.1147 | 0.0869 | 0.0208 | 0.0104 | 0.0407 |
| S/M dB | -36.4 | -36.1 | -25.1 | -19.1 | -12.9 | -12.3 | -12.9 | -17.4 | -20.5 | -17.1 |

The image opens between **250 and 500 Hz** and is widest from **500 Hz to 2 kHz**. Above 4 kHz it narrows again in the drops (S/M -17 to -20 dB) - the top is centred and the width is carried by the midrange, which is the opposite of the usual 'widen the hats' instinct.

### 3c. Where the side energy lives

| kind | sub % | bass % | lowmid % | mid % | high % | air % |
| --- | --- | --- | --- | --- | --- | --- |
| **breakdown** | 0.3 | 1.6 | 14.9 | 34.7 | 40.1 | 8.4 |
| **groove** | 1.4 | 2.8 | 14.8 | 26.7 | 30.3 | 24.0 |
| **drop** | 2.8 | 2.3 | 16.3 | 52.7 | 21.1 | 4.7 |

### 3d. How much the image moves

`sd` and `cv` are the standard deviation and coefficient of variation of the width series within the section; `slew` is the mean absolute change in width per second; `ac 1 bar` is the autocorrelation of the width series at one bar (is the movement arranged to the grid?).

**breakdown**

| band | width p10 | mean | p90 | sd | cv | slew /s | ac 1 bar | ac 2 bar |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| sub | 0.0058 | 0.0617 | 0.1505 | 0.0815 | 2.50 | 1.154 | 0.047 | 0.048 |
| bass | 0.0023 | 0.0410 | 0.1035 | 0.0699 | 3.66 | 0.929 | 0.020 | 0.055 |
| lowmid | 0.0165 | 0.1105 | 0.2545 | 0.1078 | 1.13 | 1.154 | -0.005 | 0.018 |
| mid | 0.0379 | 0.1469 | 0.2828 | 0.1068 | 0.79 | 0.965 | 0.080 | -0.113 |
| high | 0.0158 | 0.1383 | 0.3187 | 0.1368 | 1.05 | 0.857 | 0.087 | -0.103 |
| air | 0.0209 | 0.0761 | 0.2047 | 0.0781 | 1.28 | 0.620 | -0.032 | -0.069 |

**groove**

| band | width p10 | mean | p90 | sd | cv | slew /s | ac 1 bar | ac 2 bar |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| sub | 0.0000 | 0.0007 | 0.0019 | 0.0021 | 3.49 | 0.146 | 0.017 | 0.020 |
| bass | 0.0000 | 0.0012 | 0.0027 | 0.0057 | 6.00 | 0.083 | 0.009 | 0.058 |
| lowmid | 0.0012 | 0.0372 | 0.1031 | 0.0601 | 2.89 | 0.513 | 0.157 | 0.119 |
| mid | 0.0026 | 0.0668 | 0.1622 | 0.0801 | 1.31 | 0.674 | 0.194 | 0.082 |
| high | 0.0007 | 0.0347 | 0.0950 | 0.0617 | 1.87 | 0.512 | 0.081 | 0.038 |
| air | 0.0002 | 0.0602 | 0.2074 | 0.1060 | 1.80 | 0.860 | 0.130 | 0.027 |

**drop**

| band | width p10 | mean | p90 | sd | cv | slew /s | ac 1 bar | ac 2 bar |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| sub | 0.0000 | 0.0002 | 0.0006 | 0.0005 | 2.66 | 0.063 | 0.052 | 0.027 |
| bass | 0.0001 | 0.0035 | 0.0091 | 0.0061 | 2.79 | 0.105 | 0.019 | 0.025 |
| lowmid | 0.0051 | 0.0485 | 0.1288 | 0.0579 | 1.77 | 0.696 | 0.128 | 0.119 |
| mid | 0.0325 | 0.1261 | 0.2622 | 0.0949 | 1.06 | 0.896 | 0.147 | 0.163 |
| high | 0.0019 | 0.0270 | 0.0699 | 0.0337 | 1.45 | 0.438 | 0.073 | 0.046 |
| air | 0.0024 | 0.0180 | 0.0451 | 0.0291 | 2.47 | 0.346 | 0.148 | 0.083 |

In a drop the 400 Hz-2 kHz width swings from **0.032 (p10) to 0.262 (p90)** around a mean of 0.126 - a coefficient of variation of **1.06**, i.e. the spread is as large as the mean - and slews at **0.90 width-units per second**. That is the movement: the stage breathes between near-mono and wide several times a bar. Sub and bass do not move at all (cv is large only because the numbers are ~0.0002; slew 0.063/s).

It is **not** an auto-panner. The strongest periodic component of the width series in the midrange has a period of 8-12 s (roughly 6-8 bars) with a peak-to-median ratio of only 6-15, and the bar-locked autocorrelation is weak (0.13-0.21 at 1-2 bars in grooves and drops, ~0.0-0.09 in breakdowns). The movement is event-driven - each element arrives with its own width - with a slow arranged drift on top, not an LFO.

## 4. Space and tails

Measured on a 512-point STFT at a 128-sample hop (2.67 ms per frame) so that a 90 ms delay can be told from a 120 ms one. Requiring genuinely isolated transients yields about five usable hits per drop, so instead every onset is used: fit the decay over the gap to the next onset (capped at 300 ms) and extrapolate to -20 dB, and separately record the floor the band actually reaches before the next hit.

### 4a. Decay

| kind | band | decay dB/s | T20 (fit) ms | RT60 est ms | inter-onset floor dB | gap ms | % hits reaching -20 dB |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **breakdown** | mid | -131.3 | 166 | 497 | -10.4 | 132 | 8.2 |
|  | high | -79.7 | 303 | 909 | -11.7 | 181 | 6.8 |
|  | air | -108.6 | 227 | 680 | -14.2 | 175 | 19.5 |
| **groove** | mid | -177.6 | 116 | 349 | -11.7 | 110 | 13.2 |
|  | high | -91.8 | 251 | 753 | -12.3 | 163 | 11.7 |
|  | air | -108.7 | 211 | 634 | -15.5 | 145 | 23.8 |
| **drop** | mid | -197.0 | 113 | 339 | -9.6 | 120 | 4.9 |
|  | high | -69.2 | 380 | 1141 | -11.2 | 197 | 4.0 |
|  | air | -83.7 | 293 | 880 | -13.7 | 223 | 15.1 |

**Only 4.0% of 2-8 kHz hits in a drop ever fall 20 dB before the next one arrives.** The band never gets to dry out. Between hits it drops a median of **-11.2 dB** and no further.

### 4b. How much is left between the hits

Percentiles of the 2-16 kHz envelope, in dB relative to its own 99th percentile - i.e. the shape of the gap between loud and quiet moments in the top end.

| kind | p5 | p10 | p25 | p50 | p90 | % time >-12 dB | % >-20 dB | % >-30 dB |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **breakdown** | -18.0 | -16.3 | -13.0 | -9.3 | -2.4 | 70.7 | 94.0 | 99.2 |
| **groove** | -19.6 | -16.9 | -12.6 | -8.6 | -2.6 | 71.6 | 94.4 | 98.8 |
| **drop** | -16.9 | -14.4 | -11.6 | -8.5 | -2.8 | 76.4 | 96.4 | 99.7 |

| kind (air 8-16k) | p5 | p10 | p25 | p50 | p90 | % time >-20 dB |
| --- | --- | --- | --- | --- | --- | --- |
| **breakdown** | -22.3 | -19.4 | -15.5 | -10.5 | -3.6 | 86.1 |
| **groove** | -23.5 | -20.1 | -15.3 | -10.9 | -3.7 | 88.4 |
| **drop** | -20.2 | -16.8 | -12.8 | -9.4 | -3.1 | 92.8 |

The top end of a drop sits above -20 dB of its own peak **96.4% of the time** and above -30 dB **99.7%** of the time. There is effectively no silence in the high band. That continuous bed is the 'sustain in the highs'.

### 4c. Tail level at musical offsets after a hit

For every strong 2-16 kHz onset with no new attack before the offset, the level at that offset in dB relative to the hit itself. `n` is how many hits qualified.

| kind | 1/16 (90 ms) | 1/8 (181 ms) | 3/16 (271 ms) | 1/4 (362 ms) | 1/2 (724 ms) |
| --- | --- | --- | --- | --- | --- |
| **breakdown** | -4.8 (n=45) | -2.2 (n=20) | -5.5 (n=15) | -1.0 (n=8) | -3.3 (n=3) |
| **groove** | -4.7 (n=141) | -1.7 (n=60) | -4.8 (n=46) | -0.6 (n=22) | -2.3 (n=7) |
| **drop** | -7.6 (n=134) | -3.5 (n=49) | -5.3 (n=35) | -3.7 (n=23) | -3.2 (n=12) |

**One eighth note (181 ms) after a hit, the top end of a drop is still -3.5 dB below that hit. A quarter note (362 ms) later it is -3.7 dB below.** A dry mix would be 15-25 dB down by then.

### 4d. Echo repeats

Spotting a repeat inside a running break by similarity does not work - a break is already a burst of similar hits on the 16th grid, and control lags score as well as musical ones. So: take every gap of 180 ms or more with no new 2-16 kHz attack, fit the smooth decay through it, and keep bumps that poke at least 2 dB **above** that fitted tail while still sitting at least 3 dB **below** the dry hit. A bump above the tail inside a gap is a delay repeat; its lag is the delay time. Chance share for a +/-12 ms window over the 35-800 ms search range is **3.1%**, so anything near 3% is noise.

| delay | ms | breakdown % | groove % | drop % | repeat level dB (drop) | prominence dB |
| --- | --- | --- | --- | --- | --- | --- |
| 1/32 | 45.2 | 2.3 | 4.6 | 6.6 | -3.8 | 3.0 |
| 1/16 | 90.4 | 1.6 | 4.5 | 2.9 | -5.3 | 2.7 |
| 1/8T | 120.6 | 6.7 | 12.5 | 16.3 | -5.2 | 3.3 |
| 1/8 | 180.9 | 5.7 | 7.6 | 6.1 | -7.8 | 3.0 |
| 1/4T | 241.2 | 2.1 | 5.8 | 4.6 | -4.8 | 3.7 |
| dotted1/8 | 271.3 | 2.0 | 4.6 | 2.9 | -5.4 | 3.2 |
| 1/4 | 361.8 | 1.3 | 1.7 | 1.2 | -3.9 | 2.6 |
| dotted1/4 | 542.7 | 1.3 | 1.0 | 1.5 | -3.8 | 2.2 |
| 1/2 | 723.5 | 1.3 | 0.5 | 1.9 | -4.3 | 3.4 |

Raw lag histogram (10 ms bins) confirms it without assuming a grid - across the drops the modal bump lag is 110-120 ms, with a second cluster at 170-190 ms.

**Three delays are in use, and they are all short:**

- **1/8 triplet, ~120 ms** - the dominant one. 16.3% of drop repeats and 12.5% of groove repeats against a 3.1% chance floor, so roughly 5x chance. Repeats land ~5 dB under the dry hit. This is the jungle/dub triplet delay and it is what makes the break feel like it is rolling rather than stepping.
- **1/8, ~181 ms** - 6.1% in drops, and the *deepest* repeats (-7.8 dB), with the highest prominence above the tail in breakdowns (5.4 dB). This is the feature delay, used where there is room.
- **1/32, ~45 ms slapback** - 6.6% in drops. Too short to hear as an echo; it reads as thickness on the snare.

**Nothing long is in use.** Quarter note (362 ms) is at 1.2%, dotted quarter 1.5%, half note 1.9% - all at or below the chance floor, which for those lags is *higher* (3.8-7.6%) because the tolerance scales. There is no half-bar or bar-length delay anywhere in this set. The space is made from short repeats plus a ~0.6-1.1 s reverb tail, not from long echoes.

## 5. Density

Onsets are counted per band as a **rise in dB** (>=6 dB over 2 frames, local maximum, 60 ms refractory), not as raw spectral flux against a moving average - the latter fires a dozen times a bar in every band of a dense break and reports detector noise as voices.

### 5a. Onsets per bar, by band

| id | kind | sub | bass | lowmid | mid | high | air | total | 16ths used of 16 | bands per used 16th |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S00 | breakdown | 5.89 | 7.28 | 6.27 | 5.08 | 6.38 | 11.24 | 42.1 | 16.0 | 3.0 |
| S02 | groove | 5.51 | 4.98 | 7.16 | 6.31 | 5.16 | 9.87 | 39.0 | 13.0 | 3.0 |
| S04 | groove | 3.97 | 3.65 | 6.25 | 5.27 | 4.95 | 9.19 | 33.3 | 14.0 | 2.0 |
| S05 | breakdown | 4.77 | 3.11 | 7.10 | 6.77 | 4.11 | 6.99 | 32.9 | 12.0 | 3.0 |
| S07 | drop | 1.08 | 0.92 | 4.05 | 5.23 | 5.04 | 6.07 | 22.4 | 10.0 | 2.0 |
| S10 | drop | 2.07 | 5.59 | 5.15 | 4.77 | 3.01 | 4.71 | 25.3 | 12.0 | 2.0 |
| S13 | groove | 4.03 | 4.12 | 6.29 | 5.64 | 2.84 | 3.64 | 26.6 | 12.0 | 2.0 |
| S15 | drop | 1.64 | 3.26 | 7.77 | 5.79 | 5.11 | 8.37 | 31.9 | 13.0 | 3.0 |
| S21 | groove | 2.12 | 2.22 | 6.54 | 8.22 | 6.70 | 8.22 | 34.0 | 12.0 | 3.0 |
| S25 | breakdown | 2.52 | 3.16 | 4.06 | 2.89 | 1.80 | 4.87 | 19.3 | 11.0 | 1.0 |
| S30 | drop | 1.08 | 4.41 | 5.94 | 1.61 | 0.24 | 0.90 | 14.2 | 10.0 | 1.0 |
| S31 | breakdown | 2.53 | 5.29 | 4.25 | 0.57 | 0.46 | 1.95 | 15.1 | 9.5 | 1.0 |
| S32 | drop | 0.12 | 2.42 | 6.73 | 0.63 | 1.04 | 2.36 | 13.3 | 8.0 | 1.0 |
| S33 | groove | 1.53 | 3.39 | 10.66 | 5.12 | 2.41 | 4.86 | 28.0 | 13.0 | 2.0 |
| S36 | breakdown | 6.27 | 5.64 | 6.15 | 4.94 | 4.82 | 7.10 | 34.9 | 14.0 | 2.0 |

| **mean** | kind | sub | bass | lowmid | mid | high | air | total | 16ths used | bands per 16th |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  | **breakdown** | 4.40 | 4.90 | 5.57 | 4.05 | 3.51 | 6.43 | 28.9 | 12.5 | 2.0 |
|  | **groove** | 3.43 | 3.67 | 7.38 | 6.11 | 4.41 | 7.16 | 32.2 | 12.8 | 2.4 |
|  | **drop** | 1.20 | 3.32 | 5.93 | 3.61 | 2.89 | 4.48 | 21.4 | 10.6 | 1.8 |

**A drop bar has fewer events than a groove bar.** 21.4 band-onsets per bar in a drop against 32.2 in a groove and 28.9 in a breakdown. Of the 16 sixteenths in a drop bar, **10.6** carry anything at all, and each of those carries **1.8** bands - so at most two things speak at the same instant. The sub contributes **1.2 onsets per bar**: it is one sustained note, not a busy line.

### 5b. Time-frequency occupancy

On a 32-band log-frequency grid. `occupancy` = share of the plane above a threshold relative to the section's own loudest bin. `spread` = how many of the 32 bands sit within 20 dB of that frame's own loudest band, median over frames - level-free, so a quiet breakdown and a loud drop compare directly. `profile crest` = peak-to-mean of the time-averaged log-band profile.

| kind | occ -20 dB % | occ -30 dB % | occ -40 dB % | spread -20 dB (of 32) | flatness | profile crest dB |
| --- | --- | --- | --- | --- | --- | --- |
| **breakdown** | 31.1 | 71.1 | 86.8 | 24.8 | 0.0274 | 6.7 |
| **groove** | 33.5 | 70.7 | 88.4 | 20.0 | 0.0191 | 9.9 |
| **drop** | 25.0 | 67.2 | 89.0 | 11.2 | 0.0099 | 12.9 |

(The same spread measured only above 200 Hz saturates at 22-23 of 23 bands for every section type, so it carries no information - once the sub is excluded, the rest of the spectrum is always within 20 dB of itself. The discriminating measure is the full-range one, because what separates a drop is exactly how far the sub sticks up above everything else.)

The drop is the **least** flat and the **most** peaked section type: flatness 0.0099 against 0.0274 in a breakdown, profile crest 12.9 dB against 6.7 dB, and only 11 of 32 log-bands within 20 dB of the loudest band at any instant against 25 in a breakdown. A drop is a spike at the bottom with a thin spread above it, not a wall.

### 5c. Gaps per band

Share of the section each band spends more than 20 dB below its own peak - a band with a low number is running continuously.

| kind | sub | bass | lowmid | mid | high | air |
| --- | --- | --- | --- | --- | --- | --- |
| **breakdown** | 71.0 | 48.7 | 21.0 | 3.4 | 5.0 | 10.4 |
| **groove** | 30.9 | 23.0 | 11.3 | 8.8 | 4.0 | 6.9 |
| **drop** | 11.1 | 9.1 | 10.0 | 3.8 | 3.0 | 4.2 |

In a drop the sub is within 20 dB of its peak **89% of the time** - a continuous bassline, never gapped. In a breakdown it is gone **71%** of the time. The contrast is made by removing the sub wholesale, not by thinning it.

## What this means for building a jungle track

Against the two complaints - "dry, lacking effects sustain in the highs, no movement in the sound stage" and "too much going on when fully built up" - these are the reference's numbers to aim at.

1. **Band balance, drop.** sub -2 dB, bass -9, lowmid -11, mid -13, high -12, air -18 - relative to the section total. Overall tilt **-1.5 dB/oct**. Groove sits at -0.7 dB/oct, breakdown at 0.05 (flat).

2. **Build the drop downward, not upward.** Going breakdown -> drop, sub gains **+10 dB** of share while high falls **6 dB** and air falls **5 dB**. If the full build is brighter than the breakdown, it is wrong.

3. **Fewer voices at the top, not more.** Target a drop bar at **21 band-onsets** (sub 1.2, bass 3.3, lowmid 5.9, mid 3.6, high 2.9, air 4.5) against **32** in the groove. **11 of 16 sixteenths** occupied, **2 bands per occupied sixteenth**. Two things at a time, maximum.

4. **Keep the plane empty.** Drop occupancy at -20 dB = **25%** of the time-frequency plane (groove 34%), flatness **0.010**, log-band profile crest **13 dB**, only **11 of 32** log-bands live within 20 dB of the loudest at any instant. If the mix is measuring flatter than 0.015 at full build, it is the wall the user is hearing.

5. **Everything below 150 Hz is mono.** Side energy below 150 Hz must sit at least **30 dB** under the mid in the same range (reference: -33 dB). Per-band width in a drop: sub 0.0002, bass 0.0035. Any stereo widener touching the sub or the reese is off-reference.

6. **Width lives at 400 Hz-2 kHz.** The image opens between 250 and 500 Hz. In a drop the mid band holds **53% of all side energy**, lowmid 16%, high 21%, air 5%, sub+bass 5%. Target widths: lowmid 0.05, mid 0.13, high 0.03, air 0.02. Widening the hats and air is the wrong move; in the drops those bands *narrow*.

7. **Make the width move, slowly and unevenly.** The 400 Hz-2 kHz width should swing **0.03 to 0.26** within a section (sd 0.09, cv 1.1, slew 0.9 width-units/s). Not an auto-pan: the strongest periodic component has a period of 8-12 s (6-8 bars) and bar-locked autocorrelation is only 0.13-0.21. Give each element its own fixed width and let the arrangement do the moving.

8. **Delay times: 1/8 triplet (~120 ms) primary, 1/8 (~181 ms) secondary, ~45 ms slapback for thickness. Nothing longer than a quarter note.** Repeats land **-4 to -8 dB** under the dry hit (1/8 triplet ~-5 dB, 1/8 ~-8 dB), poking 3-5 dB above the reverb tail. Quarter, dotted quarter and half-note delays are at or below the chance floor in every section - do not use them.

9. **Tails: the 2-8 kHz band must not dry out.** One eighth (181 ms) after a hit it should still be within **3.5 dB** of that hit, and a quarter (362 ms) later within **3.7 dB**. Fit-extrapolated T20 for 2-8 kHz runs **173-740 ms across the drops (median 299 ms, RT60 ~0.9 s)** - the dense breaks sit near 212 ms and the sparse dub drops near 740 ms - and **293 ms** for 8-16 kHz. The band should sit above -20 dB of its own peak **96% of the time**, and fewer than **4%** of hits should ever fall 20 dB before the next one. That continuous bed is the sustain that is missing.

10. **Compress inside a section, contrast between sections.** Short-term loudness range inside a drop is only **1.8 dB** over a full minute, but breakdown-to-drop RMS steps by **6 dB**. Keep the 50 ms crest at **>=7.5 dB** (p90 10.1 dB) in the drop, which is **84%** of the 3 s crest - if that ratio falls much below 80%, the limiter has eaten the drums.

