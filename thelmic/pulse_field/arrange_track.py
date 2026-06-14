"""Print a Pulse Field track as four 16-bar SECTIONS, one per scene row, across
the instruments (FIELD continuum, GR0UND/KN0CK/GL1NT impacts, W0BBL3 wobble).

Each section is a self-contained 16-bar loop of clip automation, so you can
launch/sequence them as scenes:

    row 0  BUILD 1   tension rises, pre-drop cut at bar 15.5
    row 1  DROP 1    heavy: four-on-floor + full wobble, sustained
    row 2  BUILD 2   breakdown (first 8 bars) then re-build, pre-drop cut
    row 3  DROP 2    heaviest

Run via the LOM bridge:
    cd <worktree-with-live_channel>
    LIVE_CHANNEL_ENABLED=1 python - < thelmic/pulse_field/arrange_track.py

Automation values are in each parameter's units; envelopes are written as dense
breakpoints (1/beat) to approximate smooth ramps. Anchors are in LOCAL bars
(0..16) per section.
"""

from __future__ import annotations

import time

from thelmic.live_channel import LiveChannel

TEMPO = 140.0
SECTION_BEATS = 64           # 16 bars
SECTIONS = ["BUILD 1", "DROP 1", "BUILD 2", "DROP 2"]


def R(fut, t=25):
    try:
        return fut.result(timeout=t)
    except Exception as e:  # noqa: BLE001
        return {"_err": str(e)}


def expand(anchors, step=1.0):
    """anchors [(bar,val)] in local bars -> dense [beat,val] breakpoints."""
    a = [(bar * 4.0, float(v)) for bar, v in anchors]
    pts = []
    for i in range(len(a) - 1):
        t0, v0 = a[i]; t1, v1 = a[i + 1]
        t = t0
        while t < t1 - 1e-6:
            f = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
            pts.append([round(t, 4), round(v0 + (v1 - v0) * f, 4)])
            t += step
    pts.append([round(a[-1][0], 4), round(a[-1][1], 4)])
    return pts


