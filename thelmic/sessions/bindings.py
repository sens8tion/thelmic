"""Role/slot → resource bindings.

A binding pins a specific resource (sample path, preset name, drum-pad note)
to a session role. Storing only references + sha256 keeps sessions light;
the User Library is the canonical sample store.
"""
from __future__ import annotations
import hashlib
from dataclasses import dataclass, field, asdict
from pathlib import Path


def sha256_of(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class SampleBinding:
    role: str               # e.g. "drums.kick", "sub", "vox_call"
    browser_path: str       # e.g. "user_library/Samples/Splice"
    item_name: str          # filename
    pad_note: int | None = None   # drum-pad note for drum roles, else None
    sha256: str | None = None     # optional content hash — drift detector

    @classmethod
    def from_dict(cls, d: dict) -> "SampleBinding":
        return cls(
            role=d["role"],
            browser_path=d["browser_path"],
            item_name=d["item_name"],
            pad_note=d.get("pad_note"),
            sha256=d.get("sha256"),
        )

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None or k == "pad_note"}


@dataclass
class PresetBinding:
    role: str               # e.g. "mid_bass", "stab"
    browser_path: str       # e.g. "instruments"
    item_name: str          # e.g. "Operator"
    preset_name: str | None = None   # specific preset within the device, optional

    @classmethod
    def from_dict(cls, d: dict) -> "PresetBinding":
        return cls(
            role=d["role"],
            browser_path=d["browser_path"],
            item_name=d["item_name"],
            preset_name=d.get("preset_name"),
        )

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class Bindings:
    samples: list[SampleBinding] = field(default_factory=list)
    presets: list[PresetBinding] = field(default_factory=list)

    def set_sample(self, role: str, browser_path: str, item_name: str,
                   pad_note: int | None = None) -> SampleBinding:
        # Replace any existing binding for this role
        self.samples = [s for s in self.samples if s.role != role]
        b = SampleBinding(role=role, browser_path=browser_path,
                          item_name=item_name, pad_note=pad_note)
        self.samples.append(b)
        return b

    def set_preset(self, role: str, browser_path: str, item_name: str,
                   preset_name: str | None = None) -> PresetBinding:
        self.presets = [p for p in self.presets if p.role != role]
        p = PresetBinding(role=role, browser_path=browser_path,
                          item_name=item_name, preset_name=preset_name)
        self.presets.append(p)
        return p

    def get_sample(self, role: str) -> SampleBinding | None:
        for s in self.samples:
            if s.role == role:
                return s
        return None

    def drum_pad_bindings(self) -> list[SampleBinding]:
        return [s for s in self.samples
                if s.role.startswith("drums.") and s.pad_note is not None]

    @classmethod
    def from_dict(cls, d: dict) -> "Bindings":
        return cls(
            samples=[SampleBinding.from_dict(s) for s in d.get("samples", [])],
            presets=[PresetBinding.from_dict(p) for p in d.get("presets", [])],
        )

    def to_dict(self) -> dict:
        return {
            "samples": [s.to_dict() for s in self.samples],
            "presets": [p.to_dict() for p in self.presets],
        }
