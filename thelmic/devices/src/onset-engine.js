/*
 * onset-engine.js — Pulse Field Stage 1 core: field -> onset crystallisation.
 *
 * Pure CommonJS, NO Max API. Runnable in node for tests and require()-able
 * from the Max [js] glue (rhythmic-crystallisation.js). All the genre physics
 * lives here; the Max file only feeds it field values and renders its output
 * as MIDI.
 *
 * The engine does not know it is making a kick drum. It fires energy events
 * from field conditions. The sound source downstream decides what they sound
 * like.
 *
 * Firing model (see thelmic/devices/README.md for the spec reconciliation):
 *   - PRESSURE crossing the (urgency-adapted) threshold is the primary trigger.
 *   - HYSTERESIS: once fired, pressure must fall below (threshold - hysteresis)
 *     before the next onset arms — prevents machine-gun firing on a plateau.
 *   - REFRACTORY: a hard minimum time between onsets in ms.
 *   - STABILITY shapes tightness, not firing: low stability smears timing and
 *     lengthens notes. (The spec's "stability < ceiling" AND-gate is treated as
 *     a tightness boundary rather than a hard fire-gate, so a stable Oak field
 *     still crystallises — see README "Spec reconciliation".)
 *   - DENSITY sets how many concurrent onsets fire and pushes pitch lower.
 *   - SILENCE suppresses onsets probabilistically (active absence / gaps).
 *   - NOVELTY adds timing variance on top of stability smear.
 *   - URGENCY lowers the effective threshold (faster builds).
 *   - MOMENTUM resists suppression (keeps motion going / phrase extension).
 *
 * Pulse Field branch — Stage 1.
 */

function clamp(v, lo, hi) {
    v = +v;
    if (v !== v) { return lo; }
    if (v < lo) { return lo; }
    if (v > hi) { return hi; }
    return v;
}

function lerp(a, b, t) { return a + (b - a) * t; }

// Defaults match the spec's Stage 1 section.
var DEFAULTS = {
    onset_threshold:   0.65,   // pressure that arms an onset candidate
    stability_ceiling: 0.70,   // above this, onsets are maximally tight
    refractory_ms:     90,     // hard minimum between onsets
    hysteresis:        0.08,   // pressure must fall this far below threshold to re-arm
    urgency_adapt:     0.25,   // how much urgency lowers the effective threshold
    max_concurrent:    4,      // onset count ceiling at density = 1
    // pitch: higher density -> lower register (DnB physics)
    pitch_low_density:  50,    // MIDI note at density 0  (sparser, higher)
    pitch_high_density: 36,    // MIDI note at density 1  (dense, lower)
    pitch_spread:       3,     // semitone spread for stacked concurrent onsets
    vel_floor:          42,    // velocity at pressure == threshold
    vel_ceil:           127,   // velocity at pressure == 1
    len_tight_ms:       45,    // note length when fully stable
    len_smear_ms:       240,   // note length when fully unstable
    smear_max_ms:       55,    // timing displacement at stability 0 (only < 0.3)
    smear_stability_gate: 0.30,// stability below which smear engages (spec)
    novelty_smear_ms:   35     // extra timing variance scaled by novelty
};

/*
 * OnsetEngine
 *   opts: any subset of DEFAULTS, plus:
 *     rng: function -> [0,1)  (inject a seeded RNG for deterministic tests;
 *                              defaults to Math.random)
 */
function OnsetEngine(opts) {
    opts = opts || {};
    for (var k in DEFAULTS) {
        this[k] = (opts[k] != null) ? opts[k] : DEFAULTS[k];
    }
    this.rng = opts.rng || Math.random;

    // runtime state
    this._armed = true;
    this._last_onset_ms = -1e12;
    this._last_fire = null;   // diagnostics: last produced onset batch
}

// Update a single parameter at runtime (from Max device UI / params).
OnsetEngine.prototype.setParam = function (name, value) {
    if (DEFAULTS.hasOwnProperty(name)) { this[name] = +value; }
};

// effective (urgency-adapted) threshold
OnsetEngine.prototype.effectiveThreshold = function (urgency) {
    return clamp(this.onset_threshold - clamp(urgency, 0, 1) * this.urgency_adapt,
                 0.02, 1.0);
};

