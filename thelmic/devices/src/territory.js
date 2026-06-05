/*
 * territory.js — Pulse Field territory profiles + nearest-neighbour matching.
 *
 * Pure CommonJS, NO Max API. Encodes the three thelmic territories as field
 * signatures (spec "Territory Mapping" table) and finds which one a live field
 * vector most closely matches. Used by the monitor (Stage 3) for the territory
 * indicator and mirrored by the Python driver so both ends agree on the map.
 *
 * Pulse Field branch — Stage 3.
 */

// Representative field signatures, one per territory. Values are the centre of
// each territory's region in field-space (spec table, quantified).
var PROFILES = {
    oak: {   // moderate pressure, high stability, moderate density, low discomfort
        pressure: 0.50, stability: 0.85, density: 0.50, discomfort: 0.10,
        silence:  0.15, novelty:   0.20, urgency: 0.20, momentum:   0.55
    },
    chaos: { // high novelty, high urgency, oscillating (mid) stability
        pressure: 0.60, stability: 0.40, density: 0.60, discomfort: 0.40,
        silence:  0.20, novelty:   0.90, urgency: 0.80, momentum:   0.40
    },
    nott: {  // high discomfort, high pressure, low stability, high silence
        pressure: 0.80, stability: 0.20, density: 0.50, discomfort: 0.90,
        silence:  0.60, novelty:   0.30, urgency: 0.45, momentum:   0.55
    }
};

var DIMS = ["pressure", "stability", "density", "discomfort",
            "silence", "novelty", "urgency", "momentum"];

function dist2(field, profile) {
    var s = 0;
    for (var i = 0; i < DIMS.length; i++) {
        var d = DIMS[i];
        var fv = (field[d] != null) ? field[d] : 0;
        var pv = (profile[d] != null) ? profile[d] : 0;
        var delta = fv - pv;
        s += delta * delta;
    }
    return s;
}

/*
 * nearestTerritory(field) -> { name, distance, confidence }
 *   confidence in [0,1]: 1 when sitting exactly on a profile, decaying with
 *   distance, and lowered when the runner-up is almost as close (ambiguous).
 */
function nearestTerritory(field) {
    var best = null, bestD = Infinity, secondD = Infinity;
    for (var name in PROFILES) {
        var d = dist2(field, PROFILES[name]);
        if (d < bestD) { secondD = bestD; bestD = d; best = name; }
        else if (d < secondD) { secondD = d; }
    }
    var bestDist = Math.sqrt(bestD);
    var maxDist = Math.sqrt(DIMS.length);           // worst case in unit cube
    var proximity = 1 - (bestDist / maxDist);       // 1 = exact, 0 = far
    // separation: how much clearer the winner is than the runner-up
    var sep = (secondD === Infinity) ? 1
            : Math.min(1, (Math.sqrt(secondD) - bestDist) / maxDist + 0.0);
    var confidence = Math.max(0, Math.min(1, proximity * (0.5 + 0.5 * sep)));
    return { name: best, distance: bestDist, confidence: confidence };
}

exports.PROFILES = PROFILES;
exports.DIMS = DIMS;
exports.nearestTerritory = nearestTerritory;
