"""Landscape trajectory — position, movement, and active feature selection.

The performer has a position in the 2D terrain.  Movement speed and direction
feed into dimension computation (pressure) and drop phrase planning.

Rules
-----
- Same position + same seed → same active feature (deterministic)
- Fast movement / boundary proximity → higher pressure
- Drop phrases are planned from trajectory, not detected reactively
- Landscape topology never changes; only position changes
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from thelmic.landscape_map import Feature, LandscapeMap


@dataclass
class LandscapeTrajectory:
    landscape: LandscapeMap
    x: float = 0.0      # current position, starts at terrain centre
    y: float = 0.0
    _vx: float = field(default=0.0, repr=False)  # velocity components
    _vy: float = field(default=0.0, repr=False)
    _phrases_since_drop: int = field(default=0, repr=False)

    def move_to(self, x: float, y: float) -> None:
        """Update position; compute velocity from delta for pressure calculation."""
        self._vx = x - self.x
        self._vy = y - self.y
        self.x = float(x)
        self.y = float(y)

    @property
    def speed(self) -> float:
        """Magnitude of the last movement vector."""
        return math.sqrt(self._vx ** 2 + self._vy ** 2)

    def active_feature(self) -> Feature:
        """Feature nearest to the current position (Euclidean distance)."""
        features = self.landscape.get_features()
        return min(features, key=lambda f: _dist2(self.x, self.y, *f.position))

    def boundary_proximity(self) -> float:
        """[0, 1] — 0 = deep inside a feature, 1 = equidistant between two.

        Used as a pressure contributor: tension rises near feature boundaries.
        """
        features = self.landscape.get_features()
        dists = sorted(_dist(self.x, self.y, *f.position) for f in features)
        if len(dists) < 2 or dists[0] < 1e-9:
            return 0.0
        # Ratio of gap between closest and second-closest to total
        return min(1.0, (dists[1] - dists[0]) / max(dists[1], 1e-9))

    def pressure_base(self) -> float:
        """Base pressure value from movement speed and boundary proximity."""
        movement_pressure  = min(1.0, self.speed * 4.0)   # saturates at 0.25 units/step
        boundary_pressure  = self.boundary_proximity() * 0.5
        return min(1.0, movement_pressure + boundary_pressure)

    def advance_phrase(self) -> None:
        """Called once per phrase boundary to update the drop plan."""
        self._phrases_since_drop += 1
        # Velocity decays each phrase (movement is a gesture, not continuous)
        self._vx *= 0.5
        self._vy *= 0.5

    def phrases_until_next_drop(self) -> int:
        """How many full phrases until the next planned drop.

        Drops only build when the performer is MOVING (speed > threshold).
        Stationary play is always in groove state (ptd ≥ 2) — no anticipation
        buildup, no hat stripping, consistent loop until the user acts.

        0 = this phrase is the last before the drop (movement-triggered)
        1 = one more phrase before the drop
        2+ = groove state (stationary or early movement)
        """
        speed = self.speed
        if speed > 0.4:
            interval = 1
        elif speed > 0.1:
            interval = 2
        else:
            interval = 3
        remaining = interval - self._phrases_since_drop
        return max(0, remaining - 1)

    def is_drop_phrase(self) -> bool:
        """Whether the current phrase should commit a structural change.

        Drop interval scales with movement speed.
        Intervals are in phrases (1 phrase = 16 bars ≈ 22s at 174 BPM).

        - fast movement  (speed > 0.4) → drop every phrase (22s)
        - medium         (0.1–0.4)     → drop every 2 phrases (44s)
        - slow/stationary              → drop every 3 phrases (66s)

        References: hard techno/techno phrase lengths typically 32–64 bars;
        at 174 BPM 32 bars ≈ 22s, 64 bars ≈ 44s.
        """
        speed = self.speed
        if speed > 0.4:
            interval = 1
        elif speed > 0.1:
            interval = 2
        else:
            interval = 3
        if self._phrases_since_drop >= interval:
            self._phrases_since_drop = 0
            return True
        return False


def _dist(x: float, y: float, px: float, py: float) -> float:
    return math.sqrt((x - px) ** 2 + (y - py) ** 2)


def _dist2(x: float, y: float, px: float, py: float) -> float:
    return (x - px) ** 2 + (y - py) ** 2
