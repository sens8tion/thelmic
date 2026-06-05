# Pulse Field — Max for Live devices

Field-native generation for thelmic. The system does not ask *which note plays
next* — it asks *what is the state of the field*, and lets rhythm and texture
**crystallise** out of field conditions. This is **Option A** of the Pulse
Field plan: the devices are built in Max for Live exactly as the branch spec
describes, fed by a Python field driver over OSC.

> **This is a separate, parallel track.** It does not touch thelmic's
> planner-first engine (PhrasePlan, voices, bank generator). Run it on its own
> Live tracks. See [`docs/pulse-field-plan.md`](../../docs/pulse-field-plan.md)
> if/when you want to migrate toward Option B (pure-Python, no Max).

---

## Quickstart — first sound in ~10 minutes

Use the **combined instrument** (`thelmic.pulse-field-instrument.*`): Stage 0 +
Stage 1 in ONE device, a single self-contained JS with no `require()`, no
cross-device LOM. Fastest, lowest-risk path to hearing it.

1. **Build the bundle** (already generated, but to be safe):
   ```bash
   node thelmic/devices/tools/bundle.js
   ```
   This writes `thelmic.pulse-field-instrument.bundle.js`.
2. In Ableton, add a **Max MIDI Effect** to a MIDI track, click **edit**.
3. `File ▸ Open` → `thelmic.pulse-field-instrument.maxpat`. Select all, copy,
   paste into the device, delete the template placeholder. Save As
   `thelmic.pulse-field-instrument.amxd`. Keep the `.amxd` in the same folder as
   the `.bundle.js` (or add the folder to the device file search path).
4. After the device, add a **Drum Rack** (or any instrument). Onsets come out
   centred low (MIDI ~36–50), so a kick/perc on those notes works.
5. Turn on the device's **clock toggle** (the 5 ms onset metro).
6. Run the field driver:
   ```bash
   python -m examples.pulse_field_drive
   ```
   You should hear onsets thicken/thin as the walk crosses Oak → Chaos → Nott.
   No driver handy? Just move the field with OSC: send `/thelmic/field/pressure
   0.9` to UDP 7400, or drag sliders in the combined **test patch** (next section).

If notes don't appear: confirm the clock toggle is on, the bundle file is on the
device's search path, and `udpreceive 7400` shows OSC arriving (the `print
pulsefield` object logs onset counts to the Max console).

---

## Signal flow

```
Python (landscape position + motion -> field vector)
   │  OSC  /thelmic/field <8 floats>   (UDP 7400)
   ▼
┌──────────────────────────────┐
│ Stage 0  Field State (.amxd)  │  source of truth; 8 Live params + broadcast
└──────┬───────────────────────┘
       │ LOM param reads  /  Max broadcast outlets
       ├───────────────────────────┬───────────────────────────┐
       ▼                           ▼                           ▼
┌───────────────┐        ┌──────────────────┐         ┌────────────────┐
│ Stage 1       │        │ Stage 2          │         │ Stage 3        │
│ Rhythmic      │        │ Texture /        │         │ Monitor        │
│ Crystallisation│       │ Atmosphere       │         │ (jsui)         │
│ MIDI onsets   │        │ continuous audio │         │ visual only    │
└───────────────┘        └──────────────────┘         └────────────────┘
```

The eight field dimensions, canonical order (defined once in
[`src/field-osc-config.js`](src/field-osc-config.js)):

`pressure · stability · density · discomfort · silence · novelty · urgency · momentum`

---

## File map

```
thelmic/devices/
├── README.md                              ← this file
├── thelmic.pulse-field-instrument.maxpat  ← COMBINED instrument (fast path)
├── thelmic.pulse-field-instrument.bundle.js ← generated single-file device JS
├── thelmic.field-state.maxpat             ← Stage 0 reference patch
├── thelmic.rhythmic-crystallisation.maxpat← Stage 1 reference patch
├── thelmic.texture.maxpat                 ← Stage 2 reference patch
├── thelmic.monitor.maxpat                 ← Stage 3 reference patch
├── thelmic.pulse-field-test.maxpat        ← combined test bench (no Live needed)
├── src/
│   ├── field-osc-config.js   shared dimension set + OSC scheme + helpers
│   ├── field-state.js        Stage 0: OSC receive, params, broadcast, freeze
│   ├── onset-engine.js       Stage 1 CORE — pure physics (node-testable)
│   ├── rhythmic-crystallisation.js  Stage 1 Max glue (field -> MIDI)
│   ├── instrument-glue.js    combined Stage 0+1 glue (bare-name, bundled)
│   ├── texture-audio.js      Stage 2 CORE — pure field->control mapping
│   ├── texture.js            Stage 2 Max glue (control values -> audio graph)
│   ├── territory.js          Oak/Chaos/Nott profiles + nearest-neighbour
│   ├── monitor.js            Stage 3 glue (history, velocity, territory)
│   └── monitor-ui.js         Stage 3 jsui renderer
├── test/
│   ├── test-onset-engine.js     21 checks — Stage 1 acceptance tests as units
│   ├── test-pure-modules.js     17 checks — territory + texture mapping
│   └── test-instrument-bundle.js 7 checks — bundle end-to-end (Max API stubbed)
└── tools/
    ├── gen_maxpat.js         regenerates the .maxpat files from the config
    └── bundle.js             builds the single-file instrument bundle
