"""Session logging for self-training / process engineering corpus.

Captures three streams in a single session directory, all timestamped:
  1. Chat — human/agent exchanges (the dialogue that drove decisions)
  2. State — audio dev snapshots (tracks/devices/params/clips/master)
  3. Action — what RPCs were fired, args, results

Plus optional .als file checkpoints (copy of the saved set) so a later
training pipeline can replay the audio outcome alongside the chat that
produced it.

Layout:
    sessions/
      2026-05-02T14-32-08_practical-jackson/
        log.jsonl                 # append-only event stream
        snapshots/
          20260502T143805_intro.json
          20260502T144122_post-drop.json
        als/
          20260502T143805_intro.als    (optional, if user copies)

Usage:
    from thelmic.session_log import SessionLog
    log = SessionLog.start(name="jungle-take-3")
    log.chat("user", "make me a 165bpm jungle in G minor")
    log.chat("agent", "starting with amen breakbeat...")
    log.action("create_clip", {"track": 7, "slot": 0, "length": 64.0})
    log.snapshot(ch, label="after-drums")
    log.feedback(persona="audio_engineer",
                  likes=["sub sits well under kick"],
                  dislikes=["snare poking 5kHz on slot 4"])
    log.close()
"""
from __future__ import annotations
import json
import os
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SESSIONS_ROOT = Path(__file__).resolve().parent.parent / "sessions"


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _utc_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def _slug(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in s).strip("-")[:80]


