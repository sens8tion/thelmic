# Handoff — fresh-start agent brief

You're picking up an in-flight project cold. The previous agent's context
got too big. This doc is the single source of truth — read it end to end,
then proceed with the user's next instruction. Don't try to reconstruct
history beyond what's here.

**Branch:** `refactor/bridge-aesthetic-split`
**Last commit:** `3b8dbab docs: HANDOFF.md — single-source state doc`
**Repo:** `git@github.com:sens8tion/thelmic.git`

---

## The user's IMMEDIATE next ask (when they're ready)

> *"Fully load a drum kit with samples / default percussion instruments."*

You should:

1. Test if Live's per-pad Drum Rack load is now working (user just updated Live).
   ```python
   # Test path: bulk_load_drum_pads on a fresh DRUMS rack with these 5 hits
   items = [
     {"name": "tp_nh_cjb_kick_one_shot_low_punchy.wav",     "note": 36},
     {"name": "BOS_AJ_Drum_Snare_One_Shot_Press_A_sharp.wav","note": 38},
     {"name": "ZEN_PDB_hi_hat_closed_one_shot_tight.wav",   "note": 42},
     {"name": "shs_ins_hat_open_one_shot_Fit.wav",          "note": 46},
     {"name": "cj_cymbal_one_shot_live_ahman.wav",          "note": 49},
   ]
   ```
   These 5 are already in `~/Documents/Splice/Samples/` and mirrored to
   `~/Documents/Ableton/User Library/Samples/Splice/`. Code path is
   `thelmic.aesthetics.dnb_jungle.lifecycle.pull_samples` — already wired.

2. **If the load succeeds** (5 distinct pads populated): the user gets curated jungle drum hits per pad. Done.

3. **If it fails** (Live API still puts everything on pad 36): fall back to loading factory `24_7 Kit.adg` from `query:Drums#FileId_10800` via `load_item_at_path("drums", "24_7 Kit.adg")` — this preset ships fully populated. Wraps as `InstrumentGroupDevice` but MIDI routes through to the inner Drum Rack.

The user previously rejected the factory-kit fallback as "giving up", so try (1) first and only fall back to (2) if Live's API genuinely still has the bug.

---

## Possible Control-Surface confusion right after Live update

User noted Live didn't have ThelmicLive set as the input port after the
update, BUT RPCs were still working. Possible causes:
- Previous Live instance still running in background
- Remote Script still loaded from cache

If RPCs hang / fail when you start, ask user to verify in Live:
**Preferences → Link/Tempo/MIDI → Control Surface slot → ThelmicLive selected**.
Status bar should briefly show "ThelmicLive listening on 9878".

---

## Architecture (one-screen version)

```
thelmic/
  bridge/                       ← genre-neutral, never modify for genre reasons
    helpers/   discovery / eq / transport / params / sidechain / midi / splice
    tonality/  Key / Scale / Chord / Voicing
    grammars/  BuildDropRelease / StaticDrone / IsoRhythm / ThroughComposed / Rotational
    timeline/  Timeline + RampSpec + fire_arrangement engine
  aesthetics/
    manifest.py  pack.yaml loader
    dnb_jungle/  fleshed-out: ragga → Rotterdam arc, BuildDropRelease grammar
      pack.yaml + constants.py + patterns.py + transforms.py
      arrangement.py   ← Timeline build via bridge events
      lifecycle.py     ← setup / pull / compose / mix / prepare / preview hooks
    ambient_drone/  stub
    idm_glitch/     stub
  live_channel.py            LOM TCP client (port 9878, async, priority+bulk queues)
  live_remote_script/        Live MIDI Remote Script — REQUIRES LIVE RESTART after edit
  mediated_session.py        open_session() — canonical entry, auto-logs
  session_log.py             SessionLog — chat/action/snapshot/feedback capture
  agent_helpers.py           DEPRECATED — back-compat shim only
```

**Bridge knows nothing about any genre.** Aesthetic packs declare BPM, key,
grammar, expected track roles, mix recipes. Multiple packs share the same
bridge engine.

