/*
 * texture-audio.js — Pulse Field Stage 2 core: field -> texture control values.
 *
 * Pure CommonJS, NO Max API. Maps the field vector onto the control inputs of
 * the three-layer noise texture (sub / mid / air) described in the spec. The
 * Max layer (texture.js) feeds field values in and routes the returned control
 * values to the audio objects (noise~, svf~/reson~, lores~, *~).
 *
 * Layer model (spec Stage 2):
 *   sub  — low-frequency filtered noise; weight from pressure. Always present.
 *   mid  — bandpass noise; centre from discomfort, bandwidth from stability.
 *   air  — high-pass noise; presence from novelty.
 *
 * Field -> control mapping (spec):
 *   discomfort -> spectral brightness / filter drive
 *   urgency    -> cutoff rate of change (how fast the texture shifts)
 *   silence    -> overall amplitude (more silence => quieter)
 *   pressure   -> sub weight / noise density
 *   stability  -> filter Q / resonance (unstable => more resonant)
 *   momentum   -> rate of textural change (high momentum => slow evolution)
 *
 * All frequencies in Hz, levels in [0,1], times in ms.
 *
 * Pulse Field branch — Stage 2.
 */

function clamp(v, lo, hi) {
    v = +v;
    if (v !== v) { return lo; }
    return v < lo ? lo : (v > hi ? hi : v);
}
function lerp(a, b, t) { return a + (b - a) * t; }

var DEFAULTS = {
    sub_freq_lo:   40,    sub_freq_hi:   90,    // sub centre range
    mid_freq_lo:   300,   mid_freq_hi:   2600,  // mid centre range (discomfort)
    mid_bw_lo:     80,    mid_bw_hi:     1400,  // mid bandwidth (stability: stable=wide)
    air_freq_lo:   3000,  air_freq_hi:   9000,  // air high-pass corner
    q_lo:          0.6,   q_hi:          14.0,  // resonance (stability: unstable=high Q)
    drive_lo:      0.0,   drive_hi:      0.85,  // saturation (discomfort)
    // evolution time: how long the smoothing ramp on cutoff/levels is.
    // urgency shortens it; momentum lengthens it.
    evo_ms_fast:   40,    evo_ms_slow:   1800,
    master_floor:  0.0,   master_ceil:   0.9    // overall amp before silence cut
};

/*
 * textureControls(field, opts) -> control object:
 *   {
 *     sub_freq, sub_level,
 *     mid_freq, mid_bw, mid_q, mid_level,
 *     air_freq, air_level,
 *     drive, master, evo_ms
 *   }
 *
 * Layer levels are normalised so they sum to <= 1 (no static mix; the field
 * decides the balance every call). master scales the whole bed, cut by silence.
 */
function textureControls(field, opts) {
    opts = opts || {};
    var P = {};
    for (var k in DEFAULTS) { P[k] = (opts[k] != null) ? opts[k] : DEFAULTS[k]; }

    var pressure   = clamp(field.pressure, 0, 1);
    var stability  = (field.stability != null) ? clamp(field.stability, 0, 1) : 0.5;
    var discomfort = clamp(field.discomfort, 0, 1);
    var silence    = clamp(field.silence, 0, 1);
    var novelty    = clamp(field.novelty, 0, 1);
    var urgency    = clamp(field.urgency, 0, 1);
    var momentum   = clamp(field.momentum, 0, 1);

    // --- sub: weight from pressure, always a floor of presence ---
    var sub_freq = lerp(P.sub_freq_lo, P.sub_freq_hi, pressure);
    var sub_raw  = 0.35 + 0.65 * pressure;     // never fully gone

    // --- mid: centre from discomfort, bandwidth from stability ---
    var mid_freq = lerp(P.mid_freq_lo, P.mid_freq_hi, discomfort);
    // stable field => wide, open band; unstable => narrow, pressured band
    var mid_bw   = lerp(P.mid_bw_lo, P.mid_bw_hi, stability);
    // unstable field => high Q / resonance
    var mid_q    = lerp(P.q_lo, P.q_hi, 1 - stability);
    var mid_raw  = 0.2 + 0.8 * discomfort;

    // --- air: presence from novelty ---
    var air_freq = lerp(P.air_freq_lo, P.air_freq_hi, novelty);
    var air_raw  = 0.15 + 0.85 * novelty;

    // --- normalise the three layer weights so they don't sum hot ---
    var sum = sub_raw + mid_raw + air_raw;
    if (sum <= 0) { sum = 1; }
    var sub_level = sub_raw / sum;
    var mid_level = mid_raw / sum;
    var air_level = air_raw / sum;

    // --- drive from discomfort ---
    var drive = lerp(P.drive_lo, P.drive_hi, discomfort);

    // --- master amplitude, cut by silence ---
    var master = lerp(P.master_floor, P.master_ceil, 0.5 + 0.5 * pressure);
    master *= (1 - silence);

    // --- evolution time: urgency fast, momentum slow ---
    // blend: high urgency pulls toward fast; high momentum pulls toward slow.
    var fastness = clamp(urgency * (1 - momentum), 0, 1);
    var evo_ms = lerp(P.evo_ms_slow, P.evo_ms_fast, fastness);

    return {
        sub_freq: sub_freq, sub_level: sub_level,
        mid_freq: mid_freq, mid_bw: mid_bw, mid_q: mid_q, mid_level: mid_level,
        air_freq: air_freq, air_level: air_level,
        drive: drive, master: master, evo_ms: evo_ms
    };
}

exports.textureControls = textureControls;
exports.DEFAULTS = DEFAULTS;
