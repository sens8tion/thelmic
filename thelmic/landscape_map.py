"""Deterministic 2D landscape terrain for Thelmic.

This module is deliberately behaviour-isolated. It defines a static terrain
field that can be sampled or rendered, but it does not affect generation,
pression, MIDI, or runtime control flow.

v2 additions
------------
- Discrete seeded Chaos peaks (max() combination → clear gaps between hills)
- Feature identity system: Oak, Nott, and each Chaos peak have stable IDs
- SignatureRhythm stubs bound to each feature (not yet executed)
- Extended sample() returning nearest-feature metadata
- Low/mid frequency layered noise for terrain feel
"""

from __future__ import annotations

from dataclasses import dataclass
import math


ANCHORS: dict[str, tuple[float, float]] = {
    "oak":   (-1.0, -0.6),
    "chaos": ( 0.0,  1.0),
    "nott":  ( 1.0, -0.6),
}

ANCHOR_VOLATILITY: dict[str, float] = {
    "oak":   0.1,
    "chaos": 1.0,
    "nott":  0.3,
}

DOMAIN_MIN = -1.5
DOMAIN_MAX =  1.5


# ---------------------------------------------------------------------------
# Feature identity structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SignatureRhythm:
    """The evolved form of a rhythmic archetype bound to a terrain feature.

    Derived deterministically from (run_seed, feature_id).
    This is the musical material that voices draw from for a given location.
    """
    id:                str
    base_pattern_seed: int
    density_bias:      float           # [0, 1] — sparse ↔ dense
    syncopation_bias:  float           # [0, 1] — on-grid ↔ syncopated
    stability_bias:    float           # [0, 1] — unstable ↔ stable
    # Rhythmic content derived from biases — used by voice streams
    root_note:         int             # MIDI note for bass tonal centre (24–47)
    bass_steps:        tuple[int, ...] # which steps in a 16-step bar bass fires
    hook_motif_seed:   int             # seed for deterministic 2–5 note hook derivation


@dataclass(frozen=True)
class Feature:
    """A named terrain feature with stable identity and a rhythm stub."""
    id:               str
    position:         tuple[float, float]
    type:             str            # "oak" | "chaos_peak" | "nott"
    influence_radius: float
    signature_rhythm: SignatureRhythm


# ---------------------------------------------------------------------------
# RenderedLandscape (unchanged)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RenderedLandscape:
    width:  int
    height: int
    pixels: tuple[tuple[tuple[int, int, int], ...], ...]

    def to_ppm_bytes(self) -> bytes:
        """Return a portable pixmap byte representation for simple inspection."""
        header = f"P6\n{self.width} {self.height}\n255\n".encode("ascii")
        body = bytearray()
        for row in self.pixels:
            for red, green, blue in row:
                body.extend((red, green, blue))
        return header + bytes(body)


# ---------------------------------------------------------------------------
# LandscapeMap
# ---------------------------------------------------------------------------

