# thelmic.bridge — genre-neutral Live-control substrate

The bridge knows nothing about any specific musical genre. It contains:

- **Mechanical helpers** (`helpers/`) — track / device discovery, EQ utils,
  transport rituals, sidechain mechanics, MIDI list manipulation,
  parameter clamp-and-set with semantic-name resolution.
- **Tonality** (`tonality/`) — Key, Scale (modes), Chord factories,
  Voicing operations.
- **Narrative grammars** (`grammars/`) — protocols describing the SHAPE
  of a piece: BuildDropRelease, StaticDrone, IsoRhythm, ThroughComposed,
  Rotational. Aesthetic packs reference grammars by name.
- **Timeline engine** (`timeline/`) — typed event walker that fires
  scenes, schedules ramps, executes tempo changes, all wall-clock
  calibrated, captured into arrangement automation by session_record.
- **Re-exports** of LiveChannel + MediatedSession + SessionLog so
  `from thelmic.bridge import *` is the one-stop import for any pack.

## What the bridge does NOT contain

- Any pattern generator (drum patterns, melodic phrases, etc.)
- Any "drop" / "anticipation" / "build" semantics
- Any frequency-separation table or gain-staging defaults
- Any track-name expectations (TECTONIC, HARDKIT, …)
- Any tempo / key / time-signature defaults
- Any aesthetic preferences ("the impact is sacred", "harsh voices need taper")

Everything genre-specific lives in **`thelmic.aesthetics.<pack_name>`**.

## How an aesthetic pack works

A pack is a Python package providing:

```
pack.yaml          # manifest (key, BPM, grammar, expected roles)
__init__.py        # exports PACK_GRAMMAR, PACK_BPM, PACK_KEY_ROOT,
                   #         build_timeline(), prepare_clips(ch) (optional)
constants.py       # pack-scoped constants (drum-pitch map, mix tables)
patterns.py        # generators for drum / melodic / textural fragments
transforms.py      # anticipation, breathing, decay-tail transforms
arrangement.py     # build_timeline() returns Timeline of bridge events
```

The bridge's `fire_arrangement()` walks any Timeline. It does not know
or care whether the events represent a dnb arrangement, a drone, or
a Reichian phasing piece.

## Adding a new pack

1. `mkdir thelmic/aesthetics/your_pack/`
2. Write `pack.yaml` with bpm, key, grammar choice, required roles
3. Write `arrangement.py` with a `build_timeline()` returning Timeline
4. Optionally `prepare_clips(ch)` for content writing before the print
5. Run `python scripts/verify_packs.py` to structurally validate
6. Run `python scripts/print_with_pack.py your_pack` to print to Live

The bridge handles all the realtime ramp scheduling, RPC routing,
session-record orchestration, drift-correction polling, and arrangement
capture.

## Available grammars

| Grammar | Climax shape | Anticipation |
|---|---|---|
| `BuildDropRelease` | drop/release | tightening hats → silence → impact |
| `StaticDrone` | none | continuous swell |
| `IsoRhythm` | none | the process IS the anticipation |
| `ThroughComposed` | one global climax | harmonic tension buildup |
| `Rotational` | none (cyclical) | none |

Add a new grammar by writing `thelmic/bridge/grammars/your_grammar.py`
implementing the `Grammar` protocol from `base.py`.

## Available SemanticParam

The bridge's `SemanticParam` enum lets packs target intent rather than
device-specific param names. Resolved via `DEVICE_PARAM_MAP` to actual
Live params.

```
GAIN, CUTOFF, RESONANCE, PITCH, DETUNE, DRIVE, DENSITY, CHARACTER,
DRY_WET, THRESHOLD, RATIO, ATTACK, RELEASE, LFO_RATE, LFO_AMOUNT,
LFO_SHAPE, DELAY_TIME, DELAY_FB, REVERB_SIZE
```

Adding a new device class: extend `DEVICE_PARAM_MAP` in
`bridge/helpers/params.py` with the (semantic → param-name) mapping.
