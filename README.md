# thelmic — agentic Ableton control

> An instrument you ride, not configure.

Three things live in this branch:

1. **The original thelmic engine** — rule-based generative MIDI engine. See [ARCHITECTURE.md](ARCHITECTURE.md).
2. **A genre-neutral Live-control bridge** in `thelmic.bridge` — Live Remote Script + Python async client + helpers + tonality + narrative grammars + event-timeline engine. **Knows nothing about any specific genre.**
3. **Pluggable aesthetic packs** in `thelmic.aesthetics.{pack}` — each pack encodes one musical form (drum patterns, anticipation grammar, mix recipes, section palette, vocabulary). Today's packs:
   - `dnb_jungle` — ragga → Rotterdam arc (BuildDropRelease grammar)
   - `ambient_drone` — slow textural transformation (StaticDrone grammar)
   - `idm_glitch` — rotational variations (Rotational grammar)

The bridge is the substrate; packs are interchangeable. A future Claude prompt can compose in any registered form by switching pack — without modifying the bridge.

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
│   • priority + bulk queues      │         │   • 108 RPCs             │
│   • lazy connect, drop-on-      │         │   • LOM access           │
│     overflow, request-id corr   │         │                          │
│   • LOWER process priority      │         └──────────────────────────┘
│     (so Live's UI breathes)     │
└─────────────────────────────────┘
```

The Remote Script is a thin RPC dispatcher (~1600 lines) that exposes Live's Object Model surface. Each RPC blocks on the Live UI thread for 20–200 ms; the Python client side is fully async with bounded queues so the realtime MIDI engine never waits on it.

### What the 108 RPCs cover

| Category | RPCs | What you can do |
|----------|------|-----------------|
| Session / transport | `ping`, `get_session_info`, `set_tempo`, `start_playback`, `stop_playback`, `fire_clip`, `stop_clip`, `stop_all_clips`, `fire_scene`, `set_launch_quantization` | Tempo control, scene firing, transport, launch-quant |
| Tracks / mixer / routing | `create_midi_track`, `create_audio_track`, `delete_track`, `set_track_name`, `set_track_volume`, `set_track_pan`, `set_track_mute`, `set_track_solo`, `set_track_arm`, `set_track_monitoring`, `set_track_output_routing`, `get_track_output_options`, `set_send`, `get_return_tracks`, `get_master_track`, `get_track_info` | Full track lifecycle, output routing (bus topology), monitoring states for sidechain inputs |
| Clips | `create_clip`, `set_clip_name`, `clear_clip`, `add_notes_to_clip`, `get_clip_notes`, `remove_clip_notes`, `set_clip_loop`, `set_clip_loop_region`, `set_clip_warp`, `set_clip_envelope`, `clear_clip_envelope`, `set_clip_groove`, `clear_clip_groove`, `get_grooves` | MIDI authoring **and surgical per-note edits** (read with `note_id`+probability+velocity_deviation, remove by pitch/time region, then `add_notes_to_clip` to humanize / transpose / regenerate phrase without rewriting the clip), loop region, warp mode, automation envelopes, groove-pool assignment |
| Follow actions | `set_clip_follow_action`, `get_clip_follow_action` | Conditional clip chaining for scene-launching variation: stop, play_again, previous, next, first, last, any, other, jump — with chance weights and dwell time |
| View / capture | `select_track`, `select_scene`, `show_view`, `capture_midi` | Drive Live's UI focus from scripts (jump to Detail/Clip after generation), pull recently played MIDI from the armed track into a clip |
| Listener snapshot | `get_listener_snapshot` | Polling shim for the LOM observer pattern — one read returns is_playing, song_time, tempo, signature, metronome, session_record, and per-track playing/fired slot indices |
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

## Release: agentic studio pipeline (v0.next)

This release closes the first loop — **a single LLM hand-builds a coherent, mixed track end-to-end through the LOM bridge** — and frames the next loop, where multiple specialist personae collaborate iteratively over the same session.

### What v0.next adds

- **`thelmic/agent_helpers.py`** — high-level helpers carrying every lesson the previous sessions earned the hard way:
  - **Parameter range registry** — Live params that look like dB/Hz but are normalized 0..1 (Saturator Drive, Drum Buss, Compressor, EQ8 Frequency); the few that aren't (Drum Buss Transients ±1, EQ8 Gain raw dB, GlueComp Threshold raw dB)
  - **Gain-staging** (`gain_stage_track`, `TRACK_LEVELS`) — role-keyed defaults (sub 0.55 / hat 0.65 / present 0.78 / unity 0.85)
  - **Studio-engineer principles as code** — `HARD_CUT_SAFE_VOICES` vs `HARSH_VOICES_NEED_TAPER`, ms-scale staggers, "impact is sacred" (`pull_back_before_drop` / `thin_build_for_massive_drop` preserve the impact note untouched)
  - **Decay tails** (`crash_decay_tail`, `low_kick_decay_tail`) — never let a loud voice cut into silence
  - **Amplitude breathing** (`breathe_velocity`) — sinusoidal velocity modulation for life on held patterns
  - **Soft outros** (`soft_outro_offsets`) — harsh voices exit first, sub/kick last, reverb tail rings
  - **Multi-take** (`take_start_bar`, `TAKE_GAP_BARS`) — tile N takes side-by-side on the arrangement timeline
  - **Gotcha flags** as named booleans — `DRUM_PAD_INDIVIDUAL_LOAD_BROKEN`, `LIMITER_ON_MASTER_KILLS_BASS`, `SIMPLER_SLICING_VIA_PROPERTY`, etc. so future code can grep them out

- **`scripts/arrangement_record.py`** — health-check + thinned anticipation builds + pull-back velocity ramps + breathing + staggered outro + HARDKIT decay tail. Runs the session straight onto the arrangement timeline; supports `python scripts/arrangement_record.py N` for N takes side-by-side.

### The next loop: agent-mediated studio personnel

v0.next ends in session view. v0.next+1 starts there — and adds named
personae who iterate with the **agent-as-mediator** on the same session.
The agent stands at the centre, translating each persona's intent into
moves and capturing the entire transcript + state to the corpus. Every
exchange flows through `MediatedSession`; every move auto-logs; every
take pairs with snapshots and .als checkpoints. The corpus self-trains
the next generation.

```
                     ┌─────────────────────────────────────┐
                     │  Session view setup (the beginning) │
                     │  • sample selection (Splice MCP)    │
                     │  • beat structures by genre         │
                     │  • style / key / energy targets     │
                     └──────────────────┬──────────────────┘
                                        │
        ┌───────────────────────────────▼───────────────────────────────┐
        │                  AGENT (mediator + logger)                    │
        │  • compositional moves into Live (LoggingChannel: every       │
        │    RPC auto-logged with args + result)                        │
        │  • verbatim transcription of all persona dialogue             │
        │  • state snapshots at decision points                         │
        │  • .als checkpoints whenever a human File>Saves               │
        │  • routes feedback into next pass directives                  │
        └───────────────────────────────┬───────────────────────────────┘
                                        │
        ┌───────────────────────────────┼───────────────────────────────┐
        │                               │                               │
        ▼                               ▼                               ▼
┌───────────────┐               ┌───────────────┐               ┌───────────────┐
│  PRODUCER     │               │  AUDIO ENG    │               │  (future)     │
│  A/B over     │  ◄── agent ──►│  A/B over     │  ◄── agent ──►│  arranger,    │
│  takes        │   mediates    │  takes        │   mediates    │  performer,   │
│               │               │               │               │  mastering    │
│ likes:  …     │               │ likes:  …     │               │               │
│ dislikes: …   │               │ dislikes: …   │               │               │
└───────┬───────┘               └───────┬───────┘               └───────┬───────┘
        │                               │                               │
        └───────────────────┬───────────┴───────────────────────────────┘
                            ▼
            ┌────────────────────────────────────┐
            │  log.jsonl + snapshots + .als      │
            │      ▼                             │
            │  training corpus (self-trains      │
            │  next gen + process-engineering    │
            │  pass extracts patterns)           │
            └────────────────────────────────────┘
                            │
                            ▼
                  (loop: next compositional pass)
```

**Producer persona** — judges song-shape, hooks, energy arc, structural surprise, replay value. Feedback like *"like the breakcore-into-gabber pivot at slot 9, dislike the outro fade — too clean for this track, want a hard tail"*.

**Audio engineer persona** — judges gain staging, frequency masking, transient integrity, stereo image, glue. Feedback like *"like the mid-bass thump on master, dislike the snare poking out at 5kHz on slot 4, sub feels disconnected from kick post-drop"*.

The aggregation layer turns natural-language likes/dislikes into a structured directive set the next compositional pass executes against, while keeping the bones of the takes the personae endorsed.

### Why session view is where the loop starts

The opening setup — sample selection, beat structures by style, style/key/energy shifts — *is the substrate every persona judges against*. Producer feedback that says "more pace in row 9" needs the beat-structure layer to be addressable; engineer feedback that says "sub disconnected from kick" needs the bus/sidechain topology to be addressable. Session view, with its scene-as-section grid, makes both directly editable. The arrangement print is just a deliverable artifact; **the loop's working surface is session view**.

### What carries forward

- All 97 RPCs and the async client (no churn — the bridge is solid)
- `agent_helpers.py` with the studio-engineer principles baked in
- `memory/` corpus as system-prompt addenda for any persona
- The take-tiling pattern (`take_start_bar`) — multi-personae A/B works directly off it
- The thinned-build / sacred-impact / staggered-outro patterns — they survive every iteration

---

## Phase plan

### v0.next (this release) — agent + helpers + capture

Ships:
- 108 RPCs, async LOM bridge, hand-built Sound Design layer
- `agent_helpers.py` — every studio-engineer principle that mattered in
  the previous sessions surfaced as code (parameter range registry,
  gain staging, impact-is-sacred patterns, decay tails, breathing,
  staggered outros, multi-take tiling, gotcha flags)
- `session_log.py` + `mediated_session.py` — the mediated capture
  substrate: `open_session()` is the canonical entry point; every chat
  turn, every RPC, every persona A/B, every state snapshot, every
  .als File>Save flows through the agent into `sessions/<id>/`
- `arrangement_record.py` — the deliverable-artifact step
- README onboarding section for any agent picking this up cold

The first loop is closed: a single LLM, hand-building a coherent mixed
track end-to-end through the LOM bridge, with the entire process
captured for replay.

### v0.next+1 — multi-persona pipeline (agent-mediated)

The intent of the next release, in one sentence:

> **The agent mediates a closed iterative loop in which named human
> personae (producer, audio engineer, future arranger / performer /
> mastering) provide A/B feedback on takes, the agent translates that
> feedback into the next compositional pass, and every exchange —
> dialogue, moves, audio dev state, .als checkpoints — is captured to
> a self-training corpus.**

Why each piece matters:

- **Agent as mediator, not assistant.** The agent stands at the centre
  of every persona/Live exchange. Personae speak in natural language;
  the agent translates intent into RPCs and audio outcomes. The agent
  is the only thing that touches both sides, so the agent is also the
  only thing that can capture the full transcript faithfully.

- **Personae over a single voice.** Producer judges song-shape,
  hooks, energy arc; engineer judges gain staging, masking,
  transients, glue; future arranger judges section flow, performer
  judges feel and groove, mastering judges loudness/translation. Each
  persona's domain is bounded so directives can be aggregated cleanly
  (engineer wins on gain, producer wins on song-shape, etc).

- **A/B over takes, not specs.** Personae react to listenable output,
  not text descriptions. Every pass produces a take; every persona
  responds with `likes=[…], dislikes=[…]`; the agent converts these
  into structured directives (slot, voice, parameter, polarity).

- **Session view as working surface.** The arrangement print is a
  deliverable artifact; mutations land in session-view scenes/clips/
  devices. Sample selection, beat structures, style/key/energy are
  the substrate every persona judges against — and they're directly
  addressable in session view.

- **Capture for self-training.** Chat → moves → state diff → audio
  outcome → persona feedback, all temporally bound and replayable.
  This corpus is what the next-generation model trains on; without
  it the loop is just a craft tool. With it, the loop teaches itself.

Concrete deliverables:

1. **Persona prompt packs** in `memory/personae/`
   - `producer.md` — domain, evaluation criteria, vocabulary, A/B template
   - `audio_engineer.md` — same, plus the gain/mask/transient/glue ruleset
   - extensibility for arranger / performer / mastering
2. **Feedback collector** — converts free-form `likes`/`dislikes` into
   structured directives `{slot, voice, parameter, polarity, source_persona}`
3. **Directive aggregator** — domain-weighted conflict resolution across
   personae; emits a ranked directive list for the next pass
4. **Iteration scaffolding** — each pass reads directives, mutates the
   session, prints a take, surfaces it for A/B, captures responses,
   loops
5. **Corpus tooling** — replay a session from `log.jsonl`; diff state
   snapshots to extract "the move that produced the change"; export
   training samples (prompt, action sequence, audio outcome, feedback)

### v0.next+2 and beyond — process engineering

Once the corpus has enough sessions:

- Pattern extraction over `log.jsonl` — which moves consistently get
  endorsed, which get retracted; which directive shapes route to which
  RPC sequences; which initial conditions predict iteration count
- Auto-distillation of successful patterns into new
  `agent_helpers.py` recipes (closed loop on the helpers themselves)
- Persona refinement — fine-tune on per-persona feedback so the agent
  can predict objections before the human voices them
- Multi-agent: separate agents wearing the personae; the mediator
  agent stays neutral and orchestrates

---

## For the AI agent starting a session

You're an LLM (Claude or otherwise) picking this repo up cold. Read this before doing anything in Live.

### Read the phase plan first

Before any move, read the **Phase plan** section below. v0.next ships
the helpers, the capture substrate, and the first closed loop (single
LLM → coherent mixed track). v0.next+1 — what we're building toward —
is the agent-mediated multi-persona pipeline: producer + audio
engineer (and future arranger / performer / mastering) iterating over
takes, every exchange flowing through you and into the training
corpus. Your work in any session contributes to that corpus, so
treat capture as load-bearing, not housekeeping.

### You are the mediator

Every session in this stack runs through you. Humans (producer,
audio engineer, future personae) speak; you translate intent into
RPCs against Live; Live's state changes; humans react to the
audible result; you log all of it. **The agent isn't a tool inside
the loop — the agent is the loop's orchestrator.**

Three things flow through you and must be captured:

1. **Dialogue** — what the humans said, what you said back, verbatim, in order
2. **Moves** — every RPC fired, with args (the LoggingChannel does this for you)
3. **State** — snapshots of the audio dev state at decision points, plus .als checkpoints when the human saves

The capture is not optional. The corpus this builds is what
the next-generation model trains on, and what the
process-engineering pass uses to extract patterns. **A session
without a log might as well not have happened.**

### Open every session through `mediated_session.open_session`

```python
from thelmic.mediated_session import open_session

with open_session(name="jungle-iteration-3",
                   expected_tracks=["TECTONIC", "HARDKIT", "SUBBONK"]) as sess:
    sess.chat("user", "165bpm jungle in G minor, energy ramps to breakcore at slot 9")
    sess.chat("agent", "starting amen breakbeat into HARDKIT...")

    # Use sess.ch (LoggingChannel) for all RPCs — auto-logs every call
    sess.ch.create_clip(7, 0, 64.0).result()
    # ...build phase...

    sess.snapshot("after-drums")     # state JSON + log entry

    # When the producer/engineer responds, log their words AS they speak
    sess.feedback("producer",
                  likes=["breakcore-into-gabber pivot at scene 9"],
                  dislikes=["outro fade — too clean, want a hard tail"])
    sess.feedback("audio_engineer",
                  likes=["mid-bass thump on master"],
                  dislikes=["snare poking 5kHz on slot 4"])

    sess.als("C:/.../jungle.als", label="post-engineer-pass")  # after File>Save
    sess.note("decision: keep slot 9 pivot, retake outro with crash tail")
# `with` block auto-closes log + stops channel; summary written on exit
```

`open_session()` does the boilerplate: starts a `SessionLog`, opens a
`LiveChannel` wrapped in `LoggingChannel`, runs `health_check`, and
takes an initial snapshot so every session has a "before" diff
reference. Don't construct `LiveChannel` directly unless you're
writing a low-level utility that genuinely must not log.

### Mediation discipline

- **Transcribe humans verbatim.** Don't paraphrase their feedback before logging it. The training corpus needs the raw signal.
- **Log your own replies too.** Both sides of the dialogue belong in the log — the model learns from the agent moves as much as the human ones.
- **Snapshot before AND after material changes.** A snapshot bracketing a build phase lets the diff be reconstructed. Cheap (<1s typically), high-value.
- **Capture A/B as the persona speaks.** Don't batch up feedback at end of session — the temporal binding to the take they're reacting to is what makes the corpus learnable.
- **Checkpoint .als at every save.** When the human does File>Save, immediately call `sess.als(path, label)` so the audio outcome pairs with the log entry.

### State you need before the first RPC

### State you need before the first RPC

1. **Live must be running** with the saved session loaded. A fresh project ships with 4 default tracks — `health_check` will fail-fast on this. Do **not** load samples or build clips into a fresh project; ask the human to open the saved `.als` first.
2. **`LIVE_CHANNEL_ENABLED=1`** must be in the environment. The bridge is off by default — `LiveChannel.start()` silently no-ops without it. Set on the shell, not in code.
3. **`PYTHONIOENCODING=utf-8`** on Windows, or non-ASCII clip names will crash stdout writes mid-session.
4. **Remote Script changes need a full Live restart**, not just toggling the Control Surface dropdown. If you added an RPC, tell the human to fully restart Live before you call it.

Boilerplate to put at the top of any script:

```python
import os, sys
os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from thelmic.live_channel import LiveChannel
from thelmic.agent_helpers import health_check, find_track, TRACK_LEVELS

ch = LiveChannel(lower_priority=False); ch.start()
ok, detail = health_check(ch, expected_track_names=["TECTONIC", "HARDKIT", ...])
if not ok:
    print(f"halted: {detail}")
    sys.exit(0)
```

### Read these files before composing

- **`thelmic/agent_helpers.py`** — start here. The parameter range registry alone will save you from sending raw dB to normalized 0..1 params and silencing channels. Every gotcha is captured as a named constant.
- **`memory/MEMORY.md`** and the linked memory files — feedback the human has given on previous sessions; treat as system-prompt addenda.
- **`scripts/arrangement_record.py`** — the canonical end-to-end pattern (health check → compositional adjustments → arm record → fire scenes → softened outro → decay tails). Don't reinvent this flow.

### Default loop posture

The loop's working surface is **session view**, not arrangement view. Compose into scene slots. Use `arrangement_record.py` only as the deliverable-artifact step — the personae A/B over arrangement takes, but mutations land in session clips/devices.

The opening setup is non-negotiable substrate. Establish it explicitly with the human at session start:
- **sample selection** — Splice MCP `prompt_to_stack` + `download_asset` if needed
- **beat structures** — pick the genre's canonical pattern (amen / gabber / breakcore / four-on-floor / footwork) before laying anything down
- **style / key / energy targets** — get a sentence-level intent ("165bpm jungle in G minor, energy ramps from intro to breakcore at scene 9") before you write the first clip

### How to put the humans in the loop properly

The human is a co-pilot, not a code reviewer. Bring them in at the right altitude:

| Stage | What to ask | What NOT to ask |
|-------|------------|-----------------|
| Session-view setup | "165bpm jungle, G minor, energy arc?" — single-sentence intent | "should the kick be on the downbeat?" — that's your job |
| Sample selection | "want me to pull a Splice stack for `<vibe>`, or hand-pick from user library?" | "which of these 12 kicks?" — pick one and move |
| First take | run a full pass, then surface the take for A/B | nothing — let them hear before commenting |
| Producer A/B | "likes/dislikes on song-shape, hooks, energy?" | mix questions |
| Engineer A/B | "likes/dislikes on gain staging, masking, transients, glue?" | song-shape questions |
| Mid-pass blockers | only when you genuinely cannot proceed (Live not running, expected track missing, RPC errors) | confirmation-seeking on routine choices |

Two failure modes to avoid:
- **Decision-fatigue spam** — asking a series of micro-confirmations ("kick velocity 110 ok? snare on 2/4 ok?"). Make the call, build the take, let them critique the take. Decisions belong to the human; *moves* belong to you.
- **Blind autonomy** — building a 7-minute track without check-in. The audit point is each scene's first listenable form, not the final master.

When the human says "I'll come back" or "go ahead", you have authority to make creative moves. When they say "make me a [genre] track" without further constraint, you still need ONE round-trip on style/key/energy before composing — don't guess.

### Things you will be tempted to do that go wrong

- **Stacking gain into a saturator-then-compressor chain** — every device's *input* must stay below clip, not just the final sum
- **Sending raw dB to a 0..1 param** — Saturator Drive=14 silently clamps to 1.0 (fully maxed). Always check `param.min`/`param.max` first
- **Hard-cutting a harsh voice into silence** — use `crash_decay_tail` or ms-stagger via `soft_outro_offsets`
- **Tapering the impact note** — the drop hit is sacred, never round it
- **Building hats on .25/.75 16ths only** — sounds behind the beat. Lock to the kick grid (every 16th, accent kick-aligned positions)
- **Loading samples into individual drum-rack pads** — `selected_drum_pad + load_item` only populates the first pad. Use `bulk_load_drum_pads` or per-pad Simpler tracks
- **Putting a Limiter on the master** — clamps the bass. Use a gentle Glue Comp instead

### Session logging — always-on substrate, mediated by the agent

The mediated-session pattern (above, "You are the mediator")
describes the canonical entry point: `open_session()` returns a
`MediatedSession` that bundles the channel + log + health check +
initial snapshot. Every script and every agent loop in this stack
goes through it. Direct `SessionLog` / `LiveChannel` construction
is for low-level utilities only.

The capture layout written to `sessions/<utc_ts>_<name>/`:
- `log.jsonl` — append-only timestamped event stream (chat / action / snapshot / feedback / note / als_checkpoint / session_start / session_end)
- `snapshots/*.json` — full state walk (tempo, all tracks → devices → params with current values + min/max, clip note counts, master devices)
- `als/*.als` — copied .als files for replayable audio outcome

The corpus this builds is the v0.next+1 training substrate:
chat → moves → state diffs → audio outcomes → persona feedback,
all temporally bound, all replayable.

### When you finish a session

- Surface the take for A/B (run `scripts/arrangement_record.py` for a deliverable, or note the session-view scene set)
- If you learned something the next agent shouldn't have to re-discover, add it to `thelmic/agent_helpers.py` (as a constant, helper, or comment) — not to a memory file unless it's user-feedback shaped
- Don't write planning/decision documents — the helpers + memory + commit history carry the context

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
