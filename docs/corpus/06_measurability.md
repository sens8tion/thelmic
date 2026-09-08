# Measurability: every dimension, how it is measured, or flagged

> 2026-09-08. The rule: every dimension of musical interest the ear tracks
> must be measurable. For each one below: the input, the pattern
> representation, the surprise measure, the absence/space measure, the
> legibility measure, and a status. **Status** is one of: `now` (stdlib +
> numpy on what we already have), `stems` (needs per-track bounces, which the
> user renders), `dep` (needs a dependency we do not have installed yet),
> `approx` (measurable but with a stated simplification), `unvalidated`
> (measurable but no research validates the measure), `fit` (measurable but
> the threshold must be fitted to the user's ear), `flag` (not measurable
> with what we have; say so).

## Inputs we actually have

| Input | How | Limits |
|---|---|---|
| Stereo mix WAV, 44.1k, 16/24-bit | user bounces; `hear.py` RIFF reader | no mp3/flac (no ffmpeg) |
| Per-track stems | user exports "all individual tracks" from the arrangement | LOM cannot trigger export |
| MIDI notes per clip | LOM `get_clip_notes` (pitch, start, length, velocity, mute) | MIDI tracks only: FACA, SINO, Scorpio, SUB, ARO, kicks, MOEDOR/VOZ slice notes |
| Arrangement clip map | LOM `get_arrangement_clips` (track, start, end, name, colour) | ground truth for form, vocal identity, return structure |
| Device params | LOM `describe_param` / readback | current value only; automation lanes only by playback trace at slow tempo |
| Tempo, meter | LOM snapshot | exact |
| Sample identity | LOM Simpler sample path, slice map | exact |
| GPU + torch CUDA | Python310 env | available for any model we choose to add |

Every audio measure below is per stem where a stem exists, and per mix otherwise. Every measure is reported **per bar** (1.35 s at 178) and rolled up to phrase (4/8/16 bars) and section, in a per-lane, per-dimension table. Grid = 16ths for storage, 8ths as the primary pattern unit at this tempo (16th = 84 ms, below the ~100 ms event floor).

## The common machinery

Three things are computed the same way for every dimension, so they are defined once:

- **Episodic model.** For a discrete symbol stream (grid position, pitch class, chord label, timbre bin), a table of counts per context with exponential decay, half-life 2–4 cycles of the lane's loop. Surprise of a symbol = −log₂ P(symbol | context); uncertainty before it = entropy of the predictive distribution. This is IDyOM's short-term model with a forgetting rate. Reported as within-piece percentiles, not absolute bits.
- **Schematic prior.** Where the corpus gives one (LHL metrical weights, Krumhansl–Kessler key profiles, van Noorden tempo resonance), it initialises the episodic table and sets the learning rate. It never overrides the episodic model once that has converged (Deutsch, Margulis: repetition makes anything legible).
- **Dwell clock.** Per lane per dimension: bars since episodic surprise last exceeded threshold θ while uncertainty is below φ. The attention unit grows with exposure (1 bar early, 4–8 bars after ~2 min), so the clock is read in units, not bars. `fit`: θ, φ and the unit growth rate are the calibration targets.

Surprise events across all dimensions are then merged into one timeline and clustered by onset: events within one grid position are one event (common fate); two unaligned events inside the current attention unit are flagged `mess` unless the second is a learned response to the first (conditional-probability test in the relations dimension).

## Dimensions

### Inside a single event

| Dimension | Source | Pattern representation | Surprise | Absence / space | Legibility | Status |
|---|---|---|---|---|---|---|
| **Loudness / accent** | stem envelope; MIDI velocity | per-grid-position accent level (dB), episodic table on quantised accents | deviation from the lane's accent template; Sioros amplitude term | level dip ≥6 dB before an onset; arrival contrast between sections (already in `hear.py`) | accents spaced ≥100 ms | `now`, `approx` (band RMS, not a Moore–Glasberg loudness model) |
| **Articulation / envelope** | MIDI note length; stem per-onset attack (10→90% rise) and decay (to −20 dB) | per-position (gate, attack, decay) triple | episodic surprise on quantised triples | fraction of onsets whose decay completes before the next onset (the "clear tail") | attack ≥ ~5 ms distinguishes a hit from a swell | `now` (MIDI), `stems` (audio) |
| **Register** | MIDI pitch; stem spectral centroid and band-energy centroid | mean and range per bar | change-point in centroid between bars/sections | bands left empty (see density) | — | `now` |
| **Spatial** | stereo mix or stems: per-ERB-band inter-channel level difference (pan), inter-channel correlation (width); Auto Pan params via LOM | pan/width per lane per bar | change-point per bar; episodic on quantised pan | share of the stereo field occupied per band | two lanes with the same pan and band are one stream (Bregman) | `now` for pan/width; **`flag`** for distance/depth: direct-to-reverberant ratio needs source separation, not attempted |

