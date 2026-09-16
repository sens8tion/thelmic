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

## 9. The 16th carrier

The claim under test: *something is always carrying a 16th rhythm - usually a high filtered break, or short percussion*. Measurement only; the wav was read solely to compute envelopes and spectra (see `features48` in the script), nothing was kept but numbers. Grid: the drift-tracked grid of section 0.

### 9.1 Coverage

**Detector.** Carrier-band (1.5-16 kHz) spectral flux at 5 ms resolution, from the 48 kHz file. For every 16th, the peak flux within +-20 ms of the slot (A) is compared with the same measurement a 32nd later, between two slots (B). A slot is articulated when A >= rho x the bar's median B. A bar has a **carrier** when at least **3 of its 8 off-8th slots** are articulated and **at least 10 of 16** overall. The detector's latency (7.3 ms) is removed first; 92.5 % of carrier-band onsets land within 20 ms of the grid.

**Why 3 of 8.** A layer playing 8ths leaves the odd slots empty; a straight 16th layer fills all 8; a chopped break typically lands 3-5 of them. 3 is the brief's figure and it is *not* noise-proof on its own - at the rho used below, 3 of 8 between-slot positions spike by chance in about a quarter of bars - which is why rho is chosen against that false-alarm rate rather than fixed, and why the carrier share is also reported as a null-corrected estimate that does not depend on the rho choice. **Why 10 of 16.** It requires the layer to be continuous across the bar rather than a single roll.

**Choosing rho, and the null.** The null is the identical test run on the between-slot positions themselves: how often do 3 of 8 *between* positions spike at the same threshold? That is the false-alarm rate. Observed = c x sensitivity + (1 - c) x false-alarm, so (observed - null) / (1 - null) bounds the true carrier share c from below, and the loosest settings (where sensitivity ~ 1) give its best estimate. rho is then the setting with the smallest estimated misclassification (false alarms plus misses).

| rho | bars with carrier | odd >= 3 only | null (odd >= 3 on between-slots) | lower bound on c | est. misclassified |
|---|---|---|---|---|---|
| 1.25 | 81.9 % | 83.2 % | 47.2 % | 68.2 % | 15.0 % |
| 1.50 **(used)** | 74.5 % | 76.4 % | 26.5 % | 67.9 % | 8.7 % |
| 1.75 | 64.8 % | 67.4 % | 18.3 % | 60.1 % | 12.5 % |
| 2.00 | 56.5 % | 59.4 % | 13.5 % | 53.1 % | 17.4 % |
| 2.50 | 40.8 % | 44.8 % | 6.0 % | 41.3 % | 27.2 % |
| 3.00 | 31.3 % | 35.0 % | 3.3 % | 32.8 % | 35.3 % |

**Coverage: 74.5 % of bars** at rho = 1.5. The null-corrected estimate of the true share is **68 %**. Is it fragile?

- to the **band**: 0.7-16 kHz gives 75.7 %, 4-16 kHz gives 72.3 % - stable;
- to the **window**: judged on the mean of 2 bars 73.2 %, of 4 bars 75.5 %;
- to **rho**: yes, and the table shows exactly how. The loosest setting (false alarms 47 %) calls 82 % of bars; even the strictest (false alarms 3 %) still finds a carrier in 31 %, and there the drop is the detector losing quiet 16ths. The null-corrected share sits at 68-68 % at the two loosest settings, which is where sensitivity is closest to 1.

**Verdict on 'always':** not always, but most of the time - roughly **7 bars in 10**. The claim holds as a strong default, not as an invariant, and the gaps are not random (9.1b).

Coverage per section:

| section | start | bars | carrier | odd slots hit / bar | slots hit / bar |
|---|---|---|---|---|---|
| S1 | 0:00 | 33 | 73 % | 5.8 | 12.2 |
| S2 | 0:49 | 68 | 94 % | 6.6 | 14.4 |
| S3 | 2:28 | 67 | 70 % | 4.7 | 12.7 |
| S4 | 4:05 | 23 | 78 % | 4.6 | 12.0 |
| S5 | 4:40 | 30 | 80 % | 4.1 | 11.9 |
| S6 | 5:24 | 17 | 88 % | 5.1 | 13.1 |
| S7 | 5:49 | 38 | 61 % | 3.4 | 11.1 |
| S8 | 6:46 | 24 | 71 % | 4.0 | 11.9 |
| S9 | 7:23 | 25 | 88 % | 3.7 | 11.4 |
| S10 | 8:01 | 44 | 43 % | 2.7 | 10.4 |
| S11 | 9:06 | 39 | 54 % | 3.1 | 10.6 |
| S12 | 10:04 | 69 | 86 % | 5.8 | 13.7 |
| S13 | 11:44 | 47 | 57 % | 3.3 | 11.1 |
| S14 | 12:54 | 90 | 98 % | 6.5 | 14.3 |
| S15 | 15:05 | 19 | 63 % | 5.4 | 11.0 |
| S16 | 15:35 | 95 | 75 % | 4.5 | 11.2 |
| S17 | 17:54 | 62 | 47 % | 2.3 | 9.6 |
| S18 | 19:26 | 15 | 100 % | 4.7 | 12.7 |
| S19 | 19:50 | 47 | 85 % | 4.4 | 12.0 |

**9.1b Every stretch without a carrier** - 101 stretches, 217 bars. Length distribution: 65 x 1 bar, 18 x 2 bars, 6 x 3 bars, 3 x 4 bars, 9 longer than 4 bars. Context comes from the drop/breakdown events in `drops.md` and the record seams in `structure.md` (within 2 bars; breakdown = within the 8 bars after one).

