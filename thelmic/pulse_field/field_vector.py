"""Pulse Field — landscape position -> 8-dimension field vector.

This is the Python upstream of the Pulse Field architecture: it turns a
landscape position (and how the performer is moving through it) into the field
vector that the Max devices crystallise into sound. It reuses the EXISTING
thelmic landscape (`thelmic.landscape_map.LandscapeMap`) — the territory model
is shared, not reinvented.

    landscape (x, y) + motion  ->  FieldVector(8 dims)  ->  OSC  ->  Stage 0

The mapping encodes the spec's territory signatures:

    Oak   — moderate pressure, high stability, low discomfort   (grounded)
    Chaos — high novelty, high urgency, mid stability           (generative)
    Nott  — high discomfort/pressure, low stability, high silence (dark weight)

Dimension order is canonical and matches field-osc-config.js exactly.

Pulse Field branch — Stage 0 (Python side).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, astuple
from typing import Optional

from thelmic.landscape_map import LandscapeMap

# Canonical dimension order — MUST match field-osc-config.js DIMENSION_NAMES.
DIMENSION_NAMES = (
    "pressure", "stability", "density", "discomfort",
    "silence", "novelty", "urgency", "momentum",
)


def _clamp01(v: float) -> float:
    if v != v:  # NaN
        return 0.0
    return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)


@dataclass(frozen=True)
class FieldVector:
    """The 8-dimension Pulse Field state, all in [0, 1]."""
    pressure: float = 0.0
    stability: float = 0.5
    density: float = 0.3
    discomfort: float = 0.0
    silence: float = 0.0
    novelty: float = 0.0
    urgency: float = 0.0
    momentum: float = 0.0

    def as_dict(self) -> dict[str, float]:
        return {name: getattr(self, name) for name in DIMENSION_NAMES}

    def as_tuple(self) -> tuple[float, ...]:
        return astuple(self)


# Territory signatures — mirror of territory.js PROFILES so the Python driver
# and the Max monitor agree on the map.
TERRITORY_PROFILES: dict[str, FieldVector] = {
    "oak":   FieldVector(0.50, 0.85, 0.50, 0.10, 0.15, 0.20, 0.20, 0.55),
    "chaos": FieldVector(0.60, 0.40, 0.60, 0.40, 0.20, 0.90, 0.80, 0.40),
    "nott":  FieldVector(0.80, 0.20, 0.50, 0.90, 0.60, 0.30, 0.45, 0.55),
}


def nearest_territory(field: FieldVector) -> tuple[str, float]:
    """Return (territory_name, confidence) for the nearest profile in field-space."""
    best, best_d, second_d = None, math.inf, math.inf
    fv = field.as_tuple()
    for name, prof in TERRITORY_PROFILES.items():
        pv = prof.as_tuple()
        d = sum((a - b) ** 2 for a, b in zip(fv, pv))
        if d < best_d:
            second_d, best_d, best = best_d, d, name
        elif d < second_d:
            second_d = d
    best_dist = math.sqrt(best_d)
    max_dist = math.sqrt(len(DIMENSION_NAMES))
    proximity = 1.0 - best_dist / max_dist
    sep = 1.0 if second_d is math.inf else min(
        1.0, (math.sqrt(second_d) - best_dist) / max_dist)
    confidence = max(0.0, min(1.0, proximity * (0.5 + 0.5 * sep)))
    return best or "oak", confidence


def field_from_sample(
    sample: dict,
    speed: float = 0.0,
    boundary_proximity: float = 0.0,
    prev_pressure: Optional[float] = None,
    smoothed_speed: float = 0.0,
) -> FieldVector:
    """Map one LandscapeMap.sample() result + motion into a FieldVector.

    Args:
        sample: dict from LandscapeMap.sample(x, y) — uses volatility and the
            oak/chaos/nott influence weights.
        speed: instantaneous movement speed through the landscape (units/step).
        boundary_proximity: how close to the domain edge [0,1] (edges feel urgent).
        prev_pressure: previous frame's pressure, for the urgency derivative.
        smoothed_speed: time-averaged speed, for momentum (directional persistence).

    The mapping is intentionally simple and field-native: each dimension is a
    transparent function of terrain + motion, not a quoted pattern.
    """
    oak = sample.get("oak_influence", 0.0)
    chaos = sample.get("chaos_influence", 0.0)
    nott = sample.get("nott_influence", 0.0)
    volatility = sample.get("volatility", 0.5)

    # pressure: terrain weight (Nott is heavy) + a motion contribution + edge.
    pressure = _clamp01(
        0.25
        + 0.45 * nott
        + 0.20 * chaos
        + 0.45 * min(1.0, speed * 2.5)
        + 0.20 * boundary_proximity
    )

    # stability: inverse of terrain volatility (Oak stable, Chaos volatile).
    stability = _clamp01(1.0 - volatility)

    # density: terrain fullness — Chaos and Nott pack more concurrent potential.
    density = _clamp01(0.30 + 0.40 * chaos + 0.25 * nott)

    # discomfort: Nott's signature, with a touch of raw volatility.
    discomfort = _clamp01(0.85 * nott + 0.15 * volatility)

    # silence: active absence — strongest in Nott (dark, sparse weight).
    silence = _clamp01(0.55 * nott + 0.10 * (1.0 - chaos) * (1.0 - oak))

    # novelty: deviation / generativity — Chaos's signature.
    novelty = _clamp01(0.85 * chaos + 0.15 * volatility)

    # urgency: rate of pressure change (derivative), falling back to speed.
    if prev_pressure is None:
        urgency = _clamp01(min(1.0, speed * 3.0))
    else:
        urgency = _clamp01(abs(pressure - prev_pressure) * 6.0 + min(1.0, speed * 2.0))

    # momentum: directional persistence — sustained (smoothed) motion.
    momentum = _clamp01(0.35 + 0.65 * min(1.0, smoothed_speed * 2.5))

    return FieldVector(
        pressure=pressure, stability=stability, density=density,
        discomfort=discomfort, silence=silence, novelty=novelty,
        urgency=urgency, momentum=momentum,
    )


class FieldDriver:
    """Stateful driver: tracks position + motion, emits successive FieldVectors.

    Wraps a LandscapeMap and remembers the last position so it can compute
    speed (for pressure/urgency) and a smoothed speed (for momentum). Feed it
    positions with `update(x, y)`; it returns the current FieldVector.
    """

    DOMAIN_MIN = -1.5
    DOMAIN_MAX = 1.5

    def __init__(self, seed: int = 0, momentum_smoothing: float = 0.85) -> None:
        self.landscape = LandscapeMap(seed)
        self.momentum_smoothing = momentum_smoothing
        self._pos: Optional[tuple[float, float]] = None
        self._prev_pressure: Optional[float] = None
        self._smoothed_speed = 0.0

    def _boundary_proximity(self, x: float, y: float) -> float:
        span = self.DOMAIN_MAX - self.DOMAIN_MIN
        dx = min(x - self.DOMAIN_MIN, self.DOMAIN_MAX - x)
        dy = min(y - self.DOMAIN_MIN, self.DOMAIN_MAX - y)
        edge = min(dx, dy) / (span * 0.5)
        return _clamp01(1.0 - edge)

    def update(self, x: float, y: float) -> FieldVector:
        if self._pos is None:
            speed = 0.0
        else:
            speed = math.hypot(x - self._pos[0], y - self._pos[1])
        self._smoothed_speed = (
            self.momentum_smoothing * self._smoothed_speed
            + (1.0 - self.momentum_smoothing) * speed
        )
        sample = self.landscape.sample(x, y)
        field = field_from_sample(
            sample,
            speed=speed,
            boundary_proximity=self._boundary_proximity(x, y),
            prev_pressure=self._prev_pressure,
            smoothed_speed=self._smoothed_speed,
        )
        self._pos = (x, y)
        self._prev_pressure = field.pressure
        return field
