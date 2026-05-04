"""Named-session abstraction.

Ableton holds reference truth (the .als is what's actually built).
Thelmic sessions hold *intent and bindings* — the recipe that, replayed,
reconstructs an equivalent project from a fresh empty Live.

Public API:
    Session.open(name, pack=...)   create or load
    sess.save()                     persist intent/bindings/arrangement to disk
    sess.build(ch)                  idempotent build into Live from a fresh state
"""
from .session import Session
from .intent import Intent
from .bindings import Bindings

__all__ = ["Session", "Intent", "Bindings"]
