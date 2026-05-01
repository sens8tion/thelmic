from thelmic.landscape_map import (
    ANCHORS, LandscapeMap, RenderedLandscape, Feature, SignatureRhythm,
)


# ---------------------------------------------------------------------------
# Existing invariants (preserved)
# ---------------------------------------------------------------------------

def test_anchor_locations_are_fixed():
    assert ANCHORS == {
        "oak":   (-1.0, -0.6),
        "chaos": ( 0.0,  1.0),
        "nott":  ( 1.0, -0.6),
    }


def test_sample_returns_expected_keys():
    sample = LandscapeMap(seed=123).sample(0.25, -0.2)
    assert {
        "volatility",
        "oak_influence", "chaos_influence", "nott_influence",
        "nearest_feature_id", "nearest_feature_type", "distance_to_feature",
    }.issubset(sample.keys())


def test_sample_anchor_influences_sum_to_one():
    sample = LandscapeMap(seed=123).sample(0.25, -0.2)
    total = sample["oak_influence"] + sample["chaos_influence"] + sample["nott_influence"]
    assert abs(total - 1.0) < 1e-9


def test_sample_all_values_are_bounded():
    sample = LandscapeMap(seed=123).sample(0.25, -0.2)
    for key in ("volatility", "oak_influence", "chaos_influence", "nott_influence"):
        assert 0.0 <= sample[key] <= 1.0


def test_anchor_identity_is_preserved_with_noise():
    terrain = LandscapeMap(seed=42)
    oak   = terrain.sample(*ANCHORS["oak"])
    chaos = terrain.sample(*ANCHORS["chaos"])
    nott  = terrain.sample(*ANCHORS["nott"])
    assert chaos["volatility"] > nott["volatility"] > oak["volatility"]
    assert oak["oak_influence"]     > 0.95
    assert chaos["chaos_influence"] > 0.95
    assert nott["nott_influence"]   > 0.95


def test_seeded_terrain_is_reproducible_and_seed_sensitive():
    first  = LandscapeMap(seed=7)
    second = LandscapeMap(seed=7)
    third  = LandscapeMap(seed=8)
    points = [(-0.8, -0.4), (0.0, 0.0), (0.55, 0.2), (1.1, -0.9)]
    assert [first.sample(*p) for p in points] == [second.sample(*p) for p in points]
    assert [first.sample(*p)["volatility"] for p in points] != [
        third.sample(*p)["volatility"] for p in points
    ]


def test_render_returns_stable_rgb_image_data():
    image  = LandscapeMap(seed=5).render(width=24, height=16)
    repeat = LandscapeMap(seed=5).render(width=24, height=16)
    assert isinstance(image, RenderedLandscape)
    assert image.width  == 24
    assert image.height == 16
    assert len(image.pixels) == 16
    assert all(len(row) == 24 for row in image.pixels)
    assert image.pixels == repeat.pixels
    assert image.to_ppm_bytes().startswith(b"P6\n24 16\n255\n")


def test_nott_region_renders_darker_than_chaos_region():
    terrain     = LandscapeMap(seed=11)
    chaos_colour = terrain._colour_for_sample(terrain.sample(*ANCHORS["chaos"]))
    nott_colour  = terrain._colour_for_sample(terrain.sample(*ANCHORS["nott"]))
    assert sum(chaos_colour) > sum(nott_colour)


def test_server_svg_renders_anchor_labels_without_generation_dependency():
    from thelmic.server import _landscape_map_svg
    svg = _landscape_map_svg(width=96, height=64)
    assert svg.startswith("<svg")
    assert "Oak"   in svg
    assert "Chaos" in svg
    assert "Nott"  in svg
    assert "Thelmic landscape volatility terrain" in svg


# ---------------------------------------------------------------------------
# Chaos peak geometry
# ---------------------------------------------------------------------------

def test_chaos_peak_count_is_three_to_five():
    for seed in (1, 2, 3, 42, 999, 1103):
        terrain = LandscapeMap(seed=seed)
        n = len(terrain._chaos_peaks)
        assert 3 <= n <= 5, f"seed={seed}: {n} peaks, expected 3–5"


def test_chaos_peaks_are_positioned_near_chaos_anchor():
    chaos_x, chaos_y = ANCHORS["chaos"]
    max_distance = 1.1
    for seed in (7, 42, 1103):
        terrain = LandscapeMap(seed=seed)
        for (px, py), _radius, _strength in terrain._chaos_peaks:
            dist = ((px - chaos_x)**2 + (py - chaos_y)**2) ** 0.5
            assert dist < max_distance, (
                f"seed={seed}: peak ({px:.2f},{py:.2f}) is {dist:.2f} from Chaos anchor"
            )


