/*
 * gen_maxpat.js — generate Pulse Field .maxpat reference patchers.
 * Run: node thelmic/devices/tools/gen_maxpat.js
 *
 * Emits valid Max patcher JSON for each Pulse Field device plus a combined
 * "pulse-field-test" patch that wires Stage 0 -> Stage 1 + Stage 3 in a single
 * patcher so the whole chain can be exercised in Max without Ableton/LOM.
 *
 * These are REFERENCE patches: open them in Max to inspect/copy the wiring.
 * To ship as .amxd, create a device shell in Live (Max MIDI Effect / Audio
 * Effect) and paste these objects in — see thelmic/devices/README.md.
 *
 * Generating from the shared dimension config guarantees the patchers never
 * drift from field-osc-config.js.
 */

var fs = require("fs");
var path = require("path");
var cfg = require(path.join(__dirname, "..", "src", "field-osc-config.js"));

var OUT = path.join(__dirname, "..");
var DIMS = cfg.DIMENSION_NAMES;

// ---- patch builder --------------------------------------------------------

function Patch(rect) {
    this.boxes = [];
    this.lines = [];
    this._id = 0;
    this.rect = rect || [100, 100, 1000, 680];
}
Patch.prototype.nid = function () { return "obj-" + (++this._id); };
Patch.prototype.add = function (box) {
    if (!box.id) { box.id = this.nid(); }
    this.boxes.push({ box: box });
    return box.id;
};
Patch.prototype.obj = function (text, x, y, w, ins, outs, extra) {
    var b = {
        maxclass: "newobj", text: text,
        numinlets: ins, numoutlets: outs,
        patching_rect: [x, y, w || 120, 22]
    };
    if (outs > 0) { b.outlettype = mkOutlets(text, outs); }
    if (extra) { for (var k in extra) { b[k] = extra[k]; } }
    return this.add(b);
};
Patch.prototype.comment = function (text, x, y, w) {
    return this.add({ maxclass: "comment", text: text,
        numinlets: 1, numoutlets: 0, patching_rect: [x, y, w || 240, 20] });
};
Patch.prototype.slider = function (x, y, varname) {
    // live.slider for manual field override [0,1]
    var id = this.add({
        maxclass: "live.slider", numinlets: 1, numoutlets: 2,
        outlettype: ["", "float"], parameter_enable: 1, varname: varname,
        patching_rect: [x, y, 36, 120],
        saved_attribute_attributes: { valueof: {
            parameter_longname: varname, parameter_shortname: varname,
            parameter_mmin: 0.0, parameter_mmax: 1.0,
            parameter_type: 0, parameter_unitstyle: 1
        } }
    });
    return id;
};
Patch.prototype.dial = function (x, y, varname) {
    return this.add({
        maxclass: "live.dial", numinlets: 1, numoutlets: 2,
        outlettype: ["", "float"], parameter_enable: 1, varname: varname,
        patching_rect: [x, y, 48, 48],
        saved_attribute_attributes: { valueof: {
            parameter_longname: varname, parameter_shortname: varname,
            parameter_mmin: 0.0, parameter_mmax: 1.0,
            parameter_type: 0, parameter_unitstyle: 1
        } }
    });
};
Patch.prototype.toggle = function (x, y) {
    return this.add({ maxclass: "toggle", numinlets: 1, numoutlets: 1,
        outlettype: ["int"], patching_rect: [x, y, 24, 24] });
};
Patch.prototype.link = function (src, so, dst, di) {
    this.lines.push({ patchline: {
        source: [src, so], destination: [dst, di] } });
};
Patch.prototype.json = function () {
    return JSON.stringify({ patcher: {
        fileversion: 1,
        appversion: { major: 8, minor: 5, revision: 5, architecture: "x64", modernui: 1 },
        classnamespace: "box",
        rect: this.rect,
        openinpresentation: 0,
        boxes: this.boxes,
        lines: this.lines
    } }, null, 2);
};

function mkOutlets(text, n) {
    var a = []; for (var i = 0; i < n; i++) { a.push(""); }
    return a;
}

function write(name, patch) {
    var p = path.join(OUT, name);
    fs.writeFileSync(p, patch.json());
    console.log("wrote " + name);
}

// ---- Stage 0: field-state device ------------------------------------------

