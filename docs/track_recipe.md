# Track recipe — building a new piece end-to-end

A how-to for the next track on the same infrastructure. Walks the
build chain, names the reusable building blocks, and points at the
scripts that wired them together for `babylon_schizophrenia` so you
can fork the workflow without spelunking through commits.

## The shape of a build

```
SOURCE  →  PACK  →  SESSION  →  COMPOSE  →  PRINT
```

- **SOURCE** — gather samples (Splice MCP, BBC RemArc, Freesound,
  Internet Archive, NASA, plus Live factory presets).
- **PACK** — declare the aesthetic (`thelmic.aesthetics.<name>`):
  layout, channel meta, scene plan, optional arrangements registry,
  break patterns, transitions.
- **SESSION** — define a named recipe (`thelmic.sessions.Session`) =
  intent (BPM, key, arc, mood, overrides) + bindings (samples per
  role, presets per role). Idempotent build reconciles against current
  Live state.
- **COMPOSE** — decorate the layout with MIDI patterns + audio dupes
  per scene per channel. Pack-declared `SCENE_PLAN` does this
  automatically; one-off scripts can also add scenes outside the plan
  for arc extensions.
- **PRINT** — walk the scene timeline into the arrangement view via
  `session_record + arrangement_record`, song-time-aligned to avoid
  quantization drift. Optional flourishes at scene boundaries.

## Source layer (`thelmic.sources`)

```python
from thelmic import sources
from thelmic.sources import freesound, bbc, internet_archive, nasa

print(sources.list_sources())   # which adapters have credentials?

hits = sources.find("amen break", limit=10)              # fan-out
hits = freesound.search("hoover synth", limit=10,
                         max_duration=4)                  # single source
local_path = sources.fetch(hits[0])                       # cached
```

License gating in your search loop:

```python
def is_acceptable(lic):
    s = (lic or "").lower()
    if "publicdomain/zero" in s: return True              # CC0
    if "/licenses/by/" in s and "by-nc" not in s \
       and "by-nd" not in s and "by-sa" not in s:
        return True                                       # CC-BY plain
    return False
```

Mirror to Ableton User Library so Live's path resolver finds them:

```python
DST = Path.home() / "Documents" / "Ableton" / "User Library" / "Samples" / "Freesound"
shutil.copy2(cached, DST / f"FS_{label}_{h.id}_{safe_title}{ext}")
```

Working sweep examples — `scripts/freesound_ragga_sweep.py`,
`scripts/freesound_ska_punk_dnb_sweep.py`,
`scripts/bbc_atmos_layer.py`.

## Pack layer (`thelmic.aesthetics.<pack>`)

A pack exposes:

- `LAYOUT: MetaLayout` — N channels × M scenes, with role-typed
  channel kinds (`DRUM_RACK / SYNTH / SAMPLER / AUDIO`).
- `SCENE_PLAN: dict[scene_name, dict[role, action]]` — `"audio"` to
  duplicate slot-0 audio, or a callable returning MIDI notes.
- `CHANNEL_AUDIO: dict[role, ChannelAudio]` — frequency + level meta
  per role. Realised by `apply_channel_audio` (HP/LP per FreqRegion).
- `ARRANGEMENTS: dict[name, {layout, scene_plan, clip_length,
   description}]` (optional) — multiple arrangements over the same
  channel set. Selected via `Intent.overrides["arrangement"]`.
- `BREAK_PATTERNS / TRANSITIONS` (optional) — registries of
  pattern generator callables.

`dnb_jungle` pack has both `jungle` and `ragga` arrangements (same
8 channels, different scene names + plans). Add a new arrangement
by creating a new submodule (`compose_<name>.py`) and adding an entry
to `ARRANGEMENTS`.

## Session layer (`thelmic.sessions.Session`)

```python
sess = Session.open("my_track", pack="dnb_jungle")
sess.intent.bpm = 87.0
sess.intent.key_root = "Em"
sess.intent.overrides["arrangement"] = "ragga"
sess.bindings.set_sample("drums.kick", "user_library/Samples/Splice",
                         "your_kick.wav", pad_note=36)
sess.bindings.set_sample("break", "user_library/Samples/Splice",
                         "your_break.wav")
sess.save()
sess.build(ch)    # idempotent — re-runs are no-ops on populated state
```

Build steps (each skip-if-already-true):
1. Tempo
2. Layout — channels + scenes via `MetaLayout`
3. Drum-rack pads — per-pad hotswap (`load_sample_to_pad`)
4. Role-track samples — kind-aware (audio/sampler/synth)
5. Mix — `apply_channel_audio` realises `CHANNEL_AUDIO`
6. Compose — fills clips per `SCENE_PLAN`
7. Preset bindings — instruments per role

## Compose patterns

Pack-declared MIDI generators return note dicts. **Schema is
`start_time`** (post-49a81f3 RPC):

```python
def my_drum_pattern():
    return [
        {"pitch": 36, "start_time": 0.0, "duration": 0.25, "velocity": 115},
        {"pitch": 38, "start_time": 1.0, "duration": 0.25, "velocity": 110},
        ...
    ]
```

