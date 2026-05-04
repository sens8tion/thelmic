"""Pack-agnostic meta-format: a fixed N-channel × M-scene grid that any
aesthetic pack realizes with its own role/section assignments.

Includes audio meta (FreqRegion + LevelTarget) packs use to declare
per-role spectral territory and gain-staging discipline.
"""
from .layout import MetaLayout, ChannelSpec, SceneSpec, META_8x4, ChannelKind
from .audio import FreqRegion, LevelTarget, ChannelAudio, StageCheckpoint

__all__ = [
    "MetaLayout", "ChannelSpec", "SceneSpec", "META_8x4", "ChannelKind",
    "FreqRegion", "LevelTarget", "ChannelAudio", "StageCheckpoint",
]
