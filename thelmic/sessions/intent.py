"""Intent layer — the musical and structural choices for a named session.

Pack defaults provide the base; intent overrides what's specific to *this*
session (this BPM, this key, this arc, this concept). Storing intent rather
than printed output lets us rebuild from scratch.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Intent:
    pack: str = "dnb_jungle"
    concept: str = ""             # freeform tagline, e.g. "ragga → Rotterdam"
    bpm: float | None = None       # None = inherit from pack default
    key_root: str | None = None    # e.g. "Em", None = inherit
    signature: tuple[int, int] = (4, 4)
    arc: list[str] = field(default_factory=list)   # section sequence (overrides pack default)
    mood: str = ""                 # freeform, e.g. "menacing, sub-heavy"
    overrides: dict[str, Any] = field(default_factory=dict)
        # arbitrary per-pack overrides, e.g. {"mix.gain_levels.sub": 0.6}

    @classmethod
    def from_dict(cls, d: dict) -> "Intent":
        sig = d.get("signature", [4, 4])
        return cls(
            pack=d.get("pack", "dnb_jungle"),
            concept=d.get("concept", ""),
            bpm=d.get("bpm"),
            key_root=d.get("key_root"),
            signature=tuple(sig),
            arc=list(d.get("arc", [])),
            mood=d.get("mood", ""),
            overrides=dict(d.get("overrides", {})),
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["signature"] = list(self.signature)
        return d