---

## Lifecycle (the only entry point you should use)

```bash
python scripts/run_pack.py dnb_jungle [--phases p1,p2,...] [--skip-drops]
```

| Phase | Function | What it does | State |
|-------|----------|--------------|-------|
| `setup` | `setup_session(ch)` | Bootstrap 16 named tracks, ensure 17+ scenes, add Saturator on drums + EQ8 on every track | working |
| `pull` | `pull_samples(ch)` | Scan local Splice library, load matched samples into role tracks | working except Drum Rack per-pad load (above) |
| `compose` | `compose_clips(ch)` | Write ~30+ MIDI clips across 16 tracks | working |
| `mix` | `configure_mix(ch)` | Frequency separation HP/LP per role + audio fade-ins + SUBBONK loop=False | working |
| `prepare` | `prepare_clips(ch)` | Anticipation fills on slots 3, 6, 13 (thinned + sacred impact + breathing + pull-back) | working |
| `preview` | `preview_session(ch)` | Fire scenes in session view, NO record (audition) | working |
| `print` | (engine) | Arm session_record + walk timeline, capture into arrangement automation | working |

**Default invocation runs all 7 phases in order.** User can pass `--phases preview` to just audition existing content, `--phases print` to commit to arrangement without rebuilding, etc.

---

## What's confidently working

- **Bootstrap from a fresh empty Live project** — creates 16 named role-tracks, deletes Live's defaults
- **Operator preset loading** per synth role (Anarchy Reese, Atom Lead, Chord Minor to Major, Basic FM Bells, Boinky Saw Riser, Amp Bass)
- **Splice MCP fetch** — `describe_a_sound` + `download_asset` workflow proven
- **User Library mirroring** — auto-copies samples from `~/Documents/Splice/Samples/` to `~/Documents/Ableton/User Library/Samples/Splice/` for Live's path resolver
- **Audio clip loading** (BREAK / SUB / ORGAN / PAD)
- **Simpler sample loading** (VOX_CALL / VOX_RESP / VOX_CHOR)
- **Realtime parameter ramps captured into arrangement automation** during `session_record` (proven on legacy session: 32 ramps + 2 tempo modulations + false-drop survived to print, drift held under ±1.5 bars)
- **Master-bus targeting** — `track="MASTER"` routes to `set_master_device_param`
- **Wall-clock-calibrated scene firing** — `fire_arrangement` calibrates once against `song_time` then schedules everything on monotonic wall clock
- **Anticipation transforms** — `breathe_velocity`, `pull_back_before_drop` (impact at clip_length-0.125 stays sacred), `anticipation_fill`

## What's known broken

- **Live's per-pad Drum Rack sample load** — `selected_drum_pad = X; b.load_item(item)` is async; the load lands on pad 36 regardless of which pad we pre-selected. Verified across multiple workarounds (fresh rack, delete+recreate device, delete+recreate track, sleeps, per-pad RPC, bulk RPC). User just updated Live to test if it's fixed.
- **Live's clip-envelope playback** — `clip.create_automation_envelope(param)` + `add_breakpoint(time, value)` succeed at the API but Live's playback engine ignores them. We pivoted to **realtime `set_device_param` during `session_record`** which works.

## What requires a Live restart