| start | bars | section | what is happening | odd hits/bar | slots hit/bar | kicks/bar | rms dB (rel.) | low % |
|---|---|---|---|---|---|---|---|---|
| 0:00 | 2 | S1 | low end out | 1.0 | 8.0 | 0.0 | -8.2 | 2 % |
| 0:37 | 7 | S1 | low end out | 0.4 | 1.3 | 0.0 | -9.2 | 3 % |
| 1:16 | 1 | S2 | breakdown | 2.0 | 9.0 | 3.0 | -3.1 | 8 % |
| 1:22 | 1 | S2 | breakdown | 2.0 | 8.0 | 3.0 | -2.8 | 5 % |
| 1:26 | 1 | S2 | groove | 2.0 | 10.0 | 3.0 | -0.5 | 10 % |
| 2:21 | 1 | S2 | breakdown | 2.0 | 10.0 | 8.0 | -2.3 | 8 % |
| 2:28 | 1 | S3 | breakdown | 2.0 | 10.0 | 8.0 | -2.1 | 15 % |
| 2:34 | 4 | S3 | groove | 1.8 | 9.8 | 2.5 | -4.3 | 10 % |
| 2:44 | 14 | S3 | drop | 1.2 | 8.9 | 5.4 | -1.8 | 10 % |
| 3:26 | 1 | S3 | groove | 2.0 | 10.0 | 2.0 | +1.6 | 22 % |
| 4:25 | 1 | S4 | breakdown | 2.0 | 10.0 | 2.0 | -2.2 | 14 % |
| 4:30 | 2 | S4 | breakdown | 1.5 | 8.5 | 1.5 | -4.2 | 7 % |
| 4:35 | 2 | S4 | drop + breakdown | 1.5 | 5.0 | 1.5 | -1.9 | 5 % |
| 4:41 | 1 | S5 | groove | 1.0 | 9.0 | 5.0 | +4.7 | 20 % |
| 4:44 | 1 | S5 | groove | 1.0 | 8.0 | 3.0 | +4.3 | 20 % |
| 4:53 | 1 | S5 | drop | 2.0 | 9.0 | 3.0 | +4.7 | 20 % |
| 4:56 | 1 | S5 | groove | 1.0 | 9.0 | 5.0 | +4.4 | 20 % |
| 4:59 | 1 | S5 | groove | 2.0 | 10.0 | 3.0 | +4.6 | 20 % |
| 5:16 | 1 | S5 | drop | 2.0 | 10.0 | 4.0 | +4.7 | 18 % |
| 5:43 | 1 | S6 | low end out | 2.0 | 10.0 | 1.0 | -4.0 | 3 % |
| 5:46 | 1 | S6 | low end out | 2.0 | 10.0 | 1.0 | -4.4 | 2 % |
| 6:11 | 2 | S7 | groove | 1.5 | 9.5 | 0.5 | -1.6 | 7 % |
| 6:15 | 1 | S7 | groove | 2.0 | 10.0 | 4.0 | -0.6 | 7 % |
| 6:18 | 1 | S7 | groove | 1.0 | 9.0 | 2.0 | -0.3 | 7 % |
| 6:22 | 2 | S7 | groove | 2.0 | 9.5 | 1.5 | -1.8 | 6 % |
| 6:27 | 2 | S7 | groove | 2.0 | 9.0 | 2.5 | -0.5 | 8 % |
| 6:34 | 2 | S7 | groove | 1.0 | 5.5 | 1.5 | +0.4 | 8 % |
| 6:38 | 7 | S7 | groove | 0.7 | 8.1 | 2.6 | -0.9 | 13 % |
| 6:51 | 2 | S8 | groove | 1.5 | 9.5 | 3.5 | +0.6 | 9 % |
| 6:55 | 3 | S8 | groove | 1.3 | 8.7 | 3.3 | -0.4 | 9 % |
| 7:44 | 1 | S9 | low end out | 4.0 | 7.0 | 0.0 | -7.6 | 3 % |
| 7:54 | 2 | S9 | groove | 2.0 | 9.5 | 2.0 | +3.2 | 13 % |
| 8:01 | 1 | S10 | groove | 2.0 | 10.0 | 2.0 | +1.8 | 11 % |
| 8:04 | 9 | S10 | groove | 1.8 | 9.6 | 2.3 | +1.9 | 16 % |
| 8:20 | 3 | S10 | groove | 2.0 | 9.7 | 2.7 | +3.3 | 17 % |
| 8:26 | 4 | S10 | groove | 1.2 | 8.2 | 2.2 | +1.6 | 15 % |
| 8:40 | 3 | S10 | groove | 2.0 | 9.7 | 2.3 | +2.5 | 12 % |
| 8:46 | 1 | S10 | groove | 2.0 | 8.0 | 3.0 | +3.9 | 17 % |
| 8:50 | 3 | S10 | groove | 0.7 | 8.0 | 1.3 | +2.9 | 14 % |
| 8:59 | 1 | S10 | groove | 2.0 | 10.0 | 1.0 | +4.5 | 19 % |
| 9:06 | 2 | S11 | mix seam + breakdown | 2.0 | 9.5 | 2.5 | -3.4 | 2 % |
| 9:18 | 1 | S11 | drop + breakdown | 2.0 | 10.0 | 4.0 | +1.4 | 11 % |
| 9:21 | 2 | S11 | drop | 1.0 | 8.0 | 2.0 | -2.2 | 8 % |
| 9:29 | 1 | S11 | groove | 2.0 | 10.0 | 5.0 | +1.0 | 12 % |
| 9:34 | 6 | S11 | groove | 1.3 | 8.8 | 3.0 | -0.0 | 11 % |
| 9:44 | 1 | S11 | groove | 2.0 | 10.0 | 4.0 | +1.5 | 15 % |
| 9:52 | 1 | S11 | groove | 1.0 | 9.0 | 6.0 | +0.3 | 11 % |
| 9:57 | 4 | S11 | mix seam + breakdown | 1.0 | 6.8 | 3.0 | -0.5 | 10 % |
| 10:24 | 1 | S12 | groove | 1.0 | 8.0 | 0.0 | -0.0 | 24 % |
| 10:47 | 1 | S12 | breakdown | 1.0 | 5.0 | 0.0 | -9.3 | 2 % |
| 11:10 | 1 | S12 | groove | 2.0 | 10.0 | 2.0 | -0.3 | 20 % |
| 11:15 | 1 | S12 | groove | 2.0 | 10.0 | 1.0 | -0.4 | 13 % |
| 11:21 | 1 | S12 | groove | 2.0 | 10.0 | 1.0 | -0.1 | 14 % |
| 11:32 | 5 | S12 | drop | 1.2 | 9.2 | 1.4 | +0.1 | 13 % |
| 11:45 | 1 | S13 | groove | 1.0 | 9.0 | 2.0 | +1.0 | 19 % |
| 11:48 | 8 | S13 | drop + breakdown | 1.5 | 8.9 | 1.0 | -2.9 | 13 % |
| 12:01 | 1 | S13 | drop + breakdown | 2.0 | 10.0 | 2.0 | -0.8 | 13 % |
| 12:07 | 2 | S13 | groove | 1.5 | 9.5 | 2.0 | +0.4 | 16 % |
| 12:13 | 1 | S13 | groove | 1.0 | 9.0 | 1.0 | -1.1 | 13 % |
| 12:18 | 1 | S13 | groove | 1.0 | 9.0 | 2.0 | -1.0 | 11 % |
| 12:24 | 1 | S13 | drop | 0.0 | 8.0 | 2.0 | -0.1 | 16 % |
| 12:30 | 1 | S13 | groove | 0.0 | 8.0 | 2.0 | -0.6 | 14 % |
| 12:34 | 2 | S13 | groove | 1.0 | 9.0 | 3.5 | -1.1 | 15 % |
| 12:41 | 1 | S13 | groove | 0.0 | 8.0 | 2.0 | -0.4 | 13 % |
| 12:44 | 1 | S13 | low end out | 2.0 | 6.0 | 0.0 | -5.2 | 1 % |
| 13:08 | 1 | S14 | drop | 0.0 | 5.0 | 0.0 | -15.3 | 5 % |
| 14:40 | 1 | S14 | mix seam | 0.0 | 0.0 | 0.0 | -8.4 | 2 % |
| 15:07 | 1 | S15 | drop + breakdown | 5.0 | 9.0 | 2.0 | -0.9 | 19 % |
| 15:10 | 1 | S15 | groove | 5.0 | 8.0 | 1.0 | -1.5 | 17 % |
| 15:13 | 1 | S15 | groove | 4.0 | 6.0 | 0.0 | -0.8 | 19 % |
| 15:18 | 1 | S15 | breakdown | 2.0 | 10.0 | 0.0 | -4.6 | 10 % |
| 15:24 | 2 | S15 | breakdown | 2.0 | 7.0 | 0.0 | -3.1 | 2 % |
| 15:33 | 2 | S15 | drop | 4.0 | 8.5 | 1.0 | -0.1 | 8 % |
| 15:41 | 1 | S16 | groove | 1.0 | 6.0 | 2.0 | +1.3 | 15 % |
| 15:44 | 1 | S16 | groove | 2.0 | 6.0 | 4.0 | +1.0 | 15 % |
| 15:47 | 1 | S16 | groove | 3.0 | 8.0 | 2.0 | +1.1 | 15 % |
| 15:50 | 1 | S16 | groove | 2.0 | 10.0 | 3.0 | +1.1 | 16 % |
| 15:53 | 1 | S16 | groove | 2.0 | 8.0 | 3.0 | +1.7 | 17 % |
| 15:56 | 1 | S16 | groove | 3.0 | 9.0 | 5.0 | +1.2 | 15 % |
| 16:20 | 1 | S16 | groove | 2.0 | 6.0 | 1.0 | -3.4 | 6 % |
| 16:39 | 1 | S16 | groove | 4.0 | 9.0 | 2.0 | +1.1 | 14 % |
| 16:56 | 1 | S16 | groove | 3.0 | 9.0 | 1.0 | +1.4 | 12 % |
| 17:02 | 1 | S16 | groove | 3.0 | 9.0 | 2.0 | -0.1 | 8 % |
| 17:07 | 1 | S16 | drop | 1.0 | 6.0 | 0.0 | -8.2 | 1 % |
| 17:11 | 1 | S16 | groove | 2.0 | 9.0 | 0.0 | +2.8 | 15 % |
| 17:15 | 1 | S16 | groove | 3.0 | 8.0 | 0.0 | +2.5 | 17 % |
| 17:18 | 2 | S16 | groove | 2.5 | 8.5 | 0.0 | +2.5 | 17 % |
| 17:34 | 6 | S16 | breakdown | 0.2 | 5.5 | 0.0 | +1.4 | 20 % |
| 17:44 | 1 | S16 | breakdown | 2.0 | 7.0 | 0.0 | -6.8 | 1 % |
| 17:53 | 24 | S16 | mix seam + drop + breakdown | 0.5 | 6.9 | 1.0 | +1.0 | 29 % |
| 18:30 | 3 | S17 | breakdown | 0.3 | 8.3 | 0.0 | +0.2 | 22 % |
| 18:36 | 3 | S17 | breakdown | 2.0 | 7.7 | 1.3 | -2.2 | 21 % |
| 18:45 | 1 | S17 | drop + breakdown | 2.0 | 10.0 | 1.0 | +0.4 | 18 % |
| 18:48 | 1 | S17 | groove | 0.0 | 8.0 | 0.0 | +0.4 | 18 % |
| 18:54 | 1 | S17 | groove | 1.0 | 9.0 | 0.0 | +0.4 | 17 % |
| 18:56 | 1 | S17 | groove | 1.0 | 9.0 | 0.0 | +0.5 | 16 % |
| 19:50 | 2 | S19 | drop | 3.0 | 8.5 | 0.5 | -2.1 | 27 % |
| 19:59 | 2 | S19 | groove | 3.0 | 7.5 | 0.0 | -1.5 | 18 % |
| 20:22 | 1 | S19 | breakdown | 2.0 | 10.0 | 2.0 | -1.3 | 9 % |
| 20:35 | 1 | S19 | low end out | 0.0 | 2.0 | 0.0 | -12.3 | 1 % |
| 20:38 | 1 | S19 | groove | 2.0 | 10.0 | 0.0 | -2.4 | 8 % |

