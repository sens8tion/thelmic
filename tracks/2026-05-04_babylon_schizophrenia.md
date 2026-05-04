# Babylon Schizophrenia (working title)

> Two minutes. Fifteen scenes. One key (Em-ish). Hard tempo jumps.
> Dub stepper at 87 → ska 140 → punk 150 → hardcore/dnb 174 → 4OTF 180
> with a 32-slice amen scramble at the top.

**Build date:** 2026-05-04
**Branch:** `refactor/bridge-aesthetic-split`
**Last branch SHA before squash:** `b22d485`
**Project:** `sessions/ragga_v1` (eventually) — printed into Live arrangement view.
**Tooling:** `thelmic` Python bridge ↔ Ableton Live 12 Suite via `ThelmicLive` Remote Script (port 9878).

## Possible names

`KING TUBBY ATE GLASS` · `DUBPLATE GOT THE YIPS` · `BABYLON SCHIZOPHRENIA`
· `SELECTAH / DEFECTOR` · `BREDRIN GOT PINGED` · `87→180 W/O CONSENT`

## Tags / genre

SoundCloud forced genre: **Drum & Bass**. True genre vector: dub +
ragga + jungle + ska + punk + hardcore + gabber + dnb.

```
dub ragga jungle dubplate soundsystem amenbreak gabber hardcore
ska wurlitzer hammond reggae 87to180 ableton generative
emnaturalminor 32slice tempoanarchy live-print
```

## The arc

