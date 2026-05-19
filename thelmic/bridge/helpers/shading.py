"""Session-view clip shading by (impact × strength × density).

Maps musical meaning to Live's 14-col × 5-row color palette so a performer
can read scene character + per-clip prominence at a glance on hardware
(Push) and on screen.

## Palette structure (empirically mapped from Live 12)

70 colors arranged as 14 hue columns × 5 perceptual-intensity rows:

    col 0  pink/red     col 7  cyan
    col 1  orange       col 8  ocean blue
    col 2  peach/tan    col 9  blue
    col 3  yellow       col 10 purple
    col 4  lime         col 11 magenta
    col 5  green        col 12 dark-magenta
    col 6  teal         col 13 gray/white

Row order by perceived intensity (ascending):
    row 3 pale  <  row 0 bright  <  row 2 earthy  <  row 1 deep  <  row 4 dark

The Push controller collapses row-shade variation within a hue family,
so per-clip variation is encoded via ADJACENT HUE COLUMNS (different
hues) on the SAME row — keeping each scene anchored to its identity
column+row while clips spread across a small column range.

## Three encoded dimensions

1. Row impact          → which `row` the scene sits on
2. Instrument strength → mapped to a per-track score (0/1/2)
3. Hit density         → bucketed from clip note count (0/1/2)

Strength and density tend to negatively correlate (foundation instruments
are sparse, atmospheric layers are dense), so we combine via `max()` to
preserve spread instead of cancelling.

## Usage

    from thelmic.bridge.helpers.shading import (
        SceneShading, ShadingConfig, apply_shading,
    )

    config = ShadingConfig(
        scenes={
            0: SceneShading(identity_col=8, row=0, col_range=(6, 10)),
            5: SceneShading(identity_col=0, row=1, col_range=None),  # uniform
            ...
        },
        track_strength={1: 2, 2: 2, 0: 1, 5: 0},  # by track_index
        scene_names={0: "intro", 5: "payoff_storm"},
    )
    apply_shading(channel, config)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional


PALETTE_COLS = 14
PALETTE_ROWS = 5

# Row indices by perceived-intensity rank (ascending)
INTENSITY_ROW_ORDER = (3, 0, 2, 1, 4)


@dataclass(frozen=True)
class SceneShading:
    """How to color one scene/row.

    Args:
        identity_col: Hue column 0..13 — the scene's "identity" hue.
        row:          Row 0..4 — the scene's perceptual intensity band.
        col_range:    (min_col, max_col) inclusive, for per-clip column
                      shifts. Choose adjacent columns that stay inside
                      the scene's hue family. If None, every clip in
                      this scene gets the identity color (uniform scene
                      — useful for "peak" scenes where you don't want
                      per-clip variation, or where the identity column
                      can't safely shift, e.g. col 0 hits pink in row 0).
    """
    identity_col: int
    row: int
    col_range: Optional[tuple[int, int]] = None


@dataclass(frozen=True)
class ShadingConfig:
    """Full shading recipe for a session.

    Args:
        scenes:         slot_index → SceneShading.
        track_strength: track_index → 0 (weak) / 1 (moderate) / 2 (strong).
                        Missing tracks default to 1 (moderate).
        scene_names:    Optional slot_index → name. Names are pushed to
                        Live's scene strip alongside the color.
    """
    scenes: Mapping[int, SceneShading]
    track_strength: Mapping[int, int]
    scene_names: Mapping[int, str] = field(default_factory=dict)


def density_score(note_count: int) -> int:
    """Bucket a clip's note count into 0 (sparse) / 1 (medium) / 2 (dense).

    Defaults are tuned for ~16-beat clips at moderate tempo. Override
    by composing your own scorer if your scenes have very different
    natural densities.
    """
    if note_count >= 33:
        return 2
    if note_count <= 8:
        return 0
    return 1


def score_to_col(score: int, col_range: tuple[int, int]) -> int:
    """Map a 0..4 score linearly across `col_range` inclusive."""
    lo, hi = col_range
    span = hi - lo
    return lo + round(score / 4 * span)


def color_for_clip(
    scene: SceneShading,
    track_strength: int,
    note_count: int,
) -> int:
    """Compute the Live palette index for a single clip.

    For uniform scenes (col_range=None), returns the identity color.
    Otherwise, combines strength and density via max() and maps the
    spread to the scene's column range.
    """
    if scene.col_range is None:
        return scene.identity_col + scene.row * PALETTE_COLS
    sd = max(track_strength, density_score(note_count))
    spread_score = min(4, sd * 2)
    col = score_to_col(spread_score, scene.col_range)
    return col + scene.row * PALETTE_COLS


def apply_shading(channel, config: ShadingConfig) -> dict:
    """Apply a `ShadingConfig` to a live session via `LiveChannel`.

    Reads each clip's note count to compute its color, then sets
    scene strip colors + names and per-clip colors. Returns a summary
    `{slot: [(track_index, color_index, note_count), ...]}` for any
    diagnostic display the caller wants to render.

    `channel` must expose the LOM RPCs `get_session_info`,
    `get_clip_notes`, `set_scene_color`, `set_scene_name`, and
    `set_clip_color`. Empty/missing clips are skipped silently.
    """
    summary: dict = {}
    info = channel.get_session_info().result(timeout=3)
    n_tracks = info["track_count"]

    for slot, scene in config.scenes.items():
        identity_color = scene.identity_col + scene.row * PALETTE_COLS
        channel.set_scene_color(slot, identity_color).result(timeout=3)
        if slot in config.scene_names:
            channel.set_scene_name(slot, config.scene_names[slot]).result(timeout=3)

        per_clip: list = []
        for ti in range(n_tracks):
            try:
                r = channel.get_clip_notes(ti, slot).result(timeout=3)
                count = len(r.get("notes", []))
            except Exception:
                continue
            if count == 0:
                continue
            ts = config.track_strength.get(ti, 1)
            ci = color_for_clip(scene, ts, count)
            channel.set_clip_color(ti, slot, ci).result(timeout=3)
            per_clip.append((ti, ci, count))
        summary[slot] = per_clip

    return summary