```

The Python upstream lives in [`thelmic/pulse_field/`](../pulse_field/):
`field_vector.py` (landscape→field), `osc.py` (zero-dep OSC), and the driver
[`examples/pulse_field_drive.py`](../../examples/pulse_field_drive.py).

---

## Building the `.amxd` devices

The `.maxpat` files are **reference patches** — valid Max patcher JSON you can
open and inspect. Max for Live devices (`.amxd`) must be created from a Live
device template so they get the correct device I/O. The JS does the real work,
so the wiring transfers by copy-paste:

1. In Ableton, create a new device of the right type:
   - Stage 0 / 1 / 3 → **Max MIDI Effect**
   - Stage 2 → **Max Audio Effect**
2. Click the device's **edit** (pencil) button to open the Max editor.
3. `File ▸ Open` the matching `thelmic.*.maxpat`, select all (`Cmd/Ctrl-A`),
   copy, and paste into the device. Delete the template placeholder objects.
4. Make sure the `src/` folder is in the device's file search path
   (`Options ▸ File Preferences`, or keep the `.amxd` next to `src/`). The
   `[js ...]` objects load by filename and `require()` siblings from `src/`.
5. `File ▸ Save As` → name it `thelmic.field-state.amxd` etc.
6. For Stage 0, the eight `live.dial`/`live.slider` objects are the automatable
   Live parameters — confirm each shows `parameter_enable` on and is named for
   its dimension.

> The `[js]` objects use CommonJS `require("field-osc-config")` /
> `require("onset-engine")` etc. Max 8 supports this for files on the search
> path. Keep `src/` reachable.

---

## Field subscription — two paths

Each consumer device (Stages 1–3) gets the field one of two ways:

- **LOM observe** (runtime): send the device the message
  `observe live_set tracks <T> devices <D>` pointing at the Field State device.
  It attaches `LiveAPI` observers to every parameter whose name matches a field
  dimension. Use this once devices live on real Live tracks.
- **Inlet feed** (testing): patch field values straight into the device's left
  inlet as `field <8 floats>` (canonical order) or `<dim> <value>`. The
  combined test patch uses this — no Live, no LOM required.

OSC settings live in `src/field-osc-config.js`: port **7400**, root
**`/thelmic/field`**. Stage 0's `[udpreceive 7400]` parses OSC and the JS strips
the address prefix itself, so no `[route]` objects are needed.

---

## Driving it from Python

```bash
# stream a walk Oak -> Chaos -> Nott -> Oak to the devices on UDP 7400
python -m examples.pulse_field_drive
python -m examples.pulse_field_drive --once --rate 30 --host 127.0.0.1
```

Or in code:

```python
from thelmic.pulse_field import FieldDriver, OSCSender

driver = FieldDriver(seed=0)
with OSCSender("127.0.0.1", 7400) as osc:
    field = driver.update(x, y)            # landscape position -> FieldVector
    osc.send("/thelmic/field", *field.as_tuple())
```

`FieldDriver` reuses the existing `thelmic.landscape_map.LandscapeMap`, so the
Oak/Chaos/Nott territory model is **shared with the rest of thelmic**, not
reinvented.

---

## Acceptance tests

### Automated (run now, no Max)

```bash
# Stage 1 + pure mappings (node)
node thelmic/devices/test/test-onset-engine.js       # 21 checks
node thelmic/devices/test/test-pure-modules.js       # 17 checks
node thelmic/devices/test/test-instrument-bundle.js  #  7 checks (end-to-end)