Bars without a carrier, by context: groove 103 (47 %); drop 30 (14 %); breakdown 25 (12 %); mix seam + drop + breakdown 24 (11 %); low end out 14 (6 %); drop + breakdown 14 (6 %); mix seam + breakdown 6 (3 %); mix seam 1 (0 %).

Reading: 82 % of the gaps are 1-2 bars - a fill, a stop or a thin bar inside a running carrier, not an absence. 47 % of the carrier-less bars sit in plain groove with no event nearby; the rest cluster at drops, breakdowns, seams and low-end-out passages.

### 9.2 What carries it

Measured on the **odd-slot hits** of carrier bars (the positions only a 16th layer plays). Each hit's own spectrum is isolated by subtracting the frame before it (attack spectrum), so sustained pads and a held sub drop out.

- **shape r**: mean correlation between the 1/3-octave shapes of two random hits. Uniform percussion is one sound repeated; a break's slices are snare edge, ghost, hat, ride - mixed.
- **centroid spread**: sd of log2 centroid between hits, in octaves.
- **level sd**: accent spread between hits, dB. Breaks accent; programmed shakers don't.
- **decay**: ms for the carrier band to give back half its rise. **ring**: share of the rise still standing 50-80 ms later, just before the next 16th (0 = fully decayed).
- **low content**: attack energy 125-500 Hz relative to 1-4 kHz. **corner**: where the averaged attack spectrum falls 12 dB below its 1-4 kHz plateau (9.3).
- **flatness**: spectral flatness within an octave of the centroid (1 = noise, 0 = pitched).

Class rules (in `classify_carrier`): *uniform* (shape r >= 0.35 and level sd <= 2.5 dB) -> short percussion; otherwise a break, **high-passed** when the corner is >= 250 Hz, **full-range** when there is no corner above 125 Hz, and a partial low-cut in between is called by the nearer side (180 Hz) at low confidence. The boundaries come from the kick register: the kick's body lives at 60-250 Hz (bass.md), so a break whose hits have lost 12 dB by 250 Hz no longer carries a kick, and one still within 12 dB at 125 Hz does. The corner is taken from the **median** hit shape - averaging power instead lets the few odd-slot hits that coincide with a bass-note onset own every low band.

| sec | start | carrier | conf. | deciding evidence | hits | shape r | centroid spread oct | level sd dB | decay ms | ring | low content dB | corner Hz | centroid Hz | flatness |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S1 | 0:00 | **short percussion** | high | uniform (shape r 0.40, level sd 0.5 dB): hats / shakers | 188 | 0.40 | 0.75 | 0.5 | 15 | -0.05 | -6.5 | 319 | 5541 | 0.53 |
| S2 | 0:49 | **full-range break** | low | corner 116 Hz | 441 | 0.05 | 1.23 | 1.9 | 20 | -0.22 | +0.1 | 116 | 2568 | 0.20 |
| S3 | 2:28 | **high-passed break** | low | partial low-cut, corner 208 Hz | 288 | 0.03 | 1.02 | 4.9 | 20 | -0.60 | +0.8 | 208 | 1528 | 0.10 |
| S4 | 4:05 | **high-passed break** | low | corner 270 Hz | 97 | 0.06 | 0.99 | 5.1 | 15 | -0.61 | -4.2 | 270 | 1651 | 0.07 |
| S5 | 4:40 | **high-passed break** | low | corner 263 Hz | 114 | 0.28 | 0.79 | 3.7 | 20 | -0.55 | -2.2 | 263 | 1036 | 0.15 |
| S6 | 5:24 | **high-passed break** | low | corner 308 Hz | 83 | 0.05 | 0.93 | 4.9 | 15 | -0.23 | -5.5 | 308 | 1968 | 0.14 |
| S7 | 5:49 | **high-passed break** | low | partial low-cut, corner 222 Hz | 112 | 0.29 | 0.81 | 2.3 | 20 | -0.35 | -2.0 | 222 | 917 | 0.16 |
| S8 | 6:46 | **full-range break** | low | partial low-cut, corner 164 Hz | 87 | 0.16 | 0.91 | 4.3 | 20 | -0.29 | +3.5 | 164 | 887 | 0.22 |
| S9 | 7:23 | **full-range break** | medium | corner 84 Hz | 84 | 0.24 | 0.95 | 3.8 | 25 | -0.18 | +9.4 | 84 | 558 | 0.19 |
| S10 | 8:01 | **full-range break** | medium | corner 84 Hz | 78 | 0.23 | 1.07 | 4.4 | 22 | -0.53 | +11.8 | 84 | 465 | 0.15 |
| S11 | 9:06 | **full-range break** | medium | corner 122 Hz | 93 | 0.23 | 0.83 | 3.8 | 25 | -0.40 | +6.4 | 122 | 640 | 0.28 |
| S12 | 10:04 | **full-range break** | medium | corner 83 Hz | 385 | 0.09 | 1.04 | 3.9 | 15 | -0.62 | +8.7 | 83 | 885 | 0.12 |
| S13 | 11:44 | **full-range break** | low | partial low-cut, corner 179 Hz | 131 | 0.15 | 1.08 | 3.7 | 25 | -0.40 | -0.5 | 179 | 1186 | 0.21 |
| S14 | 12:54 | **full-range break** | low | partial low-cut, corner 153 Hz | 584 | 0.07 | 0.89 | 4.1 | 20 | -0.25 | -1.0 | 153 | 1819 | 0.15 |
| S15 | 15:05 | **full-range break** | low | partial low-cut, corner 153 Hz | 76 | 0.11 | 0.85 | 3.2 | 20 | -0.04 | -3.3 | 153 | 1228 | 0.24 |
| S16 | 15:35 | **full-range break** | medium | corner 85 Hz | 390 | 0.10 | 0.86 | 3.3 | 15 | -0.00 | +3.7 | 85 | 1008 | 0.14 |
| S17 | 17:54 | **full-range break** | low | partial low-cut, corner 151 Hz | 120 | 0.38 | 0.68 | 3.0 | 30 | -0.34 | +4.3 | 151 | 1076 | 0.16 |
| S18 | 19:26 | **short percussion** | medium | uniform (shape r 0.35, level sd 1.8 dB): congas / woodblock | 71 | 0.35 | 0.72 | 1.8 | 25 | -0.29 | +4.4 | 182 | 1320 | 0.16 |
| S19 | 19:50 | **high-passed break** | low | partial low-cut, corner 197 Hz | 193 | 0.17 | 0.74 | 4.7 | 20 | -0.44 | +2.6 | 197 | 1439 | 0.12 |

By bars: full-range break 68 %, high-passed break 26 %, short percussion 6 %.

**Read the labels with the corners next to them.** Every section's corner lies between 83 and 319 Hz. So 'high-passed break' here means a break with its kick and bass register trimmed out (corners around 200-300 Hz, in the records running 2:28-6:46 and at 19:50), and 'full-range break' means one that keeps body down to about 80-180 Hz. **No section's carrier is a thin, 1 kHz-plus filtered break.** The one genuinely high carrier is S1 (0:00-0:49), the high-passed breaks-only mix-in: centroid 5.5 kHz, uniform, level spread 0.5 dB - classed as short percussion (hats/shakers), though a very steadily played, heavily filtered break would look the same to these measures. Most calls are low-to-medium confidence: in a full mix the odd-slot hits carry everything that attacks there, not only the carrier.

What does **not** separate them: decay and ring. Every section's odd-slot hits give back half their rise in 15-30 ms and have decayed to the pre-hit floor before the next 16th (ring -0.62 to -0.00). That is itself a finding: whatever carries the 16ths is **cut short** - slices chopped to the 16th, or short hits - never a ringing slice that overlaps the next. What does separate them is uniformity and low content.

### 9.3 The filter

For breaks, the corner is where the median attack spectrum of the carrier's odd-slot hits falls 12 dB below its 1-4 kHz plateau. It is measured twice: over all carrier bars of the section, and - as asked - only over bars with **no detected kick and the low end out** (under 5 % of the spectrum below 120 Hz), where nothing else can fill the low end of the attack spectrum.

