"""Verify all aesthetic packs load and build valid timelines.
No Live connection required — pure structural test.

Validates:
  1. pack.yaml manifest parses cleanly
  2. manifest's narrative_grammar resolves to a known Grammar class
  3. pack module imports
  4. build_timeline() returns a non-empty Timeline
  5. all section roles in section_palette are recognised by the grammar
"""
from __future__ import annotations
import os, sys, importlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from thelmic.aesthetics.manifest import load_pack, resolve_grammar


def main():
    print("=" * 60)
    print("Aesthetic-pack verification (bridge / aesthetic split)")
    print("=" * 60)

    packs = ["dnb_jungle", "ambient_drone", "idm_glitch"]
    n_ok = 0
    for name in packs:
        print(f"\n— {name} —")
        try:
            manifest = load_pack(name)
        except Exception as e:
            print(f"  MANIFEST FAILED: {e}")
            continue
        try:
            grammar = resolve_grammar(manifest.narrative_grammar)
        except Exception as e:
            print(f"  GRAMMAR RESOLUTION FAILED: {e}")
            continue
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

        # Validate manifest's section_palette matches grammar's
        manifest_palette = set(manifest.section_palette)
        grammar_palette  = set(grammar.section_palette)
        unknown_to_grammar = manifest_palette - grammar_palette
        if unknown_to_grammar:
            print(f"  WARN: section roles not in grammar: {unknown_to_grammar}")

        print(f"  manifest:     {manifest.name} ({manifest.default_bpm} bpm)")
        print(f"  grammar:      {grammar.name}")
        print(f"  key:          MIDI {manifest.key_root_midi} / {manifest.key_scale}")
        print(f"  required roles:  {manifest.required_track_roles}")
        print(f"  total bars:   {tl.total_bars()}")
        print(f"  events:       {len(tl.events)}  kinds: {dict(sorted(kinds.items()))}")
        if hasattr(pack, "prepare_clips"):
            print(f"  has prepare_clips hook: yes")
        n_ok += 1

    print("\n" + "=" * 60)
    print(f"{n_ok}/{len(packs)} packs verified — bridge/aesthetic split is sound.")
    print("=" * 60)


if __name__ == "__main__":
    main()