class LandscapeMap:
    def __init__(self, seed: int):
        self.seed = int(seed)
        # Generate and cache Chaos peaks + features at construction time.
        # Everything downstream is pure sampling — no mutation after init.
        self._chaos_peaks: list[tuple[tuple[float, float], float, float]] = (
            self._generate_chaos_peaks()
        )
        self._features: list[Feature] = self._build_features()

    # ── Public API ────────────────────────────────────────────────────────────

    def sample(self, x: float, y: float) -> dict:
        raw_influences = self._influences(x, y)
        warped_x, warped_y = self._warped_point(x, y, raw_influences)
        influences = self._influences(warped_x, warped_y)
        base_volatility = sum(
            influences[name] * ANCHOR_VOLATILITY[name]
            for name in ("oak", "chaos", "nott")
        )
        noise = self._terrain_noise(warped_x, warped_y)
        anchor_strength = max(raw_influences.values())
        noise_scale = 1.0 - (0.82 * anchor_strength)
        chaos_peaks = self._chaos_peak_field(warped_x, warped_y)
        chaos_undulation = self._chaos_undulation_field(warped_x, warped_y)
        chaos_relief = self._chaos_relief_noise(warped_x, warped_y)
        terrain_variation = (
            (noise * 0.2 * noise_scale)
            + (chaos_peaks * (1.0 - raw_influences["oak"]))
            + (chaos_undulation * raw_influences["chaos"] * (1.0 - 0.65 * anchor_strength))
            + (chaos_relief * raw_influences["chaos"] * (1.0 - 0.85 * anchor_strength))
        )
        contrast_bias = (influences["nott"] * 0.04) - (influences["oak"] * 0.03)
        volatility = _clamp(base_volatility + terrain_variation + contrast_bias, 0.0, 1.0)

        # Nearest-feature metadata (from cached features — no re-derivation)
        nearest, dist = self._nearest_feature(x, y)

        return {
            "volatility":           volatility,
            "oak_influence":        influences["oak"],
            "chaos_influence":      influences["chaos"],
            "nott_influence":       influences["nott"],
            "nearest_feature_id":   nearest.id,
            "nearest_feature_type": nearest.type,
            "distance_to_feature":  dist,
        }

    def get_features(self) -> list[Feature]:
        """Return the stable feature list for this seed (cached)."""
        return list(self._features)

    def render(self, width: int, height: int) -> RenderedLandscape:
        if width <= 0 or height <= 0:
            raise ValueError("render dimensions must be positive")
        rows: list[tuple[tuple[int, int, int], ...]] = []
        for row in range(height):
            y = _lerp(DOMAIN_MAX, DOMAIN_MIN, row / max(1, height - 1))
            pixels: list[tuple[int, int, int]] = []
            for column in range(width):
                x = _lerp(DOMAIN_MIN, DOMAIN_MAX, column / max(1, width - 1))
                pixels.append(self._colour_for_sample(self.sample(x, y)))
            rows.append(tuple(pixels))
        return RenderedLandscape(width=width, height=height, pixels=tuple(rows))

    # ── Feature generation ────────────────────────────────────────────────────

    def _generate_chaos_peaks(self) -> list[tuple[tuple[float, float], float, float]]:
        """Seeded generation of 3–5 distinct Chaos peaks.

        Peaks are distributed laterally around the Chaos anchor so they form
        clearly separate hills with cool gaps between them.  A max() combination
        is used in _chaos_peak_field() to preserve separateness.
        """
        n = 3 + (self.seed % 3)              # 3, 4, or 5 peaks
        rng = _LCG(self.seed ^ 0xBEEF1A74)  # seeded PRNG, independent from noise hash

        chaos_x, chaos_y = ANCHORS["chaos"]
        lateral_half = 0.62                  # half-width of horizontal spread

        peaks: list[tuple[tuple[float, float], float, float]] = []
        for i in range(n):
            # Distribute x evenly across the lateral range then add small jitter.
            x_base = -lateral_half + (2 * lateral_half * i / max(1, n - 1))
            x = x_base + rng.next_float(-0.14, 0.14)
            y = chaos_y + rng.next_float(-0.35, 0.42)
            radius   = rng.next_float(0.11, 0.21)
            strength = rng.next_float(0.14, 0.28)
            peaks.append(((x, y), radius, strength))
        return peaks

    def _build_features(self) -> list[Feature]:
        """Build the full feature list: Oak anchor + Nott anchor + Chaos peaks."""
        features: list[Feature] = []

        # Anchor features
        for anchor_type in ("oak", "nott"):
            key = anchor_type
            fid = self._feature_id(key)
            features.append(Feature(
                id=fid,
                position=ANCHORS[anchor_type],
                type=anchor_type,
                influence_radius=0.55,
                signature_rhythm=self._make_signature_rhythm(fid),
            ))

        # Chaos peak features
        for i, ((px, py), radius, _strength) in enumerate(self._chaos_peaks):
            key = f"chaos_peak_{i}"
            fid = self._feature_id(key)
            features.append(Feature(
                id=fid,
                position=(px, py),
                type="chaos_peak",
                influence_radius=radius * 2.2,
                signature_rhythm=self._make_signature_rhythm(fid),
            ))

        return features

    def _feature_id(self, key: str) -> str:
        h = self._hash_str(key)
        return f"{key}:{h:08x}"

    def _make_signature_rhythm(self, feature_id: str) -> SignatureRhythm:
        """Derive a deterministic SignatureRhythm from seed + feature_id."""
        h = self._hash_str(feature_id)
        pattern_seed    = (self.seed ^ h) & 0xFFFFFFFF
        density_bias    = (h         & 0xFF) / 255.0
        syncopation_bias = ((h >>  8) & 0xFF) / 255.0
        stability_bias  = ((h >> 16) & 0xFF) / 255.0
        return SignatureRhythm(
            id=feature_id,
            base_pattern_seed=pattern_seed,
            density_bias=density_bias,
            syncopation_bias=syncopation_bias,
            stability_bias=stability_bias,
            root_note=_derive_root_note(pattern_seed),
            bass_steps=_derive_bass_steps(density_bias, syncopation_bias),
            hook_motif_seed=(pattern_seed * 31337) & 0xFFFFFFFF,
        )

    def _hash_str(self, key: str) -> int:
        """Deterministic hash of seed + key string."""
        h = self.seed ^ 0x9E3779B9
        for c in key:
            h = ((h * 1664525) + ord(c) + 1013904223) & 0xFFFFFFFF
        h ^= h >> 13
        h = (h * 1274126177) & 0xFFFFFFFF
        return h

    def _nearest_feature(self, x: float, y: float) -> tuple[Feature, float]:
        best = self._features[0]
        best_dist = _dist2(x, y, *best.position)
        for feature in self._features[1:]:
            d = _dist2(x, y, *feature.position)
            if d < best_dist:
                best = feature
                best_dist = d
        return best, math.sqrt(best_dist)

    # ── Terrain sampling (unchanged from v1) ─────────────────────────────────

    def _influences(self, x: float, y: float) -> dict[str, float]:
        sigma = 0.65
        weights = {}
        for name, (anchor_x, anchor_y) in ANCHORS.items():
            distance_sq = ((x - anchor_x) ** 2) + ((y - anchor_y) ** 2)
            weights[name] = math.exp(-distance_sq / (2.0 * sigma * sigma))
        total = sum(weights.values())
        return {name: weight / total for name, weight in weights.items()}

    def _warped_point(self, x: float, y: float, raw_influences: dict[str, float]) -> tuple[float, float]:
        anchor_strength = max(raw_influences.values())
        warp_scale = 1.0 - (0.9 * anchor_strength)
        skew_x = x + (0.12 * y)
        skew_y = y - (0.05 * x)
        offset_x = (skew_x - x) * warp_scale
        offset_y = (skew_y - y) * warp_scale
        chaos_zone = raw_influences["chaos"] * (1.0 - 0.65 * anchor_strength)
        low_noise_x = self._simplex_fbm(x * 0.42 + 13.1, y * 0.42 - 4.7,  salt=17)
        low_noise_y = self._simplex_fbm(x * 0.38 -  8.3, y * 0.38 + 19.4, salt=29)
        chaos_noise_x = self._simplex_fbm(x * 2.4 - 2.0, y * 2.4 + 5.0,   salt=41)
        chaos_noise_y = self._simplex_fbm(x * 2.2 + 7.0, y * 2.2 - 3.0,   salt=53)
        return (
            x + offset_x + (low_noise_x * 0.23 * warp_scale) + (chaos_noise_x * 0.32 * chaos_zone),
            y + offset_y + (low_noise_y * 0.23 * warp_scale) + (chaos_noise_y * 0.32 * chaos_zone),
        )

    def _terrain_noise(self, x: float, y: float) -> float:
        return self._simplex_fbm(x * 0.78, y * 0.78, salt=0)

    def _chaos_peak_field(self, x: float, y: float) -> float:
        """Seeded Chaos peaks combined with max() to preserve distinct hills.

        max() means only the nearest peak contributes significantly at any
        point, creating cool gaps between peaks rather than a blended mass.
        """
        if not self._chaos_peaks:
            return 0.0
        values = []
        for (px, py), sigma, amplitude in self._chaos_peaks:
            dist_sq = ((x - px) ** 2) + ((y - py) ** 2)
            values.append(amplitude * math.exp(-dist_sq / (2.0 * sigma * sigma)))
        return max(values)

    def _chaos_undulation_field(self, x: float, y: float) -> float:
        ridges = (
            ((-0.20, 0.82), 0.08, -0.16),
            (( 0.34, 0.92), 0.09, -0.13),
            ((-0.09, 1.14), 0.07,  0.14),
            (( 0.16, 1.32), 0.08, -0.11),
            (( 0.02, 0.98), 0.06,  0.17),
            ((-0.34, 1.04), 0.07, -0.10),
            (( 0.28, 1.24), 0.06,  0.09),
        )
        total = 0.0
        for (ridge_x, ridge_y), sigma, amplitude in ridges:
            dist_sq = ((x - ridge_x) ** 2) + ((y - ridge_y) ** 2)
            total += amplitude * math.exp(-dist_sq / (2.0 * sigma * sigma))
        ring = math.sin((x * 22.0) + (y * 13.0) + (self.seed * 0.01)) * 0.08
        envelope = math.exp(-(((x - 0.03) ** 2) + ((y - 1.0) ** 2)) / (2.0 * 0.36 * 0.36))
        return total + (ring * envelope)

    def _chaos_relief_noise(self, x: float, y: float) -> float:
        envelope = math.exp(-(((x - 0.02) ** 2) + ((y - 1.0) ** 2)) / (2.0 * 0.48 * 0.48))
        relief = self._simplex_fbm(x * 4.8 + 1.7, y * 4.8 - 9.1, salt=71)
        folded = (abs(relief) * 2.0) - 0.75
        slash = math.sin((x * 31.0) - (y * 18.0) + 0.4) * 0.05
        return (folded * 0.14 + slash) * envelope

    def _colour_for_sample(self, sample: dict) -> tuple[int, int, int]:
        volatility = sample["volatility"]
        if volatility < 0.45:
            t = volatility / 0.45
            colour = _mix((10, 50, 142), (82, 23, 118), t)
        else:
            t = (volatility - 0.45) / 0.55
            colour = _mix((82, 23, 118), (255, 244, 214), t)
        nott = sample["nott_influence"]
        if nott > 0.35:
            colour = _mix(colour, (24, 12, 54), (nott - 0.35) / 0.65)
        oak = sample["oak_influence"]
        if oak > 0.45:
            colour = _mix(colour, (6, 42, 132), (oak - 0.45) / 0.55)
        return colour

    def _simplex_fbm(self, x: float, y: float, salt: int) -> float:
        total = 0.0
        amplitude = 1.0
        frequency = 1.0
        amplitude_sum = 0.0
        for octave_index in range(4):
            total += amplitude * self._simplex_noise(
                x * frequency, y * frequency, octave_index + salt,
            )
            amplitude_sum += amplitude
            amplitude  *= 0.5
            frequency  *= 1.95
        return total / amplitude_sum

    def _simplex_noise(self, x: float, y: float, octave_index: int) -> float:
        skew_factor   = 0.5 * (math.sqrt(3.0) - 1.0)
        unskew_factor = (3.0 - math.sqrt(3.0)) / 6.0
        skew = (x + y) * skew_factor
        i = math.floor(x + skew)
        j = math.floor(y + skew)
        unskew = (i + j) * unskew_factor
        x0 = x - (i - unskew)
        y0 = y - (j - unskew)
        if x0 > y0:
            i1, j1 = 1, 0
        else:
            i1, j1 = 0, 1
        x1 = x0 - i1 + unskew_factor
        y1 = y0 - j1 + unskew_factor
        x2 = x0 - 1.0 + (2.0 * unskew_factor)
        y2 = y0 - 1.0 + (2.0 * unskew_factor)
        n0 = self._simplex_corner(i,      j,      x0, y0, octave_index)
        n1 = self._simplex_corner(i + i1, j + j1, x1, y1, octave_index)
        n2 = self._simplex_corner(i + 1,  j + 1,  x2, y2, octave_index)
        return _clamp(70.0 * (n0 + n1 + n2), -1.0, 1.0)

    def _simplex_corner(self, i: int, j: int, x: float, y: float, octave_index: int) -> float:
        t = 0.5 - (x * x) - (y * y)
        if t < 0:
            return 0.0
        gx, gy = _GRADIENTS[self._hash_index(i, j, octave_index) % len(_GRADIENTS)]
        t4 = t * t * t * t
        return t4 * ((gx * x) + (gy * y))

    def _hash_index(self, x: int, y: int, octave_index: int) -> int:
        value = (
            (x * 374761393)
            ^ (y * 668265263)
            ^ (octave_index * 2246822519)
            ^ (self.seed * 3266489917)
        ) & 0xFFFFFFFF
        value ^= value >> 13
        value = (value * 1274126177) & 0xFFFFFFFF
        return value


