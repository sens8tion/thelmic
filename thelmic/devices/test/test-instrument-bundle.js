/*
 * test-instrument-bundle.js — exercise the GENERATED combined-instrument bundle
 * end to end, with the Max API stubbed. Proves OSC-in -> field -> OnsetEngine
 * -> MIDI-out works in the real glue, not just the engine in isolation.
 *
 * Run: node tools/bundle.js && node test/test-instrument-bundle.js
 */

var fs = require("fs");
var path = require("path");

var bundlePath = path.join(__dirname, "..", "thelmic.pulse-field-instrument.bundle.js");
var code = fs.readFileSync(bundlePath, "utf8");

// ---- Max API stubs --------------------------------------------------------
var notes = [];     // [pitch, vel, len] captured from outlet 0
var diags = [];     // outlet 1 messages

function makeSandbox() {
    notes = []; diags = [];
    return {
        autowatch: 0, inlets: 0, outlets: 0,
        messagename: "",
        post: function () {},
        arrayfromargs: function (args) { return Array.prototype.slice.call(args); },
        outlet: function (idx) {
            var rest = Array.prototype.slice.call(arguments, 1);
            if (idx === 0) { notes.push(rest); } else { diags.push(rest); }
        },
        // Task: run scheduled callbacks immediately (smear path)
        Task: function (fn) { this.schedule = function () { fn(); }; }
    };
}

// Build a callable module: inject stubs as params, return the handlers.
function loadInstrument() {
    var sb = makeSandbox();
    var names = Object.keys(sb);
    var vals = names.map(function (n) { return sb[n]; });
    var body = code + "\n;return { field: field, anything: anything, bang: bang, " +
               "freeze: freeze, start: start, stop: stop, reset_clock: reset_clock, " +
               "param: param };";
    var factory = new Function(names.join(","), body);
    return factory.apply({}, vals);
}

var passed = 0, failed = 0;
function ok(name, cond) { if (cond) passed++; else { failed++; console.error("  FAIL: " + name); } }

// ── whole-vector path: pressure high -> onsets fire over several ticks ──────
(function () {
    var inst = loadInstrument();
    // field() takes positional floats in canonical order:
    // pressure stability density discomfort silence novelty urgency momentum
    inst.field(0.95, 0.5, 0.0, 0, 0, 0, 0, 0);
    for (var i = 0; i < 200; i++) { inst.bang(); }
    ok("instrument fires onsets from high pressure", notes.length > 0);
    ok("note triples are [pitch,vel,len]", notes.length === 0 || notes[0].length === 3);
    ok("velocity in MIDI range", notes.every(function (n) { return n[1] >= 1 && n[1] <= 127; }));
})();

// ── low pressure -> silence ────────────────────────────────────────────────
(function () {
    var inst = loadInstrument();
    inst.field(0.1, 0.5, 0, 0, 0, 0, 0, 0);
    for (var i = 0; i < 200; i++) { inst.bang(); }
    ok("no onsets below threshold", notes.length === 0);
})();

// ── density -> concurrent onsets ───────────────────────────────────────────
(function () {
    var inst = loadInstrument();
    inst.field(0.95, 0.5, 1.0, 0, 0, 0, 0, 0);  // max density
    inst.bang();
    ok("max density => multiple concurrent notes on a fire", notes.length >= 2);
})();

// ── freeze holds the field ─────────────────────────────────────────────────
(function () {
    var inst = loadInstrument();
    inst.field(0.95, 0.5, 0, 0, 0, 0, 0, 0);
    inst.freeze(1);
    inst.field(0.0, 0.5, 0, 0, 0, 0, 0, 0);     // should be ignored
    for (var i = 0; i < 100; i++) { inst.bang(); }
    ok("frozen field keeps firing despite zero update", notes.length > 0);
})();

// ── stop() silences ────────────────────────────────────────────────────────
(function () {
    var inst = loadInstrument();
    inst.field(0.95, 0.5, 0, 0, 0, 0, 0, 0);
    inst.stop();
    for (var i = 0; i < 100; i++) { inst.bang(); }
    ok("stop() halts onset output", notes.length === 0);
})();

console.log("instrument-bundle: " + passed + " passed, " + failed + " failed");
process.exit(failed === 0 ? 0 : 1);
