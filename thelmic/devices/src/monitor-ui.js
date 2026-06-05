/*
 * monitor-ui.js — Pulse Field Stage 3 jsui renderer.
 *
 * A [jsui] canvas: eight dimension bars, large pressure + stability readouts,
 * a pressure history trace, a territory indicator, and a field-velocity meter.
 * Runs inside Max's jsui (mgraphics) — not node-runnable.
 *
 * It keeps its own copy of state, fed by messages from monitor.js:
 *   field <8 floats>        canonical-order vector
 *   history <n floats>      pressure history (oldest..newest)
 *   territory <name> <conf>
 *   velocity <f>
 *
 * Pulse Field branch — Stage 3.
 */

autowatch = 1;
mgraphics.init();
mgraphics.relative_coords = 0;
mgraphics.autofill = 0;

var DIM_NAMES = ["pressure", "stability", "density", "discomfort",
                 "silence", "novelty", "urgency", "momentum"];

var vec = [0, 0.5, 0.3, 0, 0, 0, 0, 0];
var hist = [];
var territory = "—";
var confidence = 0;
var velocity = 0;

// palette (Pulse Field: deep field blues -> hot crystallisation amber)
var BG     = [0.05, 0.06, 0.10];
var GRID   = [0.16, 0.18, 0.24];
var COOL   = [0.18, 0.45, 0.85];
var HOT    = [1.00, 0.62, 0.12];
var TEXT   = [0.78, 0.82, 0.90];
var ACCENT = [0.95, 0.30, 0.45];

function mix(a, b, t) {
    if (t < 0) t = 0; if (t > 1) t = 1;
    return [a[0] + (b[0]-a[0])*t, a[1] + (b[1]-a[1])*t, a[2] + (b[2]-a[2])*t];
}

// ---- message handlers -----------------------------------------------------

function field() { vec = arrayfromargs(arguments).slice(0, 8); mgraphics.redraw(); }
function history() { hist = arrayfromargs(arguments); mgraphics.redraw(); }
function territory_msg(name, conf) { territory = name; confidence = +conf; mgraphics.redraw(); }
function velocity_msg(v) { velocity = +v; mgraphics.redraw(); }
// alias the two-word selectors used by monitor.js outlets
this.territory = territory_msg;
this.velocity = velocity_msg;

// ---- paint ----------------------------------------------------------------

function paint() {
    var w = mgraphics.size[0];
    var h = mgraphics.size[1];

    // background
    mgraphics.set_source_rgb(BG[0], BG[1], BG[2]);
    mgraphics.rectangle(0, 0, w, h);
    mgraphics.fill();

    var pad = 12;
    var topH = Math.round(h * 0.30);   // big readouts row
    var traceH = Math.round(h * 0.22); // history trace
    var barsY = pad + topH + traceH + pad;
    var barsH = h - barsY - pad - 16;

    draw_big_readouts(pad, pad, w - pad * 2, topH);
    draw_trace(pad, pad + topH + 6, w - pad * 2, traceH - 6);
    draw_bars(pad, barsY, w - pad * 2, barsH);
}

function draw_big_readouts(x, y, w, h) {
    var halfW = (w - 10) / 2;
    big_box(x, y, halfW, h, "PRESSURE", vec[0], HOT);
    big_box(x + halfW + 10, y, halfW, h, "STABILITY", vec[1], COOL);

    // territory + velocity strip along the bottom of this block
    mgraphics.select_font_face("Arial");
    mgraphics.set_font_size(11);
    mgraphics.set_source_rgb(ACCENT[0], ACCENT[1], ACCENT[2]);
    mgraphics.move_to(x, y + h + 12);
    mgraphics.show_text("TERRITORY: " + String(territory).toUpperCase() +
                        "  (" + (confidence).toFixed(2) + ")");
    mgraphics.set_source_rgb(TEXT[0], TEXT[1], TEXT[2]);
    mgraphics.move_to(x + w - 150, y + h + 12);
    mgraphics.show_text("FIELD VEL: " + (velocity).toFixed(3));
}

function big_box(x, y, w, h, label, val, col) {
    // frame
    mgraphics.set_source_rgb(GRID[0], GRID[1], GRID[2]);
    mgraphics.rectangle(x, y, w, h);
    mgraphics.set_line_width(1);
    mgraphics.stroke();
    // fill proportional to value (vertical)
    var fh = h * clamp01(val);
    var c = mix(col, HOT, val * 0.4);
    mgraphics.set_source_rgb(c[0], c[1], c[2]);
    mgraphics.rectangle(x, y + (h - fh), w, fh);
    mgraphics.fill();
    // label + numeric
    mgraphics.set_source_rgb(TEXT[0], TEXT[1], TEXT[2]);
    mgraphics.select_font_face("Arial");
    mgraphics.set_font_size(12);
    mgraphics.move_to(x + 6, y + 16);
    mgraphics.show_text(label);
    mgraphics.set_font_size(22);
    mgraphics.move_to(x + 6, y + h - 10);
    mgraphics.show_text((val).toFixed(3));
}

function draw_trace(x, y, w, h) {
    mgraphics.set_source_rgb(GRID[0], GRID[1], GRID[2]);
    mgraphics.rectangle(x, y, w, h);
    mgraphics.set_line_width(1);
    mgraphics.stroke();
    if (hist.length < 2) { return; }
    mgraphics.set_source_rgb(HOT[0], HOT[1], HOT[2]);
    mgraphics.set_line_width(1.5);
    for (var i = 0; i < hist.length; i++) {
        var px = x + (w * i / (hist.length - 1));
        var py = y + h - (h * clamp01(hist[i]));
        if (i === 0) { mgraphics.move_to(px, py); }
        else { mgraphics.line_to(px, py); }
    }
    mgraphics.stroke();
}

function draw_bars(x, y, w, h) {
    var n = DIM_NAMES.length;
    var gap = 8;
    var bw = (w - gap * (n - 1)) / n;
    for (var i = 0; i < n; i++) {
        var bx = x + i * (bw + gap);
        var v = clamp01(vec[i] != null ? vec[i] : 0);
        // frame
        mgraphics.set_source_rgb(GRID[0], GRID[1], GRID[2]);
        mgraphics.rectangle(bx, y, bw, h);
        mgraphics.set_line_width(1);
        mgraphics.stroke();
        // fill
        var c = mix(COOL, HOT, v);
        mgraphics.set_source_rgb(c[0], c[1], c[2]);
        var fh = h * v;
        mgraphics.rectangle(bx, y + (h - fh), bw, fh);
        mgraphics.fill();
        // label (abbreviated, vertical space is tight)
        mgraphics.set_source_rgb(TEXT[0], TEXT[1], TEXT[2]);
        mgraphics.select_font_face("Arial");
        mgraphics.set_font_size(9);
        mgraphics.move_to(bx + 1, y + h + 11);
        mgraphics.show_text(DIM_NAMES[i].substring(0, 5));
    }
}

function clamp01(v) { v = +v; return v < 0 ? 0 : (v > 1 ? 1 : v); }

// repaint on resize
function onresize() { mgraphics.redraw(); }
