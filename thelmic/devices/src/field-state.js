/*
 * field-state.js — Pulse Field Stage 0: Field State device.
 *
 * The single source of truth for the field vector. All other Pulse Field
 * devices read their field state from here (via LOM parameter reads keyed
 * on this device's parameter names, or via the Max outlet broadcast below).
 *
 * Responsibilities:
 *   - receive OSC from the Python layer ("/thelmic/field/<dim> <float>"
 *     or whole-vector "/thelmic/field <8 floats>")
 *   - hold the current vector, clamped to [0,1]
 *   - push values onto Live parameters (live.dial / live.numbox) so other
 *     M4L devices can read them over LOM, and so they are automatable
 *   - broadcast each dimension on a named outlet for direct Max patching
 *   - support a freeze toggle that holds the vector while OSC keeps arriving
 *   - report OSC connected / standalone status
 *
 * Patch wiring (see thelmic.field-state.maxpat):
 *   [udpreceive 7400] -> [js field-state.js]        // OSC route 0 (left inlet)
 *   [live.dial @varname pressure] etc -> inlet 1..8 // automation feedback
 *   outlets: one per dimension (broadcast) + [outlet N] status + [outlet N+1] to params
 *
 * Pure logic is delegated to field-osc-config.js so dimension order and
 * defaults never drift. This file is the Max-facing glue (uses outlet/post/
 * jsarguments and is therefore only runnable inside Max).
 *
 * Pulse Field branch — Stage 0. See thelmic/devices/README.md.
 */

var cfg = require("field-osc-config");

// ---------------------------------------------------------------------------
// Max object configuration
// ---------------------------------------------------------------------------

// One outlet per dimension (broadcast), then:
//   [N]   -> status messages ("osc <0|1>")
//   [N+1] -> "<dimname> <value>" pairs for routing into live.dial set messages
var N = cfg.DIMENSION_NAMES.length;
outlets = N + 2;
var OUT_STATUS = N;
var OUT_PARAM = N + 1;

autowatch = 1;
inlets = 1;

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

var vector = cfg.default_vector();   // {name: value}
var frozen = false;                  // freeze toggle holds vector
var osc_connected = false;           // becomes true on first OSC message
var last_osc_logical_time = -1;      // for a simple staleness watchdog

// Push the whole vector to outlets + params once at load so downstream
// devices have a defined starting state.
function loadbang() {
    broadcast_all();
    push_all_params();
    set_status(false);
}

// ---------------------------------------------------------------------------
// OSC entry points
// ---------------------------------------------------------------------------
//
// The [udpreceive] object emits the OSC address as the Max message selector
// followed by its arguments. With address "/thelmic/field/pressure 0.7",
// Max calls a function literally named "/thelmic/field/pressure" with arg
// 0.7. We can't declare a JS function with that name, so the patch uses
// [oscparse]/[route] OR strips the prefix with [substitute] and forwards a
// clean "set <dim> <value>" message. We support both styles:
//
//   set <dim> <value>        (preferred, after patch-side routing)
//   field <v0..v7>           (whole-vector blob)
//   <dim> <value>            (bare, if patch routes to leaf only)

// Preferred: explicit setter from patch-side OSC routing.
function set() {
    var a = arrayfromargs(arguments);
    if (a.length < 2) { return; }
    apply_osc(a[0], a[1]);
}

// Whole-vector blob: "field 0.1 0.2 ... 0.8"
function field() {
    var a = arrayfromargs(arguments);
    mark_osc();
    if (frozen) { return; }
    for (var i = 0; i < N && i < a.length; i++) {
        vector[cfg.DIMENSION_NAMES[i]] = cfg.clamp01(a[i]);
    }
    broadcast_all();
    push_all_params();
}

// Catch-all. Max's [udpreceive] parses OSC and dispatches the address as the
// message selector, so a raw "/thelmic/field/pressure 0.7" arrives here with
// messagename == "/thelmic/field/pressure". We strip the known root so the
// patch can wire [udpreceive 7400] straight into [js] with no routing objects.
// Also handles the whole-vector blob "/thelmic/field <8 floats>" and the bare
// leaf form "<dim> <value>".
function anything() {
    var sel = messagename;
    var a = arrayfromargs(arguments);

    // Whole-vector blob on the root address.
    if (sel === cfg.OSC.address_root) {
        field.apply(this, a);
        return;
    }

    // Leaf address "<root>/<dim>".
    var prefix = cfg.OSC.address_root + "/";
    var name = sel;
    if (sel.indexOf(prefix) === 0) {
        name = sel.substring(prefix.length);
    }

    if (a.length >= 1 && cfg.index_of(name) >= 0) {
        apply_osc(name, a[0]);
    }
}

function apply_osc(name, value) {
    if (cfg.index_of(name) < 0) { return; }
    mark_osc();
    if (frozen) { return; }
    vector[name] = cfg.clamp01(value);
    broadcast_one(name);
    push_param(name);
}

// ---------------------------------------------------------------------------
// Automation feedback
// ---------------------------------------------------------------------------
//
// When a Live parameter (live.dial) is automated or moved by hand, the patch
// feeds "<dim> <value>" into this device so the JS state tracks the param.
// To avoid a feedback loop we update state + broadcast but do NOT re-push the
// param (that's where the value came from). The patch routes these to the
// param() function below, distinct from set()/OSC.

function param() {
    var a = arrayfromargs(arguments);
    if (a.length < 2) { return; }
    var name = a[0], value = a[1];
    if (cfg.index_of(name) < 0) { return; }
    if (frozen) { return; }
    vector[name] = cfg.clamp01(value);
    broadcast_one(name);   // downstream consumers see automation too
    // intentionally no push_param() — avoids automation feedback loop
}

// ---------------------------------------------------------------------------
// Freeze
// ---------------------------------------------------------------------------

function freeze(on) {
    frozen = (on != 0);
    post("[field-state] freeze " + (frozen ? "ON" : "off") + "\n");
}

// ---------------------------------------------------------------------------
// Queries (for monitor / debug)
// ---------------------------------------------------------------------------

function bang() {
    broadcast_all();
}

function getvalue(name) {
    if (cfg.index_of(name) >= 0) {
        outlet(cfg.index_of(name), vector[name]);
    }
}

// ---------------------------------------------------------------------------
// Output helpers
// ---------------------------------------------------------------------------

function broadcast_one(name) {
    var i = cfg.index_of(name);
    if (i >= 0) { outlet(i, vector[name]); }
}

function broadcast_all() {
    for (var i = 0; i < N; i++) {
        outlet(i, vector[cfg.DIMENSION_NAMES[i]]);
    }
}

// Emit "<dim> <value>" on the param outlet; patch routes to the matching
// live.dial via [route pressure stability ...] -> [prepend set].
function push_param(name) {
    outlet(OUT_PARAM, name, vector[name]);
}

function push_all_params() {
    for (var i = 0; i < N; i++) {
        var name = cfg.DIMENSION_NAMES[i];
        outlet(OUT_PARAM, name, vector[name]);
    }
}

function mark_osc() {
    if (!osc_connected) { set_status(true); }
    osc_connected = true;
}

function set_status(connected) {
    osc_connected = connected;
    outlet(OUT_STATUS, "osc", connected ? 1 : 0);
}

// A [metro 1000] -> [js function watchdog] in the patch can call this to
// drop status back to standalone if no OSC arrives for a while. Optional.
function watchdog() {
    // If we want true staleness detection we'd compare timestamps, but Max
    // js time is awkward; we keep status sticky-on once OSC seen, and let the
    // patch reset via standalone if desired.
}

function standalone() {
    set_status(false);
}
