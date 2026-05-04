"""8×4 (or any N×M) meta-layout primitives.

A pack supplies a MetaLayout describing its channels and scenes; the
session builder uses it to bootstrap tracks + scenes deterministically.
Channel specs are role-typed so the builder picks the right Live device
(MIDI track + instrument vs audio track) without the pack having to
duplicate that logic.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ChannelKind(str, Enum):
    DRUM_RACK   = "drum_rack"     # MIDI track with Drum Rack
    SYNTH       = "synth"         # MIDI track with synth (Operator etc)
    SAMPLER     = "sampler"       # MIDI track with Simpler
    AUDIO       = "audio"         # audio track (clip in slot 0)


@dataclass
class ChannelSpec:
    role: str                              # e.g. "drums", "bass", "vox"
    kind: ChannelKind
    color: int | None = None               # Live track color hint (24-bit RGB or None)
    default_device: str | None = None      # browser item-name for kind!=DRUM_RACK
    default_browser_path: str | None = None  # e.g. "instruments"


@dataclass
class SceneSpec:
    name: str                              # e.g. "BUILD", "DROP"
    archetype: str                         # one of: "build", "drop", "break", "drop2"
    description: str = ""


@dataclass
class MetaLayout:
    channels: list[ChannelSpec]
    scenes: list[SceneSpec]

    @property
    def channel_count(self) -> int:
        return len(self.channels)

    @property
    def scene_count(self) -> int:
        return len(self.scenes)

    def channel_by_role(self, role: str) -> ChannelSpec | None:
        for c in self.channels:
            if c.role == role:
                return c
        return None

    def channel_index(self, role: str) -> int | None:
        for i, c in enumerate(self.channels):
            if c.role == role:
                return i
        return None


# ---- canonical 8×4 layouts ---------------------------------------------

META_8x4 = MetaLayout(
    channels=[
        ChannelSpec(role="drums", kind=ChannelKind.DRUM_RACK,
                    default_device="Drum Rack", default_browser_path="instruments"),
        ChannelSpec(role="break", kind=ChannelKind.AUDIO),
        ChannelSpec(role="sub",   kind=ChannelKind.AUDIO),
        ChannelSpec(role="bass",  kind=ChannelKind.SYNTH,
                    default_device="Operator", default_browser_path="instruments"),
        ChannelSpec(role="stab",  kind=ChannelKind.SYNTH,
                    default_device="Operator", default_browser_path="instruments"),
        ChannelSpec(role="pad",   kind=ChannelKind.AUDIO),
        ChannelSpec(role="vox",   kind=ChannelKind.SAMPLER,
                    default_device="Simpler", default_browser_path="instruments"),
        ChannelSpec(role="fx",    kind=ChannelKind.AUDIO),
    ],
    scenes=[
        SceneSpec(name="BUILD",  archetype="build",
                  description="tension rising, no drop drums yet"),
        SceneSpec(name="DROP",   archetype="drop",
                  description="full slam — drums + sub + bass + vox"),
        SceneSpec(name="BREAK",  archetype="break",
                  description="rhythmic flip, drums thinned, vox foreground"),
        SceneSpec(name="DROP2",  archetype="drop2",
                  description="Rotterdam/gabber variant — distorted, faster pulse"),
    ],
)
