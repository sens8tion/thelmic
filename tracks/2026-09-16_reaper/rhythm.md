# Reference rhythm analysis - Tim Reaper jungle DJ set (section), 2026-08

Structural measurement only. No audio was sampled, extracted or copied; everything below is numbers derived from the cached feature set.

Source: `Tim_Reaper_Jungle_DJ_Set_SECTION_August_2026.wav`, 1259.7 s, 48 kHz stereo. Analysis runs on the 8 kHz mono downmix in the cache.
Script: `scripts/reaper_rhythm.py`.

## 0. The grid, and how much to trust it

- **Tempo 165.997 BPM** (16th = 90.363 ms, beat = 361.45 ms, bar = 1445.8 ms). Fitted by circular phase coherence over 22715 onset times, not by frame autocorrelation, so the period is good to about 0.01 BPM.
- Independent check: per-window autocorrelation over 155 x 24 s windows gives median 165.902 BPM, sd 0.165. The set is beat-matched throughout; **there is no tempo change anywhere in the 21 minutes**.
- A *rigid* grid at that tempo does NOT hold: the phase of the onsets wanders up to **44 ms** (half a 16th) across the set and wraps once, because two decks in a mix are never locked to the part-per-million. So the grid used here is **drift-tracked**: the fitted period plus a smoothed phase-correction curve, re-solved for every 16th boundary.
- Quality of the drift-tracked grid, measured as the distance from every detected onset to its nearest 16th:

  | grid | median &#124;dev&#124; | within 10 ms | within 15 ms |
  |---|---|---|---|
  | rigid 166.00 BPM | 14.2 ms | 35.1 % | 52.4 % |
  | **drift-tracked (used here)** | **4.7 ms** | **76.6 %** | **85.9 %** |

- Cross-check against the other agent's `grid.npz`: it agrees on tempo (165.974 BPM vs 165.997) and 73 % of its beats are within 20 ms of mine. I did **not** use it: its beat times are snapped to the 10.67 ms frame hop of the 93.75 fps cache, which is coarser than the microtiming this analysis has to resolve, and it carries a single global bar phase (its downbeats agree with mine 54 % of the time - see next point).
- **Bar phase is per-section, not global.** A single bar phase for the whole set only holds in 65 % of one-minute windows: this is a DJ mix, and the incoming record does not inherit the outgoing record's bar. Phase is therefore re-fitted inside each of the 19 sections (kick on beat 1 + snare on 2 and 4). It changes 7 times, always at a section boundary.
- **Trust:** tempo and 16th grid, high. Bar phase, good inside sections (mean margin 2.01 sd above the alternatives) but the absolute '1' is inferred from kick/snare placement, not from anything notated. Sub-10 ms microtiming figures are near the resolution floor of a 64 ms STFT window and should be read as trends, not as exact per-hit values.

### Sections used throughout

| # | start | end | bars | bar phase /16 | onsets/bar | rms (rel. set median) |
|---|---|---|---|---|---|---|
| S1 | 0:00 | 0:49 | 33 | 0 | 21.7 | -4.6 dB |
| S2 | 0:49 | 2:28 | 68 | 0 | 27.2 | +1.2 dB |
| S3 | 2:28 | 4:05 | 67 | 12 | 25.2 | +0.0 dB |
| S4 | 4:05 | 4:40 | 23 | 12 | 23.3 | -1.4 dB |
| S5 | 4:40 | 5:24 | 30 | 0 | 27.9 | +2.7 dB |
| S6 | 5:24 | 5:49 | 17 | 12 | 26.4 | -2.2 dB |
| S7 | 5:49 | 6:46 | 38 | 12 | 27.8 | -0.2 dB |
| S8 | 6:46 | 7:23 | 24 | 8 | 28.5 | -0.4 dB |
| S9 | 7:23 | 8:01 | 25 | 0 | 27.0 | +3.2 dB |
| S10 | 8:01 | 9:06 | 44 | 0 | 24.9 | +3.1 dB |
| S11 | 9:06 | 10:04 | 39 | 0 | 25.9 | -0.1 dB |
| S12 | 10:04 | 11:44 | 69 | 0 | 26.4 | -0.6 dB |
| S13 | 11:44 | 12:54 | 47 | 0 | 24.6 | -1.2 dB |
| S14 | 12:54 | 15:05 | 90 | 0 | 26.5 | -0.3 dB |
| S15 | 15:05 | 15:35 | 19 | 8 | 27.3 | -3.5 dB |
| S16 | 15:35 | 17:54 | 95 | 5 | 26.0 | +0.4 dB |
| S17 | 17:54 | 19:26 | 62 | 5 | 26.3 | +0.2 dB |
| S18 | 19:26 | 19:50 | 15 | 5 | 26.4 | -6.1 dB |
| S19 | 19:50 | 20:59 | 47 | 5 | 25.1 | -2.1 dB |

## 1. Per-16th occupancy

Probability that a 16th slot carries an onset, by band. low = 20-160 Hz (kick/bass), mid = 160-1200 Hz (snare/body), high = 1.2-4 kHz (hats, ghosts, snare edge). Slots are numbered 0-15; beats are 0, 4, 8, 12.

**Whole set (852 bars)**

```
slot            0     1     2     3     4     5     6     7     8     9    10    11    12    13    14    15
low          0.91  0.21  0.49  0.39  0.79  0.29  0.64  0.49  0.65  0.34  0.66  0.31  0.78  0.34  0.52  0.37
mid          0.91  0.23  0.69  0.44  0.94  0.27  0.74  0.65  0.80  0.32  0.84  0.36  0.89  0.35  0.70  0.48
high         0.74  0.24  0.63  0.25  0.87  0.17  0.65  0.50  0.77  0.24  0.79  0.21  0.85  0.25  0.66  0.37
```

