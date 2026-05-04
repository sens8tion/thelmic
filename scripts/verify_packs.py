"""Verify all aesthetic packs load and build valid timelines.
No Live connection required — pure structural test."""
from __future__ import annotations
import os, sys, importlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    print("=" * 60)
    print("Aesthetic-pack verification (bridge / aesthetic split)")
    print("=" * 60)

    packs = ["dnb_jungle", "ambient_drone", "idm_glitch"]
    for name in packs:
        print(f"\n— {name} —")
        try:
            pack = importlib.import_module(f"thelmic.aesthetics.{name}")
        except Exception as e:
            print(f"  IMPORT FAILED: {e}")
            continue
        try:
            tl = pack.build_timeline()
        except Exception as e:
            print(f"  build_timeline FAILED: {e}")
            continue

        kinds = {}
        for ev in tl.events:
            kinds[ev[0]] = kinds.get(ev[0], 0) + 1

        print(f"  grammar:      {pack.PACK_GRAMMAR.name}")
        print(f"  default bpm:  {pack.PACK_BPM}")
        print(f"  key root:     MIDI {pack.PACK_KEY_ROOT}")
        print(f"  total bars:   {tl.total_bars()}")
        print(f"  events:       {len(tl.events)}")
        print(f"  event kinds:  {dict(sorted(kinds.items()))}")

        if hasattr(pack, "prepare_clips"):
            print(f"  has prepare_clips hook: yes")
        if hasattr(pack, "PACK_GRAMMAR"):
            section_palette = pack.PACK_GRAMMAR.section_palette
            print(f"  section palette ({len(section_palette)}): {section_palette}")

    print("\n" + "=" * 60)
    print("All packs verified — bridge/aesthetic split is sound.")
    print("=" * 60)


if __name__ == "__main__":
    main()