| sec | start | carrier | corner, all carrier bars | kick- and bass-free bars | corner, kick/bass-free |
|---|---|---|---|---|---|
| S2 | 0:49 | full-range break | 116 Hz | 5 | 195 Hz |
| S3 | 2:28 | high-passed break | 208 Hz | 2 | 261 Hz |
| S4 | 4:05 | high-passed break | 270 Hz | 4 | 268 Hz |
| S5 | 4:40 | high-passed break | 263 Hz | 0 | too few bars |
| S6 | 5:24 | high-passed break | 308 Hz | 1 | too few bars |
| S7 | 5:49 | high-passed break | 222 Hz | 0 | too few bars |
| S8 | 6:46 | full-range break | 164 Hz | 1 | too few bars |
| S9 | 7:23 | full-range break | 84 Hz | 1 | too few bars |
| S10 | 8:01 | full-range break | 84 Hz | 1 | too few bars |
| S11 | 9:06 | full-range break | 122 Hz | 2 | too few bars |
| S12 | 10:04 | full-range break | 83 Hz | 3 | 112 Hz |
| S13 | 11:44 | full-range break | 179 Hz | 6 | 199 Hz |
| S14 | 12:54 | full-range break | 153 Hz | 9 | 121 Hz |
| S15 | 15:05 | full-range break | 153 Hz | 8 | 191 Hz |
| S16 | 15:35 | full-range break | 85 Hz | 11 | 168 Hz |
| S17 | 17:54 | full-range break | 151 Hz | 4 | 107 Hz |
| S19 | 19:50 | high-passed break | 197 Hz | 6 | 136 Hz |

The kick- and bass-free bars are few (0-11 per section) but agree with the all-bars corners to within about half an octave, so the low end of the median hit is the carrier's own, not bleed from kick or sub.

Corner (Hz) around every major/mid drop in `drops.md` - the 8 bars before, the first 8 bars of the drop, and the 8 after that. 'open' = no fall of 12 dB above 45 Hz.

| drop | 8 bars before | drop bars 1-8 | drop bars 9-16 |
|---|---|---|---|
| 0:49 | open | 100 | 112 |
| 1:45 | 140 | 195 | 163 |
| 2:42 | 268 | open | open |
| 3:08 | 377 | 220 | 247 |
| 4:37 | 272 | 261 | 263 |
| 5:49 | 320 | 220 | 256 |
| 7:22 | 168 | 121 | 84 |
| 9:18 | 129 | 136 | open |
| 12:00 | open | 185 | 183 |
| 12:23 | 183 | 184 | 171 |
| 14:18 | 163 | 147 | 128 |
| 15:07 | 92 | open | 156 |
| 15:32 | 190 | 153 | 90 |
| 17:08 | 86 | 147 | 165 |
| 17:54 | 167 | open | open |
| 18:43 | 162 | 168 | 147 |
| 19:50 | open | 264 | 183 |

Across 17 drops the corner **opens** (falls by more than half an octave) into the drop 4 times, **closes** 4 times, and holds within half an octave 9 times. Median corner before 167 Hz, at the drop 176 Hz, after 164 Hz (NaN-free medians over the drops where a corner exists).

**The filter does not open at the drop.** Openings and closings are equally common and the median corner is the same before, at and after. The drop is not delivered by sweeping the break's high-pass down; the low end arrives from the kick and sub (drops.md: sub +10 dB) while the carrier keeps its own low-cut.

### 9.4 Stacking at the drop

For each major/mid drop: does the carrier's 16th pattern and timbre carry through, or is it replaced? Pattern r = correlation of the 16-slot carrier occupancy over the 8 bars before vs the first 8 of the drop; its baseline is the split-half r inside each window (what 'unchanged' looks like). Timbre = RMS dB difference of the odd-slot attack shape (plateau-relative, 250 Hz-15 kHz), with its split-half baseline. Level = carrier hit level change. Mid onsets = snare/body onsets per bar from section 1 (a full-range break arriving shows here).

| drop | pattern r | baseline r | timbre diff dB | baseline dB | carrier level dB | low content dB | mid onsets/bar | carrier bars | verdict |
|---|---|---|---|---|---|---|---|---|---|
| 1:45 | -0.07 | 0.94 | 7.5 | 5.9 | -1.9 | -0.0 | -0.2 | 100% -> 100% | **timbre kept, pattern changed** |
| 2:42 | 0.88 | 0.93 | 2.3 | 3.2 | +1.4 | +0.4 | +0.6 | 50% -> 12% | **continues** |
| 3:08 | 0.87 | 0.86 | 3.6 | 3.6 | -3.2 | +6.8 | -0.4 | 25% -> 100% | **continues** |
| 4:37 | 0.77 | 0.78 | 8.6 | 12.3 | +4.8 | +8.9 | +1.8 | 50% -> 62% | **continues** |
| 5:49 | 0.93 | 0.66 | 7.5 | 9.4 | +1.6 | +4.1 | +2.0 | 75% -> 100% | **continues** |
| 7:22 | 0.34 | 0.98 | 5.5 | 4.8 | -2.6 | +5.7 | -1.0 | 100% -> 100% | **timbre kept, pattern changed** |
| 9:18 | 0.94 | 0.47 | 4.2 | 4.0 | -4.3 | +1.2 | +1.6 | 75% -> 62% | **continues** |
| 12:00 | 0.90 | 0.95 | 5.1 | 2.0 | +2.3 | -1.8 | +1.8 | 0% -> 62% | **pattern kept, timbre changed** |
| 12:23 | 0.89 | 0.89 | 6.2 | 7.3 | -3.9 | +6.7 | +0.2 | 75% -> 75% | **continues** |
| 14:18 | 0.53 | 0.68 | 3.4 | 4.5 | +0.3 | +0.3 | +1.2 | 100% -> 100% | **timbre kept, pattern changed** |
| 15:07 | -0.27 | 0.72 | 3.5 | 2.7 | -6.4 | +3.3 | -3.1 | 100% -> 62% | **timbre kept, pattern changed** |
| 15:32 | 0.08 | 0.07 | 3.3 | 5.5 | +4.1 | +5.9 | +3.5 | 75% -> 50% | **continues** |
| 17:08 | 0.54 | 0.62 | 3.4 | 5.8 | +0.7 | +0.6 | +0.8 | 62% -> 62% | **continues** |
| 18:43 | 0.96 | 0.76 | 5.8 | - | +2.8 | +0.6 | +1.6 | 38% -> 62% | **pattern kept, timbre changed** |
| 19:50 | -0.10 | 0.78 | 5.5 | 3.9 | -5.2 | -2.4 | -2.6 | 100% -> 50% | **timbre kept, pattern changed** |

Tally: continues 8, timbre kept, pattern changed 5, pattern kept, timbre changed 2 (of 15 measurable drops).

**It stacks; it is not replaced.** 0 of 15 drops replace the carrier outright, and 15 keep at least its pattern or its timbre. The carrier's hit level changes by a median +0.3 dB (range -6.4 to +4.8) - it neither ducks under the drop nor rides over it - while its odd-slot hits gain a median +1.2 dB of 125-500 Hz body, above +3 dB at 7 drops: full-range material joins underneath the 16th layer rather than taking over from it. Timbre verdicts are the weaker half of this test - the split-half baselines are 2-12 dB, because 4 bars hold few odd-slot hits.

### 9.5 Does the carrier change character per section?

Each section's mean odd-slot attack shape (plateau-relative dB, 250 Hz-15 kHz). 'Within' is the split-half distance inside the section (first half of its hits vs second half): how much the same carrier wanders. 'To previous' is the distance to the previous section's carrier. A ratio of 2 or more, with at least 2 dB, is a change of character.

| sec | start | carrier | within dB | to previous dB | ratio | changed | corner Hz | centroid Hz |
|---|---|---|---|---|---|---|---|---|
| S1 | 0:00 | short percussion | 4.5 | - | - | - | 319 | 5541 |
| S2 | 0:49 | full-range break | 5.3 | 4.8 | 1.0 | no | 116 | 2568 |
| S3 | 2:28 | high-passed break | 3.3 | 3.9 | 0.9 | no | 208 | 1528 |
| S4 | 4:05 | high-passed break | 5.1 | 3.6 | 0.9 | no | 270 | 1651 |
| S5 | 4:40 | high-passed break | 2.8 | 7.0 | 1.8 | no | 263 | 1036 |
| S6 | 5:24 | high-passed break | 5.9 | 8.3 | 1.9 | no | 308 | 1968 |
| S7 | 5:49 | high-passed break | 3.7 | 7.7 | 1.6 | no | 222 | 917 |
| S8 | 6:46 | full-range break | 4.4 | 4.4 | 1.1 | no | 164 | 887 |
| S9 | 7:23 | full-range break | 4.1 | 2.6 | 0.6 | no | 84 | 558 |
| S10 | 8:01 | full-range break | 2.8 | 1.5 | 0.4 | no | 84 | 465 |
| S11 | 9:06 | full-range break | 4.7 | 2.9 | 0.8 | no | 122 | 640 |
| S12 | 10:04 | full-range break | 5.5 | 4.5 | 0.9 | no | 83 | 885 |
| S13 | 11:44 | full-range break | 3.4 | 4.1 | 0.9 | no | 179 | 1186 |
| S14 | 12:54 | full-range break | 2.3 | 4.1 | 1.4 | no | 153 | 1819 |
| S15 | 15:05 | full-range break | 2.7 | 4.4 | 1.8 | no | 153 | 1228 |
| S16 | 15:35 | full-range break | 1.8 | 5.4 | 2.4 | **yes** | 85 | 1008 |
| S17 | 17:54 | full-range break | 4.6 | 4.4 | 1.4 | no | 151 | 1076 |
| S18 | 19:26 | short percussion | 1.4 | 2.7 | 0.9 | no | 182 | 1320 |
| S19 | 19:50 | high-passed break | 4.1 | 1.8 | 0.7 | no | 197 | 1439 |

