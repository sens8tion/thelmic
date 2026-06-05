/*
 * field-osc-config.js — shared Pulse Field configuration.
 *
 * Single definition of the field vector's dimension set and the OSC
 * addressing scheme. Every Pulse Field device (field-state, rhythmic-
 * crystallisation, texture, monitor) requires() this module so the
 * dimension order, defaults, and OSC namespace can never drift between
 * devices.
 *
 * This is a pure CommonJS module — no Max API references — so it can be
 * required() from a Max [js] object AND from plain node (for tests).
 *
 * Pulse Field branch — Stage 0. See thelmic/devices/README.md.
 */

// The field vector, v0. Order is canonical: it defines parameter index,
// broadcast outlet order, and monitor bar order. Append-only — never
// reorder or delete, or you break every consumer's indexing.
//
// Each entry:
//   name     OSC leaf + Live parameter name + Max outlet/receive name
//   def      default value when no OSC / automation has arrived yet
//   role     short human note on the DnB-physics role (doc only)
var DIMENSIONS = [
    { name: "pressure",   def: 0.0, role: "accumulated energy; primary onset trigger" },
    { name: "stability",  def: 0.5, role: "coherence; tightness of crystallisation" },
    { name: "density",    def: 0.3, role: "concurrent-event potential; polyphony ceiling" },
    { name: "discomfort", def: 0.0, role: "sustained tension; textural character / Nott" },
    { name: "silence",    def: 0.0, role: "active absence; gap insertion" },
    { name: "novelty",    def: 0.0, role: "deviation from recent history; variation" },
    { name: "urgency",    def: 0.0, role: "rate of pressure change; build / drop speed" },
    { name: "momentum",   def: 0.0, role: "directional persistence; phrase extension" }
];

// Convenience: just the names, in canonical order.
var DIMENSION_NAMES = DIMENSIONS.map(function (d) { return d.name; });

// OSC namespace. The Python layer emits e.g. "/thelmic/field/pressure 0.7".
// A whole-vector blob form is also accepted: "/thelmic/field <8 floats>".
var OSC = {
    listen_port: 7400,          // UDP port Stage 0's [udpreceive] binds
    address_root: "/thelmic/field",
    // leaf address for one dimension
    address_for: function (name) { return OSC.address_root + "/" + name; }
};

// Clamp helper shared by every device.
function clamp01(v) {
    v = +v;
    if (v !== v) { return 0.0; }      // NaN guard
    if (v < 0.0) { return 0.0; }
    if (v > 1.0) { return 1.0; }
    return v;
}

// Look up a dimension's canonical index by name, or -1.
function index_of(name) {
    for (var i = 0; i < DIMENSIONS.length; i++) {
        if (DIMENSIONS[i].name === name) { return i; }
    }
    return -1;
}

// Build a fresh vector object {name: default} in canonical order.
function default_vector() {
    var v = {};
    for (var i = 0; i < DIMENSIONS.length; i++) {
        v[DIMENSIONS[i].name] = DIMENSIONS[i].def;
    }
    return v;
}

exports.DIMENSIONS = DIMENSIONS;
exports.DIMENSION_NAMES = DIMENSION_NAMES;
exports.OSC = OSC;
exports.clamp01 = clamp01;
exports.index_of = index_of;
exports.default_vector = default_vector;
