"""Thelmic v1.01 server.

Only the v1.0 path is active. The server is behaviour-transparent plumbing:
it exposes state, transport, UI, and MIDI output for final events produced by
the versioned note generation chain.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import threading
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from thelmic.bank_generator import Bank, BARS_PER_PHRASE, PHRASES_PER_BANK
from thelmic.landscape_map import ANCHORS, DOMAIN_MAX, DOMAIN_MIN, LandscapeMap
from thelmic.midi_out import LAYER_CHANNELS, MIDIOut, list_output_ports
from thelmic.motif_engine import VERSION as MOTIF_ENGINE_VERSION
from thelmic.motif_engine import empty_future_motifs, motifs_for_events, validate_motif_contract
from thelmic.note_generation_chain import VERSION as NOTE_GENERATION_VERSION
from thelmic.note_generation_chain import BANK_STEPS, generate_bank, structure_frames
from thelmic.stream_engine import VERSION as STREAM_ENGINE_VERSION
from thelmic.transformer_engine import VERSION as TRANSFORMER_ENGINE_VERSION
from thelmic.transformer_engine import execute_transformers
from thelmic.heat_model import INERTIA_K as _HEAT_INERTIA_K
from thelmic.heat_model import response_curve as heat_response_curve
from thelmic.heat_model import mappings as compute_heat_mappings
from thelmic.subphrase_engine import (
    TRANSFORMER_CATEGORIES as _TRANSFORMER_CATEGORIES,
    ROLE_DEFAULT_TRANSFORMERS as _ROLE_DEFAULT_TRANSFORMERS,
    transformers_for_role as _transformers_for_role,
    compute_subphrases as _compute_subphrases,
)
from thelmic.landscape_trajectory import LandscapeTrajectory
from thelmic.dimension_engine import compute as _compute_dimensions
from thelmic.archetypes import RhythmicArchetype
from thelmic.phrase_engine import pending_archetype_for


import importlib
import sys as _sys


def _reload_generation_modules() -> None:
    """Hot-reload all generation and voice modules.

    Use this when you change a voice file, dimension_engine, phrase_arc, etc.
    and want the new code to take effect at the next bank boundary without
    restarting the server (and losing the MIDI connection).

    After calling this, the next generate_bank() call uses the new code.
    Already-playing banks are not affected — MIDI continues uninterrupted.
    """
    import thelmic.dimension_engine
    import thelmic.phrase_arc
    import thelmic.anticipation_engine
    import thelmic.phrase_engine
    import thelmic.archetypes
    import thelmic.voices.kick
    import thelmic.voices.snare
    import thelmic.voices.hat
    import thelmic.voices.bass
    import thelmic.voices.hook
    import thelmic.voices.call
    import thelmic.voices.response
    import thelmic.voices.ghost_32nd
    import thelmic.note_generation_chain

    # Reload in dependency order (leaves before root)
    for mod in [
        thelmic.archetypes,
        thelmic.dimension_engine,
        thelmic.phrase_arc,
        thelmic.anticipation_engine,
        thelmic.phrase_engine,
        thelmic.voices.kick,
        thelmic.voices.snare,
        thelmic.voices.hat,
        thelmic.voices.bass,
        thelmic.voices.hook,
        thelmic.voices.call,
        thelmic.voices.response,
        thelmic.voices.ghost_32nd,
        thelmic.note_generation_chain,
    ]:
        importlib.reload(mod)

    # Re-bind the names this server module imported from those modules
    global generate_bank, structure_frames
    global BANK_STEPS
    import thelmic.note_generation_chain as _ngc
    generate_bank    = _ngc.generate_bank
    structure_frames = _ngc.structure_frames
    BANK_STEPS       = _ngc.BANK_STEPS


THELMIC_VERSION = "v1.01"
MUSIC_RULES_VERSION = "v1.0"
PRESSION_ENGINE_VERSION = "v0.9-disabled"
TEST_CONTRACT_VERSION = "v1.0"

_ROOT = Path(__file__).resolve().parent
_STATIC = _ROOT / "static"
_landscape_seed: int = 1103
_LANDSCAPE_MAP: LandscapeMap = LandscapeMap(seed=_landscape_seed)
_trajectory: LandscapeTrajectory = LandscapeTrajectory(landscape=_LANDSCAPE_MAP)
# Track committed archetype for boundary-commitment logic
_active_archetype: RhythmicArchetype | None = None

# ── Heat state (server-level globals; logic lives in heat_model.py) ───────────
_heat_target:   float  = 0.5    # raw dial position [0, 1]
_heat_applied:  float  = 0.5    # inertia-smoothed applied value [0, 1]


def _heat_state_dict() -> dict:
    return {
        "target":   _heat_target,
        "applied":  _heat_applied,
        "response": heat_response_curve(_heat_applied),
        **compute_heat_mappings(_heat_applied),
    }


def _dimensions_dict() -> dict:
    """Serialise current v1.2 Dimensions for the state payload."""
    d  = _compute_dimensions(_trajectory, _heat_applied)
    sr = _trajectory.active_feature().signature_rhythm
    return {
        "stability":  round(d.stability, 3),
        "pressure":   round(d.pressure,  3),
        "sparsity":   round(d.sparsity,  3),
        "release":    round(d.release,   3),
        "emphasis":   round(d.emphasis,  3),
        "active_archetype": _active_archetype.value if _active_archetype else None,
        "rhythmic_identity": {
            "id":               sr.id,
            "root_note":        sr.root_note,
            "bass_steps":       list(sr.bass_steps),
            "density_bias":     round(sr.density_bias,     3),
            "syncopation_bias": round(sr.syncopation_bias, 3),
            "stability_bias":   round(sr.stability_bias,   3),
        },
    }


def _set_landscape_seed(seed: int) -> None:
    """Replace the active landscape map with a new seeded terrain."""
    global _landscape_seed, _LANDSCAPE_MAP, _trajectory
    _landscape_seed = max(0, min(0xFFFF_FFFF, int(seed)))
    _LANDSCAPE_MAP  = LandscapeMap(seed=_landscape_seed)
    _trajectory     = LandscapeTrajectory(
        landscape=_LANDSCAPE_MAP, x=_trajectory.x, y=_trajectory.y,
    )

app = FastAPI()
app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")

_log = logging.getLogger(__name__)

_clients: set[WebSocket] = set()
_playing = False
_bpm = 174.0
_bank_index = 0
_playhead_step = 0
_bank_started_at_ms  = 0.0
_pause_offset_ms     = 0.0   # ms elapsed in current bank at last stop; 0 = start of bank
def _active_sr():
    return _trajectory.active_feature().signature_rhythm


_banks_initialised = False
_init_done_event   = threading.Event()


def _init_full_banks() -> None:
    """No-op check — full bank init is now purely non-blocking.

    State calls return immediately with whatever banks are available.
    The background thread upgrades from bare to full banks and broadcasts.
    """
    pass   # background thread handles init; never block the event loop


def _background_init_banks() -> None:
    """Generate full-voice banks in a background thread so startup is instant."""
    global _current_bank, _next_bank_preview, _banks_initialised
    import time as _t
    # Lower thread priority so bank generation doesn't starve the interactive session.
    try:
        import os
        os.nice(10)   # Unix: lower niceness → lower priority
    except (AttributeError, OSError):
        try:
            import ctypes
            ctypes.windll.kernel32.SetThreadPriority(-2, -15)  # Windows: THREAD_PRIORITY_IDLE
        except Exception:
            pass
    t0 = _t.perf_counter()
    try:
        # Generate bank 0 first — client can start playing immediately after this.
        _log.info("startup: generating bank 0...")
        t1 = _t.perf_counter()
        new_cur = _full_generate_bank(0)
        _log.info("startup: bank 0 done in %.0fms", (_t.perf_counter()-t1)*1000)
        with _state_lock:
            _current_bank = new_cur
        _banks_initialised = True
        _bank_dirty_set()
        _queue_broadcast(include_bank=True)

        # Generate bank 1 in the same background thread — client already has bank 0.
        _log.info("startup: generating bank 1...")
        t2 = _t.perf_counter()
        new_prev = _full_generate_bank(1)
        _log.info("startup: bank 1 done in %.0fms", (_t.perf_counter()-t2)*1000)
        with _state_lock:
            _next_bank_preview = new_prev
        _log.info("startup: full init complete in %.0fms total", (_t.perf_counter()-t0)*1000)
    except Exception:
        _log.exception("Background bank init failed")
    finally:
        _init_done_event.set()


def _full_generate_bank(bank_idx: int, **kwargs):
    """Generate a bank with current dims — convenience wrapper."""
    return generate_bank(
        bank_idx,
        dims=_compute_dimensions(_trajectory, _heat_applied),
        signature_rhythm=_active_sr(),
        previous_active_archetype=_active_archetype,
        phrases_until_drop=_trajectory.phrases_until_next_drop(),
        heat=_heat_applied,
        **kwargs,
    )


_bank_dirty: bool = False    # signals UI to flush and re-merge current bank range
_bank_generation: int = 0   # incremented on every bank regeneration; client compares

# UI event log — circular buffer of recent UI inputs with their musical effect.
_ui_event_log: list[dict] = []
_UI_EVENT_LOG_MAX = 32

def _log_ui_event(kind: str, detail: str, playhead_step: int | None = None) -> None:
    """Record a UI input event with its musical effect for display in the UI."""
    import time as _time
    entry = {
        "ts_ms":         int(_time.time() * 1000),
        "kind":          kind,
        "detail":        detail,
        "global_step":   (_bank_index * BANK_STEPS + (playhead_step or 0)),
        "feature":       _feature_display_name(_trajectory.active_feature()),
        "archetype":     (_active_archetype.value if _active_archetype
                          else pending_archetype_for(_trajectory.active_feature().signature_rhythm).value),
        "sparsity":      round(_compute_dimensions(_trajectory, _heat_applied).sparsity, 3),
    }
    _ui_event_log.append(entry)
    if len(_ui_event_log) > _UI_EVENT_LOG_MAX:
        _ui_event_log.pop(0)


def _bank_dirty_set() -> None:
    """Mark bank dirty and bump generation counter atomically."""
    global _bank_dirty, _bank_generation
    _bank_dirty       = True
    _bank_generation += 1
_position_dirty: bool = False  # set when position changes; consumed per bar in play loop

# Journey system.
#
# A "trace" is one drag gesture = one phrase (16 bars).
# The trace path is interpolated to 16 positions, one per bar.
# Each bar boundary the trajectory advances to the next position in the trace.
# Multiple traces queue up as sequential phrases.
# A click (set_position with drag=False) clears all queued traces.
#
# _journey_traces: list of pending phrases (each = list of 16 (x,y) positions)
# _active_trace:   the phrase currently being played bar by bar
# _trace_bar:      which bar within _active_trace (0-15)
_journey_traces: list[list[tuple[float, float]]] = []
_active_trace:   list[tuple[float, float]] | None = None
_trace_bar:      int = 0


def _interpolate_trace(points: list[dict], n: int = 16) -> list[tuple[float, float]]:
    """Resample a drag path to exactly n evenly-spaced positions."""
    if not points:
        return []
    if len(points) == 1:
        return [(points[0]["x"], points[0]["y"])] * n
    # Compute cumulative arc-lengths
    xs = [p["x"] for p in points]
    ys = [p["y"] for p in points]
    dists = [0.0]
    for i in range(1, len(xs)):
        d = ((xs[i]-xs[i-1])**2 + (ys[i]-ys[i-1])**2) ** 0.5
        dists.append(dists[-1] + d)
    total = dists[-1]
    result = []
    for j in range(n):
        t  = (j / (n - 1)) * total if n > 1 else 0.0
        # Find segment
        for k in range(len(dists) - 1):
            if dists[k] <= t <= dists[k+1]:
                seg = dists[k+1] - dists[k]
                frac = ((t - dists[k]) / seg) if seg > 0 else 0.0
                rx = xs[k] + frac * (xs[k+1] - xs[k])
                ry = ys[k] + frac * (ys[k+1] - ys[k])
                result.append((rx, ry))
                break
        else:
            result.append((xs[-1], ys[-1]))
    return result


def _advance_journey(bar_abs: int) -> None:
    """Called at each bar boundary during playback.

    Advances through the active trace (one bar = one position along the trace).
    When the trace ends, loads the next queued trace.
    """
    global _active_trace, _trace_bar, _journey_traces
    # Load next trace if none active
    if _active_trace is None:
        if not _journey_traces:
            return
        _active_trace = _journey_traces.pop(0)
        _trace_bar    = 0
    # Advance to next position in the trace
    if _trace_bar >= len(_active_trace):
        _active_trace = None
        return
    next_x, next_y = _active_trace[_trace_bar]
    _trace_bar += 1
    _trajectory.move_to(next_x, next_y)
    # Regraft from the next bar so the current bar keeps its events.
    from_bar = (bar_abs % 16) + 2
    _regraft_current_bank_from_bar(min(16, from_bar))
    _bank_dirty_set()
    _queue_broadcast(include_bank=True)
    if _trace_bar == len(_active_trace):
        _active_trace = None   # trace complete — next bar loads the next phrase


def _playing_bar() -> int:
    """Return the 1-indexed bar currently being played (1–16), or 1 if unknown."""
    if not _bank_started_at_ms or not _playing:
        return 1
    bank_duration_ms = (60.0 / _bpm) * 4 * BARS_PER_PHRASE * PHRASES_PER_BANK * 1000
    elapsed_ms       = time.time() * 1000 - _bank_started_at_ms
    frac             = max(0.0, min(1.0, elapsed_ms / bank_duration_ms))
    return int(frac * 16) + 1   # 1–16


def _regraft_current_bank_from_bar(from_bar: int) -> None:
    """Replace events in the current bank from `from_bar` onward.

    This gives immediate response to position changes: the bars already
    played keep their events; upcoming bars are regenerated with new dims.
    from_bar is 1-indexed (bar 1 = first bar of the bank).
    """
    global _current_bank
    if from_bar < 1 or from_bar > 16:
        return
    dims = _compute_dimensions(_trajectory, _heat_applied)
    sr   = _trajectory.active_feature().signature_rhythm
    # Re-generate a fresh bank with new dims
    new_bank = generate_bank(
        _bank_index, dims=dims, is_drop_phrase=False,
        signature_rhythm=sr,
        previous_active_archetype=_active_archetype,
        phrases_until_drop=_trajectory.phrases_until_next_drop(),
        heat=_heat_applied,
    )
    # Splice: keep events from bars < from_bar in the original bank,
    # replace bars >= from_bar with events from the new bank.
    with _state_lock:
        for phrase in _current_bank.phrases:
            phrase.events = [
                e for e in phrase.events if e.bar_index < from_bar
            ]
        for phrase_new in new_bank.phrases:
            for e in phrase_new.events:
                if e.bar_index >= from_bar:
                    # Add to the matching phrase in the current bank
                    phrase_idx = (e.bar_index - 1) // 4   # BARS_PER_PHRASE = 4
                    if 0 <= phrase_idx < len(_current_bank.phrases):
                        _current_bank.phrases[phrase_idx].events.append(e)


def _feature_display_name(feature) -> str:
    """Short human-readable name for a terrain feature."""
    t = feature.type
    if t == "oak":   return "Oak"
    if t == "nott":  return "Nott"
    # chaos_peak_0 → C1, chaos_peak_1 → C2, etc.
    if t == "chaos_peak":
        try:
            idx = int(feature.id.split("chaos_peak_")[1].split(":")[0])
            return f"C{idx + 1}"
        except (IndexError, ValueError):
            return "C?"
    return t.capitalize()


def _active_address() -> str:
    """Current parametric address: seed/feature/heat."""
    feat = _trajectory.active_feature()
    name = _feature_display_name(feat)
    return f"{_landscape_seed}/{name}/{_heat_applied:.2f}"

# Cheap bare banks at startup — no voice dims, just kick/snare/hat.
# Full banks are generated on first WebSocket connect (_init_full_banks).
_current_bank: Bank      = generate_bank(0)
_next_bank_preview: Bank = generate_bank(1)
_midi: MIDIOut | None = None
_midi_port_name: str | None = None

# Persist last-used MIDI port so server restart reconnects automatically.
# Ableton/DAW keeps the virtual port alive between server restarts; without
# auto-reconnect the user must drop and restart Ableton to restore MIDI flow.
_MIDI_CONFIG_PATH          = _ROOT / ".midi_port"
_MIDI_CHANNELS_CONFIG_PATH = _ROOT / ".midi_channels"
_PRESSION_CONFIG_PATH      = _ROOT / ".pression_channel"

# Pression CC state
_pression_channel: int = 13   # 0-indexed (DAW ch 14); configurable and persisted
_mapping_mode: str | None = None  # dimension being mapped ("stability" etc.) or None


def _load_pression_config() -> None:
    """Load persisted pression channel from disk."""
    global _pression_channel
    try:
        _pression_channel = int(_PRESSION_CONFIG_PATH.read_text(encoding="utf-8").strip())
        # Also update PRESSION_CC to use the loaded channel
        from thelmic.midi_out import PRESSION_CC, PRESSION_DIMS
        for dim in PRESSION_DIMS:
            if dim in PRESSION_CC:
                old_ch, cc_num = PRESSION_CC[dim]
                PRESSION_CC[dim] = (_pression_channel, cc_num)
    except (FileNotFoundError, ValueError, Exception):
        pass


def _save_pression_config() -> None:
    try:
        _PRESSION_CONFIG_PATH.write_text(str(_pression_channel), encoding="utf-8")
    except OSError:
        pass


def _get_pression_bar_values() -> dict[str, float]:
    """Pression values for the CURRENT BAR being played (0-1 scaled).
    Used for per-bar CC emission — gives the phrase-arc-shaped CC output.
    """
    bar    = _playing_bar() - 1   # 0-indexed
    ptd    = _trajectory.phrases_until_next_drop()
    dims   = _compute_dimensions(_trajectory, _heat_applied)
    pv     = _compute_pression_bar(bar, 16, ptd, dims, _heat_applied)
    return {k: v / 127.0 for k, v in pv.items()}   # scale back to 0-1 for MIDI helper


import math as _math


def _pression_step_values(step_in_bar: int, bar_pression: dict,
                          kick_steps: frozenset, snare_steps: frozenset) -> dict[str, float]:
    """Per-step (0-15) pression expression within a bar.

    Rules (musical_rules.md — Pression Lane Dynamics, per-step formulas):
    Envelope shapes driven by distance to last kick/snare, metrical hierarchy,
    and archetype event grid. Decay rates tuned for 174 BPM hard dance.

    Returns values [0, 1] (scaled for MIDI: multiply by 127).
    """
    s = step_in_bar
    hit_steps = kick_steps | snare_steps

    # Steps since last hit (backward distance, wrapping)
    last_hit = min(((s - h) % 16) for h in hit_steps) if hit_steps else 16

    # Metrical hierarchy weight (1.0 = strongest, 0.25 = weakest)
    if s in {0, 8}:
        metro = 1.0       # beats 1 and 3
    elif s in {4, 12}:
        metro = 0.75      # beats 2 and 4
    elif s % 2 == 0:
        metro = 0.50      # even 8th notes
    else:
        metro = 0.25      # off-beat 16ths

    # Base phrase-level values
    bp = bar_pression   # computed by _compute_pression_bar, range 0-127

    # PRESSURE — peaks on kick, decays with half-life ~2.5 steps
    kick_on   = 1.0 if s in kick_steps else 0.0
    decay_p   = _math.exp(-last_hit / 2.5)
    base_p    = 64 + 32 * metro
    pressure  = base_p * decay_p + kick_on * 30
    pressure  = max(40, min(127, int(pressure + bp.get("pressure", 64) * 0.3)))

    # STABILITY — high on beats, dips on off-beats
    stability = 100 * metro + 20 * _math.exp(-last_hit / 3.0)
    stability = max(30, min(120, int(stability * (bp.get("stability", 90) / 90))))

    # SPARSITY — inversely dense around kicks/snares; opens on off-beats
    density_pull = _math.exp(-last_hit / 2.0)
    sparsity     = 90 - 60 * density_pull
    sparsity     = max(20, min(100, int(sparsity * (bp.get("sparsity", 70) / 70))))

    # RELEASE — blooms 1-2 steps AFTER a hit (reverb tail); dry on the hit itself
    if s in hit_steps:
        release = 20   # dry transient — reverb hasn't opened yet
    else:
        tail_offset = max(0, last_hit - 1)
        release     = 20 + 80 * _math.exp(-tail_offset / 4.0)
    release = max(15, min(110, int(release * (bp.get("release", 35) / 35 + 0.1))))

    # EMPHASIS — metrical energy + kick punch; slight dip before beat 3 for tension
    pre_beat3_dip = -20 if s == 7 else 0
    emphasis      = 50 + 55 * metro * _math.exp(-last_hit / 3.5) + pre_beat3_dip
    emphasis      = max(30, min(127, int(emphasis * (bp.get("emphasis", 70) / 70))))

    return {
        "stability": stability / 127,
        "pressure":  pressure  / 127,
        "sparsity":  sparsity  / 127,
        "release":   release   / 127,
        "emphasis":  emphasis  / 127,
    }


def _get_pression_bar_step_values(step_in_bar: int) -> dict[str, float]:
    """Pression values for a specific 16th-note step within the current bar.
    Combines:
      1. Phrase-arc value (evolves bar-by-bar toward/away from drop)
      2. Step-level envelope (kick/snare grid shapes within the bar)
    """
    bar  = max(0, _playing_bar() - 1)   # 0-15 within current phrase
    ptd  = _trajectory.phrases_until_next_drop()
    dims = _compute_dimensions(_trajectory, _heat_applied)
    # is_post_drop: the phrase immediately after a drop has the release burst
    is_post = (_active_archetype is not None and ptd >= 2
               and bar < 4)   # first 4 bars of phrase = post-drop if archetype set
    bar_pv  = _compute_pression_bar(bar, 16, ptd, dims, _heat_applied,
                                    is_post_drop=is_post)

    # Get current archetype's kick/snare steps for envelope shaping
    from thelmic.archetypes import PATTERNS, select_archetype
    from thelmic.phrase_engine import pending_archetype_for
    arch = _active_archetype or pending_archetype_for(_trajectory.active_feature().signature_rhythm)
    pat  = PATTERNS.get(arch)
    kick_s  = pat.kick_steps  if pat else frozenset({0, 4, 8, 12})
    snare_s = pat.snare_steps if pat else frozenset({4, 12})

    return _pression_step_values(step_in_bar, bar_pv, kick_s, snare_s)


def _get_pression_values() -> dict[str, float]:
    """Current bar-level pression values [0,1] — used by panel display."""
    dims = _compute_dimensions(_trajectory, _heat_applied)
    return {
        "stability": dims.stability,
        "pressure":  dims.pressure,
        "sparsity":  dims.sparsity,
        "release":   dims.release,
        "emphasis":  dims.emphasis,
    }


def _compute_pression_bar(bar: int, n_bars: int, phrases_until_drop: int,
                           dims, heat: float, is_post_drop: bool = False) -> dict:
    """Compute pression values for one bar within a phrase.

    Rules (musical_rules.md — Pression Lane Dynamics):
    - PRESSURE builds toward 127 at drop; resets to 20 then rebuilds post-drop
    - SPARSITY climbs as instrumentation thins; snaps to 0 at drop
    - STABILITY collapses pre-drop, snaps to 120 at drop, settles to groove
    - RELEASE stays dry during build, bursts at drop, decays post-drop
    - EMPHASIS closes pre-drop (filter down), opens at drop, decays
    """
    t = bar / max(n_bars - 1, 1)   # 0→1 over the phrase

    if is_post_drop:
        return {
            "pressure":  int(20 + t * 50),
            "sparsity":  int(t * 60),
            "stability": int(120 - t * 30),
            "release":   int(127 - t * 92),
            "emphasis":  int(127 - t * 57),
        }

    if phrases_until_drop == 0:
        # Final phrase: maximum anticipation
        return {
            "pressure":  min(127, int(60 + t * 67)),
            "sparsity":  min(127, int(70 + t * 57)),
            "stability": max(0,   int(100 - t * 100)),
            "release":   0 if bar >= 14 else 35,
            "emphasis":  max(0,   int(80 - t * 80)),
        }
    elif phrases_until_drop == 1:
        return {
            "pressure":  int(50 + t * 30),
            "sparsity":  int(60 + t * 20),
            "stability": int(100 - t * 20),
            "release":   35,
            "emphasis":  int(70 - t * 20),
        }
    else:
        # Groove: steady with dimension values from current terrain
        return {
            "pressure":  int(dims.pressure  * 70 + 30),
            "sparsity":  int(dims.sparsity  * 70 + 30),
            "stability": int(dims.stability * 40 + 70),
            "release":   35,
            "emphasis":  int(60 + heat * 20),
        }


def _build_pression_timeline(bank_index: int) -> list[dict]:
    """Pression CC values per bar for the current and next bank.

    One entry per bar (every 16 steps). Values evolve across the phrase
    according to the pression dynamics rules in musical_rules.md.
    """
    dims = _compute_dimensions(_trajectory, _heat_applied)
    ptd  = _trajectory.phrases_until_next_drop()
    # Get archetype for step-level envelope shaping
    from thelmic.archetypes import PATTERNS
    from thelmic.phrase_engine import pending_archetype_for
    arch = _active_archetype or pending_archetype_for(_trajectory.active_feature().signature_rhythm)
    pat  = PATTERNS.get(arch)
    kick_s  = pat.kick_steps  if pat else frozenset({0, 4, 8, 12})
    snare_s = pat.snare_steps if pat else frozenset({4, 12})

    entries = []
    for bank_offset in range(1):   # current bank only — keeps payload small
        bidx = bank_index + bank_offset
        # Post-drop arc applies in the first 4 bars after a drop has occurred
        bank_is_post_drop = (_active_archetype is not None and ptd >= 2 and bank_offset == 0)
        for bar in range(16):
            # Bars 0-3 post-drop get the release burst arc
            is_post = bank_is_post_drop and bar < 4
            bar_pv = _compute_pression_bar(
                bar, 16, max(0, ptd - bank_offset), dims, _heat_applied,
                is_post_drop=is_post,
            )
            # Compact: 5 values packed as a short array [s,p,sp,r,e] per step
            # One entry per BAR with all 16 steps inlined — avoids per-entry key overhead
            step_vals = []
            for step in range(16):
                sv = _pression_step_values(step, bar_pv, kick_s, snare_s)
                step_vals.append([
                    int(sv["stability"] * 127),
                    int(sv["pressure"]  * 127),
                    int(sv["sparsity"]  * 127),
                    int(sv["release"]   * 127),
                    int(sv["emphasis"]  * 127),
                ])
            entries.append({
                "gs":    bidx * BANK_STEPS + bar * 16,   # global_step of bar start
                "steps": step_vals,                       # 16×5 compact array
            })
    return entries


def _load_saved_channels() -> None:
    """Load persisted MIDI channel mapping and apply to LAYER_CHANNELS."""
    try:
        import json as _json
        import thelmic.midi_out as _mo
        saved = _json.loads(_MIDI_CHANNELS_CONFIG_PATH.read_text(encoding="utf-8"))
        for layer, ch in saved.items():
            if layer in _mo.LAYER_CHANNELS:
                _mo.LAYER_CHANNELS[layer] = int(ch)
    except (FileNotFoundError, Exception):
        pass


def _save_channels() -> None:
    """Persist current LAYER_CHANNELS mapping to disk."""
    try:
        import json as _json
        _MIDI_CHANNELS_CONFIG_PATH.write_text(
            _json.dumps(LAYER_CHANNELS, indent=2), encoding="utf-8"
        )
    except OSError:
        pass


# Apply persisted channel mapping on startup. Save defaults on first run
# so the file always exists with the current defaults.
_load_saved_channels()
_save_channels()
_load_pression_config()

def _load_saved_midi_port() -> str | None:
    try:
        return _MIDI_CONFIG_PATH.read_text(encoding="utf-8").strip() or None
    except FileNotFoundError:
        return None

def _save_midi_port(name: str | None) -> None:
    try:
        _MIDI_CONFIG_PATH.write_text(name or "", encoding="utf-8")
    except OSError:
        pass

def _try_open_midi(port_name: str) -> bool:
    """Attempt to open a MIDI port. Returns True on success."""
    global _midi, _midi_port_name
    try:
        m = MIDIOut(port_name)
        _midi = m
        _midi_port_name = m.port_name
        _save_midi_port(m.port_name)
        return True
    except Exception as e:
        _log.warning("MIDI port '%s' unavailable: %s", port_name, e)
        return False

# Auto-connect to last-used port on startup
_saved_port = _load_saved_midi_port()
if _saved_port:
    _try_open_midi(_saved_port)
_play_thread: threading.Thread | None = None
_stop_event = threading.Event()
_state_lock = threading.Lock()
_broadcast_loop: asyncio.AbstractEventLoop | None = None

def _idle_thread(target, *args, **kwargs) -> threading.Thread:
    """Start a daemon thread at IDLE CPU priority."""
    def _wrapper():
        try:
            import ctypes
            ctypes.windll.kernel32.SetThreadPriority(-2, -15)  # THREAD_PRIORITY_IDLE
        except Exception:
            try:
                import os; os.nice(19)
            except Exception:
                pass
        target(*args, **kwargs)
    t = threading.Thread(target=_wrapper, daemon=True)
    t.start()
    return t


# Kick off background bank init now — all module-level state is defined above.
threading.Thread(target=_background_init_banks, daemon=True).start()


def _state(include_bank: bool = True) -> dict:
    global _bank_dirty
    _init_full_banks()   # no-op if already done
    with _state_lock:
        bank       = _current_bank
        bank_index = _bank_index
        preview    = _next_bank_preview
    dirty      = _bank_dirty
    _bank_dirty = False   # consumed

    # Guard: if preview is stale (bank mismatch), re-derive outside the lock.
    # This can happen if external code restores bank_index without updating preview.
    if preview.bank_index != bank_index + 1:
        preview = generate_bank(
            bank_index + 1,
            dims=_compute_dimensions(_trajectory, _heat_applied),
            signature_rhythm=_trajectory.active_feature().signature_rhythm,
            previous_active_archetype=_active_archetype,
        )
    motifs = motifs_for_events(bank.all_events()) + empty_future_motifs()
    validate_motif_contract(motifs)
    subphrases = _compute_subphrases(bank_index, bank_index * BANK_STEPS)
    _bank_modified, tx_results = execute_transformers(bank, motifs, subphrases)
    state = {
        "type": "state",
        "thelmic_version": THELMIC_VERSION,
        "music_rules_version": MUSIC_RULES_VERSION,
        "note_generation_chain_version": NOTE_GENERATION_VERSION,
        "motif_engine_version": MOTIF_ENGINE_VERSION,
        "stream_engine_version": STREAM_ENGINE_VERSION,
        "pression_engine_version": PRESSION_ENGINE_VERSION,
        "test_contract_version": TEST_CONTRACT_VERSION,
        "runtime_mode": "simple continuous v1 output",
        "playing": _playing,
        "playhead_step": _playhead_step,
        "bank_started_at_ms": _bank_started_at_ms,
        "bank_duration_ms": (60.0 / _bpm) * 4 * BARS_PER_PHRASE * PHRASES_PER_BANK * 1000,
        "bpm": _bpm,
        "landscape_position": 0.0,
        "landscape_seed": _landscape_seed,
        "landscape_xy":       {"x": _trajectory.x, "y": _trajectory.y},
        "active_feature_name": _feature_display_name(_trajectory.active_feature()),
        "address":             _active_address(),
        "bank_dirty":          dirty,
        "bank_generation":     _bank_generation,
        "heat": _heat_state_dict(),
        "dimensions": _dimensions_dict(),
        "selected_archetype": _active_archetype.value if _active_archetype else "startup",
        "active_archetype":   _active_archetype.value if _active_archetype else "startup",
        "pending_archetype":  pending_archetype_for(_trajectory.active_feature().signature_rhythm).value,
        "archetype": _active_archetype.value if _active_archetype else "startup",
        "ui_event_log":    list(_ui_event_log),
        "pression": {
            "channel":      _pression_channel,
            "mapping_mode": _mapping_mode,
            "values":       _get_pression_values(),
            "timeline":     _build_pression_timeline(bank_index),
        },
        "bank_count": bank_index + 1,
        "bank_slot": 1,
        "bank_total": PHRASES_PER_BANK,
        "quantize_bars": BARS_PER_PHRASE,
        "midi_port": _midi_port_name,
        "midi_cc_port": None,
        "midi_layer_channels": LAYER_CHANNELS,
        "pression_disabled": True,
        "runtime": {
            "output": "simple continuous v1 output",
            "v0_9_engine_enabled": False,
            "legacy_fallback_enabled": False,
            "post_generation_rescue_enabled": False,
            "pression_enabled": False,
            "event_count": len(bank.all_events()),
        },
        "force": {},
        "behaviour": {},
        "transition": {},
        "anticipation": 0.0,
        "release_pressure": 0.0,
        "instability": 0.0,
        "control_vs_chaos": 1.0,
        "resolution_likelihood": 1.0,
        "transformer_engine_version": TRANSFORMER_ENGINE_VERSION,
        # Only send phrase/bar boundary frames (not all 256) — reduces payload ~93%.
        # The UI draws bar lines and phrase labels from these; it doesn't need every step.
        "structure_frames":          [f.to_dict() for f in structure_frames(bank_index)
                                       if f.is_phrase_start or f.is_bar_start or f.is_drop_prep or f.is_drop],
        "upcoming_structure_frames": [f.to_dict() for f in structure_frames(bank_index + 1)
                                       if f.is_phrase_start or f.is_bar_start or f.is_drop_prep or f.is_drop],
        # Slim motif payload — UI only needs type, instrument, phrase_start, state
        "motifs": [{"type": m.type, "instrument": m.instrument,
                    "phrase_start": m.phrase_start, "state": m.state}
                   for m in motifs],
        "subphrases": subphrases,
        "transformer_execution": [r.to_dict() for r in tx_results],
        "next_bank_preview": {
            "bank_index":    preview.bank_index,
            "authoritative": False,
            "bank_events":   _bank_events_list(preview),   # already slimmed
        },
    }
    if include_bank or dirty:
        # Always include bank_events when dirty — the JS flush needs events to
        # merge immediately after clearing the old range.  If we send bank_dirty=True
        # without bank_events the client flushes and gets nothing back.
        state["bank_events"] = _bank_events_list(bank)
    return state


# subphrase_engine and transformer taxonomy imported at top of file


def _bank_events_list(bank: Bank) -> list[dict]:
    """Slim event list — only fields the UI actually reads.
    Full debug fields stripped to keep the WS payload < 50KB per broadcast.
    """
    events = []
    for event in bank.all_events():
        if not event.active:
            continue
        events.append({
            "l": event.layer,             # layer (short key)
            "v": event.velocity,          # velocity
            "g": event.global_step,       # global_step
            "d": round(event.duration, 3) # duration in seconds (for long-note rendering)
        })
    return events


async def _broadcast_state(include_bank: bool = True) -> None:
    if not _clients:
        return
    message = json.dumps(_state(include_bank=include_bank))
    dead: list[WebSocket] = []
    for client in list(_clients):
        try:
            await client.send_text(message)
        except Exception:
            dead.append(client)
    for client in dead:
        _clients.discard(client)


def _queue_broadcast(include_bank: bool = True) -> None:
    loop = _broadcast_loop
    if loop is None or loop.is_closed():
        return
    asyncio.run_coroutine_threadsafe(_broadcast_state(include_bank=include_bank), loop)


def _play_bank_bar_by_bar(bank_start: float) -> tuple[float, bool]:
    """Play the current bank one bar at a time via MIDI.

    Reads _current_bank.phrases fresh before each bar so that position/heat
    changes (regraft) take effect at the next bar boundary (~1.4s at 174 BPM).

    Returns (next_bank_start_time, interrupted).
    """
    from thelmic.bank_generator import BARS_PER_PHRASE
    from thelmic.midi_out import LAYER_CHANNELS, PRESSION_CC, is_grid_midi_event, event_to_abs_tick

    seconds_per_tick = 60.0 / (_bpm * 24)   # TICKS_PER_BEAT = 24
    ticks_per_bar    = 24 * 4                # BEATS_PER_BAR = 4
    n_bars           = BARS_PER_PHRASE * PHRASES_PER_BANK   # 16
    sc_channel, sc_cc = PRESSION_CC["sidechain"]

    _midi.last_playback_interrupted = False

    for bar_num in range(n_bars):
        phrase_idx    = bar_num // BARS_PER_PHRASE
        bar_in_phrase = bar_num % BARS_PER_PHRASE

        # Read CURRENT bank events fresh — reflects any regraft from position change
        with _state_lock:
            phrases = _current_bank.phrases
            phrase  = phrases[phrase_idx] if phrase_idx < len(phrases) else None

        if phrase is None:
            break

        abs_bar_idx    = phrase.phrase_index * BARS_PER_PHRASE + bar_in_phrase
        bar_start_tick = abs_bar_idx * ticks_per_bar
        bar_end_tick   = bar_start_tick + ticks_per_bar

        timeline: list = []
        for event in phrase.events:
            if not is_grid_midi_event(event):
                continue
            tick = event_to_abs_tick(event.time)
            if bar_start_tick <= tick < bar_end_tick:
                on_t  = tick * seconds_per_tick
                off_t = min(on_t + event.duration, bar_end_tick * seconds_per_tick)
                ch    = LAYER_CHANNELS[event.layer]
                timeline.append((on_t,  "on",  ch, event.note, event.velocity))
                timeline.append((off_t, "off", ch, event.note, 0))
                if event.layer == "kick":
                    timeline.append((on_t,  "cc", sc_channel, sc_cc, 127))
                    timeline.append((off_t, "cc", sc_channel, sc_cc, 0))

        timeline.sort(key=lambda x: x[0])

        # Apply heat inertia once per bar
        global _heat_applied
        _heat_applied += (_heat_target - _heat_applied) * _HEAT_INERTIA_K

        stopped = _midi._play_timeline(timeline, bank_start, stop_event=_stop_event)
        if stopped:
            # _play_timeline was interrupted (user stop, not end-of-bar).
            # Mark as interrupted so the play loop does NOT advance the bank.
            _midi.last_playback_interrupted = True
            _midi.all_notes_off()
            return time.perf_counter(), True

    # All bars completed (stop may have been set during last bar by a signal).
    # Return not-interrupted so the play loop advances the bank;
    # the outer while condition will then exit.
    bank_end = bank_start + n_bars * ticks_per_bar * seconds_per_tick
    remaining = bank_end - time.perf_counter()
    if remaining > 0:
        _midi._interruptible_sleep(remaining, _stop_event)
    return bank_end, False


def _play_loop() -> None:
    global _bank_index, _current_bank, _next_bank_preview, _playhead_step, _bank_started_at_ms, _pause_offset_ms, _heat_applied, _active_archetype
    # Consume the pause offset once so the first bank ends at the right wall-clock time.
    # Offset next_start back by how far we already were into the bank; the inner wait
    # loop then runs for only the remaining duration.
    resume_offset_secs = _pause_offset_ms / 1000.0
    _pause_offset_ms = 0.0
    next_start = time.perf_counter() - resume_offset_secs
    while not _stop_event.is_set():
        with _state_lock:
            bank       = _current_bank
            next_index = _bank_index + 1
            _playhead_step = 0

        if _midi is not None:
            try:
                # Bar-by-bar playback: reads _current_bank at every bar boundary.
                # Position changes (which update _current_bank immediately) take
                # effect within one bar (~1.4 s at 174 BPM) rather than waiting
                # the full bank (~22 s).
                def _get_current_bank():
                    with _state_lock:
                        return _current_bank
                next_start = _midi.play_bank_bar_by_bar(
                    _get_current_bank, bpm=_bpm,
                    start_time=next_start, stop_event=_stop_event,
                    on_bar_start=_advance_journey,
                    get_heat=lambda: _heat_applied,
                    get_pression=_get_pression_bar_step_values,
                    get_pression_channel=lambda: _pression_channel,
                    get_mapping_mode=lambda: _mapping_mode,
                )
            except Exception:
                _log.exception("MIDI playback failed")
                next_start = time.perf_counter()
            if getattr(_midi, "last_playback_interrupted", False):
                break
        else:
            seconds_per_bar  = (60.0 / _bpm) * 4          # one bar at current BPM
            n_bars           = BARS_PER_PHRASE * PHRASES_PER_BANK
            bar_start        = next_start
            for _bar in range(n_bars):
                bar_end = bar_start + seconds_per_bar
                while time.perf_counter() < bar_end and not _stop_event.is_set():
                    _heat_applied += (_heat_target - _heat_applied) * _HEAT_INERTIA_K
                    time.sleep(0.02)
                if _stop_event.is_set():
                    break
                # Per-bar: advance journey queue and handle position changes.
                _advance_journey(_bar)
                if _position_dirty:
                    _position_dirty = False
                    _queue_broadcast(include_bank=True)
                bar_start = bar_end
            next_start = bar_start
            if _stop_event.is_set():
                break

        # Advance trajectory BEFORE pre-generating the next preview so that
        # the preview uses the updated velocity/drop-plan state.
        _trajectory.advance_phrase()
        next_dims    = _compute_dimensions(_trajectory, _heat_applied)
        next_is_drop = _trajectory.is_drop_phrase()
        next_sr      = _trajectory.active_feature().signature_rhythm
        new_preview  = generate_bank(
            next_index + 1, dims=next_dims, is_drop_phrase=next_is_drop,
            signature_rhythm=next_sr,
            previous_active_archetype=_active_archetype,
            phrases_until_drop=_trajectory.phrases_until_next_drop(),
            heat=_heat_applied,
        )
        with _state_lock:
            _bank_index        = next_index
            _current_bank      = _next_bank_preview
            _next_bank_preview = new_preview
            _playhead_step     = 0
            _bank_started_at_ms = time.time() * 1000
            if next_is_drop:
                _active_archetype = pending_archetype_for(next_sr)
        _queue_broadcast(include_bank=True)


def _start_playback() -> None:
    global _playing, _play_thread, _bank_started_at_ms, _next_bank_preview
    if _playing:
        return
    # Ensure full banks are ready before starting — background init may still be running.
    # On first-ever start this waits up to 5s; all subsequent starts return immediately.
    if not _banks_initialised:
        _init_done_event.wait(timeout=5.0)
    _stop_event.clear()
    _playing = True
    # Resume from saved position: set bank_started_at_ms so the client's interpolation
    # immediately shows the correct step rather than jumping to 0.
    _bank_started_at_ms = time.time() * 1000 - _pause_offset_ms
    # Ensure preview is current for the actual bank_index.
    with _state_lock:
        _dims = _compute_dimensions(_trajectory, _heat_applied)
        _next_bank_preview = generate_bank(
            _bank_index + 1, dims=_dims,
            signature_rhythm=_trajectory.active_feature().signature_rhythm,
            previous_active_archetype=_active_archetype,
        )
    _play_thread = threading.Thread(target=_play_loop, daemon=True)
    _play_thread.start()


def _stop_playback() -> None:
    global _playing, _playhead_step, _bank_started_at_ms, _pause_offset_ms
    _playing = False
    _stop_event.set()
    if _midi is not None:
        _midi.all_notes_off()
    # Record where we are in the current bank so start can resume from here.
    if _bank_started_at_ms > 0:
        bank_duration_ms = (60.0 / _bpm) * 4 * BARS_PER_PHRASE * PHRASES_PER_BANK * 1000
        elapsed = time.time() * 1000 - _bank_started_at_ms
        _pause_offset_ms = max(0.0, min(elapsed, bank_duration_ms))
        _playhead_step = int(_pause_offset_ms / bank_duration_ms * BANK_STEPS)
    else:
        _pause_offset_ms = 0.0
        _playhead_step = 0
    _bank_started_at_ms = 0.0


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return (_STATIC / "index.html").read_text(encoding="utf-8")


@app.get("/api/landscape-map.svg")
async def api_landscape_map_svg(
    width: int = 180, height: int = 120, heat: float = -1.0,
) -> Response:
    width  = max(64,  min(360, int(width)))
    height = max(48,  min(240, int(height)))
    h      = _heat_applied if heat < 0 else max(0.0, min(1.0, float(heat)))
    svg    = _landscape_map_svg(width, height, heat=h)
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


def _heat_colour(r: int, g: int, b: int, heat: float) -> tuple[int, int, int]:
    """Map heat onto rendered colours.

    cold (0.0) → desaturated blue-grey, much darker
    neutral (0.5) → unchanged
    hot (1.0) → vivid orange-red tint, significantly brighter
    """
    if heat < 0.5:
        t = heat / 0.5                   # 0→1 over cold half
        # Darken heavily and push toward cold blue-grey
        lum   = 0.30 + 0.70 * t         # 0.30 at coldest → 1.0 at neutral
        r = max(0, min(255, int(r * lum * 0.80)))
        g = max(0, min(255, int(g * lum * 0.85)))
        b = max(0, min(255, int(b * lum * 1.20)))   # blue channel stays up
    else:
        t = (heat - 0.5) / 0.5          # 0→1 over hot half
        # Boost brightness and push toward orange-red
        r = max(0, min(255, int(r * (1.0 + t * 0.80))))   # strong red boost
        g = max(0, min(255, int(g * (1.0 + t * 0.30))))   # mild green
        b = max(0, min(255, int(b * (1.0 - t * 0.45))))   # suppress blue
    return r, g, b


def _landscape_map_svg(width: int, height: int, heat: float = 0.5) -> str:
    image = _LANDSCAPE_MAP.render(width=width, height=height)

    def to_px(lx: float, ly: float) -> tuple[float, float]:
        """Convert landscape coords → SVG pixel coords."""
        px = (lx - DOMAIN_MIN) / (DOMAIN_MAX - DOMAIN_MIN) * width
        py = (DOMAIN_MAX - ly) / (DOMAIN_MAX - DOMAIN_MIN) * height
        return px, py

    rects = []
    for y, row in enumerate(image.pixels):
        run_start  = 0
        run_colour = _heat_colour(*row[0], heat)
        for x in range(1, width + 1):
            raw    = row[x] if x < width else None
            colour = _heat_colour(*raw, heat) if raw is not None else None
            if colour != run_colour:
                rects.append(
                    f'<rect x="{run_start}" y="{y}" width="{x - run_start}" height="1" '
                    f'fill="rgb({run_colour[0]},{run_colour[1]},{run_colour[2]})"/>'
                )
                run_start  = x
                run_colour = colour

    overlays = []

    # ── Chaos peak circles (faint, behind anchor dots) ────────────────────────
    peak_number = 1
    for feature in _LANDSCAPE_MAP.get_features():
        if feature.type != "chaos_peak":
            continue
        cx, cy = to_px(*feature.position)
        r_px = feature.influence_radius / (DOMAIN_MAX - DOMAIN_MIN) * width
        overlays.append(
            f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r_px:.2f}" '
            f'fill="none" stroke="rgba(210,160,60,0.28)" stroke-width="0.8" '
            f'stroke-dasharray="3 3"/>'
        )
        overlays.append(
            f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="2.0" '
            f'fill="rgba(210,160,60,0.55)" stroke="none"/>'
        )
        cn = f"C{peak_number}"
        overlays.append(
            f'<text x="{cx + 4:.2f}" y="{cy - 3:.2f}" fill="rgba(210,160,60,0.85)" '
            f'font-family="Courier New, monospace" font-size="8" cursor="pointer" '
            f'stroke="#0d0d0d" stroke-width="0.4" paint-order="stroke" '
            f'onclick="navigateToFeature(\'{cn}\')">{cn}</text>'
        )
        peak_number += 1

    # ── Anchor dots + labels ──────────────────────────────────────────────────
    for name, (anchor_x, anchor_y) in ANCHORS.items():
        cx, cy = to_px(anchor_x, anchor_y)
        label = name.capitalize()
        overlays.append(
            f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="3.5" fill="#f2e7c9" '
            f'stroke="#0d0d0d" stroke-width="1.2"/>'
        )
        overlays.append(
            f'<text x="{cx + 6:.2f}" y="{cy - 5:.2f}" fill="#f2e7c9" '
            f'font-family="Courier New, monospace" font-size="10" cursor="pointer" '
            f'stroke="#0d0d0d" stroke-width="0.5" paint-order="stroke" '
            f'onclick="navigateToFeature(\'{label}\')">{label}</text>'
        )

    guide_path = (
        f"M0 {height / 3:.2f} H{width} "
        f"M0 {height * 2 / 3:.2f} H{width} "
        f"M{width / 3:.2f} 0 V{height} "
        f"M{width * 2 / 3:.2f} 0 V{height}"
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" '
        f'aria-label="Thelmic landscape volatility terrain">'
        '<rect width="100%" height="100%" fill="#0d0d0d"/>'
        + "".join(rects)
        + f'<path d="{guide_path}" stroke="rgba(255,255,255,0.12)" '
        'stroke-width="0.5" fill="none"/>'
        + "".join(overlays)
        + "</svg>"
    )


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    global _bpm, _current_bank, _next_bank_preview, _bank_index, _active_archetype
    global _midi, _midi_port_name, _broadcast_loop
    global _heat_target, _heat_applied
    global _bank_dirty, _bank_generation, _position_dirty
    global _journey_traces, _active_trace, _trace_bar
    global _pression_channel, _mapping_mode
    _bank_changed_this_msg = False   # set by handlers that already regenerated the bank
    _broadcast_loop = asyncio.get_running_loop()
    await ws.accept()
    # Wait for full banks before sending initial state.
    # Client sees "connecting" (honest), then gets fully-populated state in one shot.
    # No bare-bank → bank_dirty bounce on first connect.
    if not _banks_initialised:
        import asyncio as _asyncio
        loop = _asyncio.get_event_loop()
        await loop.run_in_executor(None, _init_done_event.wait, 12.0)
    _clients.add(ws)
    await ws.send_text(json.dumps(_state(include_bank=True)))
    try:
        while True:
            _bank_changed_this_msg = False
            raw = await ws.receive_text()
            msg = json.loads(raw)
            kind = msg.get("type")
            if kind == "start":
                _start_playback()
            elif kind == "stop":
                _stop_playback()
            elif kind == "bpm":
                _bpm = max(60.0, min(300.0, float(msg.get("value", _bpm))))
            elif kind == "axis":
                # The v1 reset keeps controls behaviour-transparent until the
                # rule-driven generator is rebuilt.
                pass
            elif kind == "refresh":
                pass
            elif kind == "midi_port":
                port_name = msg.get("value") or None
                if _midi is not None:
                    _midi.close()
                    _midi = None
                _midi_port_name = None
                if port_name:
                    _try_open_midi(port_name)
                else:
                    _save_midi_port(None)
            elif kind == "pression_mapping_lane":
                pass
            elif kind == "set_archetype":
                pass
            elif kind == "set_seed":
                try:
                    new_seed = int(msg.get("value", _landscape_seed))
                    _set_landscape_seed(new_seed)
                    _bank_changed_this_msg = True
                    # Regenerate immediately with new landscape
                    _new_cur  = _full_generate_bank(0)
                    _new_prev = _full_generate_bank(1)
                    with _state_lock:
                        _current_bank      = _new_cur
                        _next_bank_preview = _new_prev
                    _bank_dirty_set()
                    _log_ui_event("seed", f"seed={new_seed}", _playhead_step)
                except (TypeError, ValueError):
                    pass
            elif kind == "set_feature":
                # Navigate directly to a named feature: Oak, Nott, C1–C5
                name = str(msg.get("name", "")).strip()
                target = None
                for feat in _LANDSCAPE_MAP.get_features():
                    if _feature_display_name(feat).lower() == name.lower():
                        target = feat
                        break
                if target is not None:
                    _trajectory.move_to(*target.position)
                    with _state_lock:
                        _dims = _compute_dimensions(_trajectory, _heat_applied)
                        _next_bank_preview = generate_bank(
                            _bank_index + 1, dims=_dims,
                            signature_rhythm=_trajectory.active_feature().signature_rhythm,
                            previous_active_archetype=_active_archetype,
                        )
            elif kind == "set_address":
                # Full address string: "seed/feature/heat"
                try:
                    parts = str(msg.get("value", "")).strip().split("/")
                    if len(parts) == 3:
                        seed_v, feat_v, heat_v = parts
                        _set_landscape_seed(int(seed_v))
                        # Navigate to feature
                        for feat in _LANDSCAPE_MAP.get_features():
                            if _feature_display_name(feat).lower() == feat_v.strip().lower():
                                _trajectory.move_to(*feat.position)
                                break
                        _heat_target  = max(0.0, min(1.0, float(heat_v)))
                        _heat_applied = _heat_target
                except (ValueError, AttributeError):
                    pass
            elif kind == "set_position":
                try:
                    _trajectory.move_to(
                        float(msg.get("x", _trajectory.x)),
                        float(msg.get("y", _trajectory.y)),
                    )
                    _dims = _compute_dimensions(_trajectory, _heat_applied)
                    _sr   = _trajectory.active_feature().signature_rhythm
                    _ptd  = _trajectory.phrases_until_next_drop()
                    _is_drag = bool(msg.get("drag", True))
                    if not _is_drag:
                        # Click cancels all queued journey traces — immediate jump
                        _journey_traces.clear()
                        globals()["_active_trace"] = None
                        globals()["_trace_bar"]    = 0
                    if _playing and _is_drag:
                        # Drag while playing: splice from the NEXT bar — past bars
                        # keep their events so the grid matches what MIDI played.
                        from_bar = min(16, _playing_bar() + 1)
                        _regraft_current_bank_from_bar(from_bar)
                        _new_prev = generate_bank(
                            _bank_index + 1, dims=_dims,
                            is_drop_phrase=_trajectory.is_drop_phrase(),
                            signature_rhythm=_sr,
                            previous_active_archetype=_active_archetype,
                            phrases_until_drop=_ptd, heat=_heat_applied,
                        )
                        with _state_lock:
                            _next_bank_preview = _new_prev
                    else:
                        # Click (or stopped): full immediate bank replacement.
                        _new_cur  = generate_bank(
                            _bank_index, dims=_dims, is_drop_phrase=False,
                            signature_rhythm=_sr,
                            previous_active_archetype=_active_archetype,
                            phrases_until_drop=_ptd, heat=_heat_applied,
                        )
                        _new_prev = generate_bank(
                            _bank_index + 1, dims=_dims,
                            is_drop_phrase=_trajectory.is_drop_phrase(),
                            signature_rhythm=_sr,
                            previous_active_archetype=_active_archetype,
                            phrases_until_drop=_ptd, heat=_heat_applied,
                        )
                        with _state_lock:
                            _current_bank      = _new_cur
                            _next_bank_preview = _new_prev
                    _bank_dirty_set()
                    _position_dirty        = True
                    _bank_changed_this_msg = True
                    _log_ui_event(
                        "position",
                        f"→ {_feature_display_name(_trajectory.active_feature())}"
                        f" | sp={_dims.sparsity:.2f}"
                        f" | arch={pending_archetype_for(_sr).value}",
                        _playhead_step,
                    )
                except (TypeError, ValueError):
                    pass
            elif kind == "set_journey":
                # Receives the full drag path as [{x, y}, ...].
                # Interpolated to 16 positions (one per bar = one phrase).
                # Queued as the next phrase(s) to play.
                try:
                    pts = msg.get("points", [])
                    if pts:
                        trace = _interpolate_trace(pts, n=16)
                        if trace:
                            _journey_traces.append(trace)
                            # If nothing is playing yet, kick off immediately
                            if _active_trace is None and not _playing:
                                first_x, first_y = trace[0]
                                _trajectory.move_to(first_x, first_y)
                                _bank_changed_this_msg = True
                            _bank_dirty_set()
                            _log_ui_event("journey", f"trace queued ({len(trace)} steps)", None)
                except Exception:
                    pass

            elif kind == "set_heat":
                try:
                    _heat_target = max(0.0, min(1.0, float(msg.get("value", _heat_target))))
                    if not _playing:
                        _heat_applied = _heat_target
                    _log_ui_event("heat", f"heat={_heat_target:.2f}", _playhead_step)
                except (TypeError, ValueError):
                    pass

            elif kind == "set_pression_channel":
                # {"type": "set_pression_channel", "channel": 13}  (0-indexed)
                try:
                    ch = int(msg.get("channel", _pression_channel))
                    if 0 <= ch <= 15:
                        _pression_channel = ch
                        # Update PRESSION_CC entries to use new channel
                        from thelmic.midi_out import PRESSION_CC, PRESSION_DIMS
                        for dim in PRESSION_DIMS:
                            if dim in PRESSION_CC:
                                _, cc_num = PRESSION_CC[dim]
                                PRESSION_CC[dim] = (ch, cc_num)
                        _save_pression_config()
                except (TypeError, ValueError):
                    pass

            elif kind == "pression_map_start":
                # {"type": "pression_map_start", "dim": "stability"}
                # Enters mapping mode: only that dim's CC emits; notes suppressed.
                dim = str(msg.get("dim", ""))
                from thelmic.midi_out import PRESSION_DIMS
                if dim in PRESSION_DIMS:
                    _mapping_mode = dim
                    # Send all_notes_off immediately so Ableton starts clean
                    if _midi is not None:
                        _midi.all_notes_off()

            elif kind == "pression_map_stop":
                # Exit mapping mode — resume normal note + CC output
                _mapping_mode = None

            elif kind == "set_midi_channel":
                # {"type": "set_midi_channel", "layer": "kick", "channel": 0}
                # Channel is 0-indexed (0=ch1 in DAW).
                try:
                    layer = str(msg.get("layer", ""))
                    ch    = int(msg.get("channel", -1))
                    if layer in LAYER_CHANNELS and 0 <= ch <= 15:
                        LAYER_CHANNELS[layer] = ch
                        _save_channels()
                except (TypeError, ValueError):
                    pass

            elif kind == "reload_generation":
                # Hot-reload all generation modules — takes effect at next bank boundary.
                # MIDI continues uninterrupted; new code is used for next generate_bank() call.
                _reload_generation_modules()
                _bank_changed_this_msg = True
                new_cur  = _full_generate_bank(0)
                new_prev = _full_generate_bank(1)
                with _state_lock:
                    _current_bank      = new_cur
                    _next_bank_preview = new_prev
                _bank_dirty_set()
                log.info("Generation modules reloaded; banks regenerated.")

            # Regenerate current bank when stopped, unless this handler already did it.
            # Generate outside the lock — pure computation, no shared state needed.
            if not _playing and not _bank_changed_this_msg:
                _new_bank = generate_bank(
                    0,
                    dims=_compute_dimensions(_trajectory, _heat_applied),
                    signature_rhythm=_trajectory.active_feature().signature_rhythm,
                )
                with _state_lock:
                    _bank_index   = 0
                    _current_bank = _new_bank
            await _broadcast_state(include_bank=_bank_changed_this_msg or not _playing)
    except WebSocketDisconnect:
        _clients.discard(ws)


@app.get("/api/features")
async def api_features() -> dict:
    """Return the current terrain feature list with signature rhythm metadata."""
    features = _LANDSCAPE_MAP.get_features()
    return {
        "seed": _landscape_seed,
        "features": [
            {
                "id":               f.id,
                "type":             f.type,
                "position":         {"x": f.position[0], "y": f.position[1]},
                "influence_radius": f.influence_radius,
                "signature_rhythm": {
                    "id":               f.signature_rhythm.id,
                    "base_pattern_seed": f.signature_rhythm.base_pattern_seed,
                    "density_bias":      f.signature_rhythm.density_bias,
                    "syncopation_bias":  f.signature_rhythm.syncopation_bias,
                    "stability_bias":    f.signature_rhythm.stability_bias,
                },
            }
            for f in features
        ],
    }


@app.get("/api/midi-ports")
async def api_midi_ports() -> dict:
    try:
        ports = list_output_ports()
    except Exception:
        ports = []
    return {"ports": ports}


@app.get("/api/musical-rules", response_class=HTMLResponse)
async def api_musical_rules() -> str:
    """Render musical_rules.md as HTML for quick review."""
    md_path = _ROOT.parent / "musical_rules.md"
    try:
        text = md_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "<pre>musical_rules.md not found</pre>"
    # Minimal markdown → HTML (headings, code blocks, tables)
    import re, html as _html
    lines = text.split("\n")
    out = ["<html><head><meta charset='utf-8'><style>",
           "body{font-family:monospace;background:#0d0d0d;color:#e4e0d2;padding:24px;max-width:900px;margin:auto}",
           "h1,h2,h3{color:#c6a35b}h1{font-size:1.4em}h2{font-size:1.2em}h3{font-size:1.1em}",
           "pre,code{background:#151515;padding:2px 6px;border-radius:2px;color:#5fbf91}",
           "pre{padding:12px;display:block;white-space:pre-wrap;border:1px solid #2b2b2b}",
           "table{border-collapse:collapse;width:100%}td,th{border:1px solid #2b2b2b;padding:4px 8px;text-align:left}",
           "hr{border:none;border-top:1px solid #2b2b2b}",
           "</style></head><body>"]
    in_code = False
    for line in lines:
        if line.startswith("```"):
            if in_code:
                out.append("</pre>"); in_code = False
            else:
                out.append("<pre>"); in_code = True
            continue
        if in_code:
            out.append(_html.escape(line)); out.append("\n")
            continue
        if line.startswith("# "):   out.append(f"<h1>{_html.escape(line[2:])}</h1>")
        elif line.startswith("## "): out.append(f"<h2>{_html.escape(line[3:])}</h2>")
        elif line.startswith("### "): out.append(f"<h3>{_html.escape(line[4:])}</h3>")
        elif line.startswith("---"): out.append("<hr>")
        elif line.startswith("| "): out.append(
            "<tr>" + "".join(f"<td>{_html.escape(c.strip())}</td>" for c in line.split("|")[1:-1]) + "</tr>")
        elif line.startswith("|---"): out.append("")  # table separator
        else:
            esc = _html.escape(line)
            esc = re.sub(r"`([^`]+)`", r"<code>\1</code>", esc)
            esc = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", esc)
            out.append(f"<p style='margin:2px 0'>{esc}</p>")
    out.append("</body></html>")
    return "\n".join(out)


@app.get("/api/archetypes")
async def api_archetypes() -> dict:
    return {"archetypes": ["v1-rule-driven"], "selected": "v1-rule-driven"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