### Between events in one stream

| Dimension | Source | Pattern representation | Surprise | Absence / space | Legibility | Status |
|---|---|---|---|---|---|---|
| **Rhythm** | MIDI onsets; stem onsets (spectral flux per band, peak-picked) | onset table on the 16th grid per lane per loop | schematic: LHL weights `[0,−4,−3,−4,−2,−4,−3,−4,−1,−4,−3,−4,−2,−4,−3,−4]` + Sioros amplitude term; episodic: −log₂ P[pos]; combined and precision-weighted | rest ratio; onsets with ≥100 ms clear tail; omission at weight 0/−1 positions scored as the largest single term | meter precision (below) | `now` |
| **Meter / tactus** | low-band (<150 Hz) onset envelope of the mix; MIDI of kick+sub | autocorrelation of the envelope; energy at 1-beat vs 2-beat vs bar periods, weighted by van Noorden's resonance at 500 ms | a change in the dominant period (full-time ↔ half-time) between phrases | bars with no low-band periodicity (breakdown) | **precision** = autocorrelation peak clarity, or 1 − (Povel–Essens counter-evidence / max); this is the confidence term that discounts all rhythmic surprise | `now` |
| **Microtiming** | MIDI start offsets from grid; stem onset offsets | ms deviation per position | change in deviation pattern | — | corpus: not a groove lever; report only | `now`, low weight |
| **Tonality / pitch** | MIDI pitch; sub stem via YIN pitch track (monophonic) | pitch-class duration histogram, 2–4-bar window → Krumhansl–Kessler correlation → key and key clarity | per-note −log₂(profile[pc]/Σ) zero-order; episodic on scale-degree n-grams | notes per bar; bars with no pitched content | key clarity (max correlation) | `now` (MIDI, sub stem); **`dep`** for polyphonic audio pitch: needs a transcription model (basic-pitch or similar on the GPU), not installed |
| **Melodic contour** | MIDI interval signs; YIN track for the sub | contour n-grams; Jakubowski global-contour class | episodic surprise on contour symbols | — | — | `now` (MIDI); vocal-sample contour **`dep`** (same as above) |
| **Harmony** | MIDI pitch-class sets per beat/bar across melodic lanes | chord label (degree, quality) relative to the current key | episodic n-gram surprise on chord labels; K–K profile as prior | bars with a single pitch class or none | — | `now`; **`flag`** on Miles-style corpus baseline: no reference chord corpus, within-piece only |
| **Timbre** | stem per-onset features: spectral centroid, spread, flatness, log-attack; device params via LOM as ground truth | quantised timbre vector per onset; episodic table per lane | Mahalanobis distance from the lane's running timbre distribution; device-param change-points | — | blend risk: two lanes with centroid within ~1 ERB and attack within 30 ms fuse (McAdams) | `stems` |
| **Continuous trajectories** (risers, sweeps, glides) | stem per-bar centroid and band-energy slopes; LOM param values by slow-tempo playback trace | the derivative, not the value: a riser is a pattern in slope | change in slope sign or rate; a trajectory that plateaus is "curdled" | — | monotonic over ≥2 bars to register as a trajectory | `now` (audio), `approx` (LOM trace is 2–6 samples/bar) |
| **Words / voice** | arrangement clip names (which vocal, exact); vocal stem log-mel frames → self-similarity | identity of the vocal token; phrase-level repetition without transcription | new token = surprise; repeat of a token = return | bars without vocal | vocal prominence = vocal band level relative to the mix in the same bands (Hooked's top predictor) | `now` for identity/repetition/prominence; **`flag`** for lyric semantics and phoneme rhythm: needs Whisper on the GPU (`dep`, installable) and matters little to a non-Portuguese listener |

### Between streams

| Dimension | Source | Pattern representation | Surprise | Absence / space | Legibility | Status |
|---|---|---|---|---|---|---|
| **Density / texture** | stems: count of lanes with onsets per bar; mix: ERB-band occupancy (fraction of bands above a −30 dB-relative floor) | streams per bar, onsets per bar, bands occupied | change-point in stream count (this is what a breakdown or drop *is*) | 1 − occupancy; empty bands | above ~4 concurrent onset streams the corpus expects fusion | `stems` for stream count, `now` for occupancy |
| **Relations between lanes** (call/response, ducking, who owns time) | MIDI or stem onsets, two lanes | conditional onset probability P(B at t+L \| A at t) over lags L; envelope cross-correlation | a response that fails to arrive after a learned call; a new lag | gaps in A that B fills (the kick in the sub's holes) | a relation is learned when P(B\|A) at one lag is high and stable for ≥4 cycles | `now` |
| **Masking / legible dominance** | kick stem, sub stem, mix low band | onset survival: fraction of kick-stem onsets present as distinct onsets in the mix <150 Hz (≥30 ms clear of a sub onset or ≥6 dB dip before it); envelope correlation kick vs sub per ERB band <200 Hz; beat-locked share of low-band modulation energy | loss of survival or of the beat-locked share between sections | the dips themselves | ΔERB between kick fundamental and sub pitch; if <1, temporal separation is the only kind | `stems`, **`unvalidated`**: no perceptual study of kick-vs-sub or sidechain exists; **`approx`**: masking threshold is a spectral-distance heuristic, not the full Moore–Glasberg partial-loudness model |
| **Pattern under masking** | as above plus the rhythm dimension | how much onset loss the meter-precision measure tolerates | — | — | the join the research does not make | **`unvalidated`**: measurable, but nothing validates it; candidate for one more research strand (informational masking, meter inference under noise) |

### Across the whole

| Dimension | Source | Pattern representation | Surprise | Absence / space | Legibility | Status |
|---|---|---|---|---|---|---|
| **Form / hypermeter** | arrangement clip map (ground truth); mix per-bar feature vectors → Foote novelty on the self-similarity matrix | change points and whether they land on 4/8/16/32-bar downbeats | a change off the hypermetric grid; an expected boundary with no change | section length in bars vs the corpus norms (build 8–16, ≤32; core 32–64) | changes on the grid are legible *as a category* even when their content is new | `now` |
| **Return structure** | per-lane self-similarity over bars; clip map | recurrence of a bar/phrase after ≥1 section of absence | IC spike at the first event of the return, then a run at minimum IC | length of the absence (raises uncertainty, which is what pays the return) | return reward ∝ uncertainty before × match strength, decaying with count of prior returns | `now` |
| **Style / reference** | sample identity from LOM (Apache, Amen); nothing else | — | — | — | — | **`flag`**: "is this recognisable as jungle / baile funk" needs an embedding model trained on a reference set or the user's judgment; not attempted |
| **Recognisability** (Hooked features) | vocal prominence (above); within-song timbral recurrence (timbre dimension); melodic entropy of the hook (`dep` for sampled vocals) | — | — | — | — | `now` for two of three features, `dep` for the third |

### Outside the file

| Dimension | Status |
|---|---|
| **Bodily hold** (vestibular bass >90 dB(A), VLF) | **`flag`**: playback-level, depends on the PA, not in the bounce. Only the *presence* of energy <40 Hz is measurable (`now`). |
| **Trance mode** | **`flag`**: needs ≥10 continuous minutes and a listener; a track can only be scored for the *preconditions* (pulse jitter, continuity, VLF presence), all `now`. |
| **Person-side engagement** (SCR to events, HRV, beat SS-EP) | **`flag`** until hardware: Polar H10 + finger EDA, seated, ≥5 sessions, within-person only. Strand 5 has the protocol. |
| **Thresholds** (θ, φ, attention-unit growth, dwell limits, mess window) | **`fit`**: every number above is a measurement; none of the *limits* are known for this listener. Calibration = run the ear over tracks the user likes and read the limits off. |

## What is flagged, in one list

1. Lyric semantics and phoneme rhythm: needs Whisper (installable, GPU is there); low value for the target listener.
2. Polyphonic pitch and contour from *audio*: needs a transcription model; irrelevant while melodic lanes are MIDI.
3. Harmonic surprise against a genre baseline: no reference corpus; within-piece only.
4. Depth / distance in the spatial dimension: not attempted.
5. Style and genre recognisability: no model; user's judgment.
6. Perceptual loudness and masking thresholds: heuristic approximations, not the Moore–Glasberg model.
7. Pattern legibility under masking: measurable, validated by nothing.
8. Bodily hold and trance: playback and listener facts, not file facts.
9. Person-side signals: hardware.
10. Every threshold: to be fitted, not assumed.

Everything not in that list is measurable from the mix, the stems and the LOM with what is installed today.
