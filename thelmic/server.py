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
import threading
import time
from typing import Optional

import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from thelmic.bank_generator import BankGenerator
from thelmic.deformations import DEFORMATION_COLOURS
from thelmic.pressure_curves import CurveEngine
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
    "groove_lock":           "unused",
    "chaos_limit":           "clamps instability",
    "density_ceiling":       "clamps density",
    "variation_rate":        "unused",
    "kick_dominance":        "unused",
}

DEFORMATION_MODEL_DIMENSIONS: dict[str, str] = {
    "ghost_inject": "instability",
}
from thelmic.controls import Controls
from thelmic.force_engine import ForceEngine
from thelmic.intent import IntentInput
from thelmic.landscape import territory_at
from thelmic.archetypes import archetype_name_at
from thelmic.midi_out import MIDIOut, list_output_ports
from thelmic.archetypes import ARCHETYPE_BY_NAME

import importlib.resources as _res
import pathlib

_STATIC = pathlib.Path(__file__).parent / "static"

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

_playing: bool = False
_play_thread: Optional[threading.Thread] = None
_play_lock = threading.Lock()
_bank_started_at_ms: float = 0.0   # wall-clock ms when current bank began playing

_quantize_bars: int = 2   # bars between quantize boundaries (1 = every bar)
_preview_lock = threading.Lock()  # guards _current_bank writes from handler vs loop

_clients: set[WebSocket] = set()
_clients_lock = asyncio.Lock()


def _generation_curve_overrides() -> dict[str, float]:
    from thelmic.bank_generator import BARS_PER_PHRASE
    from thelmic.behaviour_hooks import compute_behaviour_overrides

    manual = _curve_engine.projected_overrides(BARS_PER_PHRASE)
    transition = _transition_engine.transition if _transition_engine else None
    force = _engine.force_state if _engine else None
    if force is None:
        return manual
    return compute_behaviour_overrides(transition, force, manual)


async def _apply_and_preview() -> None:
    """Update the display bank ahead of the current playhead, broadcast immediately.

    Phrases already played (behind the playhead) keep their original content.
    Only phrases strictly ahead of the current playhead are regenerated from
    the new state, so the grid shows what's coming without rewriting history.
    The playback loop will regenerate those same phrases at the next quantize
    boundary so MIDI catches up.
    """
    global _current_bank
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
        fresh = _generator.generate(
            _engine.force_state, _current_bank.bank_index, _engine.landscape_position,
            curve_overrides=_generation_curve_overrides(),
        )
        # Splice: keep up-to-and-including current phrase, replace the rest
        for i, phrase in enumerate(fresh.phrases):
            if i > current_phrase_idx:
                _current_bank.phrases[i] = phrase

    await _broadcast({"type": "state", **_force_state_dict()})


def _init_engine() -> None:
    global _engine, _transition_engine, _controls, _intent, _generator, _midi
    _engine = ForceEngine(landscape_position=0.0)
    _transition_engine = TransitionEngine(_engine)
    _controls = Controls()
    _intent = IntentInput(_engine, _transition_engine)
    _generator = BankGenerator(controls=_controls)
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
        events.append({
            "time": event.time,
            "layer": event.layer,
            "role": event.role,
            "velocity": event.velocity,
            "emphasis": round(event.emphasis, 2),
            "deformation": {k: round(v, 3) for k, v in event.deformation.items()},
        })
    return events


