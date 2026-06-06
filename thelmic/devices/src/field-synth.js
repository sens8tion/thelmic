/*
 * field-synth.js — field -> gen~ parameter mapping for the Pulse Field synth (v5).
 *
 * The synthesis lives in the self-morphing gen~ oscillator (embedded gen code).
 * This brain (1) reads THIS device's parameters via LiveAPI observers so manual
 * moves, bridge/API sets, AND automation lanes all reach it; (2) maps the field
 * onto the oscillator params; (3) holds the BPM-locked rhythm (silence gaps +
 * pulse) on `amp`, following Live's tempo.
 *
 * Threading note (the bug that bit us): in M4L the Live API must be set up from
 * the LOW-PRIORITY thread. We init it from the live.thisdevice bang on inlet 1,
 * NOT from the metro tick (scheduler/high-priority) where LiveAPI silently fails.
 *
 * Inlets: 0 = metro tick + param messages ; 1 = live.thisdevice (init trigger)
 * Outlet: 0 = "<param> <value>" messages into [gen~]
 *
 * Rhythm is currently tempo-locked but free-phase (not snapped to bar position);
 * transport phase-lock can be layered on later.
 */

autowatch = 1;
inlets = 2;
outlets = 1;

var F = {
    pressure: 0.0, stability: 0.5, density: 0.4, discomfort: 0.0,
    silence: 0.0, novelty: 0.0, urgency: 0.0, momentum: 0.5
};
var root = 55.0;
var gain = 0.85;
var width = 0.5;

var TICK_MS = 10;
var freeBeats = 0;
var lastStep = -1;
var gate = 1;
var accent = 1;
var bpm = 120;
var tempoAPI = null;
var paramAPIs = [];               // keep observer refs alive
var SUBDIVS = [1, 2, 4, 8, 16];   // steps/beat: 1/4 .. 1/64

function clamp(v, lo, hi) {
    v = +v; if (v !== v) { return lo; }
    return v < lo ? lo : (v > hi ? hi : v);
}
function lerp(a, b, x) { return a + (b - a) * x; }
function num(x) {
    if (x === null || x === undefined) { return null; }
    if (x.length !== undefined) { return x.length ? +x[0] : null; }
    return +x;
}

// apply a parameter value into our state
function setParam(name, value) {
    value = +value;
    if (value !== value) { return; }
    if (F.hasOwnProperty(name)) { F[name] = clamp(value, 0, 1); }
    else if (name === "root") { root = Math.max(8, value); }
    else if (name === "gain") { gain = clamp(value, 0, 1); }
    else if (name === "width") { width = clamp(value, 0, 1); }
}

// LOW-PRIORITY init (from live.thisdevice on inlet 1): tempo observer + this
// device's parameter observers. This is where LiveAPI actually works in M4L.
function init_low() {
    try {
        tempoAPI = new LiveAPI(function (args) {
            if (args && args.length >= 2 && args[0] === "tempo") { bpm = args[1]; }
        }, "live_set");
        tempoAPI.property = "tempo";
        var v = num(tempoAPI.get("tempo"));
        if (v && v > 0) { bpm = v; }
    } catch (e) {}

    try {
        var dev = new LiveAPI("this_device");
        var count = dev.getcount("parameters");
        for (var i = 0; i < count; i++) {
            var path = "this_device parameters " + i;
            var p = new LiveAPI(path);
            var nm = p.get("name");
            nm = (nm && nm.length !== undefined) ? nm[0] : nm;
            setParam(nm, num(p.get("value")));        // seed current value
            (function (name, ppath) {
                var obs = new LiveAPI(function (args) {
                    if (args && args.length >= 2 && args[0] === "value") {
                        setParam(name, args[1]);
                    }
                }, ppath);
                obs.property = "value";
                paramAPIs.push(obs);
            })(nm, path);
        }
    } catch (e) {}
}

// dial-message fallback (manual moves / automation also arrive here on inlet 0)
function anything() {
    var sel = messagename;
    var a = arrayfromargs(arguments);
    if (a.length < 1) { return; }
    if (sel === "bpm") { bpm = Math.max(20, +a[0]); return; }
    setParam(sel, a[0]);
}

function bang() {
    if (inlet === 1) { init_low(); }
    else { tick(); }
}

function tick() {
    var dt = TICK_MS / 1000.0;
    freeBeats += dt * (bpm / 60.0);          // free-run, tempo-correct

    // BPM rhythm: variable-resolution stochastic silence gaps + pulse accent
    var chop = clamp(0.65 * F.urgency + 0.35 * F.density, 0, 1);
    var stepsPerBeat = SUBDIVS[Math.round(chop * (SUBDIVS.length - 1))];
    var s = Math.floor(freeBeats * stepsPerBeat);
    if (s !== lastStep) {
        lastStep = s;
        gate = (Math.random() < F.silence) ? 0 : 1;
        var accentEvery = Math.max(1, Math.round(stepsPerBeat / lerp(1, 4, F.urgency)));
        accent = ((s % accentEvery) === 0) ? 1.0 : (1.0 - F.pressure);
    }

    var instab = 1 - F.stability;
    emit("root", root);
    emit("chaos", instab);
    emit("rate", clamp(0.15 + 0.7 * F.novelty + 0.2 * F.urgency, 0, 1));
    emit("morph", clamp(0.2 + 0.5 * F.discomfort + 0.3 * F.density, 0, 1));
    emit("bright", clamp(0.55 * F.discomfort + 0.4 * F.density, 0, 1));
    emit("fmamt", clamp(0.6 * F.discomfort + 0.4 * F.density, 0, 1));
    emit("spread", clamp(0.8 * instab + 0.2 * F.discomfort, 0, 1));
    emit("width", width);
    emit("amp", gain * gate * accent);
}

function emit(name, value) { outlet(0, name, value); }

function loadbang() { tick(); }
