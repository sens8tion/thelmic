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

## Commits on the branch

- `7d2660c` feat: ROTTERDAM_CHAIN — initial 7-lane × 8-scene gabber session
- `703f7e5` feat: revise patterns with real Rotterdam gabber conventions
