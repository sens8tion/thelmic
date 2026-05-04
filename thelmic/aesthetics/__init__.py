"""Aesthetic packs.

Each subpackage encodes a specific musical form / genre via:
  pack.yaml      — manifest (key, BPM, grammar, expected roles, vocabulary)
  patterns.py    — generators (drum patterns, melodic phrases, etc.)
  transforms.py  — anticipation transforms, breathing, decay tails
  arrangement.py — Section list using bridge.grammars.{ChosenGrammar}
  compose.py     — writes content to session-view clips
  constants.py   — pack-scoped constants (drum-pitch map, etc.)

Active pack determined by THELMIC_PACK env var or explicit import.
The bridge knows nothing about which pack is active.
"""
from importlib import import_module
import os


def get_active_pack():
    """Return the active aesthetic pack module by env var or default."""
    pack_name = os.environ.get("THELMIC_PACK", "dnb_jungle")
    return import_module(f"thelmic.aesthetics.{pack_name}")


__all__ = ["get_active_pack"]