**1 of 18** section boundaries change the carrier's character by that test - but read the 'within' column: a carrier wanders 1.4-5.9 dB inside one section, as far as it moves between neighbours, so section-to-section shape distance is too noisy to see a change. The corner and centroid are steadier, and they do move - by **record** (the 9 records of structure.md):

| record | start | bars | carrier | corner | centroid | low content dB | shape r | level sd dB |
|---|---|---|---|---|---|---|---|---|
| T0 | 0:00 | 129 | 75 % | 132 Hz | 2854 Hz | -1.0 | 0.13 | 2.9 |
| T1 | 3:08 | 45 | 98 % | 197 Hz | 1518 Hz | +1.2 | 0.03 | 4.5 |
| T2 | 4:14 | 126 | 72 % | 235 Hz | 1195 Hz | -2.5 | 0.13 | 4.3 |
| T3 | 7:22 | 70 | 59 % | 84 Hz | 518 Hz | +11.0 | 0.21 | 4.1 |
| T4 | 9:06 | 39 | 56 % | 111 Hz | 661 Hz | +6.4 | 0.20 | 4.5 |
| T5 | 10:04 | 190 | 83 % | 130 Hz | 1372 Hz | +2.1 | 0.04 | 4.0 |
| T6 | 14:42 | 129 | 76 % | 87 Hz | 1075 Hz | +3.1 | 0.10 | 3.6 |
| T7 | 17:54 | 62 | 47 % | 151 Hz | 1076 Hz | +4.3 | 0.38 | 3.0 |
| T8 | 19:27 | 62 | 89 % | 191 Hz | 1409 Hz | +3.2 | 0.23 | 4.1 |

Is the character a property of the record? Only partly. Across sections, the corner spreads 0.51 octaves (sd) *inside* a record and 0.55 octaves *between* record means; the centroid 0.57 inside against 0.72 between. Records differ (between > within), but sections within one record move nearly as much. The one contrast that stands clear of that noise is between the trimmed breaks of 3:08-7:22 (corner ~200-235 Hz, centroid 1.2-1.5 kHz, low content -2.5 to +1.2 dB) and the body-heavy 16ths of 7:22-10:04 (corner 84-111 Hz, centroid 0.5-0.7 kHz, low content +6 to +11 dB) - the stretch that also carries the programmed two-step kick (section 10). Where the character does change, the carrier change points of 9.6 mark it, since their bar vector includes the timbre coordinates.

### 9.6 Sub-sections: where the carrier changes

