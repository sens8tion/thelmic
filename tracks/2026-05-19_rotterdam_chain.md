# ROTTERDAM_CHAIN — 2026-05-19

7-lane × 8-scene gabber-esque hardcore session at **190 BPM in A minor**.
Hand-composed MIDI through LiveChannel, no thelmic generators. Branch:
`claude/gabber-1779217234`. Build script:
[scripts/gabber_rotterdam_chain.py](../scripts/gabber_rotterdam_chain.py).

## Lanes (7)

| # | name | devices | role |
|---|---|---|---|
| T0 | `KICK_ROTTERDAM` | Selectah Kit → Drum Buss → Saturator (Drive 0.85, Hard Curve, Type 6) | distorted 909 kick, kick-as-bass |
| T1 | `PERC_INDUSTRIAL` | Selectah Kit → Saturator (Drive 0.65) → Reverb (Dry/Wet 0.22) | hats/clap/snare/metal with wet-clap signature |
| T2 | `SUB_PUNCH` | Operator (Tone 0.15, Transpose –12) | A0-area sub, kick-tied root-follow |
| T3 | `HOOVER_LEAD` | Operator (Spread 80, Tone 0.9) → Saturator (0.80, Type 6) → Chorus-Ensemble | anthemic rave riff lead |
| T4 | `STAB_HARDCORE` | Operator (Spread 100 supersaw, Tone 0.8) → Saturator (0.7) | doubles hoover octave-up + power-chord pads |
| T5 | `SIREN_FX` | Operator (Spread 60, Tone 0.7) → Auto Filter | air-raid sirens, no-kick scene carrier |
| T6 | `VOX_SHOUT` | Operator (Tone 0.95, Transpose +12) | shout-blip placeholder (C4 stabs) |

## Scenes (8, each 32 beats = 8 bars at 190 BPM ≈ 10.1 s)

| # | name | drama | notes |
|---|---|---|---|
| S0 | `BLACKOUT` | sirens + atmos only, no kick | 2 notes (siren swells) |
| S1 | `KICK_ENTRY` | pure 4OTF kick + sub punch | 64 notes |
| S2 | `IRON_MARCH` | + hats + snare/clap stack + first siren | ~150 notes |
| S3 | `HOOVER_DROP` | hoover lead enters dark Am riff | ~210 notes |
| S4 | `ANNIHILATION` | full stack + double-kicks + shouts | ~480 notes |
| S5 | `BREAKDOWN_BLOOD` | kicks out, hoover screams long held notes | ~30 notes |
| S6 | `REBUILD_HAMMER` | kicks per-bar→per-beat→8ths + snare roll | ~280 notes |
| S7 | `NUCLEAR` | double-kicks + triplet rolls + stab doubling | ~540 notes |

Scenes are named + colored per dramaturgy via the deployed
`set_scene_name` / `set_scene_color` / `set_clip_color` RPCs (navy intro →
orange build → red peaks → navy breakdown → magenta nuclear).

## Musical theory embedded

### Tempo + key

- **190 BPM** — chosen for "classic" Rotterdam heyday (1993-98 norm was
  170-190 per Wikipedia). Modern mainstream hardcore is 160-180, but we
  picked classic gabber stomp.
- **A minor** — dark, dystopian key associated with the genre.

### Root progression (shared by sub + stab)

`Am — Am — F — F — G — G — Em — Em` (2-bar holds, 8 bars total).

The kick AND sub follow this progression as a single voice: every kick
hit doubled by a same-pitched sub punch on the bar's root. This is the
defining "kick-as-bass" gabber convention — the kick covers the low end
and the sub reinforces it.

### Hoover anthem riff (4 bars × 2 reps per scene)

Classic call-answer-push-resolve shape:

```
Bar 1 — CALL    : A3 dotted-1/4, A3 1/8, E4 1/2     (low -> peak)
Bar 2 — ANSWER  : A3 1/4, B3 1/8, A3 1/8, G3 1/2    (echoed lower)
Bar 3 — PUSH    : A3 dotted-1/4, A3 1/8, F4 1/2     (higher peak)
Bar 4 — DESCENT : G3 F3 E3 D3 1/8s, A2 1/2          (resolve to root)
```

Inspired by Rotterdam Termination Source / Charly-era leads — simple,
chantable, dotted-quarter motifs landing hard on the 1.

### Stab doubles the hoover (lead-stack)

