from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class SourceError(RuntimeError):
    """Adapter-level failure (network, auth, parse)."""


@dataclass(frozen=True)
class Sound:
    source: str
    id: str
    title: str
    url: str  # canonical / web URL
    download_url: str | None = None  # direct media URL, if known
    duration: float | None = None
    license: str | None = None
    tags: tuple[str, ...] = ()
    extra: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        d = f"{self.duration:.1f}s" if self.duration else "?"
        return f"<{self.source}:{self.id} {self.title!r} ({d}, {self.license})>"
