/*
 * test-pure-modules.js — node tests for territory.js and texture-audio.js.
 * Run: node thelmic/devices/test/test-pure-modules.js
 */

var path = require("path");
var terr = require(path.join(__dirname, "..", "src", "territory.js"));
var ta = require(path.join(__dirname, "..", "src", "texture-audio.js"));

var passed = 0, failed = 0;
function ok(name, cond) { if (cond) passed++; else { failed++; console.error("  FAIL: " + name); } }

// ── territory: a vector sitting on a profile matches that territory ─────────
(function () {
    for (var name in terr.PROFILES) {
        var m = terr.nearestTerritory(terr.PROFILES[name]);
        ok("profile " + name + " matches itself", m.name === name);
        ok("profile " + name + " high confidence", m.confidence > 0.5);
    }
})();

// ── territory: Nott signature (high discomfort/pressure/silence, low stab) ──
(function () {
    var nottish = { pressure: 0.85, stability: 0.15, density: 0.5, discomfort: 0.95,
                    silence: 0.65, novelty: 0.25, urgency: 0.4, momentum: 0.5 };
    ok("nott-ish field -> nott", terr.nearestTerritory(nottish).name === "nott");
    var oakish = { pressure: 0.45, stability: 0.9, density: 0.5, discomfort: 0.05,
                   silence: 0.1, novelty: 0.15, urgency: 0.15, momentum: 0.6 };
    ok("oak-ish field -> oak", terr.nearestTerritory(oakish).name === "oak");
    var chaosish = { pressure: 0.6, stability: 0.45, density: 0.6, discomfort: 0.4,
                     silence: 0.2, novelty: 0.95, urgency: 0.85, momentum: 0.35 };
    ok("chaos-ish field -> chaos", terr.nearestTerritory(chaosish).name === "chaos");
})();

// ── texture: layer levels normalise to ~1 ──────────────────────────────────
(function () {
    var c = ta.textureControls({ pressure: 0.5, stability: 0.5, discomfort: 0.5,
                                 silence: 0.0, novelty: 0.5 }, {});
    var sum = c.sub_level + c.mid_level + c.air_level;
    ok("layer levels sum to ~1", Math.abs(sum - 1) < 1e-9);
})();

// ── texture: silence cuts master ───────────────────────────────────────────
(function () {
    var loud = ta.textureControls({ pressure: 0.8, silence: 0.0 }, {});
    var quiet = ta.textureControls({ pressure: 0.8, silence: 0.9 }, {});
    ok("silence reduces master", quiet.master < loud.master);
    ok("full-ish silence near-mutes", quiet.master < loud.master * 0.5);
})();

// ── texture: discomfort raises mid centre + drive ──────────────────────────
(function () {
    var calm = ta.textureControls({ discomfort: 0.1 }, {});
    var harsh = ta.textureControls({ discomfort: 0.9 }, {});
    ok("discomfort raises mid centre freq", harsh.mid_freq > calm.mid_freq);
    ok("discomfort raises drive", harsh.drive > calm.drive);
})();

// ── texture: instability raises Q, stability widens bandwidth ──────────────
(function () {
    var stable = ta.textureControls({ stability: 0.95 }, {});
    var unstable = ta.textureControls({ stability: 0.05 }, {});
    ok("instability raises Q/resonance", unstable.mid_q > stable.mid_q);
    ok("stability widens bandwidth", stable.mid_bw > unstable.mid_bw);
})();

// ── texture: urgency speeds evolution, momentum slows it ────────────────────
(function () {
    var slow = ta.textureControls({ urgency: 0.0, momentum: 0.9 }, {});
    var fast = ta.textureControls({ urgency: 0.9, momentum: 0.0 }, {});
    ok("urgency shortens evolution time", fast.evo_ms < slow.evo_ms);
})();

console.log("pure-modules: " + passed + " passed, " + failed + " failed");
process.exit(failed === 0 ? 0 : 1);