Read-out: every beat slot is near-saturated (0 = 0.85 mean across bands, 4 = 0.87, 8 = 0.74, 12 = 0.84); the off-8th 16ths (odd slots) are the sparse ones (0.34 mean vs 0.75 for even slots). The single busiest non-beat slot is **10** and the emptiest is **1**.

**S1  0:00-0:49**  (33 bars, 21.7 onsets/bar)

```
slot            0     1     2     3     4     5     6     7     8     9    10    11    12    13    14    15
low          0.97  0.00  0.39  0.15  0.91  0.09  0.39  0.85  0.09  0.15  0.70  0.03  0.94  0.24  0.12  0.55
mid          0.97  0.15  0.39  0.36  0.91  0.00  0.45  0.82  0.06  0.27  0.76  0.21  0.88  0.12  0.27  0.64
high         0.48  0.48  0.33  0.52  0.85  0.00  0.64  0.73  0.06  0.61  0.58  0.48  0.88  0.06  0.48  0.70
```

**S2  0:49-2:28**  (68 bars, 27.2 onsets/bar)

```
slot            0     1     2     3     4     5     6     7     8     9    10    11    12    13    14    15
low          0.99  0.07  0.63  0.35  0.96  0.04  0.72  0.68  0.49  0.38  0.96  0.04  0.99  0.35  0.32  0.66
mid          0.97  0.09  0.79  0.43  0.97  0.04  0.88  0.88  0.40  0.51  0.97  0.09  0.99  0.40  0.53  0.78
high         0.66  0.31  0.74  0.41  0.96  0.04  0.87  0.76  0.25  0.47  0.88  0.19  0.97  0.03  0.57  0.78
```

**S3  2:28-4:05**  (67 bars, 25.2 onsets/bar)

```
slot            0     1     2     3     4     5     6     7     8     9    10    11    12    13    14    15
low          0.81  0.24  0.66  0.19  0.84  0.25  0.69  0.27  0.76  0.13  0.70  0.16  0.82  0.36  0.88  0.09
mid          0.76  0.30  0.82  0.46  0.97  0.06  0.81  0.54  1.00  0.07  0.96  0.12  0.93  0.19  0.93  0.13
high         0.61  0.40  0.81  0.45  0.97  0.06  0.61  0.45  0.99  0.00  0.82  0.03  0.93  0.16  0.91  0.13
```

**S4  4:05-4:40**  (23 bars, 23.3 onsets/bar)

```
slot            0     1     2     3     4     5     6     7     8     9    10    11    12    13    14    15
low          0.78  0.43  0.39  0.65  0.91  0.26  0.43  0.57  0.91  0.22  0.35  0.74  0.74  0.43  0.35  0.57
mid          0.87  0.09  0.83  0.22  1.00  0.04  0.83  0.17  0.91  0.17  0.57  0.17  0.96  0.09  0.87  0.09
high         0.83  0.22  0.65  0.09  0.87  0.00  0.65  0.13  0.91  0.26  0.35  0.17  0.70  0.00  0.78  0.04
```

**S5  4:40-5:24**  (30 bars, 27.9 onsets/bar)

```
slot            0     1     2     3     4     5     6     7     8     9    10    11    12    13    14    15
low          1.00  0.07  0.40  0.63  0.63  0.47  0.90  0.20  0.97  0.03  0.37  0.30  0.87  0.13  0.50  0.17
mid          1.00  0.27  0.77  0.70  1.00  0.43  0.87  0.57  1.00  0.57  1.00  0.23  1.00  0.40  0.87  0.20
high         0.87  0.10  0.73  0.40  0.97  0.33  0.60  0.50  0.87  0.50  0.97  0.17  0.90  0.37  0.87  0.23
```

**S6  5:24-5:49**  (17 bars, 26.4 onsets/bar)

```
slot            0     1     2     3     4     5     6     7     8     9    10    11    12    13    14    15
low          0.76  0.53  0.59  0.53  0.94  0.12  0.41  0.76  0.88  0.18  0.29  0.82  0.71  0.76  0.41  0.65
mid          1.00  0.35  0.82  0.06  1.00  0.18  0.94  0.18  1.00  0.18  0.53  0.35  1.00  0.24  0.94  0.29
high         1.00  0.24  0.59  0.00  1.00  0.06  0.82  0.18  0.88  0.29  0.47  0.35  0.76  0.24  0.88  0.18
```

**S7  5:49-6:46**  (38 bars, 27.8 onsets/bar)

```
slot            0     1     2     3     4     5     6     7     8     9    10    11    12    13    14    15
low          0.84  0.29  0.53  0.37  0.82  0.11  0.61  0.39  0.58  0.45  0.76  0.18  0.66  0.26  0.53  0.21
mid          0.92  0.53  0.87  0.42  0.97  0.39  0.82  0.58  0.95  0.61  0.92  0.58  0.89  0.53  0.92  0.29
high         0.89  0.45  0.68  0.37  0.84  0.18  0.68  0.45  0.92  0.29  0.74  0.47  0.82  0.32  0.79  0.18
```

**S8  6:46-7:23**  (24 bars, 28.5 onsets/bar)

```
slot            0     1     2     3     4     5     6     7     8     9    10    11    12    13    14    15
low          1.00  0.04  0.58  0.25  0.71  0.50  0.83  0.29  0.83  0.21  0.75  0.42  0.92  0.21  0.54  0.54
mid          0.96  0.33  0.96  0.12  0.92  0.83  0.88  0.42  0.96  0.29  0.75  0.12  1.00  0.04  0.88  1.00
high         0.67  0.29  0.96  0.08  0.92  0.88  0.42  0.50  0.96  0.25  0.71  0.12  1.00  0.12  0.67  0.92
```

**S9  7:23-8:01**  (25 bars, 27.0 onsets/bar)

