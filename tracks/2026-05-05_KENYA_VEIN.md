# KENYA VEIN (working title)

> 8 scenes. 7 lanes. 155 BPM. Em.
> Clean afro-EDM substrate, transient-chopped Zulu/female vocals through
> 8-bit Redux, kick-driven sidechained sub with a hoarse low boom layer
> for the drops. 2026 hard-house / big-room archetype shape.

**Build date:** 2026-05-05
**Branch:** `track/2026-05-04_afro-edm` (cut off `refactor/bridge-aesthetic-split`)
**Project:** session-only — no arrangement print this round.
**Tooling:** `thelmic` Python bridge ↔ Ableton Live 12 Suite via `ThelmicLive` Remote Script (port 9878).

## Possible names

`KENYA VEIN` · `BOOM HOARSE / BOOM SOFT` · `LINGALA SCHISM` · `KIBERA 155`
· `ZULU LATE BY 15MS` · `SIDECHAIN MARABOU`

## The arc (2026 EDM archetype mapping)

| # | Scene | Archetype | What happens |
|---|---|---|---|
| 0 | INTRO_PULSE       | hypnotic       | Sub holds (2-bar each), 4 kicks total, no perc, single rap fragment + reverb tail |
| 1 | INTRO_BUILD       | gather         | Sub pulses every bar, 8th hat shake, snare 2/4, 4 medium rap phrases |
| 2 | PRE_DROP          | tension/release| Hat acceleration 8th→16th→16th-trip→32nd. Snare roll bar-8. Kick + sub silent on bar 8 (the **silence pause**). Bass hint bar 7. Rap fragments accelerate. |
| 3 | DROP_FULL         | climax         | 4OTF kick + sub kick-tied + off-beat OH (1.5/3.5) + bass walk Em-G-A-B / E-A-B-D + rap chop every beat + STAB on every 1 + HOARSE_BOOM mirroring kick at +15ms |
| 4 | ROLL_PEAK         | sustain        | 4OTF + 16th kick double-up + 16th hat carpet + 8th rolling bass (root + 5th) + 8th-note rap chop + STAB quad on every beat + HOARSE_BOOM 16th rolls |
| 5 | BREAK_HYPNOTIC    | breath         | Drums silent, sub holds 8 bars, 4 long rap solo phrases, no stab, no hoarse |
| 6 | RE_BUILD          | gqom-like      | Triplet hat carpet + accelerating snare ghosts + sub density ramp (1/bar→1/beat→8th→16th) + bass roots + STAB density pyramid + accelerating rap phrases |
| 7 | FINAL_DROP        | full slam      | Full 4OTF + every-& kick accent + dense OH + bass full + heavy rap chop (8th-grid + stutters) + STAB quad + stutter + HOARSE_BOOM full crunch |

8 bars / 32 beats per scene. Tempo locked to 155 across all scenes via `set_scene_tempo`.

## Lane plan

| T | Track | Instrument | Notes |
|---|---|---|---|
| 0 | KICK_BOOM       | Drum Rack (Splice `19_Kick.wav`) | 4OTF + ghosts, EQ HP 30 |
| 1 | PERC_CRISP      | Drum Rack (Splice clean snare/hat-c/hat-o) | snare 2/4, off-beat OH in drops, EQ HP 80 LP 12k |
| 2 | SUB_VEIN        | Operator E1 sub | **sidechained heavy from KICK_BOOM** via Compressor at idx 1, EQ HP 30 LP 700 |
| 3 | BASS_KENYA      | Operator | Em walking line, drop-only, EQ HP 50 LP 400 |
| 4 | STAB_TWENTYTWO  | Drum Rack (Live-sliced FS_48404 twentytwo, 55 transient slices) | One-Shot + Trigger Mode=1, Redux2 8-bit / 0.55 SR, EQ HP 200 LP 6k, Drum Rack Attack macro 0 (no fade-in) |
| 5 | RAP_NAIROBI     | Drum Rack (Live-sliced Splice `DS_VAH3_124_rap_dry`, 83 transient slices) | One-Shot + Trigger Mode=1, Redux2 8-bit / 0.55 SR, EQ HP 150 LP 8k, Attack macro 0 |
| 6 | HOARSE_BOOM     | Operator → Saturator (Drive max, Type 4) → Erosion (Mode 2, Freq 0.3, Amount 0.85) | E1 mirrored kick at +0.04 beat (~15 ms). Active in S3/S4/S7 only. Vol 0.50. EQ HP 30 LP 1500 |

## Sources used

- **Splice (7 credits)**: `19_Kick`, `JORDY_DAZZ_snare_smack`, `pmt_clhat_coral_short`, `Hihat_Open` (Cr2), `STCR2_NAH_Bass_OneShot_Core_G`, `DS_VAH3_124_rap_dry`, `SC_BPD_vocals_high_call`. Final two became Live-sliced racks.
- **Freesound (12 IDs, all CC0/CC-BY)**: Zulu Vocal pack `132346-132396` (Fight/Yeah/Hello/Hmmf/The World/Ding Mao Chung deep+filter+reverb variants), plus `48404` *twentytwo*, `586994/607221` Shekere, `213344` Lingala. The twentytwo file became STAB_TWENTYTWO; Zulu pack staged but unused after audition.

## Bridge work this session

`thelmic/live_remote_script/__init__.py` extended (deployed to ProgramData,
required Live restart) with three new RPCs:

- `set_drum_pad_chain_device_property(track, device, note, chain_device_index, property_name, value)` — for OriginalSimpler `playback_mode` and similar properties.
- `set_drum_pad_chain_device_param(track, device, note, chain_device_index, param_index|name, value)` — for slider-type params on chain Simplers (used to set per-pad `Trigger Mode=1`).
- `get_drum_pad_chain_device_info(track, device, note, chain_device_index)` — returns class, params, and known properties for a chain device.

Plus `thelmic/sources/_config.py` extended to look up `~/.thelmic/.env` as
fallback (so the Freesound API key persists across worktrees without a
project-scoped or registry-scoped change).

## Gotchas hit

- **MP3 chopping is blocked without ffmpeg.** Pure-Python WAV slicer works
  for Splice WAV (24-bit handled), but Freesound previews are MP3 only
  (token auth) and the box has no ffmpeg/pydub/librosa/soundfile/scipy.
  Workaround: load MP3s as audio clips in Live (native decode) and use
  Live's Slice to MIDI Track with the user's eyes/ears. Bridge-side
  there's no LOM access to "Slice to New MIDI Track" (UI-only command).
- **Slice rack pads default to gate-cut on note-off.** Setting
  `playback_mode=1` (One-Shot) is necessary BUT the Drum Rack also has
  a top-level Attack macro (idx 5) that ramps in volume across all pads.
  Default 13 ≈ 38 ms attack — felt as "starts a few ms late".
  Set the macro to 0 for instant attack across the whole rack.
- **`bash cd && curl & ... wait` chain ran in the worktree root** because
  the `&` background separators ran each curl in a subshell that
  didn't inherit the cd. Files landed in repo root — moved manually.
  For future: `cd "$DST" && (curl ... &) && wait` or use absolute `-o` paths.
- **`move_track` exists in the LiveChannel API but the server-side handler
  is missing.** Tried using it to position the new sliced rack at T5;
  errored with "'Song' object has no attribute 'move_track'". Worked
  around by deleting the old track first and accepting whatever index
  the new slice landed at.
- **Operator at MIDI 16 (E0) is infrasonic** (~20 Hz). Bumped HOARSE_BOOM
  to E1 (28, ~41 Hz) to actually be audible.
