"""Mediated session — the canonical entry point for any human-in-the-loop
session in this stack.

The agent (LLM) MEDIATES every session: it stands between the humans
(producer, audio engineer, future personae) and Ableton Live. The
SessionLog is the always-on substrate beneath that mediation — every
chat turn, every RPC, every persona's A/B, every state snapshot is
captured automatically so the corpus self-trains the next generation.

This module is the wrapper that makes that posture default, not opt-in.

Usage at the top of every session script / agent loop:

    from thelmic.mediated_session import open_session
    sess = open_session(name="jungle-iteration-3",
                         expected_tracks=["TECTONIC", "HARDKIT", ...])
    # sess.ch    — LoggingChannel (every RPC auto-logged)
    # sess.log   — SessionLog (chat / feedback / snapshot / .als checkpoint)
    sess.log.chat("user", "...")
    sess.snapshot("after-drums")          # convenience: log.snapshot(ch, label)
    sess.feedback("producer", likes=[...], dislikes=[...])
    sess.close(summary="...")

The mediator pattern (the agent's job in every session):

    1. open_session()         — auto-starts log, opens channel, health-checks
    2. log every chat turn     — sess.log.chat("user"|"persona", text)
       — agent transcribes humans verbatim, logs its own replies too
    3. snapshot at decisions   — sess.snapshot("post-build-A") before/after
                                  any move that changes the audio outcome
    4. capture A/B feedback    — sess.feedback(persona, likes, dislikes)
                                  AS the persona speaks, not retroactively
    5. checkpoint .als         — when the human File>Saves, sess.als(path, label)
    6. close on session end    — sess.close(summary=...) — non-skippable

Anything that happens off-log is invisible to the training pipeline.
Treat skipping the log the way you'd treat skipping git commits:
recoverable in theory, irresponsible in practice.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .live_channel import LiveChannel
from .session_log import SessionLog, LoggingChannel


@dataclass
class MediatedSession:
    log: SessionLog
    ch: LoggingChannel              # logged proxy
    raw_ch: LiveChannel             # underlying (rarely needed)

    # ---- convenience pass-throughs (so callers never reach for log directly) ----

    def chat(self, role: str, text: str, **meta) -> None:
        self.log.chat(role, text, **meta)

    def feedback(self, persona: str, likes: list[str] | None = None,
                  dislikes: list[str] | None = None, **meta) -> None:
        self.log.feedback(persona, likes=likes, dislikes=dislikes, **meta)

    def note(self, text: str, **meta) -> None:
        self.log.note(text, **meta)

    def snapshot(self, label: str = "") -> Path:
        return self.log.snapshot(self.raw_ch, label=label)

    def als(self, path: str | Path, label: str = "") -> Path | None:
        return self.log.checkpoint_als(path, label=label)

    def close(self, summary: str = "") -> None:
        try:
            self.log.close(summary=summary)
        finally:
            self.raw_ch.stop()

    def __enter__(self) -> "MediatedSession":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc is not None:
            self.note(f"session ended with exception: {exc!r}",
                      exc_type=exc_type.__name__ if exc_type else None)
            self.close(summary=f"errored: {exc!r}")
        else:
            self.close(summary="ok")


def open_session(name: str = "session",
                  expected_tracks: Iterable[str] | None = None,
                  initial_snapshot: bool = True,
                  ) -> MediatedSession:
    """Canonical entry point. Starts the log, opens a logged Live channel,
    runs a health check, and (default) takes an initial state snapshot
    so every session has a "before" reference for the diff.

    Always use this — never construct LiveChannel + SessionLog directly
    unless you're writing a low-level utility that must not log.
    """
    log = SessionLog.start(name=name)
    raw = LiveChannel(lower_priority=False)
    raw.start()
    logged = LoggingChannel(raw, log)
    sess = MediatedSession(log=log, ch=logged, raw_ch=raw)

    # Health check — log result so failures show up in the corpus
    try:
        from .agent_helpers import health_check
        ok, detail = health_check(raw, expected_track_names=list(expected_tracks)
                                    if expected_tracks else None)
        log.note(f"health_check: {'OK' if ok else 'FAILED'}",
                  detail=detail if isinstance(detail, dict) else str(detail))
        if not ok:
            log.note("session opening with failed health — agent must surface "
                     "this to the human before composing.")
    except Exception as e:
        log.note(f"health_check error: {e}", kind="error")

    if initial_snapshot:
        try:
            sess.snapshot(label="session-open")
        except Exception as e:
            log.note(f"initial snapshot failed: {e}", kind="error")

    return sess


__all__ = ["MediatedSession", "open_session"]
