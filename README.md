# thelmic — agentic Ableton control

> An instrument you ride, not configure.

Two things live in this branch:

1. **The original thelmic engine** — a generative music engine producing MIDI directly. Rule-based: voices, archetypes, dimensions, anticipation curves, transformers. See [ARCHITECTURE.md](ARCHITECTURE.md).
2. **An LLM-driven Ableton control surface** built on top — a Live Remote Script + Python async client that gives an agent (Claude, in our testing) full programmatic control of Ableton Live: tracks, devices, clips, audio routing, sidechain, automation, drum-rack pads, master bus, Splice samples, the lot.

This README focuses on (2). The original engine docs are unchanged.

---

## What this branch demonstrates

A live-tested hypothesis: **can an LLM build a coherent, mixed, genre-correct music session in Ableton from scratch in real time?**

The session log this branch produced:
- Reese bass on Operator, hand-built via parameter introspection (195 actual params, not the 18 I'd guessed)
- A 4-scene DnB session (intro / drop / breakdown / drop+) with sidechain, parallel-bus glue, dub-flavoured stab-and-response, an FM wobble feature with automation cliff into the climax
- A jungle session at 165 BPM in G minor with Amen-style breakbeat, sub bass with kick-keyed sidechain, reggae offbeat skank, atmospheric pad, fake-drop at the 8-bar mark, dancehall vocal stabs from Splice
- All of it via the LOM bridge, with iterative live mixing decisions guided by reading actual Ableton meters

There are mistakes baked into the journey — see [`memory/`](memory/) for the corrections that turned into rules-of-thumb (gain staging discipline, EQ8 filter type values, normalized-vs-raw param ranges, the snap-pad-layered-with-snare gotcha, etc.).

---

## The bridge

### Architecture

```
┌─────────────────────────────────┐         ┌──────────────────────────┐
│  Claude (or any LLM session)    │         │  Ableton Live 12         │
│                                 │         │                          │
│  python:                        │  TCP    │  MIDI Remote Script:     │
│  thelmic.live_channel           │ ◄─────► │  ThelmicLive             │
│   • async TCP client            │   :9878 │   • UI-thread dispatcher │
│   • priority + bulk queues      │         │   • 64 RPCs              │
│   • lazy connect, drop-on-      │         │   • LOM access           │
│     overflow, request-id corr   │         │                          │
│   • LOWER process priority      │         └──────────────────────────┘
│     (so Live's UI breathes)     │
└─────────────────────────────────┘
```

The Remote Script is a thin RPC dispatcher (~1600 lines) that exposes Live's Object Model surface. Each RPC blocks on the Live UI thread for 20–200 ms; the Python client side is fully async with bounded queues so the realtime MIDI engine never waits on it.

### What the 64 RPCs cover

| Category | RPCs | What you can do |
|----------|------|-----------------|
| Session / transport | `ping`, `get_session_info`, `set_tempo`, `start_playback`, `stop_playback`, `fire_clip`, `stop_clip`, `stop_all_clips`, `fire_scene`, `set_launch_quantization` | Tempo control, scene firing, transport, launch-quant |
| Tracks / mixer / routing | `create_midi_track`, `create_audio_track`, `delete_track`, `set_track_name`, `set_track_volume`, `set_track_pan`, `set_track_mute`, `set_track_solo`, `set_track_arm`, `set_track_monitoring`, `set_track_output_routing`, `get_track_output_options`, `set_send`, `get_return_tracks`, `get_master_track`, `get_track_info` | Full track lifecycle, output routing (bus topology), monitoring states for sidechain inputs |
| Clips | `create_clip`, `set_clip_name`, `clear_clip`, `add_notes_to_clip`, `set_clip_loop`, `set_clip_loop_region`, `set_clip_warp`, `set_clip_envelope`, `clear_clip_envelope` | MIDI authoring, loop region for stutter/chop, warp mode, automation envelopes (Saturator drive ramp, filter sweep, etc.) |
| Devices | `get_device_info`, `set_device_param`, `get_device_param`, `delete_device`, `move_device`, `set_device_sidechain_source`, `get_device_routing_options`, `define_rack_macro`, `set_macro_value`, `get_rack_macros`, `snapshot_track`, `restore_track` | Per-param control, real sidechain key routing, rack macros, full-track snapshots |
| Master bus | `load_master_device`, `get_master_device_info`, `set_master_device_param`, `get_master_device_param`, `delete_master_device` | Master-track Limiter/EQ/Glue Comp |
| Drum Rack | `get_drum_pads`, `set_drum_pad_mute`, `set_drum_pad_volume`, `load_item_at_path` (with drum-pad target) | Mute the snap-pad-that-isn't-a-snap, load samples directly into pads |
| Browser / loading | `get_browser_tree`, `get_browser_items_at_path`, `list_browser_roots`, `load_browser_item`, `load_item_at_path` | Walk every browser root (instruments / samples / user_library / plugins / Splice Bridge), load by URI or path |
| Arrangement | `get_arrangement_loop`, `set_arrangement_loop` | Arrangement loop region (clip placement on timeline TBD) |
| Metering | `get_track_meter`, `get_all_meters` | Read peak/RMS in real time during playback for live mix decisions |

### Sound-design layer

`thelmic/sound_design/` sits above the bridge and is genre-agnostic:

- `Patch` dataclass — JSON-serialisable instrument patch with parent lineage
- `PatchBuilder` — fluent API with fuzzy parameter-name matching against curated device knowledge
- `apply_patch(channel, patch, track, mode='replace'|'overlay'|'morph')` — reify a Patch into Live
- `bootstrap_device_knowledge(channel, track, device)` — introspect a live device and write its actual parameter ranges as JSON. Use this **before** writing patches; the catalog values you'd guess are wrong (Saturator Drive is normalized 0..1, not −36..+36 dB; Operator has 195 params, not 18; etc.)
- `library` — filesystem-backed patch library (`~/.thelmic/patches/`)
- `devices/*.json` — device knowledge files (Operator currently bootstrapped from real Live state; others stubs)

### Splice integration

The newly-released Splice MCP plugin (April 2026) lets Claude search the Splice catalog, generate AI stacks from a prompt, and download samples. Combined with this bridge:

```
Claude prompt
   │
   ▼
mcp__splice__prompt_to_stack ──► 4-layer stack (drums/bass/keys/pad)
   │
   ▼
mcp__splice__download_asset ───► presigned URL per sample
   │
   ▼
curl to ~/Documents/Ableton/User Library/Samples/Splice/
   │
   ▼
ch.load_item_at_path(track, "user_library/Samples/Splice", filename)
   │
   ▼
Sample lands on a Live audio track, time-stretched to session BPM,
auto-keyed to session key, ready to fire
```

End-to-end: Splice prompt → playing in Ableton in under a minute.

---

## Memory & feedback corpus

[`memory/`](memory/) holds the corrections accumulated through hands-on sessions. Each one is the residue of a "wait, that doesn't work" moment:

- `feedback_audio_gain_staging.md` — every stage's input must stay below clip; don't stack hot synth + heavy saturator + comp makeup; key the melodic bus from PERC BUS, not raw kick
- `feedback_irreverent_naming.md` — name tracks/clips with character (BLO-WHOLE, ULTRAKICK, GUTPUNCH, ESOPHAGUS); expletives + wordplay approved
- `feedback_assume_rpc_adds.md` — pre-approved Remote Script extensions; just add them and reload
- `project_obviating_thelmic_engine.md` — the active hypothesis test: can hand-built LLM compositions through the LOM channel replace the rule-based engine?

These are designed to be loaded as a system-prompt addendum for any future LLM driving this stack.

---

## Quick start

### 1. Install the Remote Script

```bash
# Windows
cp -r thelmic/live_remote_script "C:/ProgramData/Ableton/Live <ver>/Resources/MIDI Remote Scripts/ThelmicLive"
# macOS
cp -r thelmic/live_remote_script "/Applications/Ableton Live <ver>.app/Contents/App-Resources/MIDI Remote Scripts/ThelmicLive"
```

Restart Live → Preferences → Link/Tempo/MIDI → set a Control Surface slot to `ThelmicLive`. You'll see "ThelmicLive listening on 9878" briefly in the status bar.

### 2. Install the Python client

```bash
pip install -e ".[dev]"
```

### 3. Smoke test

```python
import os; os.environ["LIVE_CHANNEL_ENABLED"] = "1"
from thelmic.live_channel import LiveChannel
ch = LiveChannel(); ch.start()
print(ch.ping().result(timeout=3))         # → {'pong': True, 'port': 9878}
print(ch.get_session_info().result(timeout=3))
ch.stop()
```

### 4. Build something

The `scripts/` directory has end-to-end examples:
- `build_dnb_session.py` — 4-scene DnB session (drums + reese + pad + lead), bus topology, sidechain
- `jungle_predrop_drop.py` — pre-drop / drop opener pair
- `jungle_dub_ragga.py` — dub-flavoured scene with delay-tail vocals
- `jungle_fake_drop.py` — fake drop at the 8-bar mark for tense scene transitions

Each is a single `python scripts/<name>.py` invocation given Live is running with ThelmicLive selected.

---

## Status

**Channel & RPCs:** functional. 64 RPCs, ~1600-line Remote Script, async Python client. Tested in real sessions across DnB, jungle, dub.

**Sound design:** functional. Patch / PatchBuilder / apply_patch / lineage / bootstrap-device-knowledge all working.

**Splice integration:** functional. Splice MCP → download → load → play, end-to-end automated.

**Open holes** (worth filling next):
- Drum-rack chain manipulation beyond mute (delete chain, reorder samples)
- Arrangement-view clip placement (programmatic timeline composition vs session view only)
- Audio analysis / spectrum readback (would need M4L bridge — not standard LOM)
- Curated device knowledge JSONs need bootstrapping for everything beyond Operator

**Compared to Anthropic's official Ableton connector** (April 2026): theirs is documentation-Q&A only — grounds Claude's answers in Ableton's manuals. **It does not control Live.** This branch is the agentic counterpart: actual session-building, mixing, and composition.

---

## Future shape

If extracted as a standalone project, the cleanest split is:
1. **MCP server** wrapping the Remote Script + RPC layer — surfaces all 64 commands as `mcp__ableton-control__*` tools to any LLM
2. **`thelmic-sound-design`** Python lib — Patch / PatchBuilder / curated device knowledge, usable above any LOM connector
3. **Genre+discipline prompt packs** — the memory corpus as system-prompt addenda

The Remote Script ships embedded in (1) with a one-shot installer that drops the file into Live's MIDI Remote Scripts dir.

---

## Troubleshoot

- **`ConnectionRefusedError`**: Live isn't running, ThelmicLive isn't selected as a Control Surface, or the script crashed. Check `Help → Open Log Folder` → `Log.txt` for Python tracebacks.
- **`commands_dropped` climbing**: queue's full. Either bug or Live's UI thread is stalled. Check `ch.status()`.
- **Adding new RPCs requires a full Live restart** — not just toggling the Control Surface in Preferences. Live caches imported modules; only a process restart re-imports. Clear `__pycache__/` in the Remote Script directory if a stale `.pyc` is hanging around.
- **Param values seem wrong / things go silent**: Live API parameter ranges vary wildly — many are normalized 0..1 even when the UI shows dB or Hz. **Read `param.min` / `param.max` first** (`get_device_param` returns them) before writing values. The number of mistakes I made on this in one session is documented in `memory/feedback_audio_gain_staging.md`.
- **Filter type integers in EQ Eight aren't what you'd guess** — type 3 is bell (confirmed); types 0/1 (alleged HP variants) and 6/7 (alleged LP variants) caused "no bass" outcomes when miswired. Probe by listening or by `get_device_param`.

---

## Origin

Built in a single live session as a probe of agentic music creation. Approach: hand the LLM control of Ableton, see what happens. The bridge, the sound-design layer, the Splice integration, the memory corpus, this README — all written by Claude across the session, with a real human in the chair driving direction, course-correcting on every sonic decision, and naming things much better than I would have alone.