Bar vector: carrier present (weight 2), the 16-slot articulation pattern, and two timbre coordinates (median log-centroid and low content of the bar's hits, z-scored, weight 0.5). Exact optimal partition (dynamic programming), minimum segment 2 bars. The penalty is **calibrated, not chosen**: beta = the smallest value at which bar-shuffled data averages <= 1 change point (shuffles: beta 0.25 -> 186.0, beta 0.35 -> 98.5, beta 0.5 -> 38.2, beta 0.7 -> 9.0, beta 1.0 -> 0.8, beta 1.4 -> 0.0, beta 2.0 -> 0.0, beta 2.8 -> 0.0). Chosen beta = **1.0**.

**23 carrier sub-sections.** Lengths in bars: median 32, quartiles 15-60, range 2-95. Distribution: 2-3: 1, 4-7: 2, 8-15: 3, 16-31: 5, 32-63: 8, 64-999: 4.

**Stability inside a sub-section.** Carrier present/absent matches the segment's modal state in **84 %** of bars (random segment placement with the same lengths: 77 %, p = 0.000). The 16-slot articulation pattern matches the segment's modal pattern to within 2 slots in **59 %** of bars (null 49 %, p = 0.000).

As a distribution, the carrier's 16-slot articulation profile correlates **r = 0.76** between the halves of a sub-section and **r = 0.53** across a boundary.

**Do the change points land on phrase lines?** Two tests. *Lengths*: interior sub-section lengths that are exact multiples of the phrase (phase-free). *Anchored*: bars from the nearest drop, breakdown or seam in the same record (excluding one that coincides with the change point) on the phrase lattice, exactly and within +-1 bar.

| phrase | lengths on it | chance | anchored, exact | chance | anchored, +-1 bar | chance | change points tested |
|---|---|---|---|---|---|---|---|
| 4 bars | 24 % (5/21), p = 0.63 | 25.0 % | 18 %, p = 0.84 | 25.0 % | 68 %, p = 0.84 | 75.0 % | 22 |
| 8 bars | 24 % (5/21), p = 0.11 | 12.5 % | 14 %, p = 0.53 | 12.5 % | 45 %, p = 0.29 | 37.5 % | 22 |
| 16 bars | 14 % (3/21), p = 0.14 | 6.2 % | 9 %, p = 0.40 | 6.2 % | 23 %, p = 0.40 | 18.8 % | 22 |
| 32 bars | 10 % (2/21), p = 0.14 | 3.1 % | 0 %, p = 1.00 | 3.1 % | 5 %, p = 0.89 | 9.4 % | 22 |

Lift over chance (lengths / anchored exact): 4: 1.0x / 0.7x; 8: 1.9x / 1.1x; 16: 2.3x / 1.5x; 32: 3.0x / 0.0x. p = one-sided binomial probability of doing at least that well by chance. Change points are only located to about a bar (a pattern that is re-dealt every bar has no sharp edge), so the exact tests are harsh; the +-1 bar column is the fair one.

Carrier sub-sections:

| seg | start | bars | carrier bars | type | conf. | evidence |
|---|---|---|---|---|---|---|
| 0 | 0:00 | 2 | 0 % | none | - | carrier in 0% of bars |
| 1 | 0:02 | 24 | 100 % | short percussion | high | uniform (shape r 0.40, level sd 0.5 dB): hats / shakers |
| 2 | 0:37 | 7 | 0 % | none | - | carrier in 0% of bars |
| 3 | 0:49 | 63 | 95 % | full-range break | low | corner 116 Hz |
| 4 | 2:20 | 16 | 62 % | high-passed break | low | corner 251 Hz |
| 5 | 2:44 | 14 | 0 % | none | - | carrier in 0% of bars |
| 6 | 3:04 | 58 | 97 % | high-passed break | low | partial low-cut, corner 222 Hz |
| 7 | 4:30 | 22 | 59 % | high-passed break | low | corner 263 Hz |
| 8 | 5:02 | 46 | 93 % | high-passed break | low | partial low-cut, corner 249 Hz |
| 9 | 6:11 | 33 | 33 % | none | - | carrier in 33% of bars |
| 10 | 7:00 | 34 | 97 % | full-range break | low | partial low-cut, corner 127 Hz |
| 11 | 7:51 | 89 | 49 % | none | - | carrier in 49% of bars |
| 12 | 10:04 | 61 | 92 % | full-range break | medium | corner 83 Hz |
| 13 | 11:32 | 18 | 22 % | none | - | carrier in 22% of bars |
| 14 | 12:00 | 32 | 66 % | high-passed break | low | partial low-cut, corner 182 Hz |
| 15 | 12:46 | 95 | 98 % | full-range break | low | partial low-cut, corner 154 Hz |
| 16 | 15:07 | 19 | 63 % | full-range break | low | partial low-cut, corner 153 Hz |
| 17 | 15:37 | 14 | 50 % | full-range break | low | corner 85 Hz |
| 18 | 15:57 | 67 | 87 % | full-range break | medium | corner 85 Hz |
| 19 | 17:34 | 8 | 12 % | none | - | carrier in 12% of bars |
| 20 | 17:46 | 5 | 100 % | full-range break | low | partial low-cut, corner 168 Hz |
| 21 | 17:53 | 32 | 6 % | none | - | carrier in 6% of bars |
| 22 | 18:41 | 93 | 88 % | full-range break | medium | corner 77 Hz |

### What this means for building a jungle track (carrier)

1. Keep a 16th layer running in about **68-75 % of bars** - at least 3 of the 8 off-8th slots, 10+ of 16 slots - and take it out on purpose, mostly for 1-2 bars at a time (82 % of gaps).
2. Cut every carrier hit short: the reference's odd-slot hits are back at their floor before the next 16th in every section. No ringing slices overlapping.
3. Change the carrier's pattern and timbre as blocks: sub-sections of median 32 bars, not bar by bar.

## 10. Kick pattern per section

The claim under test: *sometimes 80-120 Hz is filled by a kick four on the floor, sometimes none, sometimes rare syncopated; sometimes the kick is on a two-step like DnB; and the pattern only changes at sub-section boundaries.*

### 10.1 Isolating kicks from bass notes

Section 1's low band (20-160 Hz) mixes kick and bass. Here a **kick** is a low-mid transient (superflux in the 140-234 Hz FFT bins, which a sub note below 60 Hz cannot leak into) that passes three tests:

1. **body**: its attack spectrum carries energy in **80-160 Hz** within 9 dB of the reference kick level (the 90th percentile of slot-0 candidates, 47.0 dB). A 47 Hz sub note sits two FFT bins below 80 Hz, and its own second harmonic is ~17 dB down (bass.md), so bass notes put little here; the bass agent's kick puts 42.5 % of its energy in 60-250 Hz. Why -9 dB: slot-0 candidates (mostly kicks) peak at -7 to -4 dB, while candidates on the snare slots 4 and 12 (mostly snare bleed) peak at -13 to -10 dB; -9 dB is the valley between them;
2. **decay**: the 115-260 Hz envelope falls >= 6 dB between 100 and 150 ms after the peak;
3. **not a bass note**: it must not sit *inside a sustained bass note* (sub level steady within 4 dB from 220 ms before to 320 ms after) *without a click* (< 3 dB rise in 1-8 kHz).

**Validation.**

| body threshold | candidates | fail decay | inside a bass note, no click (false positives) | kicks kept | kicks / bar |
|---|---|---|---|---|---|
| -6 dB | 1362 | 93 | 56 (4.4 %) | 1213 | 1.42 |
| -9 dB **(used)** | 2120 | 226 | 142 (7.5 %) | 1752 | 2.06 |
| -12 dB | 3020 | 413 | 239 (9.2 %) | 2368 | 2.78 |

At the operating point, **142 detections (7.5 %)** sat inside a sustained bass note with no click and were removed as false positives. Of the 1752 kicks kept (2.06 per bar; the bass agent's independent kick-like count is 2.8 per bar), 88 % carry a click and 27 % land inside a bass note *with* a click - kicks over a held sub, which is expected with no sidechain. Detector latency 12.0 ms, removed. Kick counts move with the body threshold (table), so the classes below were re-run at -6 and -12 dB: the section classes agree with the -9 dB result for **74 %** and **79 %** of bars respectively. The sections that flip: at -6 dB S4 -> sparse / syncopated, S12 -> sparse / syncopated, S15 -> no kick, S17 -> no kick, S19 -> no kick; at -12 dB S1 -> break kick, S9 -> break kick, S17 -> break kick, S18 -> break kick, S19 -> break kick. Those calls are threshold-dependent; the rest are not.

### 10.2 Classes, and where their boundaries come from

```
- no kick: under 0.4 kicks a bar, i.e. at most one kick in every 2.5 bars.
- four on the floor: all four slots of one beat lattice >= 0.6 while the 8ths between them
  stay under 0.3. 0.6 rather than the ~0.8 a listener would expect, because the detector does
  not find every kick: its best slot anywhere in the set reaches 0.96-0.98, and most sections'
  strongest slot sits at 0.7-0.8, so a true four-on-the-floor would measure well below 1.0.
- two-step: kicks 10 then 6 sixteenths apart (0 + 10 on some rotation) both >= 0.5, the other
  slots quiet, AND programmed: successive kicks within 11 dB of each other in spectral shape (the
  set splits cleanly there: 7.6-9.8 dB against 11.8-15.8 dB) and the bar pattern repeating
  (Jaccard >= 0.45 between neighbouring bars).
- sparse / syncopated: 0.4-1.2 kicks a bar, or more but mostly off every beat lattice.
- break kick: everything else with kicks in it - dense, re-dealt, timbre varying hit to hit.
```

Two practical points. **Rotation.** The bar phase of section 0 is inferred from snare placement, which cannot tell beat 2 from beat 4 and in one record sits an 8th off, so every pattern test is rotation-invariant: four on the floor is 'all four slots of *some* beat lattice', two-step is 'two kicks 10 then 6 sixteenths apart', and the tables print occupancy rotated so the stronger of slots 0/8 is the downbeat. **Two-step vs break kick** is decided by three measurements: bar-to-bar consistency (Jaccard of successive bars' kick slots, and the share of bars within one slot of the modal pattern), timbral consistency (median RMS dB distance between the 1/4-octave attack shapes of successive kicks: one sample vs several slices), and whether the kick sits in its own band (attack energy 2-16 kHz relative to 80-250 Hz: a programmed kick has only a click up there, a break kick brings the slice's hats and snare edge with it).

### 10.3 Per section

| sec | start | bars | class | conf. | kicks/bar | pattern (# >= .6, + >= .3) | 16-slot kick occupancy (downbeat-rotated) | off the beat lattice | Jaccard bar-to-bar | modal +-1 | timbre dist dB | HF / body dB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S1 | 0:00 | 33 | **two-step** | medium | 1.58 | `#.+.......+.....` | 0.70 0.00 0.33 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.55 0.00 0.00 0.00 0.00 0.00 | 44 % | 0.53 | 0.83 | 7.6 | -16.0 |
| S2 | 0:49 | 68 | **break kick** | medium | 3.47 | `#.+.......#.....` | 0.76 0.01 0.51 0.00 0.25 0.00 0.29 0.07 0.24 0.00 0.81 0.00 0.29 0.01 0.21 0.00 | 47 % | 0.50 | 0.38 | 15.4 | -4.7 |
| S3 | 2:28 | 67 | **break kick** | high | 3.21 | `+.+.+.+.+...+.+.` | 0.40 0.01 0.40 0.03 0.49 0.00 0.45 0.00 0.34 0.00 0.15 0.00 0.52 0.00 0.40 0.00 | 45 % | 0.25 | 0.13 | 13.6 | -5.9 |
| S4 | 4:05 | 23 | **break kick** | medium | 1.48 | `+...........+...` | 0.43 0.00 0.04 0.04 0.13 0.04 0.04 0.04 0.04 0.04 0.00 0.00 0.57 0.00 0.04 0.00 | 21 % | 0.45 | 0.61 | 12.3 | -8.3 |
| S5 | 4:40 | 30 | **break kick** | medium | 3.17 | `#.+...+.#...+...` | 0.70 0.00 0.33 0.00 0.17 0.00 0.50 0.00 0.67 0.00 0.27 0.00 0.40 0.00 0.13 0.00 | 39 % | 0.23 | 0.38 | 11.8 | -7.0 |
| S6 | 5:24 | 17 | **break kick** | low | 1.88 | `#...........#...` | 0.76 0.00 0.00 0.00 0.00 0.12 0.00 0.00 0.00 0.06 0.06 0.00 0.82 0.00 0.06 0.00 | 16 % | 0.62 | 0.94 | 13.7 | -7.3 |
| S7 | 5:49 | 38 | **break kick** | high | 2.39 | `+...+...........` | 0.55 0.03 0.21 0.03 0.50 0.00 0.21 0.08 0.11 0.03 0.29 0.05 0.16 0.05 0.11 0.00 | 45 % | 0.10 | 0.31 | 13.8 | -5.5 |
| S8 | 6:46 | 24 | **break kick** | high | 2.67 | `#.....#.+.......` | 0.75 0.00 0.21 0.04 0.04 0.04 0.67 0.00 0.50 0.04 0.12 0.00 0.00 0.00 0.25 0.00 | 52 % | 0.35 | 0.45 | 13.5 | -7.3 |
| S9 | 7:23 | 25 | **two-step** | high | 2.44 | `#.....#.+.......` | 0.96 0.00 0.04 0.00 0.00 0.00 0.76 0.00 0.52 0.00 0.08 0.00 0.08 0.00 0.00 0.00 | 36 % | 0.49 | 0.67 | 9.7 | -11.9 |
| S10 | 8:01 | 44 | **two-step** | high | 2.45 | `#.....#.+.......` | 0.98 0.00 0.00 0.00 0.05 0.00 0.80 0.00 0.50 0.00 0.00 0.00 0.14 0.00 0.00 0.00 | 32 % | 0.53 | 0.81 | 9.4 | -14.5 |
| S11 | 9:06 | 39 | **break kick** | high | 3.15 | `#.+...+.+.......` | 0.77 0.05 0.38 0.08 0.13 0.08 0.59 0.00 0.56 0.03 0.10 0.00 0.18 0.00 0.08 0.13 | 48 % | 0.29 | 0.32 | 15.5 | -6.5 |
| S12 | 10:04 | 69 | **break kick** | high | 1.49 | `+.....+.........` | 0.52 0.01 0.04 0.01 0.00 0.00 0.33 0.12 0.01 0.09 0.13 0.00 0.22 0.00 0.00 0.00 | 50 % | 0.26 | 0.29 | 12.5 | -10.7 |
| S13 | 11:44 | 47 | **break kick** | high | 2.40 | `#.....#.....+...` | 0.66 0.00 0.00 0.00 0.15 0.00 0.66 0.00 0.04 0.00 0.17 0.00 0.45 0.00 0.28 0.00 | 46 % | 0.32 | 0.49 | 13.6 | -8.9 |
| S14 | 12:54 | 90 | **break kick** | high | 2.08 | `+.+.....+.......` | 0.46 0.00 0.36 0.00 0.29 0.00 0.08 0.00 0.41 0.00 0.20 0.00 0.11 0.00 0.18 0.00 | 39 % | 0.15 | 0.42 | 14.8 | -7.9 |
| S15 | 15:05 | 19 | **sparse / syncopated** | medium | 0.42 | `................` | 0.05 0.11 0.00 0.00 0.00 0.00 0.00 0.05 0.00 0.05 0.00 0.05 0.00 0.11 0.00 0.00 | 38 % | 0.00 | 0.33 | 15.7 | -16.9 |
| S16 | 15:35 | 95 | **sparse / syncopated** | low | 1.57 | `+.+.............` | 0.33 0.00 0.31 0.02 0.06 0.24 0.08 0.12 0.12 0.01 0.05 0.04 0.07 0.00 0.09 0.02 | 63 % | 0.13 | 0.17 | 15.8 | -9.5 |
| S17 | 17:54 | 62 | **sparse / syncopated** | medium | 0.60 | `................` | 0.18 0.00 0.08 0.00 0.05 0.00 0.11 0.00 0.00 0.00 0.00 0.00 0.16 0.02 0.00 0.00 | 35 % | 0.31 | 0.38 | 12.6 | -20.2 |
| S18 | 19:26 | 15 | **sparse / syncopated** | medium | 0.80 | `+...............` | 0.53 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.27 0.00 0.00 0.00 0.00 0.00 | 33 % | 0.25 | 0.89 | 9.5 | -7.8 |
| S19 | 19:50 | 47 | **sparse / syncopated** | medium | 0.68 | `+...............` | 0.36 0.06 0.00 0.00 0.04 0.00 0.00 0.00 0.00 0.00 0.02 0.00 0.02 0.00 0.17 0.00 | 38 % | 0.50 | 0.72 | 9.8 | -7.1 |

**Two-step against break kick, side by side** (medians over the sections in each class):

|  | sections | Jaccard bar-to-bar | modal +-1 | timbre dist dB | HF / body dB | kicks/bar |
|---|---|---|---|---|---|---|
| two-step | 3 | 0.53 | 0.81 | 9.4 | -14.5 | 2.44 |
| break kick | 11 | 0.29 | 0.38 | 13.6 | -7.3 | 2.40 |

**Four on the floor: not found.** No section and no sub-section has all four beats of a lattice at 0.6 with the 8ths between them quiet. What a spectrogram would show as a filled, regular 80-120 Hz lane is 2:21 (8 bars, 6.6 kicks/bar); 2:44 (15 bars, 5.3 kicks/bar): low-mid hits on **every 8th**, twice as dense as four on the floor. They are drum hits, not bass: their attack carries -23 dB and -20 dB of sub (40-62 Hz) relative to their 80-160 Hz body, where the set's kicks sit at -8 dB and a clean sub note would be strongly positive, and each has a ~10 dB click. Whether they are a kick roll or low toms, the measurement cannot say.

**A pattern outside the five classes.** Two kick sub-sections hold a near-identical pair on beat 1 and beat 4 (rotated slots 0 and 12) - 4:11 and 5:24, modal-within-one-slot 0.73 and 0.94. It repeats like a programmed kick but is not a two-step, and its timbre varies like slices; the rules call it break kick at low confidence.


### 10.4 Sub-sections: change points in the kick pattern

Bar vector = the 16-slot kick hits. Same exact partition and minimum length (2 bars) as 9.6; penalty calibrated on bar-shuffled data (beta 0.25 -> 133.1, beta 0.35 -> 38.2, beta 0.5 -> 4.5, beta 0.7 -> 0.0, beta 1.0 -> 0.0, beta 1.4 -> 0.0, beta 2.0 -> 0.0, beta 2.8 -> 0.0), chosen beta = **0.7**.

**23 kick sub-sections.** Lengths in bars: median 25, quartiles 18-45, range 7-167. Distribution: 2-3: 0, 4-7: 1, 8-15: 4, 16-31: 8, 32-63: 7, 64-999: 3.

**Stability.** The exact 16-slot kick pattern equals its segment's modal pattern in **33 %** of bars (random placement 28 %, p = 0.000); within one slot in **54 %** (null 47 %, p = 0.000).

| kick class | bars with kicks | exact modal pattern | modal within 1 slot |
|---|---|---|---|
| two-step | 103 | 40 % | 75 % |
| break kick | 430 | 24 % | 45 % |
| sparse / syncopated | 117 | 22 % | 40 % |

So 'fixed inside a sub-section' depends on the kind of kick. Taken as a *distribution*, the 16-slot kick occupancy of a sub-section's first half correlates **r = 0.85** with its second half, against **r = 0.36** across a boundary (equal windows either side). Taken as an *exact bar*, compare the classes in the table: a programmed kick repeats, a break kick re-deals its slots every bar inside a stable distribution.

**Do the change points land on phrase lines?** Two tests. *Lengths*: interior sub-section lengths that are exact multiples of the phrase (phase-free). *Anchored*: bars from the nearest drop, breakdown or seam in the same record (excluding one that coincides with the change point) on the phrase lattice, exactly and within +-1 bar.

| phrase | lengths on it | chance | anchored, exact | chance | anchored, +-1 bar | chance | change points tested |
|---|---|---|---|---|---|---|---|
| 4 bars | 38 % (8/21), p = 0.13 | 25.0 % | 14 %, p = 0.94 | 25.0 % | 77 %, p = 0.52 | 75.0 % | 22 |
| 8 bars | 19 % (4/21), p = 0.26 | 12.5 % | 5 %, p = 0.95 | 12.5 % | 36 %, p = 0.62 | 37.5 % | 22 |
| 16 bars | 5 % (1/21), p = 0.74 | 6.2 % | 5 %, p = 0.76 | 6.2 % | 18 %, p = 0.61 | 18.8 % | 22 |
| 32 bars | 5 % (1/21), p = 0.49 | 3.1 % | 0 %, p = 1.00 | 3.1 % | 9 %, p = 0.62 | 9.4 % | 22 |

Lift over chance (lengths / anchored exact): 4: 1.5x / 0.5x; 8: 1.5x / 0.4x; 16: 0.8x / 0.7x; 32: 1.5x / 0.0x. p = one-sided binomial probability of doing at least that well by chance. Change points are only located to about a bar (a pattern that is re-dealt every bar has no sharp edge), so the exact tests are harsh; the +-1 bar column is the fair one.

**Do the kick and the carrier change together?** 36 % of kick change points have a carrier change point within 1 bar (random placement 7 %, p = 0.000); within 2 bars 36 % (random 13 %, p = 0.012).


Kick sub-sections (pattern rotated so the stronger of slots 0/8 is the downbeat; sub/body = attack at 40-62 Hz relative to 80-160 Hz, floored at -40):

| seg | start | bars | class | conf. | kicks/bar | pattern | modal +-1 | timbre dist dB | sub/body dB | boundary sits at |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 0:00 | 25 | **two-step** | high | 2.08 | `#.+.......#.....` | 0.83 | 7.6 | -2 | start |
| 1 | 0:36 | 8 | **no kick** | high | 0.00 | `................` | - | - | - | - |
| 2 | 0:49 | 32 | **break kick** | medium | 2.59 | `#.+.......#.....` | 0.60 | 14.1 | -2 | drop |
| 3 | 1:35 | 23 | **break kick** | medium | 4.96 | `#.+.+.#.+.#.+.+.` | 0.32 | 16.8 | -16 | breakdown |
| 4 | 2:08 | 9 | **break kick** | low | 1.33 | `+.........+.....` | 0.80 | 14.1 | -5 | breakdown |
| 5 | 2:21 | 8 | **break kick** | medium | 6.62 | `#.#.#.#.#.#.#.#.` | 0.50 | 14.4 | -23 | breakdown |
| 6 | 2:34 | 7 | **break kick** | medium | 1.57 | `................` | 0.50 | 16.6 | -11 | - |
| 7 | 2:44 | 15 | **break kick** | high | 5.27 | `#.#.#.#.#.+.#.#.` | 0.40 | 15.0 | -20 | drop |
| 8 | 3:06 | 44 | **break kick** | high | 2.41 | `....+.+.....+.+.` | 0.24 | 12.1 | -9 | mix seam + drop |
| 9 | 4:11 | 20 | **break kick** | low | 1.35 | `+...........#...` | 0.73 | 12.7 | -19 | mix seam |
| 10 | 4:40 | 30 | **break kick** | medium | 3.17 | `#.+...+.#...+...` | 0.38 | 11.8 | -2 | drop + breakdown |
| 11 | 5:24 | 17 | **break kick** | low | 1.88 | `#...........#...` | 0.94 | 13.7 | -18 | breakdown |
| 12 | 5:51 | 39 | **break kick** | high | 2.36 | `+...+...........` | 0.30 | 13.8 | -4 | drop |
| 13 | 6:48 | 23 | **break kick** | high | 2.74 | `#.....#.+.......` | 0.48 | 13.4 | -20 | - |
| 14 | 7:23 | 82 | **two-step** | high | 2.46 | `#.....#.+.......` | 0.72 | 9.9 | -40 | mix seam + drop |
| 15 | 9:25 | 25 | **break kick** | high | 3.60 | `#.+...#.#.......` | 0.12 | 16.6 | -12 | - |
| 16 | 10:01 | 34 | **break kick** | medium | 1.35 | `+...............` | 0.52 | 14.8 | -8 | mix seam + breakdown |
| 17 | 10:52 | 46 | **break kick** | medium | 1.46 | `+.....#.....+...` | 0.52 | 11.4 | +1 | breakdown |
| 18 | 12:00 | 46 | **break kick** | high | 2.87 | `#.....#.....+.+.` | 0.45 | 14.9 | -1 | drop + breakdown |
| 19 | 13:08 | 76 | **break kick** | high | 2.07 | `+.+.+...+.......` | 0.49 | 14.6 | -5 | drop |
| 20 | 14:57 | 24 | **no kick** | medium | 0.38 | `................` | 0.29 | 16.5 | -9 | breakdown |
| 21 | 15:37 | 52 | **sparse / syncopated** | low | 2.38 | `+.+..+..........` | 0.21 | 15.6 | -16 | - |
| 22 | 16:52 | 167 | **sparse / syncopated** | medium | 0.63 | `................` | 0.54 | 12.7 | -8 | - |

### 10.5 Timeline

Runtime per class (from the sub-section classes, which is what `kick_class` in the npz holds):

| class | bars | runtime | share | where |
|---|---|---|---|---|
| no kick | 32 | 0:46 | 3.8 % | 0:36 (8 bars), 14:57 (24 bars) |
| four on the floor | 0 | 0:00 | 0.0 % | - |
| two-step | 107 | 2:34 | 12.6 % | 0:00 (25 bars), 7:23 (82 bars) |
| break kick | 494 | 11:54 | 58.0 % | 0:49 (32 bars), 1:35 (23 bars), 2:08 (9 bars), 2:21 (8 bars), 2:34 (7 bars), 2:44 (15 bars), 3:06 (44 bars), 4:11 (20 bars), 4:40 (30 bars), 5:24 (17 bars), 5:51 (39 bars), 6:48 (23 bars), 9:25 (25 bars), 10:01 (34 bars), 10:52 (46 bars), 12:00 (46 bars), 13:08 (76 bars) |
| sparse / syncopated | 219 | 5:16 | 25.7 % | 15:37 (52 bars), 16:52 (167 bars) |

**Where the class changes.** 6 class changes between neighbouring kick sub-sections: 1 at a record seam, 1 at a drop, 1 after a breakdown, 3 with no event within a bar.

Kick class in the 4 bars before vs the first 4 bars of every major/mid drop: break kick -> break kick: 8; sparse / syncopated -> sparse / syncopated: 4; no kick -> no kick: 2; no kick -> break kick: 1; break kick -> two-step: 1; two-step -> two-step: 1.

### 10.6 Relationships

**Kick class vs how much the bass moves.** Each of the bass agent's 25 sections (`bass.md`, table 4) takes the kick class that covers most of its bars:

| kick class | bass sections | bass changes / bar (mean) | median | range |
|---|---|---|---|---|
| no kick | 1 | 0.96 | 0.96 | 0.96-0.96 |
| two-step | 3 | 0.25 | 0.30 | 0.03-0.42 |
| break kick | 14 | 1.02 | 1.04 | 0.50-1.72 |
| sparse / syncopated | 7 | 0.85 | 0.87 | 0.25-1.57 |

Bass under a **break kick** moves 1.02 times a bar and under a sparse or absent kick 0.86 - about the same. The contrast is **two-step**: under a programmed two-step the bass moves only 0.25 times a bar. A locked kick gets a still bass; a moving, re-chopped kick gets a moving bass. (Sections: two-step 3, break kick 14, sparse/none 8 - small samples; read it as a lean.)

**Kick class vs the 16th carrier** (bars, from the two sets of sub-section classes):

| kick class | bars | carrier: none | carrier: high-passed break | carrier: short percussion | carrier: full-range break | bars with a carrier |
|---|---|---|---|---|---|---|
| no kick | 32 | 22 % | 0 % | 3 % | 75 % | 56 % |
| two-step | 107 | 61 % | 0 % | 21 % | 18 % | 67 % |
| break kick | 494 | 18 % | 35 % | 0 % | 46 % | 79 % |
| sparse / syncopated | 219 | 18 % | 0 % | 0 % | 82 % | 71 % |

Carrier type is a property of the carrier *sub-section* and is 'none' when fewer than half its bars carry 16ths, so a bar can have a carrier while its type reads none. Even so the pairing is clear: under a **two-step** the carrier sub-section is 'none' or short percussion in 82 % of bars and never a high-passed break; under a **break kick** it is a break (high-passed or full-range) in 82 %. A programmed kick comes with a thin or absent 16th layer; a break kick comes with the break carrying the 16ths itself.


### 10.7 Per-bar table for cross-feature alignment

`C:\Users\eric\Downloads\reaper_cache\rhythm_bars.npz` - one row per analysed bar (852 bars; a few bars are skipped where the bar phase changes between sections, so index by `bar_start_s`, not by bar number).

| array | dtype / shape | meaning |
|---|---|---|
| bar_start_s | float64 (bars) | bar start in seconds, drift-tracked grid |
| bar_dur_s | float64 (bars) | bar length (1.4458 s) |
| section_id | int16 (bars) | 0-based index of the 19 sections used in this file |
| kick_class | int8 (bars) | class of the bar's kick sub-section: 0 = no kick, 1 = four on the floor, 2 = two-step, 3 = break kick, 4 = sparse / syncopated |
| kick_hits | int8 (bars) | kicks detected in the bar (<= 1 per slot) |
| kick_occ16 | bool (bars, 16) | kick per 16th slot, section-0 bar phase (NOT rotated) |
| kick_segment_id | int16 (bars) | kick change-point sub-section |
| carrier_present | bool (bars) | 16th carrier: >= 3 of 8 odd slots and >= 10 of 16 at rho 1.5 |
| carrier_type | int8 (bars) | type of the bar's carrier sub-section: 0 = none, 1 = high-passed break, 2 = short percussion, 3 = full-range break |
| carrier_odd_hits | int8 (bars) | articulated off-8th slots (0-8) |
| carrier_occ16 | bool (bars, 16) | articulated slots, carrier band 1.5-16 kHz |
| carrier_segment_id | int16 (bars) | carrier change-point sub-section |
| kick_codes / carrier_codes | 0-d str | JSON code tables |
| meta | 0-d str | JSON: bpm, grid, rho, betas, kick threshold, script |

```python
import numpy as np, json
z = np.load(r"C:\Users\eric\Downloads\reaper_cache\rhythm_bars.npz")
codes = json.loads(str(z['kick_codes']))
```

### What this means for building a jungle track (kick)

1. Kick time in the reference: break kick 58 %, sparse / syncopated 26 %, two-step 13 %, no kick 4 %, four on the floor 0 %.
2. Hold one kick *distribution* per sub-section (median 25 bars; first half vs second half r = 0.85, across a boundary 0.36) and change it at the edge, together with the carrier where you can (36 % of kick changes have a carrier change within a bar). Inside: a two-step repeats (75 % of bars within one slot of its pattern), a break kick re-deals its slots every bar (45 %).
3. A programmed two-step is one consistent sample in its own band; a break kick is a slice that brings hats and snare edge with it and changes timbre hit to hit. Choose which one a section is, and do not blur them. Under a two-step, keep the bass nearly still (0.25 note changes a bar against ~1 under a break kick) and the 16th layer thin.
4. No four on the floor. The fullest low-mid lane in the reference is 8th-note drum hits for 8-15 bars before a cut, and the last six minutes run on a sparse, syncopated kick under a big sub.