ANY change to `thelmic/live_remote_script/__init__.py` requires a full Live restart (closing the project isn't enough — Live caches at the Python interpreter level). Deploy via:

```bash
cp thelmic/live_remote_script/__init__.py "/c/ProgramData/Ableton/Live 12 Suite/Resources/MIDI Remote Scripts/ThelmicLive/__init__.py"
rm -rf "/c/ProgramData/Ableton/Live 12 Suite/Resources/MIDI Remote Scripts/ThelmicLive/__pycache__"
```

Then **fully quit and reopen Live**.

## Live session state right now

Tracks (subject to whatever the user did during the Live update):
```
T0  DRUMS         InstrumentGroupDevice (24_7 Kit, fully populated), Saturator, EQ8
T1  AMEN          DrumGroupDevice (empty), EQ8
T2  PERC          DrumGroupDevice (empty), EQ8
T3  BREAK         EQ8 + audio clip on slot 0
T4  SUB           EQ8 + audio clip on slot 0
T5  ORGAN         EQ8 + audio clip on slot 0
T6  PAD           EQ8 + audio clip on slot 0
T7  MID_BASS      Operator (default sine), EQ8       — needs preset loaded for character
T8  STAB          Operator (default sine), EQ8
T9  REESE         Operator (default sine), EQ8
T10 LEAD          Operator (default sine), EQ8
T11 SHIMMER       Operator (default sine), EQ8
T12 VOX_CALL      Simpler (yo chargie), EQ8
T13 VOX_RESP      Simpler (big up), EQ8
T14 VOX_CHOR      Simpler (selassie i), EQ8
T15 FX            Operator (default sine), EQ8
T16-T20 KICK/SNARE/HAT_C/HAT_O/CRASH (orphan from a failed multi-track Simpler experiment)
```

Splice samples downloaded (in `~/Documents/Splice/Samples/` AND `~/Documents/Ableton/User Library/Samples/Splice/`):
- `tp_nh_cjb_kick_one_shot_low_punchy.wav`
- `BOS_AJ_Drum_Snare_One_Shot_Press_A_sharp.wav`
- `ZEN_PDB_hi_hat_closed_one_shot_tight.wav`
- `shs_ins_hat_open_one_shot_Fit.wav`
- `cj_cymbal_one_shot_live_ahman.wav`
- `TSP_IHD_160_drum_break_amen_chop_4bar.wav`
- `ZEN_RETR_175_bass_sub_bonk_Emin.wav`
- `AFP_SDRL_156_organ_bubble_cutchie_Am.wav`
- `100_-_Em_-_Guitar_Pad_Texture.wav`
- `X10_PDH_100_vocal_yo_chargie.wav`, `_big_up.wav`, `_selassie_i.wav`

5 Splice credits already spent on the drum hits.

## User's standing preferences (from prior sessions)

- **Track names should be role-named, not historical** ("DRUMS" not "HARDKIT", "MID_BASS" not "TECTONIC", "PAD" not "COLD MIST"). Already done.
- **Don't leave Live's default 4 stub tracks lying around** after bootstrap. Already handled by `cleanup_default_tracks`.
- **Be sarcastic / sardonic when things don't work, swearing OK.** Audio-engineer voice.
- **Sacred impact** — the kick+snare+crash unison at clip_length-0.125 never gets velocity-attenuated by transforms.
- **Render from arrangement, not session view** — before any Export Audio/Video, do `stop_all_clips + back_to_arrangement + song_time=0`. (See `feedback_render_from_arrangement.md`.)
- **Mediated session capture is mandatory** — every session goes through `open_session()` which logs every chat turn / RPC / state snapshot to `sessions/<id>/log.jsonl` for the self-training corpus. Don't bypass it.

## Memory files

In `~/.claude/projects/C--Users-eric-github-sens8tion-thelmic/memory/`:
- `MEMORY.md` — index
- `feedback_audio_gain_staging.md` — every stage's input must stay below clip
- `feedback_irreverent_naming.md` — name with character (3RDEYEZ vibe). **NB: contradicts the new role-named scheme; defer to role-named for tracks, irreverent for clip names + patches**
- `feedback_render_from_arrangement.md` — back_to_arrangement before export
- `project_obviating_thelmic_engine.md` — the original probe

## How to start the conversation cleanly

1. Read this file end to end (you've now done that).
2. Confirm Live is running with `ThelmicLive` selected as the Control Surface.
3. Ask if the user wants you to attempt step (1) of the immediate ask above (Splice per-pad drum load test).
4. From there: `python scripts/run_pack.py dnb_jungle --phases pull` is the one-line invocation that exercises the drum-load path.

If the user wants something different from the immediate ask, follow them. The lifecycle phases are independently runnable; you can re-enter any phase any time.
