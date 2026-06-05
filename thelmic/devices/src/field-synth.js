/*
 * field-synth.js — field -> gen~ parameter mapping for the Pulse Field synth (v4).
 *
 * The synthesis now lives in the self-morphing gen~ oscillator (field-osc.gendsp).
 * This brain maps the 8 field dimensions onto the oscillator's parameters and
 * keeps the BPM-locked rhythm envelope (silence gaps + pulse) on `amp`. It emits
 * "<param> <value>" messages from a single outlet into [gen~ field-osc].
 *
 * Field -> oscillator mapping:
 *   root        <- root dial (Hz)
 *   chaos       <- 1-stability        (erraticness of the autonomous morph)
 *   rate        <- novelty + urgency  (speed of the morph)
 *   morph       <- discomfort+density (feedback-FM richness)
 *   bright      <- discomfort+density (waveshaper drive)
 *   fmamt       <- density+discomfort (FM index)
 *   spread      <- 1-stability        (inharmonic detune)
 *   air         <- novelty            (noise layer)
 *   amp         <- gain * gate * accent  (BPM rhythm: silence gaps + pulse)
 *
 * Rhythm (BPM-locked, from Live tempo via LiveAPI):
 *   silence -> stochastic gaps; urgency/density -> grid choppiness (1/4..1/64);
 *   pressure -> pulse depth; urgency -> accent density.
 *
 * Pulse Field branch — continuous field synthesis (field->gen~ control, v4).
 */

autowatch = 1;
inlets = 1;
outlets = 1;

var F = {
    pressure: 0.0, stability: 0.5, density: 0.4, discomfort: 0.0,
    silence: 0.0, novelty: 0.0, urgency: 0.0, momentum: 0.5
};
var root = 55.0;
var gain = 0.85;
var width = 0.5;    // stereo decorrelation dial (0 = mono/centre)

var TICK_MS = 20;
var beatPhase = 0;
var lastStep = -1;
var gate = 1;
var accent = 1;
var bpm = 120;
var tempoAPI = null;
var SUBDIVS = [1, 2, 4, 8, 16];   // steps/beat: 1/4 .. 1/64

function clamp(v, lo, hi) {
    v = +v; if (v !== v) { return lo; }
    return v < lo ? lo : (v > hi ? hi : v);
}
function lerp(a, b, x) { return a + (b - a) * x; }

function init_tempo() {
    try {
        tempoAPI = new LiveAPI(function (args) {
            if (args && args.length >= 2 && args[0] === "tempo") { bpm = args[1]; }
        }, "live_set");
        tempoAPI.property = "tempo";
        var v = tempoAPI.get("tempo");
        if (v && v.length) { bpm = v[0]; } else if (+v) { bpm = +v; }
    } catch (e) { bpm = 120; }
}

// tagged setters from the live.dials: "pressure 0.5", "root 55", "gain 0.9"
function anything() {
    var sel = messagename;
    var a = arrayfromargs(arguments);
    if (a.length < 1) { return; }
    if (F.hasOwnProperty(sel)) { F[sel] = clamp(a[0], 0, 1); return; }
    if (sel === "root") { root = Math.max(8, +a[0]); return; }
    if (sel === "gain") { gain = clamp(a[0], 0, 1); return; }
    if (sel === "width") { width = clamp(a[0], 0, 1); return; }
    if (sel === "bpm") { bpm = Math.max(20, +a[0]); return; }
}

function bang() { tick(); }

function tick() {
    var dt = TICK_MS / 1000.0;
    beatPhase += dt * (bpm / 60.0);

    // BPM rhythm: variable-resolution stochastic silence gaps + pulse accent
    var chop = clamp(0.65 * F.urgency + 0.35 * F.density, 0, 1);
    var stepsPerBeat = SUBDIVS[Math.round(chop * (SUBDIVS.length - 1))];
    var s = Math.floor(beatPhase * stepsPerBeat);
    if (s !== lastStep) {
        lastStep = s;
        gate = (Math.random() < F.silence) ? 0 : 1;
        var accentEvery = Math.max(1, Math.round(stepsPerBeat / lerp(1, 4, F.urgency)));
        accent = ((s % accentEvery) === 0) ? 1.0 : (1.0 - F.pressure);
    }

    var instab = 1 - F.stability;

    // map field -> oscillator params and emit to gen~
    emit("root", root);
    emit("chaos", instab);
    emit("rate", clamp(0.15 + 0.7 * F.novelty + 0.2 * F.urgency, 0, 1));
    emit("morph", clamp(0.2 + 0.5 * F.discomfort + 0.3 * F.density, 0, 1));
    emit("bright", clamp(0.55 * F.discomfort + 0.4 * F.density, 0, 1));
    emit("fmamt", clamp(0.6 * F.discomfort + 0.4 * F.density, 0, 1));
    emit("spread", clamp(0.8 * instab + 0.2 * F.discomfort, 0, 1));
    emit("width", width);                        // stereo decorrelation
    emit("amp", gain * gate * accent);
}

function emit(name, value) { outlet(0, name, value); }

function loadbang() { init_tempo(); tick(); }