# ---------------------------------------------------------------------------
# Seeded LCG helper (isolated; not used in noise path)
# ---------------------------------------------------------------------------

class _LCG:
    """Minimal seeded linear-congruential generator for peak placement."""

    def __init__(self, seed: int) -> None:
        self._state = int(seed) & 0xFFFFFFFF

    def next_uint(self) -> int:
        self._state = (self._state * 1664525 + 1013904223) & 0xFFFFFFFF
        return self._state

    def next_float(self, lo: float = 0.0, hi: float = 1.0) -> float:
        return lo + (self.next_uint() / 0xFFFFFFFF) * (hi - lo)


# ---------------------------------------------------------------------------
# Module-level utilities (unchanged)
# ---------------------------------------------------------------------------

def _derive_root_note(seed: int) -> int:
    """Deterministic bass root note in C1–B1 range (MIDI 24–35)."""
    return 24 + (seed % 12)


def _derive_bass_steps(density: float, syncopation: float) -> tuple[int, ...]:
    """Deterministic bass rhythm pattern from density and syncopation biases."""
    if density < 0.33:
        # Sparse: beats 1 and 3
        return (0, 8)
    if density < 0.66:
        # Walking: four beats, optionally syncopated
        if syncopation > 0.5:
            return (0, 3, 8, 11)
        return (0, 4, 8, 12)
    # Dense: six steps
    if syncopation > 0.5:
        return (0, 2, 5, 8, 10, 13)
    return (0, 2, 6, 8, 10, 14)


_GRADIENTS: tuple[tuple[float, float], ...] = (
    ( 1.0,  1.0),
    (-1.0,  1.0),
    ( 1.0, -1.0),
    (-1.0, -1.0),
    ( 1.0,  0.0),
    (-1.0,  0.0),
    ( 0.0,  1.0),
    ( 0.0, -1.0),
)


def _lerp(a: float, b: float, t: float) -> float:
    return a + ((b - a) * t)


def _mix(
    a: tuple[int, int, int],
    b: tuple[int, int, int],
    t: float,
) -> tuple[int, int, int]:
    t = _clamp(t, 0.0, 1.0)
    return tuple(round(_lerp(a[index], b[index], t)) for index in range(3))  # type: ignore[return-value]


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def _dist2(x: float, y: float, px: float, py: float) -> float:
    return ((x - px) ** 2) + ((y - py) ** 2)
