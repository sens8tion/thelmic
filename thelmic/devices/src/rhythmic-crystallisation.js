/*
 * rhythmic-crystallisation.js — Pulse Field Stage 1 Max glue.
 *
 * Subscribes to the field, runs the pure OnsetEngine (onset-engine.js), and
 * renders its onset events as scheduled MIDI notes. The engine holds all the
 * physics; this file is the Max-facing layer (uses outlet/Task/post and is
 * therefore only runnable inside Max).
 *
 * Field subscription — two supported paths (see README "Field subscription"):
 *   1. LOM observe:  [js rhythmic-crystallisation.js] with `observe <devpath>`
 *      attaches LiveAPI observers to the Field State device's parameters.
 *   2. Inlet feed:   the patch routes field values straight into inlet 0 as
 *      "field <8 floats>" or "<dim> <value>" (used in the combined test patch
 *      and when you patch Stage 0's broadcast outlets in directly).
 *
 * Clock + tick — the patch drives this with [metro <tick_ms>] -> "tick". We
 * keep our own millisecond clock by accumulating tick_ms, because Max js has
 * no reliable hi-res wall clock. Onsets are emitted on the tick they fire;
 * per-event smear is realised by scheduling each note with a Max Task delay.
 *
 * Output (outlet 0): "<pitch> <velocity> <length_ms>" lists, intended for a
 * [makenote] -> [noteout] (or a drum-rack note in) downstream. Outlet 1 emits
 * diagnostics ("armed <0|1>", "threshold <f>", "count <n>").
 *
 * Pulse Field branch — Stage 1.
 */

var cfg = require("field-osc-config");
var oe = require("onset-engine");

autowatch = 1;
inlets = 1;
outlets = 2;
var OUT_NOTE = 0;
var OUT_DIAG = 1;

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

var engine = new oe.OnsetEngine({});
var fieldvec = cfg.default_vector();   // NOT named `field`: in Max js a top-level
                                       // `var field` would collide with the
                                       // "field" message handler on `this`.
var tick_interval = 5;     // metro interval (ms); settable via "tick_ms <n>"
var clock = 0;             // accumulated milliseconds
var running = 1;
var liveapis = {};         // name -> LiveAPI observer (LOM mode)

// ---------------------------------------------------------------------------
// Field input (inlet feed mode)
// ---------------------------------------------------------------------------

// "field 0.1 0.2 ... 0.8" — whole vector in canonical order.
function field() {
    var a = arrayfromargs(arguments);
    for (var i = 0; i < cfg.DIMENSION_NAMES.length && i < a.length; i++) {
        fieldvec[cfg.DIMENSION_NAMES[i]] = cfg.clamp01(a[i]);
    }
}

// Bare "<dim> <value>" and OSC-style "<root>/<dim> <value>" both arrive here.
function anything() {
    var sel = messagename;
    var a = arrayfromargs(arguments);
    var prefix = cfg.OSC.address_root + "/";
    var name = (sel.indexOf(prefix) === 0) ? sel.substring(prefix.length) : sel;
    if (a.length >= 1 && cfg.index_of(name) >= 0) {
        fieldvec[name] = cfg.clamp01(a[0]);
    }
}

// ---------------------------------------------------------------------------
// LOM observe mode
// ---------------------------------------------------------------------------
//
// `observe <device canonical path>` — e.g.
//   observe live_set tracks 0 devices 0
// Attaches a LiveAPI to each parameter whose name matches a field dimension.
// Falls back silently if the path or parameters are absent.

function observe() {
    var pathParts = arrayfromargs(arguments);
    var devPath = pathParts.join(" ");
    clear_observers();
    try {
        var dev = new LiveAPI(devPath);
        var count = dev.getcount("parameters");
        for (var i = 0; i < count; i++) {
            var pApi = new LiveAPI(devPath + " parameters " + i);
            var pname = pApi.get("name");
            if (pname && pname.length) { pname = pname[0]; }
            if (cfg.index_of(pname) >= 0) {
                attach_param_observer(pname, devPath + " parameters " + i);
            }
        }
        post("[crystallisation] observing " + Object.keys(liveapis).length +
             " field params at " + devPath + "\n");
    } catch (e) {
        post("[crystallisation] observe failed: " + e + "\n");
    }
}

function attach_param_observer(name, path) {
    var api = new LiveAPI(function (args) {
        // args: ["value", <float>]
        if (args && args.length >= 2 && args[0] === "value") {
            fieldvec[name] = cfg.clamp01(args[1]);
        }
    }, path);
    api.property = "value";
    liveapis[name] = api;
    // seed current value
    fieldvec[name] = cfg.clamp01(api.get("value"));
}

function clear_observers() {
    for (var k in liveapis) { liveapis[k] = null; }
    liveapis = {};
}

// ---------------------------------------------------------------------------
// Tick / firing
// ---------------------------------------------------------------------------

function tick() {
    if (!running) { return; }
    clock += tick_interval;
    var events = engine.step(fieldvec, clock);
    for (var i = 0; i < events.length; i++) {
        schedule(events[i]);
    }
    if (events.length > 0) {
        outlet(OUT_DIAG, "count", events.length);
    }
}

function schedule(ev) {
    if (ev.smear_ms <= 0) {
        emit(ev);
    } else {
        // realise positive smear (late) with a one-shot Task
        var t = new Task(function () { emit(ev); });
        t.schedule(ev.smear_ms);
    }
}

function emit(ev) {
    outlet(OUT_NOTE, ev.pitch, ev.velocity, ev.length_ms);
}

// ---------------------------------------------------------------------------
// Control
// ---------------------------------------------------------------------------

function start() { running = 1; }
function stop()  { running = 0; }

function reset_clock() { clock = 0; }

function tick_ms(v) { tick_interval = Math.max(1, +v); }

// Forward device-UI parameter changes into the engine, e.g.
//   "param onset_threshold 0.55"
function param() {
    var a = arrayfromargs(arguments);
    if (a.length >= 2) { engine.setParam(a[0], a[1]); }
}

function diag() {
    var d = engine.diagnostics(fieldvec.urgency);
    outlet(OUT_DIAG, "armed", d.armed ? 1 : 0);
    outlet(OUT_DIAG, "threshold", d.effective_threshold);
}

// A metro bang advances the clock/engine, so [metro <ms>] -> [js] just works
// without a separate "tick" message box. Send "diag" explicitly for stats.
function bang() { tick(); }