# Python upstream (pytest, incl. a real-socket OSC round-trip)
python -m pytest tests/test_pulse_field.py -q         # 16 checks
```

The node tests are the spec's Stage 1 acceptance criteria expressed as
deterministic units (threshold firing, refractory, hysteresis, density→
polyphony, stability→smear, silence suppression, urgency, velocity).

### In Max — combined test bench

Open `thelmic.pulse-field-test.maxpat`. It contains Stage 0 + Stage 1 + Stage 3
in one patcher with manual sliders, so you can verify the whole chain without
Live:

1. Turn on the two `[toggle]`s (drives the 5 ms onset clock and 16 ms monitor).
2. Raise the **pressure** slider past ~0.65 → onsets start printing / playing.
3. Drop **stability** below 0.3 → onset timing smears (variance in the print).
4. Raise **density** → multiple concurrent onsets per fire.
5. Raise **silence** → onsets thin out / drop.
6. Watch the **monitor jsui**: eight bars track the sliders, the pressure trace
   scrolls, and the territory label flips between OAK / CHAOS / NOTT.

### Per device (in Live)

- **Stage 0**: send `/thelmic/field/pressure 0.7` from Python → the `pressure`
  param and UI update; automate `stability` from a clip → readout tracks;
  `freeze 1` holds values while OSC keeps arriving.
- **Stage 1**: connect MIDI out to a drum rack; ramp pressure → onsets begin;
  no output should be recognisable as a *named* drum pattern (field-native).
- **Stage 2**: insert on an audio track, build the audio graph (below); sweep
  discomfort → texture brightens; silence → texture quietens; stability down →
  resonance up.
- **Stage 3**: animate dimensions → all eight bars + trace + territory track.

---

## Stage 2 audio graph (build by hand in Max)

`texture.js` emits 11 control values on its outlets; wire them into a noise
texture. Suggested graph (per spec — three parallel layers, field-mixed):

```
noise~ ─┬─ svf~   (sub: center=sub_freq)            ─ *~ sub_level ─┐
        ├─ reson~ (mid: freq=mid_freq, Q=mid_q,                     │
        │          bandwidth shaped by mid_bw)       ─ *~ mid_level ─┤─ +~ ─ overdrive~(drive) ─ *~ master ─ plugout~
        └─ hip~   (air: cutoff=air_freq)             ─ *~ air_level ─┘
```

Smooth every control with `[line~ <evo_ms>]` so the texture evolves
continuously (urgency shortens `evo_ms`, momentum lengthens it). Outlet order:
`0 sub_freq · 1 sub_level · 2 mid_freq · 3 mid_bw · 4 mid_q · 5 mid_level ·
6 air_freq · 7 air_level · 8 drive · 9 master · 10 evo_ms`.

---

## Spec reconciliation

Where the implementation deviates from the literal branch spec, and why:

1. **No pre-existing LOM bridge / Remote Script / OSC.** The spec listed these
   as dependencies; thelmic actually talks to Live over **rtmidi** and has no
   Max layer. So these devices are a from-scratch M4L build (Option A), with a
   new Python OSC sender as the bridge. There is no merge path into the
   planner-first runtime — the two architectures coexist on separate tracks.

2. **Stability is a tightness control, not a hard fire-gate.** The spec's
   pseudocode ANDs `stability < stability_ceiling` into the onset condition,
   which would silence a stable (Oak) field entirely. We instead fire on the
   **pressure** crossing and let stability shape smear + note length, so Oak
   still crystallises. `stability_ceiling` marks the boundary above which
   onsets are maximally tight.

3. **Sustained re-arm for streams.** Strict hysteresis (re-arm only when
   pressure dips below `threshold − hysteresis`) makes a held plateau fire
   once. To get rolling onsets during a build/drop, a supra-threshold field
   re-arms once the refractory window elapses. Pure edge-detection is preserved
   when `refractory_ms == 0`.

4. **Only `pressure` and `stability` pre-existed** among the eight dimensions
   (in `thelmic/dimensions.py`). The other six are new to this branch.

---

## Regenerating patchers

The `.maxpat` files are generated from the shared config so they can't drift:

```bash
node thelmic/devices/tools/gen_maxpat.js
```

Edit dimensions/OSC in `src/field-osc-config.js`, regenerate, re-import to the
`.amxd` shells.
