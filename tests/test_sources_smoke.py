"""Smoke test — imports + adapter contract. Does NOT hit the network."""

from __future__ import annotations

import inspect

from thelmic import sources
from thelmic.sources import _base


def test_imports_and_contract():
    for name in ["freesound", "bbc", "internet_archive", "nasa", "fma", "epidemic"]:
        mod = getattr(sources, name)
        assert hasattr(mod, "available")
        assert hasattr(mod, "search")
        assert hasattr(mod, "fetch")
        sig = inspect.signature(mod.search)
        assert "query" in sig.parameters
        assert "limit" in sig.parameters


def test_list_sources_returns_subset():
    enabled = sources.list_sources()
    assert "fma" not in enabled
    assert "epidemic" not in enabled
    assert "bbc" in enabled
    assert "internet_archive" in enabled
    assert "nasa" in enabled


def test_sound_dataclass_frozen():
    s = _base.Sound(source="x", id="1", title="t", url="u")
    try:
        s.title = "nope"  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("Sound should be frozen")


def test_find_disabled_sources_returns_empty_when_no_keys(monkeypatch):
    monkeypatch.delenv("FREESOUND_API_KEY", raising=False)
    # Restrict to disabled sources only — should return nothing, no exceptions.
    out = sources.find("anything", limit=3, sources=["freesound", "fma", "epidemic"])
    assert out == []
