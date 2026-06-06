/*
 * impact-synth.js — parameter forwarder for the Pulse Field IMPACT instrument.
 *
 * The grid/timing lives in the audio domain (tempo-synced [phasor~ 16n] -> gen~),
 * so this brain is purely a robust parameter bridge: it reads THIS device's
 * parameters via LiveAPI observers (low-priority init) and forwards each as a
 * "<name> <value>" message to [gen~]. That makes manual moves, bridge/API sets,
 * AND automation lanes all reach the engine (live.dial alone doesn't fire its
 * outlet on load/API-set). A slow metro re-emits the cached values as a safety.
 *
 * Inlets: 0 = re-emit tick + dial messages ; 1 = live.thisdevice (init trigger)
 * Outlet: 0 = "<name> <value>" into [gen~]
 *
 * Pulse Field branch — impact/rhythm base (control bridge).
 */

autowatch = 1;
inlets = 2;
outlets = 1;

var vals = {};
var paramAPIs = [];   // keep observer refs alive

function num(x) {
    if (x === null || x === undefined) { return null; }
    if (x.length !== undefined) { return x.length ? +x[0] : null; }
    return +x;
}

function setp(name, value) {
    if (!name || name === "Device On") { return; }
    value = +value;
    if (value !== value) { return; }
    vals[name] = value;
    outlet(0, name, value);
}

// LOW-PRIORITY init (via live.thisdevice on inlet 1): observe this device's params
function init_low() {
    try {
        var dev = new LiveAPI("this_device");
        var count = dev.getcount("parameters");
        for (var i = 0; i < count; i++) {
            var path = "this_device parameters " + i;
            var p = new LiveAPI(path);
            var nm = p.get("name");
            nm = (nm && nm.length !== undefined) ? nm[0] : nm;
            setp(nm, num(p.get("value")));
            (function (name, ppath) {
                var obs = new LiveAPI(function (args) {
                    if (args && args.length >= 2 && args[0] === "value") {
                        setp(name, args[1]);
                    }
                }, ppath);
                obs.property = "value";
                paramAPIs.push(obs);
            })(nm, path);
        }
    } catch (e) {}
}

// dial-message fallback (manual / automation also arrive on inlet 0)
function anything() {
    var a = arrayfromargs(arguments);
    if (a.length >= 1) { setp(messagename, a[0]); }
}

function bang() {
    if (inlet === 1) { init_low(); }
    else { for (var k in vals) { outlet(0, k, vals[k]); } }   // re-emit cache
}