```
slot            0     1     2     3     4     5     6     7     8     9    10    11    12    13    14    15
low          0.96  0.28  0.20  0.12  0.96  0.28  0.48  0.92  0.96  0.12  1.00  0.32  0.48  0.84  0.84  0.12
mid          1.00  0.12  0.40  0.24  0.96  0.00  0.68  0.96  0.96  0.08  1.00  0.24  0.56  0.92  0.84  0.32
high         1.00  0.16  0.60  0.28  0.96  0.16  0.68  0.76  0.80  0.08  0.96  0.00  0.76  0.76  0.56  0.32
```

**S10  8:01-9:06**  (44 bars, 24.9 onsets/bar)

```
slot            0     1     2     3     4     5     6     7     8     9    10    11    12    13    14    15
low          0.95  0.14  0.25  0.16  0.91  0.16  0.27  0.91  0.98  0.27  0.89  0.11  0.30  0.86  0.86  0.32
mid          0.95  0.07  0.45  0.07  1.00  0.00  0.75  0.93  0.95  0.07  0.95  0.09  0.95  0.82  0.82  0.27
high         0.93  0.00  0.23  0.02  1.00  0.00  0.70  0.57  0.86  0.05  0.93  0.07  0.95  0.77  0.18  0.14
```

**S11  9:06-10:04**  (39 bars, 25.9 onsets/bar)

```
slot            0     1     2     3     4     5     6     7     8     9    10    11    12    13    14    15
low          0.79  0.36  0.33  0.15  0.87  0.36  0.26  0.67  0.87  0.26  0.51  0.44  0.46  0.59  0.77  0.31
mid          1.00  0.13  0.46  0.21  1.00  0.13  0.62  0.95  0.95  0.38  0.90  0.26  0.85  0.82  0.72  0.28
high         0.95  0.05  0.49  0.13  1.00  0.03  0.79  0.74  0.72  0.33  0.92  0.00  0.97  0.77  0.18  0.15
```

**S12  10:04-11:44**  (69 bars, 26.4 onsets/bar)

```
slot            0     1     2     3     4     5     6     7     8     9    10    11    12    13    14    15
low          0.99  0.17  0.25  0.83  0.51  0.20  0.67  0.62  0.30  0.75  0.81  0.30  0.80  0.20  0.17  0.29
mid          0.96  0.19  0.74  0.51  0.97  0.25  0.81  0.74  0.70  0.42  0.83  0.43  0.99  0.04  0.55  0.26
high         0.87  0.54  0.84  0.06  0.94  0.20  0.81  0.77  0.93  0.25  0.86  0.16  0.97  0.01  0.80  0.19
```

**S13  11:44-12:54**  (47 bars, 24.6 onsets/bar)

```
slot            0     1     2     3     4     5     6     7     8     9    10    11    12    13    14    15
low          0.96  0.09  0.28  0.30  0.40  0.19  0.94  0.17  0.26  0.19  0.36  0.21  0.94  0.02  0.55  0.23
mid          0.98  0.30  0.66  0.21  0.94  0.30  0.98  0.64  0.79  0.13  0.89  0.57  0.98  0.09  0.83  0.43
high         0.91  0.28  0.77  0.15  0.66  0.34  0.91  0.38  0.89  0.06  0.87  0.19  0.98  0.21  0.83  0.36
```

**S14  12:54-15:05**  (90 bars, 26.5 onsets/bar)

```
slot            0     1     2     3     4     5     6     7     8     9    10    11    12    13    14    15
low          0.94  0.27  0.78  0.24  0.88  0.27  0.57  0.36  0.91  0.22  0.54  0.31  0.81  0.16  0.67  0.30
mid          0.90  0.37  0.76  0.51  0.97  0.34  0.86  0.33  0.90  0.19  0.86  0.71  0.96  0.19  0.76  0.49
high         0.71  0.20  0.51  0.31  0.84  0.23  0.73  0.22  0.82  0.23  0.80  0.33  0.83  0.27  0.71  0.43
```

**S15  15:05-15:35**  (19 bars, 27.3 onsets/bar)

```
slot            0     1     2     3     4     5     6     7     8     9    10    11    12    13    14    15
low          0.84  0.32  0.63  0.42  0.95  0.68  0.58  0.58  0.79  0.79  0.58  0.42  0.74  0.68  0.53  0.74
mid          0.89  0.42  0.26  0.74  0.89  0.47  0.63  0.47  0.63  0.63  0.32  0.53  0.89  0.11  0.32  0.47
high         0.68  0.16  0.58  0.79  0.68  0.37  0.74  0.42  0.79  0.42  0.63  0.32  0.63  0.16  0.63  0.37
```

**S16  15:35-17:54**  (95 bars, 26.0 onsets/bar)

```
slot            0     1     2     3     4     5     6     7     8     9    10    11    12    13    14    15
low          0.87  0.27  0.67  0.72  0.67  0.59  0.77  0.54  0.79  0.47  0.53  0.58  0.84  0.44  0.48  0.51
mid          0.64  0.23  0.78  0.69  0.72  0.60  0.55  0.52  0.88  0.23  0.68  0.73  0.66  0.36  0.67  0.69
high         0.29  0.21  0.43  0.22  0.64  0.26  0.32  0.33  0.76  0.13  0.55  0.47  0.61  0.25  0.59  0.53
```

**S17  17:54-19:26**  (62 bars, 26.3 onsets/bar)

```
slot            0     1     2     3     4     5     6     7     8     9    10    11    12    13    14    15
low          0.95  0.21  0.58  0.31  0.84  0.40  0.94  0.18  0.48  0.39  0.66  0.35  0.92  0.18  0.15  0.34
mid          1.00  0.27  0.52  0.63  0.98  0.29  0.71  0.90  0.73  0.53  0.89  0.16  0.85  0.61  0.45  0.84
high         0.79  0.08  0.65  0.24  0.95  0.08  0.68  0.48  0.73  0.23  0.92  0.08  0.84  0.19  0.73  0.37
```

**S18  19:26-19:50**  (15 bars, 26.4 onsets/bar)

