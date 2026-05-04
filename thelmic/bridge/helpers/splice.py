"""Local Splice library scanning + role matching + sample loading.

The Splice MCP (prompt_to_stack / download_asset) is the agent-driven
fetch path. This module is the GENRE-NEUTRAL Python side: scan the
locally-downloaded Splice library, score samples by role-keywords, and
load matched samples into Live tracks (drum-rack pads, audio clips,
Simpler buffers).

Aesthetic packs declare which keywords map to which roles via a
RoleSampleSpec; this module does the disk scanning and Live loading.
"""
from __future__ import annotations
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


DEFAULT_SPLICE_ROOT     = Path.home() / "Documents" / "Splice" / "Samples"
ABLETON_USER_LIB_SPLICE = (Path.home() / "Documents" / "Ableton" /
                            "User Library" / "Samples" / "Splice")


@dataclass
class RoleSampleSpec:
    """Describes how to find samples for a role."""
    role: str
    must_match: list[str] = field(default_factory=list)        # all required (lowercased substrings)
    should_match: list[str] = field(default_factory=list)      # bonus points each
    must_not_match: list[str] = field(default_factory=list)    # disqualifiers
    bpm_range: Optional[tuple[float, float]] = None            # if filename has BPM marker
    one_shot_preferred: bool = False                            # for drum hits / vocal stabs (short)
    loop_preferred: bool = False                                # for breaks / pads (long)


@dataclass
class SampleEntry:
    path: Path
    name: str            # bare filename
    name_lower: str      # cached lowercase

    @property
    def size_bytes(self) -> int:
        try: return self.path.stat().st_size
        except Exception: return 0


def scan_library(root: Path = DEFAULT_SPLICE_ROOT) -> list[SampleEntry]:
    """Walk the Splice library and return all .wav / .aif / .flac entries."""
    if not root.exists():
        return []
    out = []
    for p in root.rglob("*"):
        if not p.is_file(): continue
        if p.suffix.lower() not in (".wav", ".aif", ".aiff", ".flac"):
            continue
        out.append(SampleEntry(p, p.name, p.name.lower()))
    return out


def score_sample(entry: SampleEntry, spec: RoleSampleSpec) -> int:
    """Higher score = better match. Returns 0 if a must-match fails or
    a must-not-match hits. Otherwise 1 per should-match keyword + 10 if
    all must-matches present."""
    n = entry.name_lower
    # disqualifiers
    for bad in spec.must_not_match:
        if bad.lower() in n:
            return 0
    # required
    if spec.must_match:
        for req in spec.must_match:
            if req.lower() not in n:
                return 0
    score = 10 if spec.must_match else 0
    # bonuses
    for bonus in spec.should_match:
        if bonus.lower() in n:
            score += 1
    # bpm bonus / penalty
    if spec.bpm_range:
        m = re.search(r"(\d{2,3})_?bpm|_(\d{2,3})_", n)
        if m:
            try:
                bpm = int(m.group(1) or m.group(2))
                lo, hi = spec.bpm_range
                if lo <= bpm <= hi:
                    score += 5
                else:
                    score -= 2
            except Exception:
                pass
    # length preference
    sz = entry.size_bytes
    if spec.one_shot_preferred and sz > 1_500_000:    # > ~1.5MB likely a loop
        score -= 2
    if spec.loop_preferred and sz < 200_000:           # < 200KB likely a one-shot
        score -= 2
    return score


def find_best_matches(library: list[SampleEntry], spec: RoleSampleSpec,
                       top_n: int = 5) -> list[tuple[int, SampleEntry]]:
    """Return top-N (score, entry) pairs sorted desc."""
    scored = [(score_sample(e, spec), e) for e in library]
    scored = [s for s in scored if s[0] > 0]
    scored.sort(key=lambda s: s[0], reverse=True)
    return scored[:top_n]


# ----------------------------------------------------------------------
# Loaders — each track type takes a different path through Live's API
# ----------------------------------------------------------------------

def _ensure_in_user_library(path: Path) -> Optional[Path]:
    """Live's load_item_at_path resolves paths under the Ableton User
    Library, not the raw Splice samples folder. Copy the file there if
    not already mirrored. Returns the User-Library path (or None on fail)."""
    import shutil
    try:
        ABLETON_USER_LIB_SPLICE.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"    couldn't create User Library Splice folder: {e}")
        return None
    dest = ABLETON_USER_LIB_SPLICE / path.name
    if not dest.exists() or dest.stat().st_size != path.stat().st_size:
        try:
            shutil.copy2(path, dest)
            print(f"    + mirrored {path.name} → User Library Splice")
        except Exception as e:
            print(f"    mirror fail ({path.name}): {e}")
            return None
    return dest


def _user_library_path_for_load(path: Path) -> Optional[tuple[str, str]]:
    """Return (live_path_uri_dir, item_name) for use with load_item_at_path.
    Mirrors the file into the Ableton User Library if it's not already there."""
    mirrored = _ensure_in_user_library(path)
    if mirrored is None:
        return None
    return ("user_library/Samples/Splice", mirrored.name)


def load_audio_clip_into_slot(ch, track_index: int, slot: int,
                               sample_path: Path) -> bool:
    """Drop an audio file into a clip slot on an audio track.
    Mirrors into Ableton User Library if needed."""
    pair = _user_library_path_for_load(sample_path)
    if pair is None: return False
    path_dir, item_name = pair
    try:
        ch.load_item_at_path(track_index, path_dir, item_name).result(timeout=15)
        return True
    except Exception as e:
        print(f"    load_audio_clip fail ({sample_path.name}): {e}")
        return False


def load_simpler_sample(ch, track_index: int, sample_path: Path) -> bool:
    """Load a sample into a Simpler on the track (replaces current)."""
    pair = _user_library_path_for_load(sample_path)
    if pair is None: return False
    path_dir, item_name = pair
    try:
        ch.load_item_at_path(track_index, path_dir, item_name).result(timeout=15)
        return True
    except Exception as e:
        print(f"    load_simpler fail ({sample_path.name}): {e}")
        return False


def load_drum_pad_samples(ch, track_index: int, drum_device_idx: int,
                           pad_assignments: dict[int, Path]) -> int:
    """Bulk-load samples onto Drum Rack pads via the proper RPC.
    Mirrors into Ableton User Library Splice folder first."""
    items = []
    for note, path in pad_assignments.items():
        mirrored = _ensure_in_user_library(path)
        if mirrored is None: continue
        items.append({"name": mirrored.name, "note": int(note)})
    if not items:
        return 0
    try:
        r = ch.bulk_load_drum_pads(track_index, drum_device_idx,
                                     "user_library/Samples/Splice",
                                     items).result(timeout=60)
        loaded = r.get("loaded", []) if isinstance(r, dict) else []
        return len(loaded)
    except Exception as e:
        print(f"    bulk_load_drum_pads fail: {e}")
        return 0
