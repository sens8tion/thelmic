"""Sub-phrase segmentation and transformer taxonomy.

These are pure deterministic rule-table lookups with no server dependency.
All transformer names must be declared in musical_rules.md before appearing here.
"""

from __future__ import annotations

from thelmic.bank_generator import BARS_PER_PHRASE, PHRASES_PER_BANK
from thelmic.note_generation_chain import BANK_STEPS

STEPS_PER_BAR: int = BANK_STEPS // (BARS_PER_PHRASE * PHRASES_PER_BANK)   # 16
PHRASE_BARS:   int = BARS_PER_PHRASE * PHRASES_PER_BANK                    # 16

# ---------------------------------------------------------------------------
# Transformer taxonomy — names and categories from musical_rules.md.
# No name may appear here unless declared in the taxonomy.
# ---------------------------------------------------------------------------

TRANSFORMER_CATEGORIES: dict[str, str] = {
    "density_increase":      "density_shaping",
    "density_hold":          "density_shaping",
    "density_thin":          "density_shaping",
    "stabilise":             "rhythmic_stability",
    "destabilise":           "rhythmic_stability",
    "kick_emphasis":         "instrument_emphasis",
    "snare_suppression":     "instrument_emphasis",
    "hat_drive":             "instrument_emphasis",
    "anticipation_build":    "structural_anticipation",
    "pre_drop_non_silent":   "structural_anticipation",
    "withholding":           "structural_anticipation",
    "release_resolve":       "resolution_release",
    "release_thin":          "resolution_release",
    "relock":                "resolution_release",
}

# Role → default transformer names (from assignment rules in musical_rules.md).
ROLE_DEFAULT_TRANSFORMERS: dict[str, list[str]] = {
    "build":     ["anticipation_build"],   # pressure-driven withholding (rules §build default)
    "hold":      ["density_hold"],         # maintain pattern
    "release":   ["release_resolve"],      # pressure clears at drop (rules §release default)
    "transform": ["destabilise"],          # rhythmic instability
}


def transformers_for_role(role: str) -> list[dict]:
    """Return transformer metadata for a sub-phrase role.

    Only names declared in TRANSFORMER_CATEGORIES are returned.
    Unmapped roles return an empty list.
    """
    names = ROLE_DEFAULT_TRANSFORMERS.get(role, [])
    return [
        {"name": name, "category": TRANSFORMER_CATEGORIES[name]}
        for name in names
        if name in TRANSFORMER_CATEGORIES
    ]


def compute_subphrases(phrase_index: int, phrase_start_step: int) -> list[dict]:
    """Deterministic sub-phrase segmentation.

    [PLACEHOLDER] Fixed 4+8+4 bar layout (build/hold/release).
    Will be replaced by landscape-driven segmentation in a later phase.
    """
    layout = [
        ("build",   4),
        ("hold",    8),
        ("release", 4),
    ]
    assert sum(length for _, length in layout) == PHRASE_BARS
    segments: list[dict] = []
    bar  = 1
    step = phrase_start_step
    for role, length_bars in layout:
        length_steps = length_bars * STEPS_PER_BAR
        segments.append({
            "phrase_index": phrase_index,
            "start_bar":    bar,
            "start_step":   step,
            "length_bars":  length_bars,
            "length_steps": length_steps,
            "role":         role,
            "transformers": transformers_for_role(role),
        })
        bar  += length_bars
        step += length_steps
    return segments