| # | Scene | BPM | What happens |
|---|---|---|---|
| 0 | DUB_IN | 87 | Atmospheric intro. Sparse. (User-zeroed/muted manually for intro vibe.) |
| 1 | STEPPER | 87 | Half-time roots — kick 1+3, snare 3, organ skank on every &, walking bass |
| 2 | RAGGAJUNGLE | 87 | Full slam — chopped amen audio + sub bonk + busy ghost-snare drums + skank + walking bass + toast |
| 3 | DUBOUT | 87 | Drums drop (just crash + soft kick) + vocal echo + dub siren + sub holds + Hammond drone |
| 4 | RAGGA_FILL | 87 | Rolling fill — 32nd hat carpet + ghost-snare flurries + bar-4 roll-out + vox pitched riser |
| 5 | WURLY_REMIX | 87 | Breakdown canvas — wurly Em I-iv-v-iv skank + minimal tick (rim 1/3 + whisper hats &'s) + walking bass roots |
| 6 | SKA_PIVOT | **140** | Hard +60% jump. Driving ska — kick 1+3, snare 2+4, 8th hats + open-hat breath, walking bass, off-beat Em-Am-Bm-Am stabs, power-chord guitar doubling |
| 7 | PUNK_BURN | **150** | Acoustic Selectah Kit (proper drum rack), 4-on-floor kicks + snare 2/4 + 16th hat carpet, power chord on every beat |
| 8 | HARDCORE_DROP | 174 | User-tuned. Gabber 4OTF + impact hits + Hoover Em chords + REESEY BASS audio |
| 9 | DNB_FULL | 174 | User-tuned. double_time_dnb pattern + Break_Dnb_174 audio + reese + sparser hoover |
| 10 | KICK_4OTF | 180 | Hard 4OTF kick lane only (Hell's Screamer on its own track) |
| 11 | KICK_4OTF_ghosted | 180 | 4OTF + ghost-kick rolls on bar-4 with Heavy Room |
| 12 | AMEN_BREAKDOWN | 180 | Breakdown #2 — amen audio + sliced kick/snare peeking + Hoover drone + crowd low |
| 13 | AMEN_REBUILD | 180 | Climbing back — Hoover chord stabs + STAB rave skank + GUITAR puncts + slice half-time pattern |
| 14 | HARDCORE_FULL | 180 | Full mix — amen + 4OTF ghosted + Hoover rave stabs + STAB skank + GUITAR 4-on-floor + PUNK snare lift + sliced amen scrambled |

Tempo shifts baked via `Scene.tempo` LOM property (`set_scene_tempo` RPC),
so each scene fire snaps the project tempo and persists in `.als`.

## Print pipeline

1. `back_to_arrangement → song_time=0 → set_tempo(87)`
2. `set_session_record(True) + set_record_mode(True)`
3. `start_playback`
4. For each scene 0..14: poll `current_song_time` via `get_listener_snapshot`,
   wait until `scene_idx × 16` beats, then `fire_scene`.
5. Vinyl-scratch flourish (FX slot 4 single fire) at the &-of-4 of scenes
   5 and 11 — heralds the dub→ska and 4OTF→breakdown transitions.
6. 8-bar tail after scene 14 fires.
7. `stop_playback → back_to_arrangement → song_time=0 → set_tempo(87)`.

`scripts/print_arc_to_arrangement.py`.

## Mix

`scripts/eq_clean_lanes.py` walked all 19 tracks and applied EQ8 with
HP/LP per track role to clear frequency space:

```
Kick lanes (T0/T14/T17/T18)  HP 30   LP open
SUB                           HP 30   LP 700   (sub-only, < 100 Hz)
BASS / BASS_AUDIO             HP 50   LP 400   (no sub clash)
BREAK / BREAK_RACK / SLICES   HP 80   LP 12k
WURLY                         HP 200  LP 5k
HAMMOND / STAB                HP 200  LP 6k
GUITAR                        HP 200  LP 8k
HOOVER / VOX                  HP 150  LP 8k
PAD                           HP 250  LP 8k
ATMOS                         HP 250  LP 12k
FX                            HP 180  LP open
```

## Track inventory at print time

| T | Name | Device | Notes |
|---|------|--------|-------|
| 0 | DRUMS | DrumGroup (curated 5-pad) | kick, snare, hat_c, hat_o, crash on 36/38/42/46/49 |
| 1 | BREAK | audio | TSP_IHD_160 amen — slot 0/2 dub use, slot 9/12-14 hardcore use |
| 2 | TSP_IHD_160_drum_break_amen_chop_4bar | DrumGroup | 32 amen slices on pads 36-67 |
| 3 | SUB | audio | ZEN_RETR_175_bass_sub_bonk_Emin (warp Complex Pro mode 6) |
| 4 | BASS | Operator | walking bass MIDI |
| 5 | STAB | DrumGroup (Selectah Kit) | chromatic stab voice on pads 52+ — ragga skank |
| 6 | PAD | audio | RP_SK_87_Keys_organ_feeler_G (warp Complex Pro) |
| 7 | VOX | Simpler (dv_vocal_rasta) + Grain Delay (Bubbles, pitch zeroed) | sparse rasta toaster, full-length triggers |
| 8 | FX | audio | AA_Dub_Siren_F + BBC_vinyl_scratch on slot 4 |
| 9 | HAMMOND | Wah Synth Organ.adg | sustained Em chord beds for dub scenes |
| 10 | WURLY_SKANK | Basic Wurly DI + Vinyl Distortion (Dubplate) + Saturator (A Bit Warmer) | factory `Progression Reggae Upbeat Skank` clip transposed -8 to Em |
| 11 | BREAK_RACK | DrumGroup (Riddim Rager Kit) | 5 native MIDI break patterns from `breaks_ragga` |
| 12 | ATMOS | audio | BBC_pulsing_bass_hum / general_crackle / rowdy_crowd_hall |
| 13 | GUITAR | DrumGroup (Selectah substrate) | 4 power-chord one-shots on pads 36-39 |
| 14 | HARDCORE_KIT | (user hand-tuned) | gabber kicks + impact hits |
| 15 | HOOVER | Simpler (Hoover Synth) | rave hoover stabs |
| 16 | BASS_AUDIO | (user hand-tuned) | REESEY BASS 90BPM D loop for dnb scenes |
| 17 | PUNK_KIT | DrumGroup (Selectah Kit) | acoustic-style punk drums |
| 18 | KICK_4OTF | DrumGroup | Hell's Screamer on pad 36, Heavy Room on pad 37 |

## Source material inventory

### Splice (paid)
Drum hits curated by user:
`tp_nh_cjb_kick_one_shot_low_punchy.wav`,
`BOS_AJ_Drum_Snare_One_Shot_Press_A_sharp.wav`,
`ZEN_PDB_hi_hat_closed_one_shot_tight.wav`,
`shs_ins_hat_open_one_shot_Fit.wav`,
`cj_cymbal_one_shot_live_ahman.wav`.

Audio loops/one-shots:
`TSP_IHD_160_drum_break_amen_chop_4bar.wav`,
`ZEN_RETR_175_bass_sub_bonk_Emin.wav`,
`100_-_Em_-_Guitar_Pad_Texture.wav` (later replaced by Freesound),
`X10_PDH_100_vocal_yo_chargie / _big_up / _selassie_i.wav`.

This-build-specific Splice (7 credits):
`DIASPORA_classicriddims_one_shot_organ_bubble_Emin.wav`,
`PAT_LOK_brass_one_shot_chord_realhorns_discostab_Emin.wav`,
`RP_SK_87_Keys_organ_feeler_G.wav`,
`SS_DR_85_organ_chords_rhythm_delay_mawga_Gmin.wav`,
`lfb2_bass_90_giico_Em.wav`,
`dv_vocal_rasta.wav`,
`AA_Dub_Siren_F.wav`.

### BBC RemArc (personal/research only)
`BBC_pulsing_bass_hum`, `BBC_general_crackle`, `BBC_rowdy_crowd_hall`,
`BBC_factory_siren`, `BBC_vinyl_scratch`. Fetched via `thelmic.sources.bbc`.

### Freesound (CC0 / CC-BY only)
55 samples across 14 categories — see `scripts/freesound_ragga_sweep.py`
and `scripts/freesound_ska_punk_dnb_sweep.py`. Highlights used in this
build: `xKicks - Hell's Screamer / Heavy Room` (gabber_kick),
`Hoover Synth` (hoover), `4 power-chord one-shots` (power_chord),
`REESEY BASS 90BPM D` (reece_bass), `Break_Dnb_174_Bpm_01` (dnb_break).

### Live factory
`Selectah Kit.adg` (drum rack — used 4× across STAB/GUITAR/PUNK_KIT/KICK_4OTF
because most other "kits" are wrapped Instrument Racks),
`Riddim Rager Kit.adg` (BREAK_RACK substrate),
`24_7 Kit.adg` (originally for DRUMS fallback, not used in final),
`Wah Synth Organ.adg` (HAMMOND),
`Vinyl Distortion / Dubplate.adv` + `Saturator / A Bit Warmer.adv` (WURLY dirt),
`Grain Delay / Bubbles.adv` (VOX),
`Progression Reggae Upbeat Skank I - IV - V - IV C Major 85 bpm.alc`
(WURLY_SKANK MIDI clip, transposed -8 to E).

### Live grooves
`Drum Booth / Grooves / Swing Reggae.agr` — applied to DRUMS + STAB +
HAMMOND + WURLY clips for all dub-side scenes (0-5).

## Notable musical decisions

- **All tonal tracks unified to Em natural minor** by mapping E-major
  G♯/C♯/D♯ → G/C/D after the factory wurly transpose landed in E major
  (see `scripts/ragga_unify_em_and_dirty_wurly.py`).
- **BREAK_SLICES (T2) chops are weaponised** — sparse kick+snare in
  scene 12 (breakdown peek), half-time rebuild in 13, full 32-position
  scrambled permutation in 14.
- **Vox is sparse + grain-delayed** (45% wet, pitch zeroed, coarse 0.30,
  feedback 0.78) — one or two D3 triggers per clip max.
- **WURLY_REMIX scene 5** is a "breakdown canvas" — proven to flatter
  whatever you drop on top of it.
- **Riser technique** (`vox_pitched_riser`): same one-shot retriggered
  per bar, +1 semitone each time. Universally safe (touches every
  chromatic note). Works before either DROP or BREAK.

## Scripts that built this (in order)

```
scripts/session_example_ragga.py         define + build ragga_v1
scripts/ragga_dancehall_dressup.py       Selectah on STAB, Hammond track,
                                          rolling RAGGAJUNGLE fill
scripts/ragga_groove_and_factory_skank.py  Swing Reggae groove + factory
                                            wurly skank import
scripts/ragga_unify_em_and_dirty_wurly.py  E maj → Em + Dubplate dirt
scripts/build_break_rack.py              5 native MIDI break patterns on
                                          BREAK_RACK
scripts/bbc_atmos_layer.py               BBC samples → ATMOS track
scripts/freesound_ragga_sweep.py         25 CC samples
scripts/freesound_ska_punk_dnb_sweep.py  30 CC samples for hardcore arc
scripts/arc_scenes_6_to_9.py             ska/punk/hardcore/dnb scenes
scripts/layer_scenes_12_to_14.py         hardcore extension layers
                                          (incl. break-slice patterns)
scripts/eq_clean_lanes.py                frequency separation
scripts/print_arc_to_arrangement.py      song-time-aligned print
```

## What didn't make it but exists

- The 5 Splice samples DIASPORA / PAT_LOK / SS_DR not directly placed
  on tracks — sit in User Library Splice for use in future builds.
- 17 of 25 ragga-sweep Freesound samples not yet placed (vinyl crackle
  variations, sub bass drones, AI vocal toasts).
- 23 of 30 hardcore-sweep Freesound samples not yet placed.
- BBC `factory_siren` sits in User Library — not yet placed in scene.
- Scenes 6-7 ska/punk had no acceptable-license CC samples for upstroke
  guitar / horns / vocals — used Live stock + power-chord drum rack
  instead.

## Memory hooks for reproduction

- The new RPCs (`set_scene_tempo`, `get_scene_tempo`,
  `select_track`, `select_scene`, `get_clip_notes`, `remove_clip_notes`,
  `get_grooves`, `set_clip_groove`, etc.) live in `live_remote_script`.
  All require Live restart after deploy.
- The pack registry (`thelmic.aesthetics.dnb_jungle.ARRANGEMENTS`)
  exposes `jungle` and `ragga` arrangements. Switch via
  `intent.overrides["arrangement"] = "ragga"`.
- Pack also exposes `BREAK_PATTERNS`, `TRANSITIONS`, `BREAK_DESCRIPTIONS`,
  `TRANSITION_NOTES` for direct use.