@dataclass
class SessionLog:
    """Append-only timestamped event log for a single session.

    Events go to sessions/<id>/log.jsonl as one JSON dict per line.
    State snapshots go to sessions/<id>/snapshots/.
    """
    session_id: str
    root: Path
    started_at: str = field(default_factory=_utc_iso)

    @classmethod
    def start(cls, name: str = "", root: Path | None = None) -> "SessionLog":
        sid = f"{_utc_compact()}_{_slug(name) or 'session'}"
        base = (root or SESSIONS_ROOT) / sid
        (base / "snapshots").mkdir(parents=True, exist_ok=True)
        (base / "als").mkdir(parents=True, exist_ok=True)
        log = cls(session_id=sid, root=base)
        log._write({
            "ts": log.started_at, "kind": "session_start",
            "session_id": sid, "name": name,
        })
        return log

    @classmethod
    def resume(cls, session_id: str, root: Path | None = None) -> "SessionLog":
        base = (root or SESSIONS_ROOT) / session_id
        if not base.exists():
            raise FileNotFoundError(f"no session at {base}")
        return cls(session_id=session_id, root=base)

    # ------------------------------------------------------------------
    # Event writers
    # ------------------------------------------------------------------

    def _write(self, payload: dict) -> None:
        with (self.root / "log.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def chat(self, role: str, text: str, **meta: Any) -> None:
        """Record a chat turn. role typically 'user' | 'agent' | 'producer' |
        'audio_engineer'. meta can carry tool calls, citations, etc."""
        self._write({
            "ts": _utc_iso(), "kind": "chat", "role": role,
            "text": text, "meta": meta or None,
        })

    def action(self, name: str, args: dict | None = None,
                result: Any = None, **meta: Any) -> None:
        """Record an RPC call or scripted move."""
        self._write({
            "ts": _utc_iso(), "kind": "action", "name": name,
            "args": args, "result": result, "meta": meta or None,
        })

    def feedback(self, persona: str, likes: list[str] | None = None,
                  dislikes: list[str] | None = None, **meta: Any) -> None:
        """Record a persona's A/B feedback over the latest take."""
        self._write({
            "ts": _utc_iso(), "kind": "feedback", "persona": persona,
            "likes": likes or [], "dislikes": dislikes or [], "meta": meta or None,
        })

    def note(self, text: str, **meta: Any) -> None:
        """Free-form annotation (decisions, blockers, observations)."""
        self._write({
            "ts": _utc_iso(), "kind": "note", "text": text,
            "meta": meta or None,
        })

    # ------------------------------------------------------------------
    # State snapshots — full session walk
    # ------------------------------------------------------------------

    def snapshot(self, ch, label: str = "") -> Path:
        """Walk the live session and dump a state snapshot to JSON.

        Captures: tempo, track count, per-track (name, vol, pan, mute, solo,
        is_midi, devices [class, params with min/max/value], clip slots
        [name, length, note count]), master devices.

        Returns the snapshot file path.
        """
        ts = _utc_compact()
        slug = _slug(label) or "snap"
        path = self.root / "snapshots" / f"{ts}_{slug}.json"
        snap = self._walk_session(ch)
        snap["captured_at"] = _utc_iso()
        snap["label"] = label
        with path.open("w", encoding="utf-8") as f:
            json.dump(snap, f, indent=2, ensure_ascii=False)
        self._write({
            "ts": _utc_iso(), "kind": "snapshot",
            "label": label, "path": str(path.relative_to(self.root)),
            "track_count": snap.get("track_count"),
        })
        return path

    def _walk_session(self, ch) -> dict:
        out: dict = {"tracks": []}
        try:
            sess = ch.get_session_info().result(timeout=5)
            out["tempo"] = sess.get("tempo")
            out["track_count"] = sess.get("track_count")
        except Exception as e:
            out["session_error"] = str(e)
            return out
        for ti in range(out.get("track_count", 0)):
            try:
                info = ch.get_track_info(ti).result(timeout=5)
            except Exception as e:
                out["tracks"].append({"index": ti, "error": str(e)})
                continue
            tdata = {
                "index": ti,
                "name": info.get("name"),
                "is_midi": info.get("is_midi_track"),
                "volume": info.get("volume"),
                "pan": info.get("panning"),
                "mute": info.get("mute"),
                "solo": info.get("solo"),
                "devices": [],
                "clips": [],
            }
            for di, d in enumerate(info.get("devices", [])):
                ddata = {
                    "index": di,
                    "class_name": d.get("class_name"),
                    "name": d.get("name"),
                    "params": [],
                }
                try:
                    dinfo = ch.get_device_info(ti, di).result(timeout=5)
                    for p in dinfo.get("parameters", []):
                        ddata["params"].append({
                            "index": p.get("index"),
                            "name": p.get("name"),
                            "value": p.get("value"),
                            "min": p.get("min"),
                            "max": p.get("max"),
                        })
                except Exception as e:
                    ddata["error"] = str(e)
                tdata["devices"].append(ddata)
            for slot in range(17):
                try:
                    notes = ch.get_clip_notes(ti, slot).result(timeout=2).get("notes", [])
                    if notes:
                        tdata["clips"].append({
                            "slot": slot,
                            "note_count": len(notes),
                        })
                except Exception:
                    pass
            out["tracks"].append(tdata)
        try:
            master = []
            for di in range(8):
                try:
                    info = ch.get_master_device_info(di).result(timeout=3)
                    master.append({
                        "index": di,
                        "class_name": info.get("class_name"),
                        "params": [{"name": p["name"], "value": p["value"]}
                                    for p in info.get("parameters", [])],
                    })
                except Exception:
                    break
            out["master_devices"] = master
        except Exception as e:
            out["master_error"] = str(e)
        return out

    # ------------------------------------------------------------------
    # .als checkpointing — copies the user's set for replay
    # ------------------------------------------------------------------

    def checkpoint_als(self, als_path: str | Path, label: str = "") -> Path | None:
        """Copy the .als file (after the user has saved it in Live) so the
        log entry is paired with the audio state. Returns destination path.
        Live's API can't trigger save — user does File>Save first."""
        src = Path(als_path)
        if not src.exists():
            self.note(f"als checkpoint failed — file missing: {als_path}",
                      label=label, kind="error")
            return None
        ts = _utc_compact()
        slug = _slug(label) or "als"
        dst = self.root / "als" / f"{ts}_{slug}.als"
        shutil.copy2(src, dst)
        self._write({
            "ts": _utc_iso(), "kind": "als_checkpoint",
            "label": label, "src": str(src),
            "dst": str(dst.relative_to(self.root)),
            "size": dst.stat().st_size,
            "src_mtime": src.stat().st_mtime,
        })
        return dst

    # ------------------------------------------------------------------
    # Closing
    # ------------------------------------------------------------------

    def close(self, summary: str = "") -> None:
        self._write({
            "ts": _utc_iso(), "kind": "session_end",
            "summary": summary,
        })

    def path(self) -> Path:
        return self.root


# ----------------------------------------------------------------------
# Helper: bind a SessionLog to a LiveChannel so every RPC auto-logs
# ----------------------------------------------------------------------

class LoggingChannel:
    """Thin proxy around LiveChannel that auto-logs every method call to
    a SessionLog. Use only when you want full RPC trace — adds I/O overhead.

    Usage:
        ch = LoggingChannel(LiveChannel(), log)
        ch.start()
        ch.fire_scene(0).result()      # logged
    """
    _SKIP = {"start", "stop", "status", "_enqueue"}

    def __init__(self, channel, log: SessionLog):
        self._ch = channel
        self._log = log

    def __getattr__(self, name: str):
        attr = getattr(self._ch, name)
        if not callable(attr) or name in self._SKIP or name.startswith("_"):
            return attr

        def wrapped(*args, **kwargs):
            self._log.action(name, args={"args": args, "kwargs": kwargs})
            return attr(*args, **kwargs)
        return wrapped


__all__ = ["SessionLog", "LoggingChannel", "SESSIONS_ROOT"]