function fieldState() {
    var p = new Patch();
    p.comment("Pulse Field — Stage 0: FIELD STATE (source of truth)", 20, 10, 460);
    var udp = p.obj("udpreceive " + cfg.OSC.listen_port, 20, 44, 150, 0, 1);
    var js  = p.obj("js field-state.js", 20, 90, 150, 1, DIMS.length + 2, {
        saved_object_attributes: { filename: "field-state.js", parameter_enable: 0 } });
    p.link(udp, 0, js, 0);

    // freeze toggle -> [t b f]-ish: send "freeze 1/0"
    var frz = p.toggle(200, 44);
    var frzMsg = p.obj("prepend freeze", 200, 74, 100, 1, 1);
    p.link(frz, 0, frzMsg, 0);
    p.link(frzMsg, 0, js, 0);
    p.comment("freeze", 230, 46, 60);

    // one live.dial per dimension, fed by the param outlet (index DIMS.length+1)
    var paramOut = DIMS.length + 1;
    var routeArgs = DIMS.join(" ");
    var route = p.obj("route " + routeArgs, 20, 150, 360, 1, DIMS.length + 1);
    p.link(js, paramOut, route, 0);

    var x = 20;
    for (var i = 0; i < DIMS.length; i++) {
        var d = p.dial(x, 190, DIMS[i]);
        var setm = p.obj("prepend set", x, 250, 70, 1, 1);
        // route outlet i carries the value for DIMS[i]
        p.link(route, i, setm, 0);
        p.link(setm, 0, d, 0);
        // dial movement -> "<dim> <val>" -> js param() via [prepend <dim>] -> [prepend param]
        var lbl = p.obj("prepend " + DIMS[i], x, 310, 90, 1, 1);
        var pp  = p.obj("prepend param", x, 340, 90, 1, 1);
        p.link(d, 0, lbl, 0);
        p.link(lbl, 0, pp, 0);
        p.link(pp, 0, js, 0);
        p.comment(DIMS[i].substring(0, 6), x, 178, 60);
        x += 84;
    }
    write("thelmic.field-state.maxpat", p);
}

// ---- Stage 1: rhythmic-crystallisation device -----------------------------

function crystallisation() {
    var p = new Patch();
    p.comment("Pulse Field — Stage 1: RHYTHMIC CRYSTALLISATION", 20, 10, 460);
    p.comment("field in via LOM observe or inlet feed; MIDI out below", 20, 30, 460);

    var js = p.obj("js rhythmic-crystallisation.js", 20, 120, 220, 1, 2, {
        saved_object_attributes: { filename: "rhythmic-crystallisation.js", parameter_enable: 0 } });

    // [metro 5] -> [js] : a bang advances the engine clock by one tick.
    var tgl = p.toggle(20, 56);
    var metro = p.obj("metro 5", 20, 84, 70, 2, 1);
    p.link(tgl, 0, metro, 0);
    p.link(metro, 0, js, 0);
    p.comment("on/off  -> 5ms tick clock", 50, 58, 220);

    // MIDI rendering: js note outlet (0) -> [unpack] -> [makenote] -> [noteout]
    var unpack = p.obj("unpack i i i", 20, 160, 130, 1, 3);
    var makenote = p.obj("makenote 100 200", 20, 200, 130, 3, 2);
    var noteout = p.obj("noteout", 20, 240, 70, 2, 0);
    p.link(js, 0, unpack, 0);
    p.link(unpack, 0, makenote, 0);   // pitch
    p.link(unpack, 1, makenote, 1);   // velocity
    p.link(unpack, 2, makenote, 2);   // duration (ms)
    p.link(makenote, 0, noteout, 0);
    p.link(makenote, 1, noteout, 1);

    // diagnostics outlet (1) -> print
    var dbg = p.obj("print crystal", 260, 160, 100, 1, 0);
    p.link(js, 1, dbg, 0);
    write("thelmic.rhythmic-crystallisation.maxpat", p);
}

// ---- Stage 2: texture device (control + documented audio graph) ------------

