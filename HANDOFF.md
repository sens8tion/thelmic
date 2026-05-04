# Handoff — current state for fresh-start agent

This branch: `refactor/bridge-aesthetic-split` (pushed to origin).
Last commit: `fdbed68 fix: drum content via factory 24_7 Kit`.

## Architecture

```
thelmic/
  bridge/                    ← genre-neutral substrate (no aesthetic choices)
    helpers/                 — discovery / eq / transport / params / sidechain / midi / splice
    tonality/                — Key / Scale / Chord / Voicing
    grammars/                — BuildDropRelease / StaticDrone / IsoRhythm / ThroughComposed / Rotational
    timeline/                — generic event-walker engine + ramp scheduling
  aesthetics/
    manifest.py              — pack.yaml loader
    dnb_jungle/              — fleshed-out, ragga → Rotterdam arc
      pack.yaml + constants.py + patterns.py + transforms.py
      arrangement.py         — Timeline of bridge events
      lifecycle.py           — setup / pull / compose / mix / prepare / preview phases
    ambient_drone/           — stub (manifest + arrangement only)
    idm_glitch/              — stub (manifest + arrangement only)
  agent_helpers.py           — DEPRECATED back-compat shim
  live_channel.py / live_remote_script/ / mediated_session.py / session_log.py
                             — unchanged (LOM bridge mechanism)
```

## Lifecycle phases

```bash
python scripts/run_pack.py dnb_jungle [--phases p1,p2,...]
```

Phases run in this order:

