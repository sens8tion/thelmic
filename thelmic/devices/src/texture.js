/*
 * texture.js — Pulse Field Stage 2 Max glue.
 *
 * Subscribes to the field, runs the pure mapping (texture-audio.js), and routes
 * the resulting control values to the audio graph. This file is Max-facing
 * (outlet/post); the audio objects themselves are wired in the patch — see
 * thelmic.texture.maxpat and README "Stage 2 audio graph".
 *
 * Field subscription: same two paths as Stage 1 (LOM observe or inlet feed).
 *
 * The patch drives [metro <tick_ms>] -> "tick". On each tick we recompute the
 * control bundle and emit each value on its own labelled outlet so the patch
 * can fan them into [line~]/[svf~]/[lores~]/[*~] with smoothing ramps of
 * length evo_ms.
 *
 * Outlets (see thelmic.texture.maxpat):
 *   0 sub_freq   1 sub_level
 *   2 mid_freq   3 mid_bw    4 mid_q   5 mid_level
 *   6 air_freq   7 air_level
 *   8 drive      9 master    10 evo_ms
 *
 * Pulse Field branch — Stage 2.
 */

var cfg = require("field-osc-config");
var ta = require("texture-audio");

autowatch = 1;
inlets = 1;
outlets = 11;

var fieldvec = cfg.default_vector();   // not `field`: avoids Max top-level
                                       // var/`this.field` handler collision
var tick_interval = 20;    // ms; control rate, not audio rate
var running = 1;
var liveapis = {};

// ---- field input (inlet feed) --------------------------------------------

function field() {
    var a = arrayfromargs(arguments);
    for (var i = 0; i < cfg.DIMENSION_NAMES.length && i < a.length; i++) {
        fieldvec[cfg.DIMENSION_NAMES[i]] = cfg.clamp01(a[i]);
    }
}

function anything() {
    var sel = messagename;
    var a = arrayfromargs(arguments);
    var prefix = cfg.OSC.address_root + "/";
    var name = (sel.indexOf(prefix) === 0) ? sel.substring(prefix.length) : sel;
    if (a.length >= 1 && cfg.index_of(name) >= 0) {
        fieldvec[name] = cfg.clamp01(a[0]);
    }
}

// ---- LOM observe (shared pattern with Stage 1) ---------------------------

function observe() {
    var devPath = arrayfromargs(arguments).join(" ");
    clear_observers();
    try {
        var dev = new LiveAPI(devPath);
        var count = dev.getcount("parameters");
        for (var i = 0; i < count; i++) {
            var pPath = devPath + " parameters " + i;
            var pApi = new LiveAPI(pPath);
            var pname = pApi.get("name");
            if (pname && pname.length) { pname = pname[0]; }
            if (cfg.index_of(pname) >= 0) { attach(pname, pPath); }
        }
        post("[texture] observing " + Object.keys(liveapis).length + " params\n");
    } catch (e) { post("[texture] observe failed: " + e + "\n"); }
}
function attach(name, path) {
    var api = new LiveAPI(function (args) {
        if (args && args.length >= 2 && args[0] === "value") {
            fieldvec[name] = cfg.clamp01(args[1]);
        }
    }, path);
    api.property = "value";
    liveapis[name] = api;
    fieldvec[name] = cfg.clamp01(api.get("value"));
}
function clear_observers() {
    for (var k in liveapis) { liveapis[k] = null; }
    liveapis = {};
}

// ---- tick ----------------------------------------------------------------

function tick() {
    if (!running) { return; }
    var c = ta.textureControls(fieldvec, {});
    outlet(0, c.sub_freq);
    outlet(1, c.sub_level);
    outlet(2, c.mid_freq);
    outlet(3, c.mid_bw);
    outlet(4, c.mid_q);
    outlet(5, c.mid_level);
    outlet(6, c.air_freq);
    outlet(7, c.air_level);
    outlet(8, c.drive);
    outlet(9, c.master);
    outlet(10, c.evo_ms);
}

function start() { running = 1; }
function stop()  { running = 0; }
function tick_ms(v) { tick_interval = Math.max(1, +v); }
function bang() { tick(); }