Reusable break/transition libraries:

```python
from thelmic.aesthetics.dnb_jungle import (
    BREAK_PATTERNS,        # rolling_dub_ragga, stepper_half_time,
                            # skank_carpet, dub_minimal_space,
                            # double_time_dnb
    TRANSITIONS,           # vox_pitched_riser, hat_acceleration
    BREAK_DESCRIPTIONS,
    TRANSITION_NOTES,
)
```

Available drum rack pad mappings: `breaks_ragga` uses Riddim Rager / Selectah
GM-mapped layout (KICK 36, PERC 37, SNARE 38, CLAP 39, SNARE_JAZZ 40,
KICK_HARD 41, HAT_C 42, TOM_LO 43, CRASH 44, TOM_MID 45, HAT_O 46,
TOM_HI 47, BLIP_LO 48, CRASH_HARD 49, BLIP_HI 50, RIDE 51).

## Per-scene tempo

```python
ch.set_scene_tempo(scene_index, bpm)   # bake into Scene.tempo LOM
ch.get_scene_tempo(scene_index)        # returns -1.0 if unbound
```

Persists in the .als. Live snaps the project tempo when the scene fires.
`bpm=0` (or negative) unbinds.

## Print

`scripts/print_arc_to_arrangement.py` is the canonical pattern:

1. `back_to_arrangement → song_time=0 → set_tempo(<scene_0_bpm>)`
2. `set_session_record(True) + set_record_mode(True)`
3. `start_playback`
4. For each scene: poll `current_song_time` via `get_listener_snapshot`,
   wait until `(scene_idx × beats_per_scene)`, then `fire_scene`.
5. Optional: fire single FX clips for flourishes between scenes.
6. Tail (8 bars) so the last scene records fully.
7. `stop_playback → session_record off → record_mode off →
   back_to_arrangement → song_time=0`.

**Use `current_song_time` from `get_listener_snapshot`, not
`get_session_info`** — the latter doesn't expose it.

## Mix

`scripts/eq_clean_lanes.py` — walks all tracks, ensures EQ8, sets
band 1 (HP) and band 8 (LP) per role. Frequency separation rules:

```
kick lanes        HP 30   LP open
sub               HP 30   LP 700
bass              HP 50   LP 400
break / drum      HP 80   LP 12k
wurly / hammond   HP 200  LP 5-6k
guitar / hoover   HP 150-200  LP 8k
vox               HP 150  LP 8k
pad               HP 250  LP 8k
atmos             HP 250  LP 12k
fx                HP 180  LP open
```

For deeper gain staging, `apply_channel_audio(ch, roles, channel_audio,
metered=True)` measures actual peaks and writes per-device output
trim corrections. Costs ~25 s per device.

## Common gotchas

- **Drum Rack vs Instrument Rack**: most factory `.adg` kits in
  `drums/` are *Instrument Racks containing drum racks* — the outer
  wrapper filters MIDI notes, so notes 36/38/42 don't trigger drum
  pads. Confirmed bare `DrumGroupDevice` kits: `Selectah Kit.adg`,
  `Riddim Rager Kit.adg`. Use these as your substrate, then
  `load_sample_to_pad` to overwrite.
- **Auto-detected loop regions** are often wrong on imported audio —
  set `loop_end` explicitly via `set_clip_loop_region`, or disable
  warp with `set_clip_warp(track, slot, warping=False)` and let the
  sample play at native rate.
- **`.alc` clips bring their own track** — Live spawns a new track
  with the original instrument context when you load a Live Clip.
  Plan to rename / merge afterwards.
- **`.agr` groove files** — load via `load_item_at_path(track,
  'packs/Drum Booth/Grooves', 'Swing Reggae.agr')`. Lands in the
  groove pool; apply with `set_clip_groove(track, slot, pool_idx)`.
- **MIDI `time` vs `start_time`**: post-49a81f3 RPC reads `start_time`
  exclusively. Generators using `time` silently collapse all notes
  to t=0.
- **Live restart for Remote Script changes**: any edit to
  `live_remote_script/__init__.py` requires deploying to
  `/c/ProgramData/Ableton/Live 12 Suite/Resources/MIDI Remote
  Scripts/ThelmicLive/__init__.py` and a full Live restart. Toggling
  the Control Surface to None and back sometimes works; quitting
  and reopening Live always works.

## Suggested next-track recipe

1. New session intent: pick BPM + key + mood. Override arrangement
   if using `ragga` vs `jungle` or build a new one.
2. New samples: run a focused Freesound sweep with relevant queries
   (e.g. `house upstroke`, `garage shuffle`, `breakcore tear`). Mirror
   to User Library.
3. Pick a kit substrate (`Selectah Kit` or `Riddim Rager` —
   confirmed bare drum racks). Overwrite GM-positioned pads with the
   curated samples.
4. Compose using `BREAK_PATTERNS` / `TRANSITIONS` plus your own.
5. Bake tempos via `set_scene_tempo`.
6. EQ via `eq_clean_lanes` adapted for your track set.
7. Print via `print_arc_to_arrangement` adapted for your scene count
   + tempo map.
