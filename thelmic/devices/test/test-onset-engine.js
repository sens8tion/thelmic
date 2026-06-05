/*
 * test-onset-engine.js — node tests for the pure onset crystallisation core.
 * Run: node thelmic/devices/test/test-onset-engine.js
 *
 * These mirror the Stage 1 acceptance tests from the spec, but as fast,
 * deterministic unit checks (no Max required). A seeded RNG makes smear and
 * silence suppression reproducible.
 */

var path = require("path");
var oe = require(path.join(__dirname, "..", "src", "onset-engine.js"));
var OnsetEngine = oe.OnsetEngine;

// mulberry32 — tiny deterministic PRNG so tests are reproducible.
function seeded(seed) {
    var a = seed >>> 0;
    return function () {
        a |= 0; a = (a + 0x6D2B79F5) | 0;
        var t = Math.imul(a ^ (a >>> 15), 1 | a);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
}

var passed = 0, failed = 0;
function ok(name, cond) {
    if (cond) { passed++; }
    else { failed++; console.error("  FAIL: " + name); }
}
function eq(name, a, b) { ok(name + " (" + a + " == " + b + ")", a === b); }

// Drive the engine across a span of time at a fixed tick, counting onsets.
function run(engine, field, ticks, dt_ms, t0) {
    var t = t0 || 0;
    var total = 0, batches = 0;
    for (var i = 0; i < ticks; i++) {
        var ev = engine.step(field, t);
        if (ev.length > 0) { total += ev.length; batches++; }
        t += dt_ms;
    }
    return { onsets: total, batches: batches };
}

// ── 1. Below threshold -> silence ──────────────────────────────────────────
(function () {
    var e = new OnsetEngine({ rng: seeded(1) });
    var r = run(e, { pressure: 0.2, stability: 0.5 }, 200, 10);
    eq("no onsets below threshold", r.onsets, 0);
})();

// ── 2. Above threshold -> onsets begin firing ──────────────────────────────
(function () {
    var e = new OnsetEngine({ rng: seeded(1), refractory_ms: 90 });
    var r = run(e, { pressure: 0.9, stability: 0.5, density: 0.0 }, 200, 10);
    ok("onsets fire above threshold", r.batches > 0);
    // density 0 -> exactly one onset per batch
    eq("density 0 => 1 onset per batch", r.onsets, r.batches);
})();

// ── 3. Refractory bounds the rate ──────────────────────────────────────────
(function () {
    var e = new OnsetEngine({ rng: seeded(1), refractory_ms: 100, hysteresis: 0 });
    // 1000ms of held high pressure at 1ms ticks: at most ~10 onsets (refractory).
    var r = run(e, { pressure: 1.0, stability: 0.5, density: 0 }, 1000, 1);
    ok("refractory caps rate (<=11 in 1s @100ms)", r.batches <= 11);
    ok("refractory still allows firing (>=8 in 1s)", r.batches >= 8);
})();

// ── 4. Hysteresis prevents machine-gun on a plateau ────────────────────────
(function () {
    // With huge refractory cleared by long dt, a held plateau must NOT refire
    // until pressure dips below threshold-hysteresis.
    var e = new OnsetEngine({ rng: seeded(1), refractory_ms: 0, hysteresis: 0.1 });
    var t = 0;
    var first = e.step({ pressure: 0.9, stability: 0.5, density: 0 }, t); t += 50;
    var second = e.step({ pressure: 0.9, stability: 0.5, density: 0 }, t); t += 50;
    eq("first crossing fires", first.length, 1);
    eq("held plateau does not refire (hysteresis)", second.length, 0);
    // drop below threshold-hysteresis to re-arm, then cross again
    e.step({ pressure: 0.4, stability: 0.5, density: 0 }, t); t += 50;
    var third = e.step({ pressure: 0.9, stability: 0.5, density: 0 }, t);
    eq("re-arms after dip", third.length, 1);
})();

// ── 5. Density -> concurrent onsets + lower pitch ──────────────────────────
(function () {
    var lo = new OnsetEngine({ rng: seeded(2) });
    var hi = new OnsetEngine({ rng: seeded(2) });
    var loEv = lo.step({ pressure: 0.9, stability: 0.5, density: 0.0 }, 0);
    var hiEv = hi.step({ pressure: 0.9, stability: 0.5, density: 1.0 }, 0);
    eq("density 0 => 1 concurrent", loEv.length, 1);
    eq("density 1 => max concurrent", hiEv.length, oe.DEFAULTS.max_concurrent);
    ok("higher density => lower pitch", hiEv[0].pitch < loEv[0].pitch);
})();

// ── 6. Stability -> timing variance (smear) ────────────────────────────────
(function () {
    // Low stability (<0.3) must produce non-zero smear; high stability tight.
    function maxAbsSmear(stab) {
        var e = new OnsetEngine({ rng: seeded(7), refractory_ms: 0, hysteresis: 0 });
        var m = 0, t = 0;
        for (var i = 0; i < 50; i++) {
            // toggle pressure to keep re-arming
            e.step({ pressure: 0.1, stability: stab }, t); t += 10;
            var ev = e.step({ pressure: 0.95, stability: stab, density: 0 }, t); t += 10;
            for (var j = 0; j < ev.length; j++) {
                if (Math.abs(ev[j].smear_ms) > m) { m = Math.abs(ev[j].smear_ms); }
            }
        }
        return m;
    }
    ok("low stability smears timing", maxAbsSmear(0.05) > 0);
    eq("high stability is tight (no smear)", maxAbsSmear(0.9), 0);
    // length: unstable longer than stable
    var u = new OnsetEngine({ rng: seeded(1) });
    var s = new OnsetEngine({ rng: seeded(1) });
    var uev = u.step({ pressure: 0.9, stability: 0.0, density: 0 }, 0);
    var sev = s.step({ pressure: 0.9, stability: 1.0, density: 0 }, 0);
    ok("unstable note longer than stable", uev[0].length_ms > sev[0].length_ms);
})();

// ── 7. Silence -> onset suppression (statistical) ──────────────────────────
(function () {
    function batchCount(sil, mom) {
        var e = new OnsetEngine({ rng: seeded(123), refractory_ms: 90 });
        return run(e, { pressure: 0.95, stability: 0.5, density: 0,
                        silence: sil, momentum: mom || 0 }, 400, 10).batches;
    }
    var none = batchCount(0.0);
    var heavy = batchCount(0.85);
    ok("silence suppresses onsets", heavy < none);
    ok("momentum resists suppression", batchCount(0.85, 0.9) >= batchCount(0.85, 0.0));
})();

// ── 8. Urgency lowers effective threshold ──────────────────────────────────
(function () {
    var e = new OnsetEngine();
    ok("urgency lowers threshold",
       e.effectiveThreshold(1.0) < e.effectiveThreshold(0.0));
    // pressure that wouldn't fire at urgency 0 fires at urgency 1
    var calm = new OnsetEngine({ rng: seeded(1) });
    var rush = new OnsetEngine({ rng: seeded(1) });
    var pr = 0.5; // below default threshold 0.65
    eq("calm: no fire at p=0.5", calm.step({ pressure: pr, stability: 0.5, urgency: 0 }, 0).length, 0);
    ok("urgent: fires at p=0.5", rush.step({ pressure: pr, stability: 0.5, urgency: 1.0 }, 0).length > 0);
})();

// ── 9. Velocity scales with pressure ───────────────────────────────────────
(function () {
    var a = new OnsetEngine({ rng: seeded(1) });
    var b = new OnsetEngine({ rng: seeded(1) });
    var soft = a.step({ pressure: 0.66, stability: 0.5, density: 0 }, 0)[0];
    var hard = b.step({ pressure: 1.0, stability: 0.5, density: 0 }, 0)[0];
    ok("harder pressure => higher velocity", hard.velocity > soft.velocity);
    ok("velocity within MIDI range", hard.velocity <= 127 && soft.velocity >= 1);
})();

console.log("onset-engine: " + passed + " passed, " + failed + " failed");
process.exit(failed === 0 ? 0 : 1);