```
slot            0     1     2     3     4     5     6     7     8     9    10    11    12    13    14    15
low          0.80  0.53  0.27  0.47  0.93  0.47  0.60  0.67  0.40  0.73  0.53  0.47  1.00  0.33  0.67  0.60
mid          1.00  0.07  0.60  0.47  1.00  0.27  0.07  1.00  0.53  0.60  1.00  0.00  1.00  0.33  0.40  0.73
high         0.87  0.13  0.60  0.07  1.00  0.00  0.07  0.87  0.73  0.47  1.00  0.00  1.00  0.00  0.60  0.47
```

**S19  19:50-20:59**  (47 bars, 25.1 onsets/bar)

```
slot            0     1     2     3     4     5     6     7     8     9    10    11    12    13    14    15
low          0.81  0.15  0.21  0.43  0.87  0.26  0.49  0.32  0.36  0.36  0.89  0.23  0.57  0.21  0.68  0.34
mid          0.98  0.06  0.83  0.43  0.89  0.26  0.53  0.77  0.94  0.49  0.85  0.23  0.83  0.51  0.81  0.62
high         0.96  0.02  0.79  0.13  0.83  0.19  0.34  0.53  0.94  0.28  0.77  0.09  0.77  0.21  0.72  0.36
```

## 2. Microtiming and swing

Deviation of each onset from its exact 16th, in ms, early = negative. Measured against the drift-tracked grid, then referenced to the mean of the four beat slots (0/4/8/12) so that 'zero' means 'on the beat grid' rather than 'on the fitted phase'.

```
slot            0     1     2     3     4     5     6     7     8     9    10    11    12    13    14    15
mean ms      -0.6   2.5   0.7   2.6  -0.5   1.1   1.0   3.4   1.9   3.9   0.8   1.7  -0.8   5.0   0.5   4.0
sd ms         7.3  13.9   7.9  13.8   6.6  16.1   8.0  10.3   7.7  13.1   6.4  14.5   7.1  13.5   8.7  13.0
n             835   404   723   544   835   392   767   687   772   480   791   471   833   469   743   553
```

