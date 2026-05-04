"""Pack-agnostic meta-format: a fixed N-channel × M-scene grid that any
aesthetic pack realizes with its own role/section assignments."""
from .layout import MetaLayout, ChannelSpec, SceneSpec, META_8x4, ChannelKind

__all__ = ["MetaLayout", "ChannelSpec", "SceneSpec", "META_8x4", "ChannelKind"]