def _force_state_dict() -> dict:
    fs = _engine.force_state
    pos = _engine.landscape_position
    pressure_curves = _curve_engine.state_dict()
    pressure_curves["pending_ids"] = sorted(_pending_curve_starts)
    bank_slot = len(_engine.bank_history) % 4 + 1
    return {
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
        "bank_events": _bank_events_list(_current_bank),
        "midi_port": _midi.port_name if _midi else None,
        "midi_cc_port": _midi_cc.port_name if _midi_cc else None,
        "archetype": archetype_name_at(density=_engine.force_state.density),
        "selected_archetype": _generator.selected_archetype,
        "deformation_colours": DEFORMATION_COLOURS,
        "deformation_model_dimensions": DEFORMATION_MODEL_DIMENSIONS,
        "dimension_roles": DIMENSION_ROLES,
        "pressure_curves": pressure_curves,
        "quantize_bars": _quantize_bars,
        "bank_started_at": _bank_started_at_ms,
        "bank_duration_ms": round((16 * 4 * 60000) / _bpm, 1),
        "transition": _transition_engine.state_dict() if _transition_engine else {},
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


async def _broadcast(msg: dict) -> None:
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
    global _playing, _current_bank
    bank_idx = 0
    bank_start: float | None = None   # absolute start of current bank (prevents drift)
    while _playing:

        _start_pending_curves()
        snapshot = _engine.begin_bank()
        bank = _generator.generate(
            _engine.force_state, bank_idx, _engine.landscape_position,
            curve_overrides=_generation_curve_overrides(),
        )
        _current_bank = bank

        if _midi is None:
            _playing = False
            break

        if bank_start is None:
            bank_start = time.perf_counter()

        global _bank_started_at_ms
        _bank_started_at_ms = time.time() * 1000
        try:
            asyncio.run_coroutine_threadsafe(
                _broadcast({"type": "state", **_force_state_dict()}), _get_loop()
            )
        except Exception:
            pass

        # Play bar by bar — advances the curve engine once per bar so CC output
        # fires at bar resolution rather than phrase resolution (4× finer).
        # Quantize boundaries can now fire on any bar, not just phrase ends.
        from thelmic.bank_generator import BARS_PER_PHRASE
        bar_end = bank_start
        for phrase in bank.phrases:
            if not _playing:
                break
            for bar_in_phrase in range(BARS_PER_PHRASE):
                if not _playing:
                    break
                bar_end = _midi.play_bar_in_phrase_blocking(
                    phrase, bar_in_phrase, bpm=_bpm, bank_start=bank_start,
                )

                # Advance transition first — landscape position updates before
                # curves read it, so deformations see the correct position
                if _transition_engine:
                    _transition_engine.advance(bars=1)

                # Advance curve engine 1 bar; send CC outputs on the CC port
                cc_messages = _curve_engine.advance(bars=1)
                if _midi_cc:
                    for cc_target, cc_num, val in cc_messages:
                        parts = cc_target.split(":")
                        ch = int(parts[1]) if len(parts) >= 3 else 0
                        _midi_cc.send_cc(ch, cc_num, val)

                # Quantize boundary — fires every _quantize_bars bars.
                # Pending curves are started and upcoming phrases are regenerated
                # so both MIDI and the grid catch up to the current state.
                abs_bar = phrase.phrase_index * BARS_PER_PHRASE + bar_in_phrase + 1
                if abs_bar % max(1, _quantize_bars) == 0:
                    injected_curve = _start_pending_curves()
                    next_idx = phrase.phrase_index + 1
                    regenerated = False
                    if next_idx < len(bank.phrases):
                        with _preview_lock:
                            fresh = _generator.generate(
                                _engine.force_state, bank_idx, _engine.landscape_position,
                                curve_overrides=_generation_curve_overrides(),
                            )
                            bank.phrases[next_idx:] = fresh.phrases[next_idx:]
                            _current_bank = bank
                            regenerated = True
                    if injected_curve or regenerated:
                        try:
                            asyncio.run_coroutine_threadsafe(
                                _broadcast({"type": "state", **_force_state_dict()}), _get_loop()
                            )
                        except Exception:
                            pass

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
    global _event_loop
    _event_loop = asyncio.get_event_loop()
    _init_engine()
    yield
    global _playing
    _playing = False
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
    global _playing, _play_thread, _bpm

    kind = msg.get("type")

    if kind == "axis":
        value = float(msg.get("value", 0.0))
        if _playing:
            # Set transition target only — the playback loop drives the journey.
            # Do NOT regenerate the preview bank here: force dimensions must
            # reflect current_position (advanced per bar), not the target.
            _intent.set_axis(value)
            await _broadcast({"type": "state", **_force_state_dict()})
        else:
            # Stopped: set position immediately and regenerate preview
            _intent.set_axis_immediate(value)
            await _apply_and_preview()

    elif kind == "play":
        if _midi is None:
            await _broadcast({"type": "error", "message": "No MIDI port selected. Choose a port first."})
            return
        with _play_lock:
            if not _playing:
                _playing = True
                _play_thread = threading.Thread(target=_playback_loop, daemon=True)
                _play_thread.start()
        await _broadcast({"type": "state", **_force_state_dict()})

    elif kind == "stop":
        _playing = False
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
    args = parser.parse_args()

    global _bpm
    _bpm = args.bpm

    print(f"thelmic — open http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