/*
 * step(field, now_ms)
 *   field: object with any of pressure/stability/density/silence/novelty/
 *          urgency/momentum (missing -> 0, except stability -> 0.5).
 *   now_ms: monotonic clock in milliseconds.
 *
 * Returns an array of onset events (possibly empty). Each event:
 *   { pitch, velocity, length_ms, smear_ms }
 *   - smear_ms is the signed timing displacement to apply before sounding;
 *     positive = late, negative = early. The Max layer schedules accordingly.
 */
OnsetEngine.prototype.step = function (field, now_ms) {
    var p   = clamp(field.pressure, 0, 1);
    var s   = (field.stability != null) ? clamp(field.stability, 0, 1) : 0.5;
    var d   = clamp(field.density, 0, 1);
    var sil = clamp(field.silence, 0, 1);
    var nov = clamp(field.novelty, 0, 1);
    var urg = clamp(field.urgency, 0, 1);
    var mom = clamp(field.momentum, 0, 1);

    var thr = this.effectiveThreshold(urg);

    // Edge re-arm: pressure relaxed below the hysteresis floor (debounces a
    // noisy crossing right at the threshold).
    if (!this._armed && p < thr - this.hysteresis) {
        this._armed = true;
    }

    // Sustained re-arm: a held supra-threshold field re-arms once the
    // refractory window elapses, so a build/drop produces a steady stream of
    // onsets (rolling kicks) rather than a single shot. Disabled when
    // refractory_ms == 0, which leaves pure hysteresis edge-detection.
    if (!this._armed && this.refractory_ms > 0 &&
        (now_ms - this._last_onset_ms) >= this.refractory_ms) {
        this._armed = true;
    }

    // Refractory: nothing can fire yet.
    if (now_ms - this._last_onset_ms < this.refractory_ms) {
        return [];
    }

    // Primary trigger: armed AND pressure across threshold.
    if (!(this._armed && p >= thr)) {
        return [];
    }

    // An onset *event* occurs. Consume arm + refractory regardless of whether
    // silence suppresses the audible hit — that's what produces real gaps.
    this._armed = false;
    this._last_onset_ms = now_ms;

    // Silence suppression, resisted by momentum (motion wants to continue).
    var suppress_prob = sil * (1 - 0.5 * mom);
    if (this.rng() < suppress_prob) {
        this._last_fire = [];
        return [];
    }

    // How many concurrent onsets — density drives polyphony.
    var count = 1 + Math.round(d * (this.max_concurrent - 1));

    // Shared per-event mappings.
    var base_pitch = Math.round(lerp(this.pitch_low_density,
                                     this.pitch_high_density, d));
    var velocity = Math.round(clamp(lerp(this.vel_floor, this.vel_ceil,
                                         (p - thr) / Math.max(1e-6, 1 - thr)),
                                    1, 127));
    var length_ms = Math.round(lerp(this.len_smear_ms, this.len_tight_ms, s));

    // Smear: engages only when stability is low (spec), plus novelty variance.
    var stability_smear = (s < this.smear_stability_gate)
        ? (1 - s) * this.smear_max_ms
        : 0;
    var novelty_smear = nov * this.novelty_smear_ms;

    var events = [];
    for (var i = 0; i < count; i++) {
        // Stack concurrent onsets across a small pitch spread, centred low.
        var pitch = base_pitch;
        if (count > 1) {
            pitch = base_pitch - Math.round((i / (count - 1)) * this.pitch_spread);
        }
        pitch = Math.round(clamp(pitch, 0, 127));

        var smear = ((this.rng() * 2) - 1) * (stability_smear + novelty_smear);

        events.push({
            pitch: pitch,
            velocity: velocity,
            length_ms: length_ms,
            smear_ms: Math.round(smear)
        });
    }

    this._last_fire = events;
    return events;
};

// Diagnostics snapshot for the device UI / monitor.
OnsetEngine.prototype.diagnostics = function (urgency) {
    return {
        armed: this._armed,
        effective_threshold: this.effectiveThreshold(urgency || 0),
        last_onset_ms: this._last_onset_ms,
        last_count: this._last_fire ? this._last_fire.length : 0
    };
};

exports.OnsetEngine = OnsetEngine;
exports.DEFAULTS = DEFAULTS;
exports._clamp = clamp;
exports._lerp = lerp;
