"""FastAPI server — web UI entry point.

Usage:
    python -m thelmic.server [--bpm 174] [--port 8000]

Open http://localhost:8000 in a browser.
MIDI output goes to the virtual 'thelmic' port.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import threading
import time
from typing import Optional

import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from thelmic.bank_generator import BankGenerator
from thelmic.arrangement import (
    arrangement_diagnostics, ensure_beat_bed, generate_sub_from_bassline,
)
from thelmic.bass import generate_planned_bass
from thelmic.behaviour_field import compute_behaviour_field
from thelmic.call_response import (
    CallResponseState, Mode, default_state, advance_mode,
)
from thelmic.calls import generate_planned_calls
from thelmic.responses import generate_planned_responses
from thelmic.hook import generate_planned_hook
from thelmic.pression import (
    PressionBar, compute_bank_timeline, audit_pression_compliance,
    DEFAULT_CC_MAP, DIMENSION_NAMES, DIMENSION_COLOURS,
    BARS_PER_BANK, empty_timeline, TEST_PULSE_VALUES,
)
from thelmic.deformations import DEFORMATION_COLOURS
from thelmic.deformations_anchor import apply_anchor_withholding
from thelmic.deformations_dynamics import apply_behaviour_dynamics
from thelmic.pressure_curves import CurveEngine
from thelmic.phrase_plan import PhrasePlan, generate_phrase_plan
from thelmic.rhythm import conformance_for_landscape
from thelmic.stabs import (
    collect_call_events, generate_stabs_from_calls, generate_stabs_from_bass,
)
from thelmic.drop_enforcer import DropCommitState, add_survivor_signal, enforce_drop_relock
from thelmic.support_enforcer import enforce_supporting_layer_compliance
from thelmic.syntax_enforcer import enforce_phrase_syntax
from thelmic.phase11 import Phase11State, enforce_priority_and_sparsity
from thelmic.transition_engine import TransitionEngine

# Roles each dimension currently plays — updated as deformations are wired in
DIMENSION_ROLES: dict[str, str] = {
    # Force state
    "anticipation":          "future · Nott tension",
    "release_pressure":      "impact role · resolve",
    "instability":           "ghost inject",
    "density":               "archetype · velocity",
    "control_vs_chaos":      "future",
    "resolution_likelihood": "display only",
    # Controls
    "chaos_limit":           "clamps instability",
    "density_ceiling":       "clamps density",
}

DEFORMATION_MODEL_DIMENSIONS: dict[str, str] = {
    "ghost_inject": "instability",
}
from thelmic.controls import Controls
from thelmic.force_engine import ForceEngine
from thelmic.intent import IntentInput
from thelmic.landscape import territory_at
from thelmic.archetypes import archetype_name_at
from thelmic.midi_out import LAYER_CHANNELS, MIDIOut, is_grid_midi_event, list_output_ports
from thelmic.archetypes import ARCHETYPE_BY_NAME

import importlib.resources as _res
import pathlib

_STATIC = pathlib.Path(__file__).parent / "static"
_log = logging.getLogger(__name__)
_BAR_LOG = logging.getLogger("thelmic.bar_timing")   # enable with --timing
_TIMING_WARN_MS = 2.0

# Fields emitted by _BAR_LOG per bar (tab-separated for easy grep/cut):
#   time_ms         wall-clock ms since process start (monotonic)
#   bar             absolute bar index within bank (1-based)
#   phrase          phrase index (0-based)
#   bar_in_phrase   bar within phrase (0-based)
#   boundary        1 if this is a quantize boundary, else 0
#   play_ms         time inside play_bar_in_phrase_blocking
#   overhead_ms     total time from play() returning to next play() start
#   transition_ms   _transition_engine.advance()
#   curves_ms       _curve_engine.advance() + CC send
#   state_build_ms  _live_state_dict() construction
#   enqueue_ms      _queue_broadcast_threadsafe()
#   swap_ms         phrase slice swap at boundary (0 if no boundary)
#   run_coro_ms     asyncio.run_coroutine_threadsafe() call at boundary (0 if none)
#   prep_ready      1 if prepared_regeneration was already done, else 0
#   thread_id       OS thread id of playback loop
_T0 = time.perf_counter()   # reference for relative timestamps

# ---------------------------------------------------------------------------
# Engine singleton (module-level, shared across WS connections)
# ---------------------------------------------------------------------------

_engine: Optional[ForceEngine] = None
_transition_engine: Optional[TransitionEngine] = None
_controls: Optional[Controls] = None
_intent: Optional[IntentInput] = None
_generator: Optional[BankGenerator] = None
_midi: Optional[MIDIOut] = None      # drum notes port
_midi_cc: Optional[MIDIOut] = None  # CC automation port (separate)
_bpm: float = 174.0
_current_bank = None   # Bank | None
_curve_engine: CurveEngine = CurveEngine()
_pending_curve_starts: set[int] = set()
_cr_state: CallResponseState = default_state()
_phrase_plan: PhrasePlan = generate_phrase_plan()
_pression_timeline: list[PressionBar] = empty_timeline()
_pression_cc_map:   dict[str, tuple[int, int]] = dict(DEFAULT_CC_MAP)
_pression_bar_idx:  int = 0   # current bar being played (0-based within bank)
_active_pression_mapping_lane: Optional[str] = None
# Active archetype locked at bank start; only changes at drop commit or new bank.
# pending_archetype_name is what density/slider currently implies — may differ.
_active_archetype_name:  Optional[str] = None
_pending_archetype_name: Optional[str] = None
_runtime_debug: dict = {"anchors_dropped_per_bar": {}}
_drop_commit_state = DropCommitState()
_phase11_state = Phase11State()
_boundary_timing: dict = {
    "bank_generation_ms": 0.0,
    "next_bank_prepare_ms": 0.0,
    "bank_swap_ms": 0.0,
    "state_build_ms": 0.0,
    "json_serialization_ms": 0.0,
    "websocket_enqueue_ms": 0.0,
    "websocket_broadcast_ms": 0.0,
    "midi_note_send_ms": 0.0,
    "midi_cleanup_ms": 0.0,
    "boundary_total_ms": 0.0,
    "loop_iteration_ms": 0.0,
    "gc_pause_suspected": False,
}

_playing: bool = False
_play_thread: Optional[threading.Thread] = None
_play_lock = threading.Lock()
_bank_started_at_ms: float = 0.0   # wall-clock ms when current bank began playing

_quantize_bars: int = 2   # bars between quantize boundaries (1 = every bar)
_preview_lock = threading.Lock()  # guards _current_bank writes from handler vs loop

_clients: set[WebSocket] = set()
_clients_lock = asyncio.Lock()
_broadcast_queue: Optional[asyncio.Queue] = None
_broadcast_task: Optional[asyncio.Task] = None
_last_broadcast_metrics: dict = {
    "json_serialization_ms": 0.0,
    "websocket_broadcast_ms": 0.0,
}


def _generation_curve_overrides() -> dict[str, float]:
    from thelmic.bank_generator import BARS_PER_PHRASE
    from thelmic.behaviour_hooks import compute_behaviour_overrides

    manual = _curve_engine.projected_overrides(BARS_PER_PHRASE)
    transition = _transition_engine.transition if _transition_engine else None
    force = _engine.force_state if _engine else None
    if force is None:
        return manual
    return compute_behaviour_overrides(transition, force, manual)


def _event_bar(event) -> int:
    return int(event.time.split(".")[0])


def _append_events_to_bank(bank, events: list) -> list:
    from thelmic.bank_generator import BARS_PER_PHRASE

    appended = []
    for event in events:
        phrase_index = (_event_bar(event) - 1) // BARS_PER_PHRASE
        if 0 <= phrase_index < len(bank.phrases):
            bank.phrases[phrase_index].events.append(event)
            appended.append(event)
    return appended


def _events_per_bar(events: list) -> dict[int, int]:
    counts: dict[int, int] = {}
    for event in events:
        bar = _event_bar(event)
        counts[bar] = counts.get(bar, 0) + 1
    return counts


def _survivor_events(bank) -> list:
    return [
        event for event in bank.all_events()
        if event.role == "survivor" or getattr(event, "survives_silence", False)
    ]


def _survivor_tick_count(bank) -> int:
    return len({event.time for event in _survivor_events(bank)})


def _survivor_signature(event) -> tuple:
    return (
        event.time, event.layer, event.role, event.note,
        getattr(event, "survives_silence", False),
    )


def _survivor_trace_present(bank, signature: tuple | None) -> bool:
    if signature is None:
        return False
    return any(_survivor_signature(event) == signature for event in _survivor_events(bank))


def _survivor_trace_snapshot(bank, signature: tuple | None) -> dict:
    for event in _survivor_events(bank):
        if signature is None or _survivor_signature(event) == signature:
            from thelmic.syntax_enforcer import time_to_bar_step
            _, step = time_to_bar_step(event.time)
            return {
                "created_at_phase": "survivor_signal",
                "step": step,
                "role": event.role,
                "survives_silence": getattr(event, "survives_silence", False),
            }
    return {
        "created_at_phase": "survivor_signal",
        "step": None,
        "role": None,
        "survives_silence": False,
    }


def _record_timing(name: str, value_ms: float) -> float:
    value = round(value_ms, 3)
    if value > _TIMING_WARN_MS:
        _log.warning("%s %.3fms", name, value)
    return value


def _apply_behaviour_modules_to_bank(bank, overrides: dict[str, float]) -> None:
    global _runtime_debug, _cr_state
    if not _engine:
        _runtime_debug = {
            "anchors_dropped_per_bar": {},
            "bass_events_per_bar": {},
            "hook_events_per_bar": {},
            "stab_events_per_bar": {},
        }
        return
    transition = _transition_engine.transition if _transition_engine else None
    behaviour = compute_behaviour_field(_engine.force_state, transition)
    if "anchor_drop" in overrides:
        behaviour.anchor_drop_prob = overrides["anchor_drop"]
    if "ghost_velocity" in overrides:
        behaviour.ghost_velocity = overrides["ghost_velocity"]
    if "anchor_velocity" in overrides:
        behaviour.anchor_velocity = overrides["anchor_velocity"]
    progress = transition.progress if transition else 0.0
    _runtime_debug = apply_anchor_withholding(bank, behaviour, progress)
    base_events = list(bank.all_events())
    landscape_position = _engine.landscape_position

    # Collect bars present in this bank
    from thelmic.stabs import _time_to_bar_step
    bars_present: list[int] = sorted({
        _time_to_bar_step(e.time)[0]
        for e in base_events
        if _time_to_bar_step(e.time)[1] >= 0
    })

    # Advance call/response mode state bar-by-bar through this bank
    bank_base = bank.bank_index * 16  # global bar offset for phrase boundary detection
    for bar_in_bank in bars_present:
        _cr_state = advance_mode(_cr_state, bank_base + bar_in_bank)

    mode = _cr_state.force_mode if _cr_state.force_mode is not None else _cr_state.mode
    source = next(
        (e for e in base_events if e.layer in {"kick", "snare"}),
        base_events[0] if base_events else None,
    )

    bassline_events: list = generate_planned_bass(
        base_events, behaviour, _phrase_plan,
        landscape_position=landscape_position,
    )
    hook_events: list = generate_planned_hook(base_events, behaviour, _phrase_plan)
    leader = _phase11_state.call_response_leader
    leader_layer = "bassline" if leader == "bass" else leader

    # Stab is the primary call/response voice. Bassline participates as the
    # paired body of the exchange, using the same planner-owned slots.
    planned_calls = generate_planned_calls(
        base_events, behaviour, _phrase_plan, leader_layer="stab",
    )
    planned_responses = generate_planned_responses(
        base_events, behaviour, _phrase_plan, leader_layer="stab",
    )
    bassline_calls = generate_planned_calls(
        base_events, behaviour, _phrase_plan, leader_layer="bassline",
    )
    bassline_responses = generate_planned_responses(
        base_events, behaviour, _phrase_plan, leader_layer="bassline",
    )
    if leader_layer == "bassline":
        call_response_bassline_events = bassline_calls.events + bassline_responses.events
    else:
        call_response_bassline_events = bassline_responses.events
    stab_events: list = planned_calls.events + planned_responses.events
    bassline_events.extend(call_response_bassline_events)
    sub_events: list = generate_sub_from_bassline(
        bassline_events, behaviour, landscape_position=landscape_position,
    )

    _log.debug(
        "bank=%d mode=%s calls_rendered=%d responses_rendered=%d",
        bank.bank_index, mode.value,
        planned_calls.stats.get("call_events_rendered", 0),
        planned_responses.stats.get("response_events_rendered", 0),
    )

    appended_bassline = _append_events_to_bank(bank, bassline_events)
    appended_sub   = _append_events_to_bank(bank, sub_events)
    appended_hooks = _append_events_to_bank(bank, hook_events)
    appended_stabs = _append_events_to_bank(bank, stab_events)
    beat_bed_stats = ensure_beat_bed(bank, _phrase_plan, _phase11_state)
    survivor_stats = add_survivor_signal(bank, _phrase_plan)
    survivor_after_generation = _survivor_events(bank)
    survivor_signature = (
        _survivor_signature(survivor_after_generation[0])
        if survivor_after_generation else None
    )
    survivor_trace = _survivor_trace_snapshot(bank, survivor_signature)
    survivor_trace["present_after_generation"] = _survivor_trace_present(
        bank, survivor_signature
    )
    syntax_stats   = enforce_phrase_syntax(bank, _phrase_plan)
    survivor_stats["survivor_ticks_after_suppression"] = _survivor_tick_count(bank)
    survivor_trace["present_after_silence_suppression"] = _survivor_trace_present(
        bank, survivor_signature
    )
    support_stats  = enforce_supporting_layer_compliance(bank, _phrase_plan)
    survivor_trace["present_after_support_enforcer"] = _survivor_trace_present(
        bank, survivor_signature
    )
    priority_stats = enforce_priority_and_sparsity(bank, _phrase_plan, _phase11_state)
    drop_stats     = enforce_drop_relock(
        bank, _phrase_plan, _drop_commit_state, syntax_stats
    )
    if drop_stats.get("commit_applied", 0):
        _phase11_state.mark_drop_committed()
        # Archetype commit at drop: active_archetype advances to pending_archetype.
        # This is the ONLY place active_archetype may change instantly.
        global _active_archetype_name, _pending_archetype_name
        if _pending_archetype_name and _pending_archetype_name != _active_archetype_name:
            _log.debug(
                "archetype commit at drop: %s → %s",
                _active_archetype_name, _pending_archetype_name,
            )
            _active_archetype_name = _pending_archetype_name
    survivor_stats["survivor_ticks_in_final_output"] = _survivor_tick_count(bank)
    survivor_trace["present_after_drop_relock"] = _survivor_trace_present(
        bank, survivor_signature
    )
    survivor_trace["present_in_final_output"] = survivor_trace["present_after_drop_relock"]
    survivor_trace["removed_by"] = None
    survivor_trace["removal_reason"] = None
    if survivor_signature is not None:
        checks = [
            ("silence_suppression", "present_after_silence_suppression"),
            ("support_enforcer", "present_after_support_enforcer"),
            ("drop_relock", "present_after_drop_relock"),
        ]
        for phase, key in checks:
            if not survivor_trace[key]:
                survivor_trace["removed_by"] = phase
                survivor_trace["removal_reason"] = "survivor missing after pass"
                break
    _runtime_debug["bassline_events_per_bar"]  = _events_per_bar(appended_bassline)
    _runtime_debug["sub_events_per_bar"]       = _events_per_bar(appended_sub)
    _runtime_debug["hook_events_per_bar"]      = _events_per_bar(appended_hooks)
    _runtime_debug["stab_events_per_bar"]      = _events_per_bar(appended_stabs)
    _runtime_debug.update(beat_bed_stats)
    _runtime_debug.update(planned_calls.stats)
    _runtime_debug.update(planned_responses.stats)
    _runtime_debug.update(syntax_stats)
    _runtime_debug.update(support_stats)
    _runtime_debug.update(priority_stats)
    _runtime_debug.update(drop_stats)
    _runtime_debug.update(survivor_stats)
    _runtime_debug["survivor_trace"] = survivor_trace
    _runtime_debug["survivor_events_final"] = len(_survivor_events(bank))
    _runtime_debug["call_response_mode"]       = mode.value
    _runtime_debug["call_response_bars_in_mode"] = _cr_state.bars_in_mode
    _runtime_debug["call_response_leader"] = _phase11_state.call_response_leader
    _runtime_debug["pending_call_response_leader"] = _phase11_state.pending_call_response_leader
    _runtime_debug["leader_committed_at_drop"] = _phase11_state.leader_committed_at_drop
    _runtime_debug["phrase_mode"] = _phase11_state.phrase_mode.value
    _runtime_debug["pending_phrase_mode"] = _phase11_state.pending_phrase_mode.value
    _runtime_debug["phrase_mode_committed_at_drop"] = _phase11_state.phrase_mode_committed_at_drop
    _runtime_debug["build_length_bars"] = _phase11_state.build_length_bars
    _runtime_debug["silence_length_bars"] = _phase11_state.silence_length_bars
    _runtime_debug["bass_source"] = "phrase_plan"
    _runtime_debug["bass_tonal_centre"] = 36
    _runtime_debug["hook_source"] = "phrase_plan"
    conformance = round(conformance_for_landscape(landscape_position), 3)
    _runtime_debug["bass_conformance"] = conformance
    _runtime_debug["stab_conformance"] = conformance
    _runtime_debug.update(arrangement_diagnostics(bank, _phase11_state))
    pression_modulated_count = apply_behaviour_dynamics(bank, behaviour)

    # Pre-compute pression timeline for this bank.
    # Pression is computed AFTER enforce_phrase_syntax so it sees only
    # surviving (post-enforcement) events.  apply_behaviour_dynamics also
    # runs post-enforcement.  Pression never creates events.
    global _pression_timeline
    _pression_timeline = compute_bank_timeline(
        force=_engine.force_state,
        behaviour=behaviour,
        transition=_transition_engine.transition if _transition_engine else None,
        cr_mode=mode,
        bank=bank,
    )

    # Phase 7 compliance audit — prove pression is control-only.
    pression_audit = audit_pression_compliance(
        timeline=_pression_timeline,
        bank=bank,
        cc_map=_pression_cc_map,
    )
    pression_audit["pression_modulated_events_count"] = pression_modulated_count
    _runtime_debug.update(pression_audit)


def _prepare_regenerated_bank(bank_idx: int):
    t0 = time.perf_counter()
    overrides = _generation_curve_overrides()
    # Use locked active archetype so within-bank regen never changes archetype.
    fresh = _generator.generate(
        _engine.force_state, bank_idx, _engine.landscape_position,
        curve_overrides=overrides,
        active_archetype=_active_archetype_name if _playing else None,
    )
    _apply_behaviour_modules_to_bank(fresh, overrides)
    elapsed = _record_timing("next_bank_prepare_ms", (time.perf_counter() - t0) * 1000)
    return fresh, elapsed


def _active_pression_cc_map() -> dict[str, tuple[int, int]]:
    """Return the CC map allowed for Pression output right now."""
    if _active_pression_mapping_lane is None:
        return _pression_cc_map
    pair = _pression_cc_map.get(_active_pression_mapping_lane)
    if pair is None:
        return {}
    return {_active_pression_mapping_lane: pair}


def _install_prepared_regeneration_when_ready(prepared: dict, bank, next_idx: int) -> None:
    global _current_bank
    prepared["thread"].join()
    result = prepared["box"].get("result")
    if not result:
        return
    fresh, _generation_ms = result
    with _preview_lock:
        bank.phrases[next_idx:] = fresh.phrases[next_idx:]
        _current_bank = bank
    try:
        asyncio.run_coroutine_threadsafe(_broadcast_full_state_deferred(), _get_loop())
    except Exception:
        pass


def _generate_and_install_regeneration(bank_idx: int, bank, next_idx: int) -> None:
    global _current_bank
    fresh, _generation_ms = _prepare_regenerated_bank(bank_idx)
    with _preview_lock:
        bank.phrases[next_idx:] = fresh.phrases[next_idx:]
        _current_bank = bank
    try:
        asyncio.run_coroutine_threadsafe(_broadcast_full_state_deferred(), _get_loop())
    except Exception:
        pass


async def _broadcast_full_state_deferred(delay: float = 0.025) -> None:
    global _boundary_timing
    if delay > 0.0:
        await asyncio.sleep(delay)
    t_state = time.perf_counter()
    msg = {"type": "state", **_force_state_dict(include_bank=True)}
    state_ms = _record_timing(
        "state_build_ms", (time.perf_counter() - t_state) * 1000
    )
    await _broadcast(msg)
    _boundary_timing["state_build_ms"] = state_ms


def _manual_current_overrides() -> dict[str, float]:
    return _curve_engine.overrides()


def _send_behaviour_filter_cc(manual_overrides: dict[str, float]) -> None:
    if not (_engine and _midi_cc) or "cc:0:74" in manual_overrides:
        return
    transition = _transition_engine.transition if _transition_engine else None
    behaviour = compute_behaviour_field(_engine.force_state, transition)
    _midi_cc.send_cc(0, 74, behaviour.filter_target)


async def _apply_and_preview() -> None:
    """Update the display bank ahead of the current playhead, broadcast immediately.

    Phrases already played (behind the playhead) keep their original content.
    Only phrases strictly ahead of the current playhead are regenerated from
    the new state, so the grid shows what's coming without rewriting history.
    The playback loop will regenerate those same phrases at the next quantize
    boundary so MIDI catches up.
    """
    global _current_bank, _drop_commit_state
    if not (_generator and _engine and _current_bank):
        await _broadcast({"type": "state", **_force_state_dict()})
        return

    # Work out which phrase the playhead is currently inside
    if _bank_started_at_ms > 0 and _playing:
        elapsed_ms = time.time() * 1000 - _bank_started_at_ms
        from thelmic.bank_generator import BARS_PER_PHRASE, BEATS_PER_BAR
        ms_per_phrase = BARS_PER_PHRASE * BEATS_PER_BAR * (60000.0 / _bpm)
        current_phrase_idx = min(int(elapsed_ms / ms_per_phrase), len(_current_bank.phrases) - 1)
    else:
        current_phrase_idx = -1   # not playing — regenerate everything

    with _preview_lock:
        if not _playing:
            _drop_commit_state = DropCommitState()
        overrides = _generation_curve_overrides()
        # Use locked active archetype for preview; density change is visible
        # only via pending archetype and takes effect at the next drop.
        fresh = _generator.generate(
            _engine.force_state, _current_bank.bank_index, _engine.landscape_position,
            curve_overrides=overrides,
            active_archetype=_active_archetype_name if _playing else None,
        )
        _apply_behaviour_modules_to_bank(fresh, overrides)
        # Splice: keep up-to-and-including current phrase, replace the rest
        for i, phrase in enumerate(fresh.phrases):
            if i > current_phrase_idx:
                _current_bank.phrases[i] = phrase

    await _broadcast({"type": "state", **_force_state_dict()})


def _init_engine() -> None:
    global _engine, _transition_engine, _controls, _intent, _generator, _midi, _phase11_state
    _engine = ForceEngine(landscape_position=0.0)
    _transition_engine = TransitionEngine(_engine)
    _controls = Controls()
    _intent = IntentInput(_engine, _transition_engine)
    _generator = BankGenerator(controls=_controls)
    _phase11_state = Phase11State()
    _phase11_state.set_immediate(_engine.landscape_position)
    # MIDI init is deferred — no port selected yet
    _midi = None


def _open_midi_port(port_name: Optional[str]) -> str:
    """Open (or switch to) the notes MIDI port. Returns the connected port name."""
    global _midi
    if _midi is not None:
        _midi.close()
    _midi = MIDIOut(port_name=port_name)
    return _midi.port_name


def _open_midi_cc_port(port_name: Optional[str]) -> str:
    """Open (or switch to) the CC MIDI port. Returns the connected port name."""
    global _midi_cc
    if _midi_cc is not None:
        _midi_cc.close()
    _midi_cc = MIDIOut(port_name=port_name)
    return _midi_cc.port_name


def _bank_events_list(bank) -> list:
    if bank is None:
        return []
    events = []
    for event in bank.all_events():
        if event.layer == "survivor":
            continue
        events.append({
            "time": event.time,
            "layer": event.layer,
            "role": event.role,
            "active": getattr(event, "active", True),
            "velocity": event.velocity,
            "note": event.note,
            "duration": event.duration,
            "midi_send": is_grid_midi_event(event),
            "midi_channel": LAYER_CHANNELS.get(event.layer),
            "emphasis": round(event.emphasis, 2),
            "survives_silence": getattr(event, "survives_silence", False),
            "structural_authority": getattr(event, "structural_authority", True),
            "deformation": {k: round(v, 3) for k, v in event.deformation.items()},
        })
    return events


def _force_state_dict(include_bank: bool = True) -> dict:
    """Build the WebSocket state payload.

    include_bank=True  — full state including bank_events (sent at quantize
                         boundaries when the grid has actually changed)
    include_bank=False — live state: force dimensions, transition, territory
                         (sent every bar so the UI tracks the journey in real
                         time without waiting for a quantize boundary)
    """
    fs = _engine.force_state
    transition = _transition_engine.transition if _transition_engine else None
    behaviour = compute_behaviour_field(fs, transition)
    pos = _engine.landscape_position
    pressure_curves = _curve_engine.state_dict()
    pressure_curves["pending_ids"] = sorted(_pending_curve_starts)
    bank_slot = len(_engine.bank_history) % 4 + 1
    d = {
        "landscape_position": round(pos, 3),
        "territory": territory_at(pos),
        "anticipation": round(fs.anticipation, 3),
        "release_pressure": round(fs.release_pressure, 3),
        "instability": round(fs.instability, 3),
        "density": round(fs.density, 3),
        "control_vs_chaos": round(fs.control_vs_chaos, 3),
        "resolution_likelihood": round(_engine.resolution_likelihood, 3),
        "bank_count": len(_engine.bank_history),
        "bank_slot": bank_slot,
        "bank_total": 4,
        "playing": _playing,
        "bpm": _bpm,
        "midi_port": _midi.port_name if _midi else None,
        "midi_cc_port": _midi_cc.port_name if _midi_cc else None,
        "midi_layer_channels": dict(LAYER_CHANNELS),
        "archetype": archetype_name_at(density=_engine.force_state.density),
        "selected_archetype": _generator.selected_archetype,
        "active_archetype":   _active_archetype_name,
        "pending_archetype":  _pending_archetype_name,
        "deformation_colours": DEFORMATION_COLOURS,
        "deformation_model_dimensions": DEFORMATION_MODEL_DIMENSIONS,
        "dimension_roles": DIMENSION_ROLES,
        "pressure_curves": pressure_curves,
        "quantize_bars": _quantize_bars,
        "bank_started_at": _bank_started_at_ms,
        "bank_duration_ms": round((16 * 4 * 60000) / _bpm, 1),
        "transition": _transition_engine.state_dict() if _transition_engine else {},
        "phase11": _phase11_state.to_dict(),
        "active_pression_mapping_lane": _active_pression_mapping_lane,
        "call_response": {
            "mode": _cr_state.mode.value,
            "bars_in_mode": _cr_state.bars_in_mode,
            "mode_duration_bars": _cr_state.mode_duration_bars,
            "force_mode": _cr_state.force_mode.value if _cr_state.force_mode else None,
        },
        "phrase_plan": _phrase_plan.to_dict(),
        "pression": {
            "current_bar": _pression_bar_idx,
            "current": (_pression_timeline[_pression_bar_idx].bar_peak()
                        if 0 <= _pression_bar_idx < len(_pression_timeline)
                        else {d: 0 for d in DIMENSION_NAMES}),
            "timeline": [pb.to_dict() for pb in _pression_timeline],
            "cc_map": {k: list(v) for k, v in _pression_cc_map.items()},
            "colours": DIMENSION_COLOURS,
            "active_mapping_lane": _active_pression_mapping_lane,
        },
        "runtime": {**_runtime_debug, "boundary_timing": _boundary_timing},
        "force": {
            "anticipation": round(fs.anticipation, 3),
            "instability": round(fs.instability, 3),
            "release_pressure": round(fs.release_pressure, 3),
        },
        "behaviour": {
            "ghost_intensity": round(behaviour.ghost_intensity, 3),
            "ghost_clustering": round(behaviour.ghost_clustering, 3),
            "anchor_drop_prob": round(behaviour.anchor_drop_prob, 3),
            "filter_target": round(behaviour.filter_target, 3),
            "gate_tightness": round(behaviour.gate_tightness, 3),
            "energy_level": round(behaviour.energy_level, 3),
            "accent_strength": round(behaviour.accent_strength, 3),
            "ghost_velocity": round(behaviour.ghost_velocity, 3),
            "anchor_velocity": round(behaviour.anchor_velocity, 3),
        },
    }
    if include_bank:
        d["bank_events"] = _bank_events_list(_current_bank)
    return d


def _live_state_dict() -> dict:
    fs = _engine.force_state
    transition = _transition_engine.transition if _transition_engine else None
    behaviour = compute_behaviour_field(fs, transition)
    pos = _engine.landscape_position
    bank_slot = len(_engine.bank_history) % 4 + 1
    return {
        "type": "state",
        "landscape_position": round(pos, 3),
        "territory": territory_at(pos),
        "anticipation": round(fs.anticipation, 3),
        "release_pressure": round(fs.release_pressure, 3),
        "instability": round(fs.instability, 3),
        "density": round(fs.density, 3),
        "control_vs_chaos": round(fs.control_vs_chaos, 3),
        "resolution_likelihood": round(_engine.resolution_likelihood, 3),
        "bank_count": len(_engine.bank_history),
        "bank_slot": bank_slot,
        "bank_total": 4,
        "playing": _playing,
        "bpm": _bpm,
        "midi_port": _midi.port_name if _midi else None,
        "midi_cc_port": _midi_cc.port_name if _midi_cc else None,
        "archetype": archetype_name_at(density=_engine.force_state.density),
        "selected_archetype": _generator.selected_archetype,
        "active_archetype": _active_archetype_name,
        "pending_archetype": _pending_archetype_name,
        "quantize_bars": _quantize_bars,
        "bank_started_at": _bank_started_at_ms,
        "bank_duration_ms": round((16 * 4 * 60000) / _bpm, 1),
        "transition": _transition_engine.state_dict() if _transition_engine else {},
        "phase11": _phase11_state.to_dict(),
        "midi_layer_channels": dict(LAYER_CHANNELS),
        "pression_bar_idx": _pression_bar_idx,   # current bar, for UI cursor
        "active_pression_mapping_lane": _active_pression_mapping_lane,
        "phrase_plan": _phrase_plan.to_dict(),
        "runtime": {**_runtime_debug, "boundary_timing": _boundary_timing},
        "force": {
            "anticipation": round(fs.anticipation, 3),
            "instability": round(fs.instability, 3),
            "release_pressure": round(fs.release_pressure, 3),
        },
        "behaviour": {
            "ghost_intensity": round(behaviour.ghost_intensity, 3),
            "ghost_clustering": round(behaviour.ghost_clustering, 3),
            "anchor_drop_prob": round(behaviour.anchor_drop_prob, 3),
            "filter_target": round(behaviour.filter_target, 3),
            "gate_tightness": round(behaviour.gate_tightness, 3),
            "energy_level": round(behaviour.energy_level, 3),
            "accent_strength": round(behaviour.accent_strength, 3),
            "ghost_velocity": round(behaviour.ghost_velocity, 3),
            "anchor_velocity": round(behaviour.anchor_velocity, 3),
        },
    }


def _start_pending_curves() -> bool:
    """Start armed pressure curves at a quantization boundary.

    Returns True if any curve was injected into the next generated material.
    """
    if not _pending_curve_starts:
        return False
    for curve_id in sorted(_pending_curve_starts):
        _curve_engine.start(curve_id)
    _pending_curve_starts.clear()
    return True


def _queue_broadcast_nowait(msg: dict) -> None:
    if _broadcast_queue is None:
        return
    while _broadcast_queue.full():
        try:
            _broadcast_queue.get_nowait()
            _broadcast_queue.task_done()
        except asyncio.QueueEmpty:
            break
    try:
        _broadcast_queue.put_nowait(msg)
    except asyncio.QueueFull:
        pass


def _queue_broadcast_threadsafe(msg: dict) -> None:
    loop = _get_loop()
    if loop is None:
        return
    t_enqueue = time.perf_counter()
    loop.call_soon_threadsafe(_queue_broadcast_nowait, msg)
    _boundary_timing["websocket_enqueue_ms"] = _record_timing(
        "websocket_enqueue_ms", (time.perf_counter() - t_enqueue) * 1000
    )


async def _broadcast_worker_loop() -> None:
    global _last_broadcast_metrics
    while True:
        msg = await _broadcast_queue.get()
        try:
            t_json = time.perf_counter()
            data = json.dumps(msg)
            json_ms = _record_timing(
                "json_serialization_ms", (time.perf_counter() - t_json) * 1000
            )
            t_send = time.perf_counter()
            async with _clients_lock:
                dead = set()
                for ws in _clients:
                    try:
                        await ws.send_text(data)
                    except Exception:
                        dead.add(ws)
                _clients.difference_update(dead)
            send_ms = _record_timing(
                "websocket_broadcast_ms", (time.perf_counter() - t_send) * 1000
            )
            _last_broadcast_metrics = {
                "json_serialization_ms": json_ms,
                "websocket_broadcast_ms": send_ms,
            }
        finally:
            _broadcast_queue.task_done()


async def _broadcast(msg: dict) -> None:
    _queue_broadcast_nowait(msg)


async def _broadcast_direct(msg: dict) -> None:
    data = json.dumps(msg)
    async with _clients_lock:
        dead = set()
        for ws in _clients:
            try:
                await ws.send_text(data)
            except Exception:
                dead.add(ws)
        _clients.difference_update(dead)


def _playback_loop() -> None:
    global _playing, _current_bank, _boundary_timing
    bank_idx = 0
    bank_start: float | None = None   # absolute start of current bank (prevents drift)
    while _playing:

        _start_pending_curves()
        snapshot = _engine.begin_bank()
        overrides = _generation_curve_overrides()

        # Lock active archetype at bank start.  Within-bank regeneration
        # (quantize boundaries, preview) must use this name so archetype
        # cannot change mid-phrase due to slider/density movement.
        # Only drops are allowed to commit a new active archetype.
        global _active_archetype_name, _pending_archetype_name
        from thelmic.archetypes import select_archetype as _select_arch
        _pending_archetype_name = _select_arch(
            _engine.force_state.density, _generator.selected_archetype,
        ).name
        if _active_archetype_name is None:
            _active_archetype_name = _pending_archetype_name   # first bank

        bank = _generator.generate(
            _engine.force_state, bank_idx, _engine.landscape_position,
            curve_overrides=overrides,
            active_archetype=_active_archetype_name,
        )
        _apply_behaviour_modules_to_bank(bank, overrides)
        _current_bank = bank

        if _midi is None:
            _playing = False
            break

        if bank_start is None:
            bank_start = time.perf_counter()

        global _bank_started_at_ms
        _bank_started_at_ms = time.time() * 1000
        # Full state at bank start — build on playback thread, queue to broadcast worker.
        # Avoids asyncio.run_coroutine_threadsafe overhead on the timing-critical path.
        _queue_broadcast_threadsafe({"type": "state", **_force_state_dict(include_bank=True)})

        # Play bar by bar — advances the curve engine once per bar so CC output
        # fires at bar resolution rather than phrase resolution (4× finer).
        # Quantize boundaries can now fire on any bar, not just phrase ends.
        from thelmic.bank_generator import BARS_PER_PHRASE
        bar_end = bank_start
        prepared_regeneration = None
        for phrase in bank.phrases:
            if not _playing:
                break
            for bar_in_phrase in range(BARS_PER_PHRASE):
                if not _playing:
                    break
                current_abs_bar = phrase.phrase_index * BARS_PER_PHRASE + bar_in_phrase + 1
                next_idx_for_prep = phrase.phrase_index + 1
                if (
                    (current_abs_bar + 1) % max(1, _quantize_bars) == 0
                    and next_idx_for_prep < len(bank.phrases)
                    and prepared_regeneration is None
                ):
                    prep_box: dict = {}

                    def _prep() -> None:
                        prep_box["result"] = _prepare_regenerated_bank(bank_idx)

                    prep_thread = threading.Thread(target=_prep, daemon=True)
                    prepared_regeneration = {
                        "next_idx": next_idx_for_prep,
                        "thread": prep_thread,
                        "box": prep_box,
                    }
                    prep_thread.start()

                abs_bar = phrase.phrase_index * BARS_PER_PHRASE + bar_in_phrase + 1
                next_idx = phrase.phrase_index + 1
                is_boundary = (abs_bar % max(1, _quantize_bars) == 0)

                # Look up pre-computed pression bar for step-level CC injection.
                _pb = (
                    _pression_timeline[abs_bar - 1]
                    if _pression_timeline and 0 <= abs_bar - 1 < len(_pression_timeline)
                    else None
                )
                t_play_start = time.perf_counter()
                bar_end = _midi.play_bar_in_phrase_blocking(
                    phrase, bar_in_phrase, bpm=_bpm, bank_start=bank_start,
                    pression_bar=_pb,
                    pression_cc_map=_active_pression_cc_map() if _midi_cc else None,
                    pression_cc_port=_midi_cc,
                )
                t_after_play = time.perf_counter()
                play_ms = (t_after_play - t_play_start) * 1000

                # ── Transition advance ──────────────────────────────────────
                t0 = time.perf_counter()
                if _transition_engine:
                    _transition_engine.advance(bars=1)
                if _engine:
                    _engine.set_landscape_position(_phase11_state.advance(bars=1))
                transition_ms = (time.perf_counter() - t0) * 1000

                # ── Curve advance + CC ──────────────────────────────────────
                t0 = time.perf_counter()
                manual_overrides = _manual_current_overrides()
                cc_messages = _curve_engine.advance(bars=1)
                if _midi_cc:
                    for cc_target, cc_num, val in cc_messages:
                        parts = cc_target.split(":")
                        ch = int(parts[1]) if len(parts) >= 3 else 0
                        _midi_cc.send_cc(ch, cc_num, val)
                    _send_behaviour_filter_cc(manual_overrides)
                curves_ms = (time.perf_counter() - t0) * 1000

                # Pression CCs are now emitted at step resolution inside
                # play_bar_in_phrase_blocking (injected into MIDI timeline).
                # Update tracking variable for UI state broadcast.
                global _pression_bar_idx
                _pression_bar_idx = abs_bar - 1

                # ── Live state build + enqueue ──────────────────────────────
                t0 = time.perf_counter()
                live_msg = _live_state_dict()
                state_build_ms = (time.perf_counter() - t0) * 1000

                t0 = time.perf_counter()
                _queue_broadcast_threadsafe(live_msg)
                enqueue_ms = (time.perf_counter() - t0) * 1000

                _boundary_timing["state_build_ms"] = round(state_build_ms, 3)
                _boundary_timing["websocket_enqueue_ms"] = round(enqueue_ms, 3)

                # ── Quantize boundary ───────────────────────────────────────
                swap_ms = 0.0
                run_coro_ms = 0.0
                prep_ready = 0
                generation_ms = 0.0
                regenerated = False

                if is_boundary:
                    t_boundary = time.perf_counter()
                    injected_curve = _start_pending_curves()

                    if next_idx < len(bank.phrases):
                        if (
                            prepared_regeneration is not None
                            and prepared_regeneration["next_idx"] == next_idx
                            and not prepared_regeneration["thread"].is_alive()
                            and not injected_curve
                        ):
                            # Pre-generation finished — instant swap
                            prep_ready = 1
                            t0 = time.perf_counter()
                            fresh, generation_ms = prepared_regeneration["box"]["result"]
                            bank.phrases[next_idx:] = fresh.phrases[next_idx:]
                            _current_bank = bank
                            swap_ms = (time.perf_counter() - t0) * 1000
                            regenerated = True
                        elif injected_curve:
                            threading.Thread(
                                target=_generate_and_install_regeneration,
                                args=(bank_idx, bank, next_idx),
                                daemon=True,
                            ).start()
                        elif prepared_regeneration is not None:
                            threading.Thread(
                                target=_install_prepared_regeneration_when_ready,
                                args=(prepared_regeneration, bank, next_idx),
                                daemon=True,
                            ).start()
                        prepared_regeneration = None

                    boundary_work_ms = (time.perf_counter() - t_boundary) * 1000

                    if regenerated:
                        # Build full state on playback thread (fast), then queue it.
                        # Avoids asyncio.run_coroutine_threadsafe overhead on the hot path.
                        t0 = time.perf_counter()
                        full_msg = {"type": "state", **_force_state_dict(include_bank=True)}
                        _queue_broadcast_threadsafe(full_msg)
                        run_coro_ms = (time.perf_counter() - t0) * 1000

                    _boundary_timing = {
                        "bank_generation_ms": generation_ms,
                        "next_bank_prepare_ms": generation_ms,
                        "bank_swap_ms": round(swap_ms, 3),
                        "state_build_ms": round(state_build_ms, 3),
                        "json_serialization_ms": _last_broadcast_metrics.get("json_serialization_ms", 0.0),
                        "websocket_enqueue_ms": round(enqueue_ms, 3),
                        "websocket_broadcast_ms": _last_broadcast_metrics.get("websocket_broadcast_ms", 0.0),
                        "midi_note_send_ms": getattr(_midi, "last_send_ms", 0.0),
                        "midi_cleanup_ms": getattr(_midi, "last_cleanup_ms", 0.0),
                        "boundary_total_ms": round(boundary_work_ms, 3),
                        "play_ms": round(play_ms, 2),
                        "loop_iteration_ms": 0.0,
                        "gc_pause_suspected": False,
                    }
                    _boundary_timing["gc_pause_suspected"] = (
                        boundary_work_ms > _TIMING_WARN_MS
                        and generation_ms == 0.0
                        and swap_ms < _TIMING_WARN_MS
                    )
                    _record_timing("boundary_total_ms", boundary_work_ms)

                # ── Per-bar timing log ──────────────────────────────────────
                t_end = time.perf_counter()
                overhead_ms = (t_end - t_after_play) * 1000
                loop_ms = (t_end - t_after_play) * 1000
                _boundary_timing["loop_iteration_ms"] = round(loop_ms, 3)
                _boundary_timing["play_ms"] = round(play_ms, 2)

                if _BAR_LOG.isEnabledFor(logging.DEBUG):
                    _BAR_LOG.debug(
                        "time_ms=%.1f\tbar=%d\tphrase=%d\tbar_in_phrase=%d\t"
                        "boundary=%d\tplay_ms=%.1f\toverhead_ms=%.2f\t"
                        "transition_ms=%.3f\tcurves_ms=%.3f\t"
                        "state_build_ms=%.3f\tenqueue_ms=%.3f\t"
                        "swap_ms=%.3f\trun_coro_ms=%.3f\t"
                        "prep_ready=%d\tthread_id=%d",
                        (t_end - _T0) * 1000,
                        abs_bar, phrase.phrase_index, bar_in_phrase,
                        int(is_boundary), play_ms, overhead_ms,
                        transition_ms, curves_ms,
                        state_build_ms, enqueue_ms,
                        swap_ms, run_coro_ms,
                        prep_ready, threading.get_ident(),
                    )

                if overhead_ms > _TIMING_WARN_MS:
                    _log.warning(
                        "bar=%d overhead=%.2fms boundary=%d "
                        "state_build=%.3f enqueue=%.3f swap=%.3f run_coro=%.3f",
                        abs_bar, overhead_ms, int(is_boundary),
                        state_build_ms, enqueue_ms, swap_ms, run_coro_ms,
                    )
                    if overhead_ms > _TIMING_WARN_MS and generation_ms == 0.0 and swap_ms < _TIMING_WARN_MS:
                        _boundary_timing["gc_pause_suspected"] = True

        _engine.commit_bank(snapshot)
        bank_start = bar_end   # chain next bank from bar end (no drift)
        bank_idx += 1
    _playing = False


_event_loop: Optional[asyncio.AbstractEventLoop] = None


def _get_loop() -> asyncio.AbstractEventLoop:
    return _event_loop


# ---------------------------------------------------------------------------
# App (lifespan defined here so all globals are in scope)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    global _event_loop, _broadcast_queue, _broadcast_task
    _event_loop = asyncio.get_event_loop()
    _broadcast_queue = asyncio.Queue(maxsize=3)
    _broadcast_task = asyncio.create_task(_broadcast_worker_loop())
    _init_engine()
    yield
    global _playing
    _playing = False
    if _broadcast_task:
        _broadcast_task.cancel()
    if _midi:
        _midi.close()
    if _midi_cc:
        _midi_cc.close()


app = FastAPI(title="thelmic", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = _STATIC / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    async with _clients_lock:
        _clients.add(ws)
    # Send initial state
    await ws.send_text(json.dumps({"type": "state", **_force_state_dict()}))
    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            await _handle_message(msg)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        async with _clients_lock:
            _clients.discard(ws)


async def _handle_message(msg: dict) -> None:
    global _playing, _play_thread, _bpm, _active_pression_mapping_lane, _cr_state, _drop_commit_state, _phase11_state

    kind = msg.get("type")

    if kind == "axis":
        value = float(msg.get("value", 0.0))
        if _playing:
            # Set transition target only — the playback loop drives the journey.
            # Do NOT regenerate the preview bank here: force dimensions must
            # reflect current_position (advanced per bar), not the target.
            _intent.set_axis(value)
            _phase11_state.set_target(value)
            await _broadcast({"type": "state", **_force_state_dict()})
        else:
            # Stopped: set position immediately and regenerate preview
            _intent.set_axis_immediate(value)
            _phase11_state.set_immediate(value)
            await _apply_and_preview()

    elif kind == "play":
        if _midi is None:
            await _broadcast({"type": "error", "message": "No MIDI port selected. Choose a port first."})
            return
        with _play_lock:
            if not _playing:
                _playing = True
                _drop_commit_state = DropCommitState()
                _phase11_state.set_immediate(_engine.landscape_position)
                # Reset archetype lock so the first bank re-derives from density.
                _active_archetype_name  = None
                _pending_archetype_name = None
                _play_thread = threading.Thread(target=_playback_loop, daemon=True)
                _play_thread.start()
        await _broadcast({"type": "state", **_force_state_dict()})

    elif kind == "stop":
        _playing = False
        _cr_state = default_state()   # reset mode on stop
        _drop_commit_state = DropCommitState()
        _phase11_state.set_immediate(_engine.landscape_position)
        await _broadcast({"type": "state", **_force_state_dict()})

    elif kind == "pression_cc_map":
        # Update CC mapping for one or more pression dimensions.
        # Payload: {"value": {"pressure": [channel, cc_num], ...}}
        updates = msg.get("value", {})
        for dim, pair in updates.items():
            if dim in DIMENSION_NAMES and isinstance(pair, (list, tuple)) and len(pair) == 2:
                _pression_cc_map[dim] = (int(pair[0]), int(pair[1]))
        await _broadcast({"type": "state", **_force_state_dict()})

    elif kind == "pression_mapping_lane":
        raw = msg.get("value")
        _active_pression_mapping_lane = raw if raw in DIMENSION_NAMES else None
        await _broadcast({"type": "state", **_force_state_dict()})

    elif kind == "call_response_mode":
        raw = msg.get("value")
        import dataclasses
        if raw is None:
            _cr_state = dataclasses.replace(_cr_state, force_mode=None)
        else:
            try:
                _cr_state = dataclasses.replace(_cr_state, force_mode=Mode(raw))
            except ValueError:
                pass
        await _broadcast({"type": "state", **_force_state_dict()})

    elif kind == "bpm":
        _bpm = max(60.0, min(300.0, float(msg.get("value", 174.0))))
        await _apply_and_preview()

    elif kind == "control":
        key = msg.get("key")
        value = float(msg.get("value", 0.5))
        if key and hasattr(_controls, key):
            setattr(_controls, key, value)
        await _apply_and_preview()

    elif kind == "quantize_bars":
        global _quantize_bars
        _quantize_bars = max(1, int(msg.get("value", 2)))
        await _broadcast({"type": "state", **_force_state_dict()})

    elif kind == "set_archetype":
        name = msg.get("value")
        _generator.selected_archetype = name if (name and name in ARCHETYPE_BY_NAME) else None
        await _apply_and_preview()

    elif kind == "curve_add":
        curve_id = _curve_engine.add(
            shape      = msg.get("shape", "linear"),
            bars       = int(msg.get("bars", 8)),
            from_value = float(msg.get("from_value", 0.0)),
            to_value   = float(msg.get("to_value", 1.0)),
            target     = msg.get("target", "ghost_inject"),
            next_id    = msg.get("next_id"),
            loop       = bool(msg.get("loop", False)),
        )
        await _broadcast({"type": "state", **_force_state_dict()})

    elif kind == "curve_start":
        curve_id = int(msg.get("id", 0))
        _pending_curve_starts.add(curve_id)
        await _broadcast({"type": "state", **_force_state_dict()})

    elif kind == "curve_stop":
        target = msg.get("target", "")
        _curve_engine.stop(target)
        for curve_id, curve in list(_curve_engine._curves.items()):
            if curve.target == target:
                _pending_curve_starts.discard(curve_id)
        await _apply_and_preview()

    elif kind == "curve_remove":
        curve_id = int(msg.get("id", 0))
        _pending_curve_starts.discard(curve_id)
        _curve_engine.remove(curve_id)
        await _broadcast({"type": "state", **_force_state_dict()})

    elif kind == "midi_port":
        port_name = msg.get("value")
        try:
            _open_midi_port(port_name)
            await _broadcast({"type": "state", **_force_state_dict()})
        except RuntimeError as e:
            await _broadcast({"type": "error", "message": str(e)})

    elif kind == "midi_cc_port":
        port_name = msg.get("value")
        try:
            _open_midi_cc_port(port_name)
            await _broadcast({"type": "state", **_force_state_dict()})
        except RuntimeError as e:
            await _broadcast({"type": "error", "message": str(e)})


@app.get("/api/midi-ports")
async def get_midi_ports():
    return {"ports": list_output_ports()}


@app.get("/api/archetypes")
async def get_archetypes():
    return {"archetypes": list(ARCHETYPE_BY_NAME.keys())}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="thelmic web UI")
    parser.add_argument("--bpm", type=float, default=174.0)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument(
        "--timing", action="store_true",
        help="Enable per-bar timing log on stderr (thelmic.bar_timing logger). "
             "Output is tab-separated — pipe to a file and analyse with cut/awk. "
             "Fields: " + "\t".join([
                 "time_ms", "bar", "phrase", "bar_in_phrase",
                 "boundary", "play_ms", "overhead_ms",
                 "transition_ms", "curves_ms", "state_build_ms", "enqueue_ms",
                 "swap_ms", "run_coro_ms", "prep_ready", "thread_id",
             ])
    )
    args = parser.parse_args()

    global _bpm
    _bpm = args.bpm

    if args.timing:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        _BAR_LOG.addHandler(handler)
        _BAR_LOG.setLevel(logging.DEBUG)
        # Also enable the warn-level main logger
        logging.basicConfig(level=logging.WARNING,
                            format="%(asctime)s %(name)s %(levelname)s %(message)s")
        print("thelmic — timing log enabled (stderr). Fields: "
              "time_ms bar phrase bar_in_phrase boundary play_ms overhead_ms "
              "transition_ms curves_ms state_build_ms enqueue_ms "
              "swap_ms run_coro_ms prep_ready thread_id")
    else:
        logging.basicConfig(level=logging.WARNING,
                            format="%(asctime)s %(name)s %(levelname)s %(message)s")

    print(f"thelmic — open http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
