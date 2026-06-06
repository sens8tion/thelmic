"""Build Pulse Field .amxd devices by injecting objects into Live's template.

Starts from Live's unencrypted "Max Instrument" starter template (via amxd.py),
adds standard, documented maxpat objects (the same JSON format Max reads), and
re-wraps. The template already provides `midiin` and `plugout~` (audio to Live);
we wire our synthesis into `plugout~`.

  build_test_tone(out)   minimal cycle~ tone + one automatable param (pipeline proof)
  build_field_synth(out)  the full continuous field synthesis (see task 9)

Pulse Field branch — M4L device authoring.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from thelmic.pulse_field import amxd

PLUGOUT = "obj-2"   # audio-to-Live sink in the instrument template
SRC_DIR = Path(__file__).resolve().parent.parent / "devices" / "src"

# the 8 automatable field dimensions, in canonical order
FIELD_DIMS = ["pressure", "stability", "density", "discomfort",
              "silence", "novelty", "urgency", "momentum"]


class PatchBuilder:
    """Append boxes/lines to a template patcher; ids auto-numbered from 100."""

    def __init__(self, kind: str = "instrument"):
        self.kind_bytes, self.patcher = amxd.load_template(kind)
        self.p = self.patcher["patcher"]
        self._n = 100

    def _id(self) -> str:
        self._n += 1
        return f"obj-{self._n}"

    def obj(self, text, x, y, w=80, ins=2, outs=1, outtypes=None, extra=None):
        bid = self._id()
        box = {
            "maxclass": "newobj", "text": text, "id": bid,
            "numinlets": ins, "numoutlets": outs,
            "patching_rect": [x, y, w, 22],
        }
        if outs:
            box["outlettype"] = outtypes or (["signal"] * outs)
        if extra:
            box.update(extra)
        self.p["boxes"].append({"box": box})
        return bid

    def dial(self, varname, x, y, lo=0.0, hi=1.0, init=0.0):
        bid = self._id()
        box = {
            "maxclass": "live.dial", "id": bid,
            "numinlets": 1, "numoutlets": 2, "outlettype": ["", "float"],
            "parameter_enable": 1, "varname": varname,
            "patching_rect": [x, y, 48, 48],
            "saved_attribute_attributes": {"valueof": {
                "parameter_longname": varname, "parameter_shortname": varname,
                "parameter_mmin": lo, "parameter_mmax": hi,
                "parameter_initial": [init], "parameter_initial_enable": 1,
                "parameter_type": 0, "parameter_unitstyle": 1,
            }},
        }
        self.p["boxes"].append({"box": box})
        return bid

    def link(self, src, so, dst, di):
        self.p["lines"].append({"patchline": {
            "source": [src, so], "destination": [dst, di]}})

    def save(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        amxd.write_amxd(path, self.patcher, self.kind_bytes)


def build_test_tone(out_path):
    """Minimal proof: a 220 Hz tone with one automatable 'level' param."""
    b = PatchBuilder("instrument")
    osc = b.obj("cycle~ 220", 200, 220, 80, 2, 1)
    amp = b.obj("*~ 0.0", 200, 270, 60, 2, 1)
    smooth = b.obj("line~", 320, 220, 60, 2, 1)
    level = b.dial("level", 320, 150, 0.0, 1.0, 0.2)
    b.link(osc, 0, amp, 0)
    b.link(level, 0, smooth, 0)     # dial -> line~ -> *~ right inlet (smoothed gain)
    b.link(smooth, 0, amp, 1)
    b.link(amp, 0, PLUGOUT, 0)      # to Live, both channels
    b.link(amp, 0, PLUGOUT, 1)
    b.save(out_path)
    return out_path


def gen_patcher(genexpr_name="field-osc.genexpr", ins=0, outs=2):
    """Build the nested gen patcher dict (classnamespace dsp.gen) holding the
    GenExpr codebox, with [in 1..ins] -> codebox and codebox -> [out 1..outs].
    EMBEDDED in the [gen~] box so the code travels with the device and gen~ can't
    serve a stale cached version keyed on a shared external filename.

    ins>0 is REQUIRED when the GenExpr reads in1/in2 (e.g. a phasor) — without an
    [in N] operator wired to the codebox, inN is silently 0.
    """
    code = (SRC_DIR / genexpr_name).read_text(encoding="utf-8")
    ci = max(1, ins)
    boxes = [{"box": {"maxclass": "codebox", "id": "obj-1", "numinlets": ci,
                      "numoutlets": outs, "outlettype": [""] * outs,
                      "patching_rect": [20, 120, 600, 380], "code": code,
                      "fontname": "Lato", "fontsize": 12.0, "fontface": 0,
                      "style": ""}}]
    lines = []
    for i in range(ins):
        iid = "obj-in%d" % (i + 1)
        boxes.append({"box": {"maxclass": "newobj", "id": iid, "numinlets": 0,
                              "numoutlets": 1, "outlettype": [""],
                              "text": "in %d" % (i + 1),
                              "patching_rect": [20 + i * 60, 20, 40, 22]}})
        lines.append({"patchline": {"source": [iid, 0], "destination": ["obj-1", i]}})
    for o in range(outs):
        oid = "obj-out%d" % (o + 1)
        boxes.append({"box": {"maxclass": "newobj", "id": oid, "numinlets": 1,
                              "numoutlets": 0, "text": "out %d" % (o + 1),
                              "patching_rect": [20 + o * 60, 540, 40, 22]}})
        lines.append({"patchline": {"source": ["obj-1", o], "destination": [oid, 0]}})
    return {
        "fileversion": 1,
        "appversion": {"major": 8, "minor": 1, "revision": 2,
                       "architecture": "x64", "modernui": 1},
        "classnamespace": "dsp.gen",
        "rect": [0, 0, 680, 520],
        "boxes": boxes,
        "lines": lines,
    }


def build_field_synth(out_path, js_name="field-synth.js"):
    """The continuous field synth: a self-morphing gen~ oscillator (embedded
    GenExpr) whose waveform perpetually morphs, with the field mapped onto its
    parameters by [js field-synth.js] and a BPM-locked rhythm envelope on amp.
    8 field dims + root + gain are automatable live.dials.

    Writes the .amxd and copies the JS beside it (device folder search path),
    so Live loads the whole thing with no Max editing.
    """
    out_path = Path(out_path)
    b = PatchBuilder("instrument")

    # control brain: inlet 0 = tick + param msgs; inlet 1 = live.thisdevice init
    js = b.obj("js " + js_name, 40, 360, 150, 2, 1, outtypes=[""],
               extra={"saved_object_attributes": {"filename": js_name,
                                                   "parameter_enable": 0}})

    # clock: device-load -> metro -> js inlet 0 (tick). live.thisdevice ALSO bangs
    # js inlet 1 to run LiveAPI init on the low-priority thread.
    thisdev = b.obj("live.thisdevice", 240, 270, 100, 0, 3,
                    outtypes=["bang", "", ""])
    startm = b.obj("t 1", 240, 300, 40, 1, 1, outtypes=[""])
    metro = b.obj("metro 10", 240, 330, 70, 2, 1, outtypes=["bang"])
    b.link(thisdev, 0, startm, 0)
    b.link(startm, 0, metro, 0)
    b.link(metro, 0, js, 0)
    b.link(thisdev, 0, js, 1)              # init LiveAPI (low-priority)

    # automatable params: 8 field dims + root + gain -> [prepend] -> js
    x = 40
    inits = {"stability": 0.5, "density": 0.3, "momentum": 0.5}
    for name in FIELD_DIMS:
        d = b.dial(name, x, 40, 0.0, 1.0, inits.get(name, 0.0))
        pp = b.obj("prepend " + name, x, 300, 90, 1, 1, outtypes=[""])
        b.link(d, 0, pp, 0); b.link(pp, 0, js, 0)
        x += 70
    rootd = b.dial("root", x, 40, 20.0, 220.0, 55.0)
    rpp = b.obj("prepend root", x, 300, 90, 1, 1, outtypes=[""])
    b.link(rootd, 0, rpp, 0); b.link(rpp, 0, js, 0); x += 70
    gaind = b.dial("gain", x, 40, 0.0, 1.0, 0.85)
    gpp = b.obj("prepend gain", x, 300, 90, 1, 1, outtypes=[""])
    b.link(gaind, 0, gpp, 0); b.link(gpp, 0, js, 0); x += 70
    widthd = b.dial("width", x, 40, 0.0, 1.0, 0.5)  # stereo decorrelation
    wpp = b.obj("prepend width", x, 300, 90, 1, 1, outtypes=[""])
    b.link(widthd, 0, wpp, 0); b.link(wpp, 0, js, 0)

    # the self-morphing STEREO oscillator (embedded gen code) -> limiters -> Live.
    # @oversample 4 tames aliasing fizz from the feedback-FM / waveshaper.
    gen = b.obj("gen~ @oversample 8", 40, 440, 160, 1, 2,
                outtypes=["signal", "signal"], extra={"patcher": gen_patcher()})
    b.link(js, 0, gen, 0)
    limL = b.obj("clip~ -1. 1.", 40, 480, 80, 3, 1)
    limR = b.obj("clip~ -1. 1.", 130, 480, 80, 3, 1)
    b.link(gen, 0, limL, 0)
    b.link(gen, 1, limR, 0)
    b.link(limL, 0, PLUGOUT, 0)
    b.link(limR, 0, PLUGOUT, 1)

    b.save(out_path)
    shutil.copyfile(SRC_DIR / js_name, out_path.parent / js_name)
    return out_path


# parametric impact instrument: same device, retuned per frequency band
IMPACT_PARAMS = [
    # (name, lo, hi, init)  -- tune is 0..1, mapped exp to 20Hz-8kHz in gen
    ("tune", 0.0, 1.0, 0.4),
    ("tone", 0.0, 1.0, 0.0),
    ("punch", 0.0, 1.0, 0.5),
    ("decay", 0.0, 1.0, 0.3),
    ("density", 0.0, 1.0, 0.35),    # 0 = four-on-the-floor
    ("entropy", 0.0, 1.0, 0.0),
    ("seed", 0.0, 1.0, 0.2),        # regen: nudge for a different fixed pattern
    ("level", 0.0, 1.0, 0.8),
]


def build_impact(out_path, js_name="impact-synth.js"):
    """The impact / rhythm-base instrument: a tempo-synced [phasor~ 16n] drives a
    gen~ that fires grid-locked impacts; entropy controls placement scatter +
    before/after-grid timing. One parametric device (tune/tone/punch/decay/
    density/entropy/level) meant to be replicated per band (sub/mid/high). All
    params automatable. Not MIDI — a shaped layer.
    """
    out_path = Path(out_path)
    b = PatchBuilder("instrument")

    # control bridge (params -> gen), inlet 0 re-emit/msgs, inlet 1 init
    js = b.obj("js " + js_name, 40, 360, 150, 2, 1, outtypes=[""],
               extra={"saved_object_attributes": {"filename": js_name,
                                                   "parameter_enable": 0}})

    # transport-locked bar phasor (0..1 per bar); gen derives the 16th grid +
    # a stable per-step pattern from it.
    phasor = b.obj("phasor~ 1n", 40, 410, 90, 2, 1, outtypes=["signal"])

    # clock for the bridge + low-priority init
    thisdev = b.obj("live.thisdevice", 240, 270, 100, 0, 3,
                    outtypes=["bang", "", ""])
    startm = b.obj("t 1", 240, 300, 40, 1, 1, outtypes=[""])
    metro = b.obj("metro 50", 240, 330, 70, 2, 1, outtypes=["bang"])
    b.link(thisdev, 0, startm, 0)
    b.link(startm, 0, metro, 0)
    b.link(metro, 0, js, 0)
    b.link(thisdev, 0, js, 1)

    # automatable param dials -> prepend -> js inlet 0
    x = 40
    for (name, lo, hi, init) in IMPACT_PARAMS:
        d = b.dial(name, x, 40, lo, hi, init)
        pp = b.obj("prepend " + name, x, 300, 90, 1, 1, outtypes=[""])
        b.link(d, 0, pp, 0); b.link(pp, 0, js, 0)
        x += 70

    # gen impact engine (embedded, mono): deterministic, seeded pattern
    gen = b.obj("gen~ @oversample 2", 40, 460, 170, 1, 1, outtypes=["signal"],
                extra={"patcher": gen_patcher("impact-osc.genexpr", ins=1, outs=1)})
    b.link(phasor, 0, gen, 0)        # in1 = bar phasor
    b.link(js, 0, gen, 0)            # param messages into inlet 0
    lim = b.obj("clip~ -1. 1.", 40, 500, 80, 3, 1)
    b.link(gen, 0, lim, 0)
    b.link(lim, 0, PLUGOUT, 0)
    b.link(lim, 0, PLUGOUT, 1)

    b.save(out_path)
    shutil.copyfile(SRC_DIR / js_name, out_path.parent / js_name)
    return out_path


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "PF Continuum.amxd"
    print("wrote", build_field_synth(out))
