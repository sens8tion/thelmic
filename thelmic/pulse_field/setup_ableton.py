"""Set up a playable Pulse Field session in a running Ableton Live, via LOM.

Uses the thelmic Live bridge (ThelmicLive Remote Script over TCP 9878) to:
  1. set tempo,
  2. append a MIDI track named for the Pulse Field instrument,
  3. load the 3RDEYEZ drum kit so onsets have sounds,
  4. write a rendered field-crystallisation MIDI clip into slot 0.

This lets you HEAR field-native crystallisation immediately — the clip is the
output of the real onset engine (rendered by tools/render_demo_clip.js) — with
no Max device required. When the Stage 0+1 .amxd instrument is later saved from
Max and dropped on this track, it drives the same drum kit live over OSC.

    # render the notes, then set up the session:
    node thelmic/devices/tools/render_demo_clip.js 16 174 > notes.json
    python -m thelmic.pulse_field.setup_ableton notes.json

Requires the bridge: ThelmicLive selected as a Control Surface in Live, and
LIVE_CHANNEL_ENABLED=1 in the environment. This is a SEPARATE track from the
planner-first engine — it appends, it does not touch existing tracks.
"""

from __future__ import annotations

import json
import sys

from thelmic.live_channel import LiveChannel

# Force UTF-8 so non-ASCII status output doesn't crash on a cp1252 console.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

# ASCII-only names (Live accepts unicode, but keep these portable for logs).
TRACK_NAME = "CRYST8 :: pulse field"
CLIP_NAME = "FIELD CRYST8 > build-drop"
# A real Drum Rack kit so onset notes (36-50) map to drum pads. NOTE: the
# browser's 3RDEYEZ.adg is an Instrument Rack, not a Drum Rack, so it won't map
# onsets to pads — pick any *Drum Rack* .adg here.
DRUM_KIT = ("drums", "606 Core Kit.adg")   # (browser path, item name)


def _r(future, timeout=12):
    """Resolve a bridge future, returning its result or an error marker."""
    try:
        return future.result(timeout=timeout)
    except Exception as exc:  # noqa: BLE001 - report, don't crash setup
        return {"_error": f"{exc.__class__.__name__}: {exc}"}


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: setup_ableton.py <notes.json>")
        return 2
    with open(sys.argv[1], "r", encoding="utf-8") as fh:
        clip = json.load(fh)

    bpm = float(clip.get("bpm", 174))
    length_beats = float(clip.get("length_beats", 64))
    notes = clip["notes"]

    ch = LiveChannel()
    ch.start()
    print("ping:", _r(ch.ping(), 4))

    before = _r(ch.get_session_info())
    track_count = int(before.get("track_count", 1)) if isinstance(before, dict) else 1
    print(f"tempo -> {bpm}:", _r(ch.set_tempo(bpm)))

    # reuse an existing Pulse Field track if present, else append a new one
    new_idx = None
    for i in range(track_count):
        info = _r(ch.get_track_info(i), 5)
        name = info.get("name", "") if isinstance(info, dict) else ""
        if name.startswith("CRYST8"):
            new_idx = i
            print(f"reusing existing Pulse Field track at index {i}")
            break
    if new_idx is None:
        created = _r(ch.create_midi_track(-1))
        new_idx = track_count
        if isinstance(created, dict):
            for key in ("index", "track_index"):
                if isinstance(created.get(key), int):
                    new_idx = created[key]
                    break
        print(f"created MIDI track at index {new_idx}: {created}")

    print("name:", _r(ch.set_track_name(new_idx, TRACK_NAME)))

    # load the 3RDEYEZ drum kit (browser path, item name)
    kit = _r(ch.load_item_at_path(new_idx, DRUM_KIT[0], DRUM_KIT[1]), 20)
    print(f"load kit {DRUM_KIT[1]}:", kit)

    # write the crystallisation clip into slot 0
    _r(ch.clear_clip(new_idx, 0), 5)
    print("create clip:", _r(ch.create_clip(new_idx, 0, length_beats)))
    print(f"add {len(notes)} notes:", _r(ch.add_notes_to_clip(new_idx, 0, notes), 20))
    print("name clip:", _r(ch.set_clip_name(new_idx, 0, CLIP_NAME)))

    # nice-to-haves; ignore if the bridge rejects the args
    _r(ch.set_track_color(new_idx, 0x8A2BE2), 4)
    _r(ch.set_clip_color(new_idx, 0, 0xFF9E0C), 4)

    print("\nDONE. Fire the clip on track", new_idx,
          f"('{TRACK_NAME}') to hear the field crystallise.")
    print("Drop the Pulse Field .amxd before the drum rack to drive it live over OSC.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