def test_chaos_peaks_are_laterally_spread():
    """Peaks are distributed across the horizontal range — no two peaks share
    the same x-bin, ensuring visible lateral separation."""
    for seed in (7, 42, 100, 1103):
        terrain = LandscapeMap(seed=seed)
        x_positions = [px for (px, _py), _, _ in terrain._chaos_peaks]
        # The x spread should cover at least 0.8 of the lateral range
        assert max(x_positions) - min(x_positions) >= 0.80, (
            f"seed={seed}: peaks are too clustered horizontally "
            f"(spread={max(x_positions)-min(x_positions):.2f})"
        )


def test_chaos_peak_field_is_higher_at_peak_centres_than_far_away():
    """Each peak centre should produce a high field value compared to a
    distant neutral point, confirming peaks are real hills."""
    neutral_x, neutral_y = -1.0, -0.6   # Oak anchor — far from Chaos zone
    for seed in (7, 42, 1103):
        terrain = LandscapeMap(seed=seed)
        neutral_val = terrain._chaos_peak_field(neutral_x, neutral_y)
        for (px, py), _sigma, amplitude in terrain._chaos_peaks:
            peak_val = terrain._chaos_peak_field(px, py)
            assert peak_val > neutral_val, (
                f"seed={seed}: peak at ({px:.2f},{py:.2f}) not higher than neutral point"
            )


def test_chaos_peak_field_uses_max_not_sum():
    """max() combination: the peak field at a peak centre should roughly equal
    that peak's own amplitude (dominant), not the sum of all peaks."""
    terrain = LandscapeMap(seed=42)
    if not terrain._chaos_peaks:
        return
    (px, py), sigma, amplitude = terrain._chaos_peaks[0]
    field_at_centre = terrain._chaos_peak_field(px, py)
    # Field should be close to amplitude (max of all gaussians at this point)
    assert field_at_centre <= amplitude * 1.05, (
        "peak field exceeds single-peak amplitude — sum() may be in use"
    )


# ---------------------------------------------------------------------------
# Feature identity system
# ---------------------------------------------------------------------------

def test_feature_list_has_oak_nott_and_chaos_peaks():
    terrain  = LandscapeMap(seed=42)
    features = terrain.get_features()
    types    = [f.type for f in features]
    assert "oak"        in types
    assert "nott"       in types
    assert "chaos_peak" in types


def test_feature_count_is_two_anchors_plus_peak_count():
    for seed in (7, 42, 1103):
        terrain    = LandscapeMap(seed=seed)
        n_peaks    = len(terrain._chaos_peaks)
        n_features = len(terrain.get_features())
        assert n_features == n_peaks + 2, (
            f"seed={seed}: expected {n_peaks+2} features, got {n_features}"
        )


def test_feature_ids_are_unique():
    for seed in (7, 42, 1103):
        ids = [f.id for f in LandscapeMap(seed=seed).get_features()]
        assert len(ids) == len(set(ids)), f"seed={seed}: duplicate feature IDs"


def test_feature_ids_are_deterministic():
    for seed in (7, 42, 1103):
        ids1 = [f.id for f in LandscapeMap(seed=seed).get_features()]
        ids2 = [f.id for f in LandscapeMap(seed=seed).get_features()]
        assert ids1 == ids2


def test_feature_ids_differ_across_seeds():
    ids_a = {f.id for f in LandscapeMap(seed=7).get_features()}
    ids_b = {f.id for f in LandscapeMap(seed=8).get_features()}
    # Anchor IDs include the seed hash so they differ between seeds
    assert ids_a != ids_b


def test_feature_positions_match_anchors_and_peaks():
    terrain  = LandscapeMap(seed=42)
    features = terrain.get_features()
    oak_feature  = next(f for f in features if f.type == "oak")
    nott_feature = next(f for f in features if f.type == "nott")
    assert oak_feature.position  == ANCHORS["oak"]
    assert nott_feature.position == ANCHORS["nott"]
    peak_positions = [f.position for f in features if f.type == "chaos_peak"]
    peak_data_pos  = [(x, y) for (x, y), _, _ in terrain._chaos_peaks]
    assert peak_positions == peak_data_pos


def test_feature_influence_radius_is_positive():
    for feature in LandscapeMap(seed=42).get_features():
        assert feature.influence_radius > 0, f"{feature.id}: non-positive radius"


def test_get_features_returns_copy():
    terrain = LandscapeMap(seed=42)
    f1 = terrain.get_features()
    f2 = terrain.get_features()
    assert f1 == f2
    assert f1 is not f2   # new list each call, same contents


