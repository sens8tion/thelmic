/*
 * render_demo_clip.js — render a playable Pulse Field MIDI clip.
 * Run: node thelmic/devices/tools/render_demo_clip.js [bars] [bpm] > notes.json
 *
 * Drives the REAL, tested onset engine (onset-engine.js) across a crafted DnB
 * field arc — intro, build, pre-drop gap, drop, sustain — and emits the onset
 * events as MIDI notes in beat-time. The Python LOM setup script reads this
 * JSON and writes it into an Ableton clip, so you can hear field-native
 * crystallisation immediately, no Max device required.
 *
 * This is a DEMO of the engine's output, not a port: the physics stays
 * canonical in onset-engine.js. The field arc here is hand-authored to show a
 * recognisable build/drop shape; in the real instrument the field comes from
 * landscape position over OSC.
 */

var path = require("path");
var oe = require(path.join(__dirname, "..", "src", "onset-engine.js"));

var bars = parseInt(process.argv[2] || "16", 10);
var bpm = parseFloat(process.argv[3] || "174");
var TICK_MS = 8;
var beats_per_bar = 4;
var ms_per_beat = 60000 / bpm;
var total_ms = bars * beats_per_bar * ms_per_beat;

// Deterministic RNG so the demo clip is reproducible.
function mulberry32(seed) {
    var a = seed >>> 0;
    return function () {
        a |= 0; a = (a + 0x6D2B79F5) | 0;
        var t = Math.imul(a ^ (a >>> 15), 1 | a);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
}

function clamp01(v) { return v < 0 ? 0 : (v > 1 ? 1 : v); }

// Field arc as a function of normalised time u in [0,1).
// Phases: intro [0,.25) build [.25,.47) GAP [.47,.5) drop [.5,.75) sustain [.75,1)
function fieldAt(u) {
    var f = { pressure: 0, stability: 0.6, density: 0.3, discomfort: 0.1,
              silence: 0.1, novelty: 0.2, urgency: 0.2, momentum: 0.5 };
    if (u < 0.25) {                          // intro: grounded, sparse
        var a = u / 0.25;
        f.pressure = 0.34 + 0.22 * a;
        f.stability = 0.85;
        f.density = 0.15 + 0.1 * a;
        f.silence = 0.25;
        f.urgency = 0.15;
    } else if (u < 0.47) {                    // build: pressure + density rise
        var b = (u - 0.25) / 0.22;
        f.pressure = 0.56 + 0.38 * b;
        f.stability = 0.82 - 0.4 * b;
        f.density = 0.25 + 0.5 * b;
        f.urgency = 0.4 + 0.4 * b;
        f.silence = 0.08;
        f.momentum = 0.5 + 0.2 * b;
    } else if (u < 0.5) {                     // pre-drop GAP: the breath
        f.pressure = 0.2;
        f.stability = 0.2;
        f.density = 0.2;
        f.silence = 0.85;
        f.urgency = 0.6;
    } else if (u < 0.75) {                    // DROP: rolling onsets
        f.pressure = 0.95;
        f.stability = 0.55;
        f.density = 0.82;
        f.discomfort = 0.4;
        f.urgency = 0.5;
        f.silence = 0.06;
        f.momentum = 0.7;
    } else {                                  // sustain: vary, novelty up
        var s = (u - 0.75) / 0.25;
        f.pressure = 0.78 + 0.08 * Math.sin(s * Math.PI * 4);
        f.stability = 0.6;
        f.density = 0.45 + 0.1 * Math.sin(s * Math.PI * 3);
        f.novelty = 0.55;
        f.urgency = 0.3;
        f.silence = 0.12;
    }
    for (var k in f) { f[k] = clamp01(f[k]); }
    return f;
}

// Slightly lower threshold than the device default so the intro swells in
// sparsely rather than sitting fully silent for the first bars.
var engine = new oe.OnsetEngine({ rng: mulberry32(0x5152), refractory_ms: 70,
                                  onset_threshold: 0.50 });
var notes = [];
var clock = 0;

while (clock < total_ms) {
    var u = clock / total_ms;
    var field = fieldAt(u);
    var events = engine.step(field, clock);
    for (var i = 0; i < events.length; i++) {
        var ev = events[i];
        var t_ms = clock + (ev.smear_ms || 0);
        if (t_ms < 0) { t_ms = 0; }
        var start_beats = (t_ms / ms_per_beat);
        var dur_beats = Math.max(0.06, ev.length_ms / ms_per_beat);
        notes.push({
            pitch: ev.pitch,
            start_time: +start_beats.toFixed(4),
            duration: +dur_beats.toFixed(4),
            velocity: ev.velocity
        });
    }
    clock += TICK_MS;
}

var out = {
    bpm: bpm,
    bars: bars,
    length_beats: bars * beats_per_bar,
    note_count: notes.length,
    notes: notes
};
process.stdout.write(JSON.stringify(out));
process.stderr.write("rendered " + notes.length + " onsets over " + bars +
                     " bars @ " + bpm + "bpm\n");
