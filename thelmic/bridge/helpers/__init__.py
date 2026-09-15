"""Mechanical helpers — work for any musical form.

Split out of the monolithic thelmic.agent_helpers into purpose-named
submodules so an aesthetic pack can import only what it needs.
"""
from .discovery   import find_track, find_device, ensure_device, health_check
from .eq          import (hz_to_norm, norm_to_hz, set_eq_band, set_band_frequency,
                          disable_all_eq_bands,
                          EQ8_HP_48, EQ8_HP_12, EQ8_LOW_SHELF, EQ8_BELL,
                          EQ8_NOTCH, EQ8_HIGH_SHELF, EQ8_LP_12, EQ8_LP_48,
                          EQ8_FREQ_LOW_HZ, EQ8_FREQ_HIGH_HZ,
                          EQ8_LOW_SHELF_GUESS,
                          EQ8_HP_12_GUESS, EQ8_HP_48_GUESS,
                          EQ8_LP_12_GUESS, EQ8_LP_48_GUESS)
from .transport   import hard_reset, arm_take, disarm_take, ms_to_beats
from .params      import (set_param, describe_param, safe_set_param,
                          parse_display, param_with_display, set_by_display,
                          SemanticParam, resolve_semantic_param)
from .sidechain   import sidechain_pump
from .midi        import to_clip_notes, repeat_pattern
from .shading     import (SceneShading, ShadingConfig, apply_shading,
                          color_for_clip, density_score, score_to_col,
                          PALETTE_COLS, PALETTE_ROWS, INTENSITY_ROW_ORDER)

__all__ = [
    "find_track", "find_device", "ensure_device", "health_check",
    "hz_to_norm", "norm_to_hz", "set_eq_band", "set_band_frequency",
    "disable_all_eq_bands",
    "EQ8_HP_48", "EQ8_HP_12", "EQ8_LOW_SHELF", "EQ8_BELL",
    "EQ8_NOTCH", "EQ8_HIGH_SHELF", "EQ8_LP_12", "EQ8_LP_48",
    "EQ8_FREQ_LOW_HZ", "EQ8_FREQ_HIGH_HZ",
    "EQ8_LOW_SHELF_GUESS",
    "EQ8_HP_12_GUESS", "EQ8_HP_48_GUESS", "EQ8_LP_12_GUESS", "EQ8_LP_48_GUESS",
    "hard_reset", "arm_take", "disarm_take", "ms_to_beats",
    "set_param", "describe_param", "safe_set_param",
    "parse_display", "param_with_display", "set_by_display",
    "SemanticParam", "resolve_semantic_param",
    "sidechain_pump",
    "to_clip_notes", "repeat_pattern",
    "SceneShading", "ShadingConfig", "apply_shading",
    "color_for_clip", "density_score", "score_to_col",
    "PALETTE_COLS", "PALETTE_ROWS", "INTENSITY_ROW_ORDER",
]