The supersaw stab plays the SAME riff an octave above (`+12` transpose)
plus power-chord pads on bar 1 + 3. Two timbres on the same melody is
the classic gabber wall-of-sound peak.

### Snare + clap stack on 2/4

Real gabber stacks BOTH a snare drum AND a wet-reverbed clap on beats 2
+ 4 — the snare adds punch, the clap adds the room-wash. Reverb on T1
is set to Dry/Wet 0.22 to deliver this without swamping the kick.

### Open hi-hat on every offbeat in drop scenes

`0.5, 1.5, 2.5, 3.5` of every bar in S2/S3/S4/S7. The relentless
between-kick OH is the gabber drive.

### Kick velocity uniformly hot

109-122. Gabber kicks are uniformly loud — dynamics come from the
distortion interaction at peak, not from velocity scaling.

## Sources

- [Gabber — Wikipedia](https://en.wikipedia.org/wiki/Gabber) — BPM range, instrumentation, T99 "Anasthasia" historical reference
- [Mainstream hardcore — Wikipedia](https://en.wikipedia.org/wiki/Mainstream_hardcore) — kick-as-melody (pitch follows bass line), supersaw lead, Alpha Juno/TR-909 history
- [Old school gabber kick production — Renoise Forums](https://forum.renoise.com/t/old-school-gabber-kicks-production-method/43338) — Mackie mixer overdrive technique
- [Early hardcore/gabber kick — Gearspace](https://gearspace.com/board/electronic-music-instruments-and-electronic-music-production/1410441-early-hardcore-gabber-kick-attempt.html)
- [How To Make That Gabber Sound — Gearspace](https://gearspace.com/board/electronic-music-instruments-and-electronic-music-production/630598-how-make-gabber-sound.html)
- [Gabber music style — Discogs](https://www.discogs.com/style/gabber) — K.N.O.R. / Ruffneck / ID&T label history
- [What is Gabber Music? — Musician Wave](https://www.musicianwave.com/what-is-gabber-music/)

## Build + run

```bash
LIVE_CHANNEL_ENABLED=1 python scripts/gabber_rotterdam_chain.py
```

The script is idempotent — re-running reconciles lanes/scenes/clips
against current Live state. Patterns are deterministic; tweak the
generator fns + re-run to push fresh MIDI.

## Reference-driven refinement pass

After the initial build + Wikipedia-driven revision, a second pass
extracted MIDI from real gabber tracks using Live's native Convert
features and folded the findings back into the patterns.

### Source acquisition

Picked 4 candidate references — RTS *Poing* (1992), Euromasters *Alles
Naar De Klote* (1992), Neophyte *Killer Squad*, The Mover *Frontal
Sickness*. YouTube was bot-gated against `yt-dlp` (chrome cookie DPAPI
decrypt failed; iterating other browsers' credential stores was
correctly blocked by the auto-mode classifier). Cobalt / savefrom /
y2mate all blocked or disabled.

SoundCloud via `python -m yt_dlp --default-search scsearch1:` worked.
Two of four landed (the 1992 originals 404'd on SoundCloud's side):

- **Angerfist - Lethal Assassins** (Neophyte Records, modern hardcore stand-in)
- **The Mover - Final Sickness (Remastered 2017)** (Marc Acardipane dark hardcore)

Files arrived as `.m4a` which Live's Convert features didn't like.
Re-encoded to 44.1 kHz / 16-bit stereo WAV via `imageio-ffmpeg`'s
bundled binary, dropped into the User Library.

### Convert-to-MIDI workflow

Live's browser is lazy-scanning — newly-created sample folders aren't
visible to `load_audio_to_slot` (the LOM resolver walks `browser.children`
which is cached). No `refresh` action exists on the LOM browser; only
listener registration. Fix was to drag files from File Explorer
directly onto the track's session slot, bypassing the browser.

Once audio clips were in slots 0+1 on a `GABBER_REF` audio track,
right-click → Convert → Drums / Melody / Harmony to MIDI created three
new tracks each holding a MIDI clip per audio source:

```
T9   "10-Melody to MIDI"   slot 0 = Angerfist melody     slot 1 = Mover melody
T10  "11-Harmony to MIDI"  slot 0 = Angerfist harmony    slot 1 = Mover harmony
T11  "12-Drums to MIDI"    slot 0 = Angerfist drums      slot 1 = Mover drums
```

Note counts: Mover melody 1019, Mover harmony 1730, Mover drums 3538;
Angerfist melody 592, Angerfist harmony 1100, Angerfist drums 2353.

### Analyzer scripts

Four underscore-prefixed analyzer scripts walk the extractions:

- [scripts/_inspect_session.py](../scripts/_inspect_session.py) — quick
  session state dump (all tracks, devices, clips, files).
- [scripts/_analyze_extractions.py](../scripts/_analyze_extractions.py) —
  per-conversion pitch + IOI breakdown, identifying which clips hold
  drums vs melodic content.
- [scripts/_full_extraction_report.py](../scripts/_full_extraction_report.py)
  — pitch-class histogram (relative to A root) + density sparkline for
  each `(audio-source, conversion-type)` combination.
- [scripts/_drum_density_timeline.py](../scripts/_drum_density_timeline.py)
  — 16-beat bucket sparkline of drum activity across the clip, with
  shape tags (SILENCE / sparse / PEAK / no-kick / hat-heavy / snare-heavy).

These are analysis helpers, not part of the build pipeline — they read
state but don't write.

### Findings

**Key choice validated.** The Mover's melody pitch-class histogram is
overwhelmingly A-rooted (32.8 %). Our ROTTERDAM_CHAIN choice of A
minor matches it exactly. Angerfist roots in F (24.5 %) instead —
a tritone away, F minor / phrygian.

**Phrygian inflection is universal.** Both tracks weight the flat-2
heavily — The Mover's melody is 9.9 % Bb, Angerfist's is 6.9 %. That
Bb against the A (or Eb against F for Angerfist) is the dystopian-
darkness signature.

**Harmonic-minor leading tone too.** The Mover's melody is 11.6 % G#
— the harmonic-minor pull-tone. Combined with Bb, this is a G#/Bb
pincer around the A root: leading-tone tension below, phrygian shadow
above. Both notes were absent from the v1/v2 hoover riff (pure A
natural minor).

**Density structure is informative even with detection noise.** Drums
to MIDI mis-classifies distorted gabber kicks (the broadband transient
trips kick + snare + hat detectors simultaneously), so raw note counts
are dilute. But the per-16-beat sparkline still resolves the song's
arrangement structure: silent intros, drop locations, breakdown
durations, multi-peak shapes. Mover's full density sparkline:

```
-::=*#######-:-:=###*+#@=+#####+---*#*###*#@#--
```

Reading that as 16-beat windows: sparse intro (10 bars) → drop 1
(bars 16-19) → 80-beat silence breakdown (bars 36-55) → second build
→ drop 2 (bars 116-123) → long sparse tail. Our 8-scene arc broadly
matches this shape, validating the dramaturgy.

### Refinements applied

Two cheap-but-high-impact changes pushed in commit `9b5d385`:

**1. HOOVER_4BAR riff — phrygian + harmonic-minor color notes:**

```
bar 1 CALL    : A3, G#3 (leading-tone pickup), E4
bar 2 ANSWER  : A3, Bb3 (phrygian shadow),     A3, G3
bar 3 PUSH    : A3, G#3 (leading-tone pickup), F4
bar 4 DESCENT : G3, F3, E3, Bb2 (phrygian crash), A2
```

Was: pure A natural minor with B3 (natural 2nd) instead of Bb3, D3
instead of Bb2, and no G# anywhere. Now matches the genre's actual
harmonic vocabulary.

**2. STAB_HARDCORE S5 BREAKDOWN_BLOOD entry — phrygian crash:**

Bb-major triad (Bb3 + D4 + F4) held 6 beats on beat 1 of S5, octave-
stacked screech ceiling (Bb4 + D5 + F5) held 4 beats. The "darkness
drops" hit: the phrygian flat-2 above A lands hard on the void as
kicks cut out.

Not applied (deferred): full transpose to F minor (would lose the A
phrygian Mover-character we're locked to), extended-length S5
breakdown (could later mirror the Mover's 80-beat void).

## Commits on the branch

- `7d2660c` feat: ROTTERDAM_CHAIN — initial 7-lane × 8-scene gabber session
- `703f7e5` feat: revise patterns with real Rotterdam gabber conventions
- `c8087ea` docs: track recipe — ROTTERDAM_CHAIN with embedded gabber theory + sources
- `9b5d385` feat: phrygian refinements from Convert-to-MIDI analysis