# ---------------------------------------------------------------------------
# SignatureRhythm stubs
# ---------------------------------------------------------------------------

def test_signature_rhythms_are_present_on_every_feature():
    for feature in LandscapeMap(seed=42).get_features():
        assert isinstance(feature.signature_rhythm, SignatureRhythm), (
            f"{feature.id}: missing SignatureRhythm"
        )


def test_signature_rhythm_fields_are_bounded():
    for feature in LandscapeMap(seed=42).get_features():
        r = feature.signature_rhythm
        assert 0.0 <= r.density_bias      <= 1.0, f"{feature.id}: density_bias out of range"
        assert 0.0 <= r.syncopation_bias  <= 1.0
        assert 0.0 <= r.stability_bias    <= 1.0


def test_signature_rhythm_ids_are_unique():
    rhythms = [f.signature_rhythm for f in LandscapeMap(seed=42).get_features()]
    ids = [r.id for r in rhythms]
    assert len(ids) == len(set(ids))


def test_signature_rhythms_are_deterministic():
    for seed in (7, 42, 1103):
        r1 = [f.signature_rhythm for f in LandscapeMap(seed=seed).get_features()]
        r2 = [f.signature_rhythm for f in LandscapeMap(seed=seed).get_features()]
        assert r1 == r2


def test_signature_rhythms_differ_across_seeds():
    r7 = {f.signature_rhythm.base_pattern_seed
          for f in LandscapeMap(seed=7).get_features()}
    r8 = {f.signature_rhythm.base_pattern_seed
          for f in LandscapeMap(seed=8).get_features()}
    assert r7 != r8


def test_signature_rhythm_base_seed_varies_per_feature():
    seeds = [f.signature_rhythm.base_pattern_seed
             for f in LandscapeMap(seed=42).get_features()]
    assert len(seeds) == len(set(seeds)), "every feature must have a unique base_pattern_seed"


# ---------------------------------------------------------------------------
# Extended sample() — nearest-feature metadata
# ---------------------------------------------------------------------------

def test_sample_nearest_feature_id_is_a_known_feature():
    terrain  = LandscapeMap(seed=42)
    known    = {f.id for f in terrain.get_features()}
    sample   = terrain.sample(0.1, 0.8)
    assert sample["nearest_feature_id"] in known


def test_sample_nearest_feature_type_is_valid():
    terrain = LandscapeMap(seed=42)
    for x, y in [(0.0, 1.0), (-1.0, -0.6), (1.0, -0.6), (0.0, 0.0)]:
        t = terrain.sample(x, y)["nearest_feature_type"]
        assert t in ("oak", "nott", "chaos_peak"), f"unknown type '{t}' at ({x},{y})"


def test_sample_distance_to_feature_is_non_negative():
    terrain = LandscapeMap(seed=42)
    for x, y in [(0.0, 0.0), (-0.8, -0.4), (0.5, 0.9)]:
        assert terrain.sample(x, y)["distance_to_feature"] >= 0.0


def test_nearest_feature_at_anchor_is_that_anchor():
    terrain = LandscapeMap(seed=42)
    # Oak anchor should be nearest to itself (no chaos_peak is placed there)
    oak_sample = terrain.sample(*ANCHORS["oak"])
    assert oak_sample["nearest_feature_type"] == "oak", (
        f"expected 'oak' nearest at oak anchor, got '{oak_sample['nearest_feature_type']}'"
    )


def test_nearest_feature_is_deterministic():
    terrain = LandscapeMap(seed=42)
    s1 = terrain.sample(0.1, 0.5)
    s2 = terrain.sample(0.1, 0.5)
    assert s1["nearest_feature_id"]   == s2["nearest_feature_id"]
    assert s1["distance_to_feature"]  == s2["distance_to_feature"]


# ---------------------------------------------------------------------------
# SVG debug overlay
# ---------------------------------------------------------------------------

def test_svg_contains_chaos_peak_labels():
    from thelmic.server import _landscape_map_svg
    svg = _landscape_map_svg(width=180, height=120)
    assert "C1" in svg, "SVG must label the first Chaos peak"


def test_svg_peak_count_matches_feature_list():
    from thelmic.server import _LANDSCAPE_MAP, _landscape_map_svg
    n_peaks = sum(1 for f in _LANDSCAPE_MAP.get_features() if f.type == "chaos_peak")
    svg = _landscape_map_svg(width=180, height=120)
    for i in range(1, n_peaks + 1):
        assert f"C{i}" in svg, f"SVG missing label C{i}"
