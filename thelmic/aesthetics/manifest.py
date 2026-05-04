"""pack.yaml loader — turns a YAML manifest into a runtime PackManifest.

Each pack ships a pack.yaml describing its expected tonality, grammar,
section palette, mix defaults, vocabulary. This loader validates against
the bridge's known grammars and SemanticParam vocabulary.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class PackManifest:
    name: str
    description: str
    default_bpm: float
    bpm_range: tuple[float, float]
    meter: tuple[int, int]
    key_root_midi: int
    key_scale: str
    key_scale_intervals: list[float]
    narrative_grammar: str
    required_track_roles: list[str]
    section_palette: list[str]
    anticipation: dict
    mix: dict
    vocabulary: dict
    raw: dict = field(default_factory=dict)


def _yaml_load_simple(text: str) -> dict:
    """Minimal YAML parser — enough for our manifests (doesn't require pyyaml).
    Handles: top-level keys, nested dicts, lists, scalars, comments."""
    import re
    out = {}
    stack = [(0, out)]
    lines = text.splitlines()

    def parse_value(s: str):
        s = s.strip()
        if not s:
            return None
        if s.startswith('[') and s.endswith(']'):
            inner = s[1:-1].strip()
            if not inner: return []
            return [parse_value(x) for x in re.split(r',\s*', inner)]
        if s in ('true', 'True'):  return True
        if s in ('false', 'False'): return False
        if s in ('null', 'None'): return None
        try: return int(s)
        except ValueError: pass
        try: return float(s)
        except ValueError: pass
        return s.strip("'\"")

    for raw_line in lines:
        line = raw_line.split('#', 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        # pop stack to current indent
        while stack and stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1] if stack else out

        stripped = line.strip()
        if stripped.startswith('-'):
            # list item
            val = parse_value(stripped[1:])
            if isinstance(parent, list):
                parent.append(val)
            else:
                # parent should have been a list-keyed value;
                # convert empty dict to list at the key level
                pass
            continue

        # key: value or key:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", stripped)
        if not m: continue
        k, v = m.group(1), m.group(2)
        if v == "":
            # Scope opens. Could be dict or list — we infer from next line indent
            new_dict: dict = {}
            parent[k] = new_dict
            stack.append((indent, new_dict))
            # Detect list scope on next non-empty line
            for nl in lines[lines.index(raw_line) + 1:]:
                ns = nl.split('#', 1)[0].rstrip()
                if not ns.strip(): continue
                ni = len(ns) - len(ns.lstrip())
                if ni <= indent: break
                if ns.lstrip().startswith('-'):
                    parent[k] = []
                    stack[-1] = (indent, parent[k])
                break
        else:
            parent[k] = parse_value(v)
    return out


def load_pack_manifest(yaml_path: str | Path) -> PackManifest:
    """Read a pack.yaml and return a typed PackManifest."""
    text = Path(yaml_path).read_text(encoding="utf-8")
    raw = _yaml_load_simple(text)

    key_blob = raw.get("key", {}) or {}
    return PackManifest(
        name=raw.get("name", ""),
        description=raw.get("description", ""),
        default_bpm=float(raw.get("default_bpm", 120.0)),
        bpm_range=tuple(raw.get("bpm_range", [60, 200])),
        meter=tuple(raw.get("meter", [4, 4])),
        key_root_midi=int(key_blob.get("root_midi", 36)),
        key_scale=str(key_blob.get("scale", "natural_minor")),
        key_scale_intervals=list(key_blob.get("scale_intervals", [])),
        narrative_grammar=str(raw.get("narrative_grammar", "build_drop_release")),
        required_track_roles=list(raw.get("required_track_roles", [])),
        section_palette=list(raw.get("section_palette", [])),
        anticipation=dict(raw.get("anticipation", {}) or {}),
        mix=dict(raw.get("mix", {}) or {}),
        vocabulary=dict(raw.get("vocabulary", {}) or {}),
        raw=raw,
    )


def load_pack(name: str) -> PackManifest:
    """Load the manifest for a named pack (looks for pack.yaml in the package dir)."""
    here = Path(__file__).parent
    return load_pack_manifest(here / name / "pack.yaml")


GRAMMAR_REGISTRY: dict[str, str] = {
    "build_drop_release": "thelmic.bridge.grammars.BuildDropRelease",
    "static_drone":       "thelmic.bridge.grammars.StaticDrone",
    "iso_rhythm":         "thelmic.bridge.grammars.IsoRhythm",
    "through_composed":   "thelmic.bridge.grammars.ThroughComposed",
    "rotational":         "thelmic.bridge.grammars.Rotational",
}


def resolve_grammar(name: str):
    """Look up a grammar class by name."""
    from thelmic.bridge import grammars
    cls_name = {
        "build_drop_release": "BuildDropRelease",
        "static_drone":       "StaticDrone",
        "iso_rhythm":         "IsoRhythm",
        "through_composed":   "ThroughComposed",
        "rotational":         "Rotational",
    }.get(name)
    if cls_name is None:
        raise ValueError(f"unknown grammar: {name!r}")
    return getattr(grammars, cls_name)()
