"""Session — named musical-intent record, idempotently buildable into Live."""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from .intent import Intent
from .bindings import Bindings, SampleBinding


REPO_ROOT = Path(__file__).resolve().parents[2]
SESSIONS_DIR = REPO_ROOT / "sessions"


@dataclass
class Session:
    name: str
    intent: Intent = field(default_factory=Intent)
    bindings: Bindings = field(default_factory=Bindings)
    notes: str = ""

    @property
    def dir(self) -> Path:
        return SESSIONS_DIR / self.name

    # ---- IO --------------------------------------------------------------

    @classmethod
    def open(cls, name: str, pack: str = "dnb_jungle") -> "Session":
        """Load if exists, else create fresh."""
        d = SESSIONS_DIR / name
        if (d / "intent.yaml").exists():
            return cls.load(name)
        sess = cls(name=name, intent=Intent(pack=pack))
        d.mkdir(parents=True, exist_ok=True)
        sess.save()
        return sess

    @classmethod
    def load(cls, name: str) -> "Session":
        d = SESSIONS_DIR / name
        if not d.exists():
            raise FileNotFoundError(f"session not found: {d}")
        intent = Intent.from_dict(_read_yaml(d / "intent.yaml"))
        bindings = Bindings.from_dict(_read_yaml(d / "bindings.yaml"))
        notes_path = d / "notes.md"
        notes = notes_path.read_text(encoding="utf-8") if notes_path.exists() else ""
        return cls(name=name, intent=intent, bindings=bindings, notes=notes)

    def save(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        _write_yaml(self.dir / "intent.yaml", self.intent.to_dict())
        _write_yaml(self.dir / "bindings.yaml", self.bindings.to_dict())
        if self.notes:
            (self.dir / "notes.md").write_text(self.notes, encoding="utf-8")
        self._log(f"save")

    # ---- build -----------------------------------------------------------

    def audit(self, ch) -> list:
        """Read current Live state vs declared CHANNEL_AUDIO; return drift."""
        from importlib import import_module
        from thelmic.meta import audit_session
        from thelmic.bridge.helpers.discovery import find_track
        pack_pkg = import_module(f"thelmic.aesthetics.{self.intent.pack}")
        channel_audio = getattr(pack_pkg, "CHANNEL_AUDIO", {}) or {}
        layout = getattr(pack_pkg, "LAYOUT", None)
        roles = {}
        if layout is not None:
            for spec in layout.channels:
                ti = find_track(ch, spec.role.upper())
                if ti is not None:
                    roles[spec.role] = ti
        return audit_session(ch, roles, channel_audio)

    def build(self, ch) -> dict:
        """Idempotently reconstruct the session in Live.

        Reads current Live state and only fills gaps. Safe to re-run.
        Order: tempo → pack setup phase → sample bindings → preset bindings.
        """
        from .builder import build_session
        result = build_session(ch, self)
        self._log(f"build {result}")
        return result

    # ---- helpers ---------------------------------------------------------

    def _log(self, msg: str) -> None:
        log = self.dir / ".build_log"
        ts = datetime.now().isoformat(timespec="seconds")
        with log.open("a", encoding="utf-8") as f:
            f.write(f"{ts}  {msg}\n")


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
