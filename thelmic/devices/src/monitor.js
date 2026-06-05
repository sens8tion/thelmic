/*
 * monitor.js — Pulse Field Stage 3 glue: field subscription + history buffer.
 *
 * Feeds the jsui renderer (monitor-ui.js). This file holds the live vector, a
 * rolling pressure-history ring buffer, the territory match (territory.js), and
 * a field-velocity estimate (rate of change across all dims). It forwards a
 * compact state bundle to the jsui via a named [send]/[receive] pair inside the
 * device, or directly if both run in one [js]/[jsui] pair.
 *
 * Max-facing (outlet/post). Field subscription: LOM observe or inlet feed.
 *
 * Outlets:
 *   0 -> jsui state (a "draw" message; the jsui pulls via getState in practice)
 *   1 -> "territory <name> <confidence>"
 *   2 -> "velocity <f>"
 *
 * Pulse Field branch — Stage 3.
 */

var cfg = require("field-osc-config");
var terr = require("territory");

autowatch = 1;
inlets = 1;
outlets = 3;

var fieldvec = cfg.default_vector();   // not `field`: avoids Max top-level
                                       // var/`this.field` handler collision
var prev_field = cfg.default_vector();
var HISTORY = 240;                 // ~4s of samples at 60fps
var pressure_hist = [];
var liveapis = {};
var velocity = 0;

// ---- field input ----------------------------------------------------------

// "field <8 floats>" — whole vector in canonical order.
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

// ---- LOM observe ----------------------------------------------------------

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
        post("[monitor] observing " + Object.keys(liveapis).length + " params\n");
    } catch (e) { post("[monitor] observe failed: " + e + "\n"); }
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

// ---- tick / compute -------------------------------------------------------

function tick() {
    // field velocity: RMS of per-dim deltas since last tick
    var s = 0;
    for (var i = 0; i < cfg.DIMENSION_NAMES.length; i++) {
        var d = cfg.DIMENSION_NAMES[i];
        var delta = fieldvec[d] - prev_field[d];
        s += delta * delta;
        prev_field[d] = fieldvec[d];
    }
    velocity = Math.sqrt(s / cfg.DIMENSION_NAMES.length);

    // pressure history ring
    pressure_hist.push(fieldvec.pressure);
    if (pressure_hist.length > HISTORY) { pressure_hist.shift(); }

    var t = terr.nearestTerritory(fieldvec);

    // Feed the jsui everything it draws, all on outlet 0 (one cord to [jsui]).
    var vecMsg = ["field"];
    for (var k = 0; k < cfg.DIMENSION_NAMES.length; k++) {
        vecMsg.push(fieldvec[cfg.DIMENSION_NAMES[k]]);
    }
    outlet(0, vecMsg);
    outlet(0, ["history"].concat(pressure_hist));
    outlet(0, "territory", t.name, t.confidence);
    outlet(0, "velocity", velocity);

    // Mirror territory/velocity on dedicated outlets for patch use.
    outlet(1, "territory", t.name, t.confidence);
    outlet(2, "velocity", velocity);
}

// Accessors the jsui calls (when sharing the same js scripting namespace) or
// the patch routes out.
function getField() { return fieldvec; }
function getHistory() { return pressure_hist; }
function getVelocity() { return velocity; }

function bang() { tick(); }