# per track: [sectionA, sectionB, sectionC, sectionD]; each {param:[(bar,val)]}
B1, D1, B2, D2 = 0, 1, 2, 3
ARRANGE = {
    "continuum": [
        {  # BUILD 1
            "gain": [(0, .2), (14, .5), (15.5, .12), (16, .12)],
            "pressure": [(0, .05), (15, .7), (16, .7)],
            "density": [(0, .3), (15, .6), (16, .6)],
            "discomfort": [(0, .1), (15, .5), (16, .5)],
            "urgency": [(0, .05), (15, .75), (16, .75)],
            "silence": [(0, .15), (13, .45), (15.5, .75), (16, .75)],
            "novelty": [(0, .2), (16, .4)], "tilt": [(0, -.5)], "span": [(0, .25)],
        },
        {  # DROP 1
            "gain": [(0, .52), (16, .5)], "pressure": [(0, .8), (16, .8)],
            "density": [(0, .66), (16, .64)], "discomfort": [(0, .6), (16, .58)],
            "urgency": [(0, .5), (16, .5)], "silence": [(0, 0), (16, 0)],
            "novelty": [(0, .4), (16, .42)], "tilt": [(0, -.5)], "span": [(0, .25)],
        },
        {  # BUILD 2 (breakdown then re-build)
            "gain": [(0, .3), (8, .28), (15, .46), (15.5, .12), (16, .12)],
            "pressure": [(0, .15), (8, .2), (15, .82), (16, .82)],
            "density": [(0, .38), (8, .4), (16, .66)],
            "discomfort": [(0, .2), (15, .6), (16, .6)],
            "urgency": [(0, .12), (15, .8), (16, .8)],
            "silence": [(0, .3), (8, .4), (15.5, .72), (16, .72)],
            "novelty": [(0, .4), (16, .5)], "tilt": [(0, -.5)], "span": [(0, .25)],
        },
        {  # DROP 2
            "gain": [(0, .58), (16, .58)], "pressure": [(0, .9), (16, .9)],
            "density": [(0, .72), (16, .72)], "discomfort": [(0, .74), (16, .74)],
            "urgency": [(0, .6), (16, .6)], "silence": [(0, 0), (16, 0)],
            "novelty": [(0, .55), (16, .55)], "tilt": [(0, -.5)], "span": [(0, .25)],
        },
    ],
    "GR0UND": [
        {"level": [(0, 0), (7, 0), (8, .4), (15, .85), (15.5, 0), (16, 0)], "density": [(0, 0)], "punch": [(0, .6)]},
        {"level": [(0, .95), (16, .95)], "density": [(0, 0)], "punch": [(0, .6)]},
        {"level": [(0, 0), (8, 0), (9, .5), (15, .9), (15.5, 0), (16, 0)], "density": [(0, 0)], "punch": [(0, .6)]},
        {"level": [(0, 1.0), (16, 1.0)], "density": [(0, 0)], "punch": [(0, .6)]},
    ],
    "KN0CK": [
        {"level": [(0, .2), (15, .7), (15.5, 0), (16, 0)], "density": [(0, .2), (15, .5), (16, .5)], "entropy": [(0, .1), (16, .2)]},
        {"level": [(0, .85), (16, .85)], "density": [(0, .5), (16, .5)], "entropy": [(0, .2), (16, .2)]},
        {"level": [(0, .3), (8, .25), (15, .75), (15.5, 0), (16, 0)], "density": [(0, .3), (16, .55)], "entropy": [(0, .2), (8, .3), (16, .45)]},
        {"level": [(0, .9), (16, .9)], "density": [(0, .62), (16, .62)], "entropy": [(0, .3), (16, .3)]},
    ],
    "GL1NT": [
        {"level": [(0, .1), (15, .6), (16, .6)], "density": [(0, .3), (14, .85), (16, .7)], "entropy": [(0, .2), (16, .5)]},
        {"level": [(0, .6), (16, .6)], "density": [(0, .7), (16, .68)], "entropy": [(0, .5), (16, .5)]},
        {"level": [(0, .3), (8, .3), (15, .65), (16, .6)], "density": [(0, .4), (14, .85), (16, .75)], "entropy": [(0, .3), (16, .6)]},
        {"level": [(0, .72), (16, .72)], "density": [(0, .85), (16, .85)], "entropy": [(0, .6), (16, .6)]},
    ],
    "W0BBL3": [
        {"level": [(0, 0), (7, 0), (8, .4), (15, .8), (15.5, 0), (16, 0)], "wob": [(0, .3), (15, .7), (16, .7)], "cutoff": [(0, .2), (15, .5), (16, .5)], "density": [(0, .3), (16, .5)], "tilt": [(0, .5)], "span": [(0, .25)]},
        {"level": [(0, .9), (16, .9)], "wob": [(0, .8), (16, .8)], "cutoff": [(0, .5), (16, .5)], "density": [(0, .5), (16, .5)], "tilt": [(0, .5)], "span": [(0, .25)]},
        {"level": [(0, 0), (8, 0), (9, .45), (15, .85), (15.5, 0), (16, 0)], "wob": [(0, .4), (15, .85), (16, .85)], "cutoff": [(0, .35), (16, .5)], "density": [(0, .4), (16, .55)], "tilt": [(0, .5)], "span": [(0, .25)]},
        {"level": [(0, .95), (16, .95)], "wob": [(0, .9), (16, .9)], "cutoff": [(0, .56), (16, .56)], "density": [(0, .6), (16, .6)], "tilt": [(0, .5)], "span": [(0, .25)]},
    ],
}


def main():
    ch = LiveChannel(); ch.start()
    print("ping:", R(ch.ping(), 4))
    print("tempo:", R(ch.set_tempo(TEMPO)))

    si = R(ch.get_session_info())
    n = int(si.get("track_count", 0)) if isinstance(si, dict) else 0
    idx_by_key = {}
    for i in range(n):
        ti = R(ch.get_track_info(i))
        nm = ti.get("name", "") if isinstance(ti, dict) else ""
        for key in ARRANGE:
            if key in nm:
                idx_by_key[key] = (i, nm)

    # ensure enough scenes exist
    sc = R(ch.get_scene_count()) if hasattr(ch, "get_scene_count") else {}
    have = sc.get("count", 0) if isinstance(sc, dict) else 0
    for _ in range(max(0, len(SECTIONS) - have)):
        R(ch.create_scene(-1))

    for s_i, s_name in enumerate(SECTIONS):
        try:
            R(ch.set_scene_name(s_i, s_name), 4)
        except Exception:
            pass
        for key, sections in ARRANGE.items():
            if key not in idx_by_key:
                print("MISSING", key); continue
            idx, nm = idx_by_key[key]
            R(ch.clear_clip(idx, s_i), 6)
            R(ch.create_clip(idx, s_i, SECTION_BEATS), 8)
            R(ch.set_clip_name(idx, s_i, s_name), 4)
            R(ch.set_clip_loop(idx, s_i, True), 4)
            for pname, anchors in sections[s_i].items():
                bps = expand(anchors, step=1.0)
                R(ch.set_clip_envelope(idx, s_i, idx, 0, pname, bps), 20)
        print("section", s_i, s_name, "written")

    print("set launch quantization (1 bar):", R(ch.set_launch_quantization(1)))
    print("DONE. Launch scenes 1-4 (BUILD 1 / DROP 1 / BUILD 2 / DROP 2).")


if __name__ == "__main__":
    main()