function texture() {
    var p = new Patch();
    p.comment("Pulse Field — Stage 2: TEXTURE / ATMOSPHERE", 20, 10, 460);
    var js = p.obj("js texture.js", 20, 90, 160, 1, 11, {
        saved_object_attributes: { filename: "texture.js", parameter_enable: 0 } });
    p.comment("metro 20 -> message 'tick' -> [js texture.js]", 20, 60, 400);

    var labels = ["sub_freq", "sub_level", "mid_freq", "mid_bw", "mid_q",
                  "mid_level", "air_freq", "air_level", "drive", "master", "evo_ms"];
    for (var i = 0; i < labels.length; i++) {
        var line = p.obj("line~", 20 + i * 0, 140 + i * 26, 80, 2, 1);
        p.link(js, i, line, 0);
        p.comment(labels[i] + " -> [line~] -> audio graph", 110, 140 + i * 26, 320);
    }
    p.comment("AUDIO GRAPH (build by hand — see README Stage 2):", 20, 440, 460);
    p.comment("noise~ -> svf~ (sub) ; noise~ -> reson~ (mid, freq/Q) ; noise~ -> hip~ (air)", 20, 460, 600);
    p.comment("mix by *~ sub_level/mid_level/air_level ; overdrive~ by drive ; *~ master -> plugout~", 20, 480, 640);
    write("thelmic.texture.maxpat", p);
}

// ---- Stage 3: monitor device ----------------------------------------------

function monitor() {
    var p = new Patch([100, 100, 560, 460]);
    p.comment("Pulse Field — Stage 3: MONITOR", 20, 10, 300);
    var js = p.obj("js monitor.js", 20, 44, 140, 1, 3, {
        saved_object_attributes: { filename: "monitor.js", parameter_enable: 0 } });
    var ui = p.add({ maxclass: "jsui", numinlets: 1, numoutlets: 1,
        outlettype: [""], patching_rect: [20, 90, 520, 320],
        saved_object_attributes: { filename: "monitor-ui.js", parameter_enable: 0 } });
    // monitor.js outlet 0 carries field/history/territory/velocity to the jsui
    p.link(js, 0, ui, 0);
    var tgl = p.toggle(170, 44);
    var metro = p.obj("metro 16", 200, 44, 70, 2, 1);
    p.link(tgl, 0, metro, 0);
    p.link(metro, 0, js, 0);
    p.comment("on/off -> 16ms repaint; feed field via observe/inlet", 20, 414, 520);
    write("thelmic.monitor.maxpat", p);
}

// ---- Combined test patch (no Live / no LOM needed) ------------------------

function combined() {
    var p = new Patch([60, 60, 1180, 720]);
    p.comment("Pulse Field — COMBINED TEST (Stage 0 -> 1 + 3, no Live needed)", 20, 8, 700);
    p.comment("Drag the sliders to drive the field; watch the monitor + MIDI print.", 20, 26, 700);

    // Stage 0
    var fs0 = p.obj("js field-state.js", 20, 300, 150, 1, DIMS.length + 2, {
        saved_object_attributes: { filename: "field-state.js", parameter_enable: 0 } });
    var udp = p.obj("udpreceive " + cfg.OSC.listen_port, 200, 300, 150, 0, 1);
    p.link(udp, 0, fs0, 0);

    // manual sliders -> "<dim> <val>" -> field-state
    var x = 20;
    for (var i = 0; i < DIMS.length; i++) {
        var s = p.slider(x, 60, "test_" + DIMS[i]);
        var lbl = p.obj("prepend " + DIMS[i], x, 190, 90, 1, 1);
        p.link(s, 0, lbl, 0);
        p.link(lbl, 0, fs0, 0);
        p.comment(DIMS[i].substring(0, 6), x, 44, 60);
        x += 70;
    }

    // pack the 8 broadcast outlets into "field <8 floats>" for consumers
    var pak = p.obj("pak f f f f f f f f", 20, 360, 240, DIMS.length, 1);
    for (var j = 0; j < DIMS.length; j++) { p.link(fs0, j, pak, j); }
    var fieldmsg = p.obj("prepend field", 20, 392, 100, 1, 1);
    p.link(pak, 0, fieldmsg, 0);

    // Stage 1 consumer
    var cry = p.obj("js rhythmic-crystallisation.js", 20, 470, 220, 1, 2, {
        saved_object_attributes: { filename: "rhythmic-crystallisation.js", parameter_enable: 0 } });
    p.link(fieldmsg, 0, cry, 0);
    var tgl1 = p.toggle(300, 430);
    var metro1 = p.obj("metro 5", 330, 430, 70, 2, 1);
    p.link(tgl1, 0, metro1, 0);
    p.link(metro1, 0, cry, 0);
    var unpack = p.obj("unpack i i i", 20, 510, 130, 1, 3);
    var makenote = p.obj("makenote 100 200", 20, 545, 130, 3, 2);
    var noteout = p.obj("noteout", 20, 580, 70, 2, 0);
    p.link(cry, 0, unpack, 0);
    p.link(unpack, 0, makenote, 0);
    p.link(unpack, 1, makenote, 1);
    p.link(unpack, 2, makenote, 2);
    p.link(makenote, 0, noteout, 0);
    p.link(makenote, 1, noteout, 1);
    var pr = p.obj("print onset", 260, 510, 100, 1, 0);
    p.link(cry, 1, pr, 0);

    // Stage 3 consumer
    var mon = p.obj("js monitor.js", 460, 470, 140, 1, 3, {
        saved_object_attributes: { filename: "monitor.js", parameter_enable: 0 } });
    p.link(fieldmsg, 0, mon, 0);
    var tgl2 = p.toggle(620, 440);
    var metro2 = p.obj("metro 16", 650, 440, 70, 2, 1);
    p.link(tgl2, 0, metro2, 0);
    p.link(metro2, 0, mon, 0);
    var ui = p.add({ maxclass: "jsui", numinlets: 1, numoutlets: 1,
        outlettype: [""], patching_rect: [460, 510, 520, 180],
        saved_object_attributes: { filename: "monitor-ui.js", parameter_enable: 0 } });
    p.link(mon, 0, ui, 0);

    write("thelmic.pulse-field-test.maxpat", p);
}

