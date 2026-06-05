/*
 * instrument-glue.js — combined Pulse Field INSTRUMENT glue (Stage 0 + Stage 1
 * in one device). Bare-name, require-free: it assumes the field config helpers
 * and OnsetEngine are already in scope. The bundler (tools/bundle.js) prepends
 * the stripped field-osc-config.js and onset-engine.js to produce a single
 * self-contained file, thelmic.pulse-field-instrument.bundle.js, so there is
 * NO require() search-path dependency in Max and NO logic duplication (the
 * physics stays canonical in onset-engine.js).
 *
 * One [js] object does everything:
 *   - receive OSC ("/thelmic/field/<dim>" or whole-vector "/thelmic/field ...")
 *   - hold the field vector, freeze on demand
 *   - on each metro bang, run the OnsetEngine and emit MIDI
 *
 * Globals expected from the prepended modules (bare, not namespaced):
 *   DIMENSION_NAMES, OSC, clamp01, index_of, default_vector, OnsetEngine
 * Max globals: outlet, autowatch, inlets, outlets, arrayfromargs, messagename,
 *   post, Task.
 *
 * Outlets: 0 = "<pitch> <velocity> <length_ms>" (-> unpack -> makenote -> noteout)
 *          1 = diagnostics ("count <n>", "armed <0|1>", "threshold <f>")
 *
 * Pulse Field branch — combined instrument.
 */

autowatch = 1;
inlets = 1;
outlets = 2;
var OUT_NOTE = 0;
var OUT_DIAG = 1;

var engine = new OnsetEngine({});
var fieldvec = default_vector();
var frozen = false;
var tick_interval = 5;     // ms; metro interval (settable via "tick_ms <n>")
var clock = 0;
var running = 1;

// ---- field input (OSC) ----------------------------------------------------

// whole-vector blob "field <8 floats>" (also "/thelmic/field <8 floats>")
function field() {
    if (frozen) { return; }
    var a = arrayfromargs(arguments);
    for (var i = 0; i < DIMENSION_NAMES.length && i < a.length; i++) {
        fieldvec[DIMENSION_NAMES[i]] = clamp01(a[i]);
    }
}

// leaf "/thelmic/field/<dim> <v>", bare "<dim> <v>", and the root blob
function anything() {
    var sel = messagename;
    var a = arrayfromargs(arguments);
    if (sel === OSC.address_root) { field.apply(this, a); return; }
    var prefix = OSC.address_root + "/";
    var name = (sel.indexOf(prefix) === 0) ? sel.substring(prefix.length) : sel;
    if (!frozen && a.length >= 1 && index_of(name) >= 0) {
        fieldvec[name] = clamp01(a[0]);
    }
}

function freeze(on) { frozen = (on != 0); }

// ---- tick / firing --------------------------------------------------------

// metro bang advances the engine one tick — [metro <ms>] -> [js] just works.
function bang() {
    if (!running) { return; }
    clock += tick_interval;
    var events = engine.step(fieldvec, clock);
    for (var i = 0; i < events.length; i++) { schedule(events[i]); }
    if (events.length > 0) { outlet(OUT_DIAG, "count", events.length); }
}

function schedule(ev) {
    if (ev.smear_ms <= 0) { emit(ev); }
    else { var t = new Task(function () { emit(ev); }); t.schedule(ev.smear_ms); }
}

function emit(ev) { outlet(OUT_NOTE, ev.pitch, ev.velocity, ev.length_ms); }

// ---- control --------------------------------------------------------------

function start() { running = 1; }
function stop()  { running = 0; }
function reset_clock() { clock = 0; }
function tick_ms(v) { tick_interval = Math.max(1, +v); }

// engine tuning, e.g. "param onset_threshold 0.55"
function param() {
    var a = arrayfromargs(arguments);
    if (a.length >= 2) { engine.setParam(a[0], a[1]); }
}

function diag() {
    var d = engine.diagnostics(fieldvec.urgency);
    outlet(OUT_DIAG, "armed", d.armed ? 1 : 0);
    outlet(OUT_DIAG, "threshold", d.effective_threshold);
}
