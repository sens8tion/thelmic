"""JUNGLE GRID - lay the session out as 8x8 section boards for a grid controller.

The user plays the session from an 8x8 grid that shifts by a page of 8 tracks left and right and by an
octave of 8 scenes up and down. Each window is one whole section: section N's lanes on page N, its
scenes in octave N, and every page uses the same column roles.

  column   1 spine        2 main break  3 16ths      4 sub         5-6 extras               7-8
  page 1   SPINE-TINGLER  AMEN-DMENT    THROW-UP     F-HOLE        STAB-VEST, BELL-END      RAW-DEAL, EAR-WIG
  page 2   SPINAL-TAP     COLD-CUTS     TOPSOIL      SUB-POENA     RASP-UTIN, LIP-SERVICE   RAW-DEAL, SPARE-RIB
  page 3   SPINELESS      CHOPPER       SWEAT-SHOP   SUB-LIMINAL   BOOT-LEG, RASP-BERRY     HALO-PERIDOL, RAW-DEAL

Scenes: section 1 in 1-8, section 2 in 9-16, section 3 in 17-24, pre-drop row on top. Sections move by
INSERTING empty scenes above them, so whole rows slide down with every clip in them; nothing is copied or
rewritten. Idempotent: a board already in place is left alone.

    python scripts/jungle_grid.py
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(SCRIPTS_DIR))

PAGE = OCTAVE = 8
PAGES = [
    ["SPINE-TINGLER", "AMEN-DMENT", "THROW-UP", "F-HOLE", "STAB-VEST", "BELL-END", "RAW-DEAL", "EAR-WIG"],
    ["SPINAL-TAP", "COLD-CUTS", "TOPSOIL", "SUB-POENA", "RASP-UTIN", "LIP-SERVICE", "RAW-DEAL", "SPARE-RIB"],
    ["SPINELESS", "CHOPPER", "SWEAT-SHOP", "SUB-LIMINAL", "BOOT-LEG", "RASP-BERRY", "HALO-PERIDOL", "RAW-DEAL"],
]
# each section's top row, found by the clip its spine holds there (the clip is named after the row)
SECTION_TOPS = [("SPINE-TINGLER", "waiting room"), ("SPINAL-TAP", "the dock"), ("SPINELESS", "small print")]


def track_names(ch):
    n = ch.get_session_info().result(timeout=5)["track_count"]
    return [ch.get_track_info(i).result(timeout=5)["name"] for i in range(n)]


def order_tracks(ch):
    """Live's API has no track move (Song.move_track doesn't exist), so this only makes sure SPARE-RIB is
    there and reports the order still to be dragged into place by hand."""
    names = track_names(ch)
    if "SPARE-RIB" not in names:
        ch.create_midi_track(-1).result(timeout=10)
        ch.set_track_name(len(names), "SPARE-RIB").result(timeout=3)
        print("  created SPARE-RIB (keeps page 2 eight lanes wide)")
        names = track_names(ch)
    flat = [nm for page in PAGES for nm in page]
    if names[:len(flat)] == flat:
        print("  tracks already in page order")
        return
    for k, page in enumerate(PAGES):
        print(f"  page {k + 1} should be: " + ", ".join(f"{k * PAGE + i + 1} {nm}" for i, nm in enumerate(page)))
    print("  current: " + ", ".join(f"{i + 1} {nm}" for i, nm in enumerate(names)))


def section_row(ch, track, clip_name):
    t = track_names(ch).index(track)
    scenes = ch.get_scene_count().result(timeout=5)["count"]
    for s in range(scenes):
        try:
            if ch.get_clip_props(t, s).result(timeout=5).get("name") == clip_name:
                return s
        except Exception:
            pass
    raise SystemExit(f"no clip named {clip_name!r} on {track}")


def place_sections(ch):
    for k, (track, clip_name) in enumerate(SECTION_TOPS):
        target = k * OCTAVE
        at = section_row(ch, track, clip_name)
        if at > target:
            raise SystemExit(f"section {k + 1} starts at row {at + 1}, below its octave (row {target + 1}): not moving it up")
        for _ in range(target - at):
            ch.create_scene(at).result(timeout=5)              # an empty row above pushes the section down
        print(f"  section {k + 1} ({clip_name}): row {at + 1} -> row {section_row(ch, track, clip_name) + 1}")


def main():
    from thelmic.live_channel import LiveChannel
    ch = LiveChannel(lower_priority=False)
    ch.start()
    try:
        print("== tracks into pages of 8")
        order_tracks(ch)
        print("== sections into octaves of 8")
        place_sections(ch)
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