// ---- Combined INSTRUMENT (Stage 0 + Stage 1 in one device) ----------------
// The fast path to sound: one [js] (the bundled, require-free build) receives
// OSC and emits MIDI. Drop on a MIDI track before a drum rack.

function instrument() {
    var p = new Patch([100, 100, 640, 460]);
    p.comment("Pulse Field — INSTRUMENT (field + crystallisation in one device)", 20, 8, 600);
    p.comment("OSC in on " + cfg.OSC.listen_port + " -> MIDI onsets out. Feed with examples/pulse_field_drive.py", 20, 26, 600);

    var udp = p.obj("udpreceive " + cfg.OSC.listen_port, 20, 60, 170, 0, 1);
    var js = p.obj("js thelmic.pulse-field-instrument.bundle.js", 20, 100, 280, 1, 2, {
        saved_object_attributes: { filename: "thelmic.pulse-field-instrument.bundle.js", parameter_enable: 0 } });
    p.link(udp, 0, js, 0);

    // tick clock
    var tgl = p.toggle(330, 60);
    var metro = p.obj("metro 5", 360, 60, 70, 2, 1);
    p.link(tgl, 0, metro, 0);
    p.link(metro, 0, js, 0);
    p.comment("on -> 5ms onset clock", 330, 40, 220);

    // freeze
    var frz = p.toggle(470, 60);
    var frzMsg = p.obj("prepend freeze", 470, 88, 110, 1, 1);
    p.link(frz, 0, frzMsg, 0);
    p.link(frzMsg, 0, js, 0);
    p.comment("freeze field", 500, 40, 100);

    // MIDI out
    var unpack = p.obj("unpack i i i", 20, 150, 130, 1, 3);
    var makenote = p.obj("makenote 100 200", 20, 190, 130, 3, 2);
    var noteout = p.obj("noteout", 20, 230, 70, 2, 0);
    p.link(js, 0, unpack, 0);
    p.link(unpack, 0, makenote, 0);
    p.link(unpack, 1, makenote, 1);
    p.link(unpack, 2, makenote, 2);
    p.link(makenote, 0, noteout, 0);
    p.link(makenote, 1, noteout, 1);

    var dbg = p.obj("print pulsefield", 320, 150, 120, 1, 0);
    p.link(js, 1, dbg, 0);

    p.comment("In Live: Max MIDI Effect -> this device -> Drum Rack. Turn on the clock toggle.", 20, 270, 600);
    write("thelmic.pulse-field-instrument.maxpat", p);
}

fieldState();
crystallisation();
instrument();
texture();
monitor();
combined();
console.log("done.");