| Phase | What it does | State |
|-------|--------------|-------|
| `setup` | Bootstrap 16 named tracks (deletes Live's defaults), ensure Saturator on drums + EQ8 on every role-track, ensure 17+ scenes | works |
| `pull` | Scan local Splice library, load matched samples into role tracks (audio clips, Simplers, Drum Rack) | works for audio clips + Simplers; Drum Rack uses factory 24_7 Kit fallback (per-pad load broken in Live) |
| `compose` | Write MIDI patterns into ~30+ session-view clips across all 16 tracks | works |
| `mix` | Frequency separation HP/LP per role + audio clip fade-ins + SUBBONK loop=False | works |
| `prepare` | Anticipation fills on pre-drop slots (3, 6, 13) — thinned + sacred impact + breathing | works |
| `preview` | Fire scenes in session view, no record (audition) | works |
| `print` | Arm session_record + walk timeline, capture into arrangement automation lanes | works (verified earlier on the legacy session: 32 ramps + 2 tempo modulations + false drop printed at ±1.4 bar drift) |

## What's working confidently

- **Bridge / aesthetic split** — `verify_packs.py` confirms 3 packs build valid Timelines
- **Track creation, naming, instrument loading, scene creation** — bootstrap from a fresh empty project produces 16 named role-tracks
- **Operator preset loading per role** — MID_BASS / STAB / REESE / LEAD / SHIMMER / FX get distinct factory presets (Anarchy Reese, Atom Lead, etc.)
- **Splice MCP fetch** — `describe_a_sound`, `download_asset` workflow proven (5 drum hits + 7 misc samples already downloaded for this session)
- **User Library mirroring** — samples copied from `~/Documents/Splice/Samples/` into `~/Documents/Ableton/User Library/Samples/Splice/` for Live's path resolver
- **Audio clip loading** — `load_item_at_path` works for audio sample tracks (BREAK, SUB, ORGAN, PAD)
- **Simpler sample loading** — VOX_CALL / RESP / CHOR all load their respective vocal one-shots
- **Realtime parameter ramps during session_record** — `set_device_param` calls during arrangement playback get captured as automation lanes (proven on legacy session: 32 ramps survived to print)
- **Tempo modulation events** — `set_tempo` mid-arrangement works
- **Wall-clock-calibrated scene firing** — drift held under ~1.4 bars across 18+ scene fires
- **Master-bus targeting** — ramps with `track="MASTER"` route via `set_master_device_param` (tidx=-1)
- **Anticipation transforms** — `breathe_velocity`, `pull_back_before_drop`, `anticipation_fill` (impact at clip_length-0.125 stays sacred)

## What's known broken

- **Live's `bulk_load_drum_pads` / per-pad sample loading** — `selected_drum_pad = X; b.load_item(item)` is an async race where `load_item` always lands on pad 36 regardless of which pad we selected. **Verified empirically across multiple workarounds**: fresh rack, delete+recreate device, delete+recreate track, sleeps between loads, per-pad RPC calls. Every approach yields "5/5 loaded" RPC reports but only ONE pad sticks (always 36, with the LAST sample). User is updating Live now to test if the new version fixes this.

  **Current workaround**: load `Drums/24_7 Kit.adg` factory preset which ships fully populated. Wrapped in an InstrumentGroupDevice; MIDI on the track still routes to the inner Drum Rack normally.

- **Clip envelopes silently dropped** — `clip.create_automation_envelope(param)` + `add_breakpoint(time, value)` succeed at the API layer but Live's playback engine ignores them. Pivoted to **realtime `set_device_param` during `session_record`** which Live captures into arrangement automation. This is the proven path for ramps.

## Required Live restarts

After ANY change to `thelmic/live_remote_script/__init__.py`, deploy via:
```bash
cp thelmic/live_remote_script/__init__.py "/c/ProgramData/Ableton/Live 12 Suite/Resources/MIDI Remote Scripts/ThelmicLive/__init__.py"
rm -rf "/c/ProgramData/Ableton/Live 12 Suite/Resources/MIDI Remote Scripts/ThelmicLive/__pycache__"
```
Then **fully quit and restart Live** (closing the project isn't enough). Live caches MIDI Remote Scripts at the Python interpreter level.

## Memory files (legacy session feedback that still applies)

- `feedback_audio_gain_staging.md` — every stage's input must stay below clip
- `feedback_irreverent_naming.md` — name with character (3RDEYEZ vibe) — *contradicts the current role-named scheme; resolve which the user wants*
- `feedback_render_from_arrangement.md` — `stop_all_clips + back_to_arrangement + song_time=0` before Export
- `project_obviating_thelmic_engine.md` — the original probe: can hand-built LLM compositions through the LOM channel replace the rule-based engine?

## State of the user's Live session right now

Tracks present (from before user updates Live):
```
T0  DRUMS         InstrumentGroupDevice (24_7 Kit), Saturator, EQ8
T1  AMEN          DrumGroupDevice (empty), EQ8
T2  PERC          DrumGroupDevice (empty), EQ8
T3  BREAK         EQ8 + audio clip on slot 0
T4  SUB           EQ8 + audio clip on slot 0
T5  ORGAN         EQ8 + audio clip on slot 0
T6  PAD           EQ8 + audio clip on slot 0
T7  MID_BASS      Operator (default sine), EQ8       — needs Operator preset loaded
T8  STAB          Operator (default sine), EQ8       — needs preset
T9  REESE         Operator (default sine), EQ8       — needs preset
T10 LEAD          Operator (default sine), EQ8       — needs preset
T11 SHIMMER       Operator (default sine), EQ8       — needs preset
T12 VOX_CALL      Simpler (yo chargie), EQ8
T13 VOX_RESP      Simpler (big up), EQ8
T14 VOX_CHOR      Simpler (selassie i), EQ8
T15 FX            Operator (default sine), EQ8       — needs preset
T16-T20 KICK/SNARE/HAT_C/HAT_O/CRASH (orphan from per-track Simpler experiment, can be deleted)
```

Splice samples downloaded (5 credits spent + 7 already-existing):
- tp_nh_cjb_kick_one_shot_low_punchy.wav
- BOS_AJ_Drum_Snare_One_Shot_Press_A_sharp.wav
- ZEN_PDB_hi_hat_closed_one_shot_tight.wav
- shs_ins_hat_open_one_shot_Fit.wav
- cj_cymbal_one_shot_live_ahman.wav
(All in `~/Documents/Splice/Samples/` and mirrored to `~/Documents/Ableton/User Library/Samples/Splice/`)

## Open user-flagged issues

1. **"check the percussion"** → currently 24_7 factory kit (whole kit). User dislikes this approach; wanted curated Splice drum hits per-pad which the Live API can't deliver.
2. **"don't tie tracks to old musical intents"** → done (renamed to DRUMS/MID_BASS/PAD/etc.)
3. **"clean up Live's default 4 stub tracks"** → done (`cleanup_default_tracks`)
4. **Outstanding: orphan KICK/SNARE/HAT_C/HAT_O/CRASH tracks from a failed experiment** — remove on next setup or by hand

## Best-bet starting point for fresh agent

If the user wants to **start from scratch architecturally**: revert to `claude/practical-jackson-c96170` (the legacy branch where the actual jungle session is fully fleshed out and printable end-to-end).

If the user wants to **continue this branch**: focus on
- Re-test per-pad drum loading after Live update (5 minutes of work — `load_drum_pad_samples` already in place)
- Wire factory Operator presets into setup (so MID_BASS sounds like a bass not a sine)
- Flesh out ambient_drone and idm_glitch packs
- Implement the persona feedback loop (v0.next+1)

Whatever direction: read `bridge/README.md` and `thelmic/aesthetics/dnb_jungle/lifecycle.py` first.