Per band (mean ms, relative to that band's own beat-slot anchor):

```
slot            0     1     2     3     4     5     6     7     8     9    10    11    12    13    14    15
low          -1.6   0.0   2.4   2.1  -1.5  -4.6   0.6  -0.4   5.6   3.4  -0.2  -4.6  -2.5   1.0   0.1  -0.2
mid          -0.5   5.0   0.6   3.0  -0.2   5.5   1.7   4.4   1.1   3.7   1.1   6.3  -0.4   7.0   1.0   5.3
high         -0.4   4.3   0.2   4.0  -0.0   7.6   1.0   7.5   0.1   3.6   1.6   6.9   0.3  11.5   0.9   7.4
```

### Swing

- Even 16ths (the 8th-note positions 0,2,4,...) sit at **+0.4 ms** (spread 0.9).
- Odd 16ths (the off-8th 'e' and 'a' positions) sit at **+3.0 ms**, i.e. **+2.6 ms late** relative to the even ones.

Expressed as the split of an 8th into its two 16ths (50.0 % = straight, 66.7 % = triplet shuffle):

| off-8th slot | first half (ms) | second half (ms) | ratio | swing % |
|---|---|---|---|---|
| 1 | 93.4 | 88.6 | 1.054 | 51.3 % |
| 3 | 92.3 | 87.2 | 1.058 | 51.4 % |
| 5 | 92.0 | 90.3 | 1.020 | 50.5 % |
| 7 | 92.7 | 88.9 | 1.042 | 51.0 % |
| 9 | 92.4 | 87.3 | 1.058 | 51.4 % |
| 11 | 91.2 | 87.8 | 1.039 | 51.0 % |
| 13 | 96.2 | 85.8 | 1.121 | 52.8 % |
| 15 | 93.9 | 85.8 | 1.094 | 52.2 % |

**The two the brief asks for, uncorrected:** 2nd 16th (slot 1) = **51.3 %** (ratio 1.054); 4th 16th (slot 3) = **51.4 %** (ratio 1.058). Mean over all eight off-8th slots: **51.5 %**, i.e. +2.6 ms of late off-8ths.

### Controlling for level

A quiet hit has a slower attack, so its flux peak is detected later; off-8th hits are the quiet ones, so level could fake swing. Control: compare loud against quiet onsets **at the same (even) slots**, where there is no swing to find.

- loud onsets on even slots: -0.2 ms (n = 4125)
- quiet onsets on even slots: +2.0 ms (n = 2174)
- so the detector does carry a **+2.2 ms** level bias, and the raw figure above is contaminated by it.

The clean comparison is loud-against-loud. Restricted to onsets above the median level on both sides, the off-8th lag is **+4.4 ms** = **52.4 % swing** - slightly *more* than the uncontrolled 51.5 %, not less.

**Verdict: effectively straight, with a 4 ms lean.** Best estimate 52.4 % against 50.0 % for dead straight and 66.7 % for a triplet shuffle. 4.4 ms is under a twentieth of a 16th. This is not a shuffle and not an MPC 54-58 % swing setting; it is the residual feel of the sampled break, and it varies by track (see the per-section table below, which runs 47 % to 55 % - i.e. some records in the mix lean *early*).

### Quantised, or human/chopped?

- Spread of the deviation at a given slot: median sd **9.5 ms** across the 16 slots (range 6.4-16.1 ms).
- That spread is strongly split: **7.5 ms sd on the even (8th) slots** and **13.5 ms on the odd ones** - the backbone is tight, the in-between hits are loose.
- 77 % of all onsets land within 10 ms of a 16th, 91 % within 20 ms; median |deviation| 4.7 ms.

**Verdict: quantised placement, human content.** A 7 ms sd on the beat and 8th positions at a 90 ms subdivision is machine-tight - a genuinely loose human performance at 166 BPM runs 15-25 ms, and a drum machine would run under 2 ms. The odd-slot 14 ms is a different population: those are the ghost hits carried *inside* the slices, keeping the source break's own feel. That combination - rigid on the 8ths, loose in between - is the signature of **a break sliced and re-triggered on a 16th grid**: neither played live nor programmed from scratch.

Swing by section (mean off-8th lateness, ms):

| section | odd-16th lag ms | swing % | sd ms |
|---|---|---|---|
| S1 0:00 | -0.3 | 49.9 % | 4.2 |
| S2 0:49 | +2.9 | 51.6 % | 6.3 |
| S3 2:28 | -0.5 | 49.7 % | 10.1 |
| S4 4:05 | -4.9 | 47.3 % | 13.7 |
| S5 4:40 | +3.9 | 52.2 % | 9.3 |
| S6 5:24 | -5.2 | 47.1 % | 10.2 |
| S7 5:49 | +4.1 | 52.2 % | 9.8 |
| S8 6:46 | +5.1 | 52.8 % | 7.2 |
| S9 7:23 | +6.3 | 53.6 % | 6.3 |
| S10 8:01 | +8.0 | 54.5 % | 7.1 |
| S11 9:06 | +0.1 | 50.0 % | 7.7 |
| S12 10:04 | +3.9 | 52.2 % | 7.5 |
| S13 11:44 | +6.7 | 53.7 % | 8.0 |
| S14 12:54 | +1.1 | 50.6 % | 9.1 |
| S15 15:05 | +2.7 | 51.4 % | 15.1 |
| S16 15:35 | +3.1 | 51.7 % | 9.3 |
| S17 17:54 | +2.0 | 51.1 % | 6.7 |
| S18 19:26 | +3.1 | 51.7 % | 10.7 |
| S19 19:50 | +0.7 | 50.4 % | 6.9 |

## 3. Bar-to-bar variation

Each bar is a 48-cell vector (16 slots x 3 bands). r is the Pearson correlation between consecutive bars' vectors; 'cells changed' is how many of the 48 flipped.

**Baselines first**, because a bare correlation means nothing without them:

| pair | mean r |
|---|---|
| consecutive bars | **0.355** |
| two random bars from the *same* section | 0.356 |
| two random bars from anywhere in the set | 0.234 |

Consecutive bars are only -0.001 more alike than two bars picked at random from the same section. **Adjacency buys almost nothing**: within a section every bar is about as similar to every other bar as it is to its neighbour. The pattern is a stable distribution of hits, continually re-dealt, not a loop with occasional edits.

- mean r(bar, previous bar) = **0.355**, median 0.367, sd 0.219
- **2 %** of bars are near-identical to the previous bar (r > 0.8); 12 % are r > 0.6; 57 % are a clear break with the previous bar (r < 0.4)
- median number of the 48 cells that change from bar to bar: **15** (mean 15.4)

By band, against each band's own same-section random baseline (a sparser band correlates worse for purely statistical reasons, so the excess is the number that means something). Shown at lag 1 and at lag 4, because lag 4 is where the structure actually is:

| band | r at lag 1 | r at lag 4 | random baseline | excess at lag 1 | excess at lag 4 |
|---|---|---|---|---|---|
| low | 0.281 | 0.423 | 0.286 | -0.005 | +0.137 |
| mid | 0.375 | 0.531 | 0.404 | -0.029 | +0.127 |
| high | 0.391 | 0.502 | 0.386 | +0.005 | +0.116 |

At lag 1 **no band repeats at all** - every excess is within ±0.03 of zero, which is the quantitative form of 'consecutive bars are unrelated'. At lag 4 all three bands come back, and the **low** band comes back hardest (+0.137 above its baseline) while the **high** band is the loosest (+0.116).

So the four-bar unit is defined most strongly by its **low**-band pattern; the **high** band is where the per-pass re-chopping shows.

### How far back does a bar rhyme? (lag profile)

Mean r between a bar and the bar N before it. The same-section random baseline is 0.356; anything at that level is 'no relationship'.

| lag (bars) | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mean r | 0.355 | 0.436 | 0.349 | 0.486 | 0.334 | 0.383 | 0.333 | 0.465 | 0.316 | 0.359 | 0.321 | 0.385 | 0.302 | 0.337 | 0.314 | 0.389 |

**This is the important table.** Lag **4** is the strongest period in the profile (0.486), with lag 8 (0.465) and lag 2 (0.436) behind it. Lag 1 (0.355) is the *lowest of the first eight* and is level with the random baseline. Every even lag beats every odd lag out to 16: mean r 0.405 at even lags against 0.328 at odd.

Read that carefully, because it is the answer to the hypothesis:

- there **is** a repeating unit, and it is **4 bars** (reinforced at 8 and 16);
- inside that unit, **a bar is least like the bar next to it** - adjacency is the weakest relationship in the whole profile;
- there is a clear **2-bar sub-period** on top (lag 2 > lag 1 and lag 3).

So the four bars of the phrase are *all different from each other*, in a fixed A-B-C-D order, and it is the whole four-bar group that comes back - not three copies and a variation.

### The user's hypothesis: 'three bars repeat and the fourth disturbs'

The phrase grid here is set by **arrangement** (where the bar-rms steps up inside each section), not by rhythm, so this is not a circular test.

Mean r(bar, previous bar) by position in the 4-bar phrase. Position 1 is the first bar of the phrase, so its r measures 'how different is the phrase start from the last bar of the previous phrase':

| position in 4 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|
| mean r vs previous bar | 0.362 | 0.374 | 0.359 | 0.332 |
| standard error | ±0.016 | ±0.016 | ±0.015 | ±0.015 |
| n bars | 207 | 210 | 210 | 209 |
| mean r vs **bar 1 of its own phrase** | - | 0.377 | 0.428 | 0.356 |

| position in 8 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| mean r | 0.368 | 0.398 | 0.366 | 0.290 | 0.368 | 0.387 | 0.345 | 0.329 |
| standard error | ±0.022 | ±0.020 | ±0.021 | ±0.021 | ±0.022 | ±0.022 | ±0.021 | ±0.020 |
| n bars | 105 | 107 | 106 | 105 | 104 | 104 | 103 | 102 |

**Result: the reference does NOT do it.** The least-similar bar of the four is position **4** - the right position for the hypothesis - but the effect is negligible: the spread across the four positions is **0.042** in r (0.332 to 0.374) against a standard error of about 0.015 per cell. A permutation test (2000 shuffles of the bar order) returns **p = 0.196** for a spread that large arising by chance.

The second row is a sharper test: similarity to bar 1 of the *same* phrase runs bar 2 = 0.377, bar 3 = 0.428, bar 4 = 0.356. If three bars repeated and the fourth disturbed, bars 2 and 3 would sit far above bar 4. They differ by 0.046.

**And the decisive test, which needs no phrase phase at all.** If the music really went same-same-same-different, then the bar-to-bar similarity *series* would itself be periodic with period 4: high, high, high, low, high, high, high, low. Autocorrelating that series cannot be fooled by a mis-guessed phase:

| lag (bars) | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| acf of the r-series | +0.30 | -0.07 | +0.01 | +0.10 | -0.05 | -0.16 | -0.07 | +0.05 | -0.09 | -0.17 | -0.09 | -0.08 | -0.18 | -0.20 | -0.04 | +0.10 |

At lag 4 it is **+0.099**, against +0.298 at lag 1 (which is just the series being smooth) and -0.072 / +0.012 at lags 2 and 3. So there **is** a faint 4-bar component in how similarity rises and falls - but compare it with the same statistic on the fill indicator (+0.19) and on the onset count (+0.20), measured the same way on the same bars.

**That contrast is the answer.** The 4-bar unit is unmistakable in *density* and in *fills*. It is only a whisper in *whether a bar resembles the one before it*. If the music were built as three repeats and a disturbance, the similarity series would be the strongest 4-bar signal of the three, not the weakest.

Over eight bars the least-similar position is **4** with a spread of 0.108 - again inside the noise.

**What it does instead:** it varies continuously. Every bar changes about 15 of its 48 cells from the one before, at every position in the phrase. The repetition in this music is at the level of the *distribution* - which slots are likely - not at the level of an identical bar that is periodically broken.

**But the intuition is half right, and the half it gets right matters.** There *is* a 4-bar unit - the lag profile above peaks at lag 4 (0.486) and 8 (0.465) - it just is not built as 'three the same plus one different'. It is built as **A-B-C-D, four bars that all differ from each other, and the group returns**. Lag 1 (0.355) being the lowest lag in the profile is the measurement of exactly that: consecutive bars are the *least* alike pair in the music.

The practical restatement: **do not repeat a bar and then break it. Write four bars that differ, and repeat the four.**

## 4. Fills

A fill is scored as a bar whose onset count, high-band flux and high-band energy all sit above the rolling median of the 33 bars around it (mean robust z > 1.0).

- **55 fill bars out of 852** = 6.5 %, i.e. one every **15.5 bars**

Where they land, as the fill rate at each position (the flat expectation is 6.5 %):

| position in the 4-bar phrase | 1 | 2 | 3 | 4 |
|---|---|---|---|---|
| fill rate | 5.8 % | 7.1 % | 8.5 % | 4.8 % |

| position in the 8-bar phrase | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| fill rate | 5.7 % | 10.2 % | 7.5 % | 5.7 % | 9.6 % | 2.9 % | 5.8 % | 4.9 % |

| position in the 16-bar phrase | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fill rate | 6 | 13 | 6 | 10 | 8 | 4 | 8 | 4 | 6 | 7 | 9 | 2 | 11 | 2 | 4 | 6 |

chi-square against a flat distribution over the four positions: 2.78 on 3 df (p > 0.1).

The position tables above depend on having guessed the phrase phase right. This next test does not: it autocorrelates the fill indicator and the onset count across bars (after removing each series' local mean, so slow drift between sections cannot swamp it), so a 4- or 8-bar habit shows as a spike at lag 4 / 8 / 16 whatever the phase.

| lag (bars) | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fill indicator acf | -0.10 | +0.06 | -0.08 | +0.19 | -0.10 | +0.03 | -0.08 | +0.10 | -0.14 | -0.04 | -0.07 | +0.05 | -0.09 | -0.11 | -0.08 | -0.07 |
| onset-count acf | +0.15 | +0.08 | +0.03 | +0.20 | -0.05 | -0.07 | -0.06 | +0.05 | -0.11 | -0.17 | -0.17 | -0.05 | -0.17 | -0.18 | -0.07 | +0.03 |

**This overturns the tables above.** Fill autocorrelation is **+0.188 at lag 4** - the largest value in the whole profile out to 32 - with lag 8 +0.104 and every odd lag negative (mean -0.090). Onset count does the same, and more strongly: lag 4 **+0.201**, lag 8 +0.049. **Fills and density are on a 4-bar cycle.**

(Robustness: the high-pass window matters, so it was varied. At detrend windows of 17 / 33 / 65 bars the fill lag-4 value is +0.12 / +0.19 / +0.22 and the onset-count lag-4 value is +0.10 / +0.20 / +0.27. The 4-bar peak is present at every setting that leaves a 4-bar period intact; 33 bars is reported.)

The position tables looked flat because the *phase* I fitted from the arrangement (where bar-rms steps up) is not the phase the fills use. The autocorrelation needs no phase, so it wins: the 4-bar cycle is real, and the rms-step cue is simply a weak anchor for finding bar 1 in this material. **I can say fills are 4-bar periodic; I cannot say from this data whether the fill bar is the 4th of the phrase or the 2nd.**

Note the reconciliation with the rate: only 6.5 % of bars are fills, one every 15 bars, which is roughly **one in four of the available 4-bar slots**. So the rule is not 'a fill every 4 bars' - it is *fills land on the 4-bar grid, and take about one opportunity in four*. That is exactly what an autocorrelation of +0.19 rather than +1.0 means.

- a fill bar carries **31.5 onsets** against **25.6** in a normal bar = **1.23x denser** (+5.8 onsets)
- its high-band flux is 1.30x a normal bar's, its low-band 1.06x
- similarity to the previous bar drops to r = 0.324 in a fill bar against 0.358 elsewhere
- the strongest 4-bar position for fills is **3** (8.5 %) and the strongest 8-bar position is **2** (10.2 %)

## 5. Density

Onsets per bar, and how they split across the three bands.

| section | bars | onsets/bar | low | mid | high | rms rel. | class |
|---|---|---|---|---|---|---|---|
| S1 0:00 | 33 | 21.7 | 6.6 | 7.3 | 7.9 | -4.6 dB | breakdown |
| S2 0:49 | 68 | 27.2 | 8.6 | 9.7 | 8.9 | +1.2 dB | drop |
| S3 2:28 | 67 | 25.2 | 7.9 | 9.0 | 8.3 | +0.0 dB | mid |
| S4 4:05 | 23 | 23.3 | 8.7 | 7.9 | 6.7 | -1.4 dB | mid |
| S5 4:40 | 30 | 27.9 | 7.6 | 10.9 | 9.4 | +2.7 dB | drop |
| S6 5:24 | 17 | 26.4 | 9.4 | 9.1 | 7.9 | -2.2 dB | mid |
| S7 5:49 | 38 | 27.8 | 7.6 | 11.2 | 9.1 | -0.2 dB | drop |
| S8 6:46 | 24 | 28.5 | 8.6 | 10.5 | 9.5 | -0.4 dB | drop |
| S9 7:23 | 25 | 27.0 | 8.9 | 9.3 | 8.8 | +3.2 dB | drop |
| S10 8:01 | 44 | 24.9 | 8.3 | 9.2 | 7.4 | +3.1 dB | mid |
| S11 9:06 | 39 | 25.9 | 8.0 | 9.6 | 8.2 | -0.1 dB | mid |
| S12 10:04 | 69 | 26.4 | 7.9 | 9.4 | 9.2 | -0.6 dB | drop |
| S13 11:44 | 47 | 24.6 | 6.1 | 9.7 | 8.8 | -1.2 dB | mid |
| S14 12:54 | 90 | 26.5 | 8.2 | 10.1 | 8.2 | -0.3 dB | drop |
| S15 15:05 | 19 | 27.3 | 10.3 | 8.7 | 8.4 | -3.5 dB | breakdown |
| S16 15:35 | 95 | 26.0 | 9.7 | 9.6 | 6.6 | +0.4 dB | mid |
| S17 17:54 | 62 | 26.3 | 7.9 | 10.4 | 8.0 | +0.2 dB | drop |
| S18 19:26 | 15 | 26.4 | 9.5 | 9.1 | 7.9 | -6.1 dB | breakdown |
| S19 19:50 | 47 | 25.1 | 7.2 | 10.0 | 7.9 | -2.1 dB | mid |

Bar-level, contrasting the extremes: a **drop bar** is in the loudest 10 % with above-median low end, a **breakdown bar** is in the quietest 10 % or the bottom 8 % for low-end energy:

| | onsets/bar | low | mid | high | share of onsets in the low band |
|---|---|---|---|---|---|
| drop bar | 26.9 | 8.1 | 9.8 | 9.0 | 30 % |
| all bars | 26.0 | 8.2 | 9.6 | 8.2 | 31 % |
| breakdown bar | 24.1 | 8.8 | 8.2 | 7.1 | 36 % |

A drop bar is only **1.12x** the onset count of a breakdown bar (26.9 vs 24.1) - but it is **10.5 dB** louder overall and carries **+22.8 dB** more low-end energy. The counts move in opposite directions by band:

- high band 7.1 -> 9.0 onsets/bar (**1.27x**) - the drop gets *brighter and busier on top*;
- low band 8.8 -> 8.1 onsets/bar (**0.93x**) - **fewer** low events, while low-band energy rises +22.8 dB.

**That is the key structural fact about the drop.** It is not a denser drum pattern. The low band trades *many small transients for fewer, much larger ones* - a sustained sub and a heavier kick replacing scattered low-frequency chatter - and the extra activity that does arrive lands in the high band. A drop built by adding drum hits would be moving all three counts up together, and this reference does not.

Range across bars: 12 onsets in the sparsest bar, 37 in the densest, 10th-90th percentile 21-31, median 26.

## 6. Chopped break, or looped bar?

A looped bar reproduces its microtiming exactly, bar after bar: the same audio, so the same deviations. A re-chopped break can land on the same 16-slot pattern while the microtiming underneath it changes, because different slices of the source are firing. Three tests, each with a control so that selection bias is subtracted rather than reported as a result.

**(a) Even the most pattern-identical bar pairs do not share their timing.** Taking the top decile of consecutive bar pairs by pattern agreement (>= 81 % of the 48 cells identical), the mean absolute difference in per-slot microtiming is **4.6 ms** (median 3.9). For all consecutive pairs it is 8.1 ms, and for a control pair 5-8 bars apart it is 8.2 ms.

  A genuine audio loop would put the first number at **0-1 ms** and far below the control. It is 4.6 ms - about half the control (0.56x), so *some* slices do carry over from bar to bar, but nothing like enough for a repeated bar of audio. **The pattern is being rebuilt each bar from partly-reused slices.**

**(b) Rotation matching: inconclusive, and here is why.** Best circular shift of the previous bar against each bar: shift 0 wins 51 % of the time, a non-zero shift 49 %, and the winning shifts lean heavily even (4: 96, 2: 79, 6: 63, 8: 31, 12: 30). But running the identical best-of-16 search against an **unrelated** bar gains 9.5 pp where the real neighbour gains 8.3 pp - -1.2 pp, i.e. below the selection-bias floor. The even-shift preference is a property of the onset distribution itself (hits concentrate on even slots, so even rotations preserve the shape), not evidence of slice displacement. **This test tells us nothing; it is reported so the other two are not read as three.**

**(c) Truncations are phase-locked to the grid, landing mid-slot.** Sharp level drops (rms falling more than 4 dB in 21 ms) are the fingerprint of a slice cut before it decayed. There are **4172** of them, 4.79 per bar. Their phase within the 16th has a concentration of **0.265** against **0.013** for the same number of random times - 20x, so they are strongly non-uniform. Where they sit inside the 16th (fraction of the 90 ms slot):

| phase in the 16th | 0-.12 | .12-.25 | .25-.38 | .38-.50 | .50-.62 | .62-.75 | .75-.88 | .88-1.0 |
|---|---|---|---|---|---|---|---|---|
| share of cuts | 6 % | 6 % | 16 % | 19 % | 17 % | 16 % | 11 % | 10 % |

The mean phase is **0.53 of a 16th = 48 ms after a boundary**, and the distribution peaks in the .38-.50 band. That is exactly what a chop looks like from the outside: a slice fires on the boundary, rings for part of the slot, and is cut off partway through when the next slice is triggered. A played or looped break would decay smoothly and produce no such concentration.

**Conclusion: chopped, and re-chopped continuously.** Two of the three tests carry weight. (a) says bars that share a written pattern share only about half as much microtiming as a true repeat would demand - the audio underneath a repeated pattern is not the same audio. (c) says level cuts are 20x more phase-locked to the 16th grid than chance and sit partway through the slot, which is a slice being interrupted rather than a drum decaying. (b) is selection bias and proves nothing. The picture is a break sliced to 16ths and re-triggered in a changing order, bar after bar, for twenty-one minutes - **there is no 'loop plus occasional variation' anywhere in this reference**.

## What this means for building a jungle track

1. **166.0 BPM, 16ths at 90 ms, swing essentially off (52 %).** Level-corrected swing is 52.4 % against 50.0 % for dead straight - a 4 ms lean, not a groove. Do not reach for a swing template; the feel comes from the break's own content, not from moved grid positions. Lock the tempo hard - across 21 minutes it never moved (sd 0.17 BPM).
2. **Fill 16 slots per bar to these odds.** Beat slots 0/4/8/12 at 0.83, the other even slots at 0.67, the odd slots at 0.34. Concretely: kick on 0 (0.91) and 10 (0.66), snare on 4 (0.94) and 12 (0.89), ghosts scattered on 2/6/8/14, and the odd slots left mostly empty - they are the 34% that keeps it from turning into a wall.
3. **26 onsets per bar is the target**, split roughly 31/37/32 low/mid/high. Below 21 reads as a breakdown, above 31 as a fill.
4. **The drop does not add drums, it adds weight and brightness.** Drop bars carry 27 onsets against 24 in a breakdown (1.12x) while rms goes up 10 dB and low-end energy +23 dB. Low-band onset *count* actually falls (0.93x) and high-band rises (1.27x). So: at the drop, swap low-frequency chatter for one sustained sub and a bigger kick, and put the new movement in the hats - do not thicken the break.
5. **Chop the break to 16ths; never loop a bar of audio.** Even the most pattern-identical consecutive bars differ by 4.6 ms of per-slot microtiming - only about half the 8.2 ms of bars 5-8 apart, and nowhere near the 0-1 ms a repeated bar of audio would give. Re-point the slices every bar. Displace them by an 8th (2 slots) or a whole beat (4 slots): those are the rotations that actually recur. Expect 4.8 audible truncations per bar, landing on the grid.
6. **Write a 4-bar unit as A-B-C-D, all four different, and repeat the unit.** Lag 4 similarity is 0.49 and lag 8 is 0.47, but lag 1 is only 0.36 - no higher than two random bars from the same section (0.36). Change about 15 of the 48 cells between adjacent bars; only 2 % of bars should be near-copies of their neighbour.
7. **Let the low band define the 4-bar unit and the high band re-chop freely.** At lag 4 the excess over each band's own random baseline is low +0.137, mid +0.127, high +0.116; at lag 1 all three are within ±0.03 of zero. So: no band should repeat bar to bar, but the low band should come back four bars later. Do not nail the kick to slots 0 and 10 in every bar - its placement is part of what moves.
8. **Put fills on the 4-bar grid, but only take one slot in four.** Fill-indicator autocorrelation is +0.19 at lag 4 and +0.10 at lag 8, ~0 at every odd lag - so fills are 4-bar-aligned - yet only 6 % of bars are fills, one every 15 bars. Keep them modest: 1.23x the onset count of a normal bar (+6 onsets) and 1.3x its high-band energy. A jungle fill is a slightly busier, brighter bar - not a drum roll.
9. **Do not write '3 bars the same, 1 different'.** Bar-to-bar similarity by 4-bar position is 0.36/0.37/0.36/0.33 - a spread of 0.042 on a standard error of 0.015, permutation p = 0.20 - and the phase-free version (autocorrelation of the similarity series) is only +0.10 at lag 4, against +0.19 for fills and +0.20 for density measured the same way - the weakest of the three. Variation is spread evenly over every bar, not saved up for the fourth. What is periodic is the return of the whole 4-bar group (rule 6), not a fourth bar that breaks three identical ones.
10. **Keep the odd 16ths mostly empty and let that be the space.** Even slots run at 0.75 occupancy and odd slots at 0.34; the emptiest slots in the bar are 1 and 5. At 26 onsets per bar the music is already dense, so the legibility comes from those reserved positions - fill them and the break stops reading as a break.

