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
from thelmic.controls import Controls
from thelmic.force_engine import ForceEngine
from thelmic.intent import IntentInput
from thelmic.landscape import territory_at
from thelmic.archetypes import archetype_name_at
from thelmic.midi_out import MIDIOut, list_output_ports

import importlib.resources as _res
import pathlib

_STATIC = pathlib.Path(__file__).parent / "static"

# ---------------------------------------------------------------------------
# Engine singleton (module-level, shared across WS connections)
# ---------------------------------------------------------------------------

_engine: Optional[ForceEngine] = None
_controls: Optional[Controls] = None
_intent: Optional[IntentInput] = None
_generator: Optional[BankGenerator] = None
_midi: Optional[MIDIOut] = None
_bpm: float = 174.0
_current_bank = None   # Bank | None

_playing: bool = False
_play_thread: Optional[threading.Thread] = None
_play_lock = threading.Lock()

_clients: set[WebSocket] = set()
_clients_lock = asyncio.Lock()


def _init_engine() -> None:
    global _engine, _controls, _intent, _generator, _midi
    _engine = ForceEngine(landscape_position=0.0)
    _controls = Controls()
    _intent = IntentInput(_engine)
    _generator = BankGenerator(controls=_controls)
    # MIDI init is deferred — no port selected yet
    _midi = None


def _open_midi_port(port_name: Optional[str]) -> str:
    """Open (or switch to) a MIDI port. Returns the connected port name."""
    global _midi
    if _midi is not None:
        _midi.close()
    _midi = MIDIOut(port_name=port_name)
    return _midi.port_name


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
        })
    return events


def _force_state_dict() -> dict:
    fs = _engine.force_state
    pos = _engine.landscape_position
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
        "playing": _playing,
        "bpm": _bpm,
        "bank_events": _bank_events_list(_current_bank),
        "midi_port": _midi.port_name if _midi else None,
        "archetype": archetype_name_at(
            density=_engine.force_state.density,
            instability=_engine.force_state.instability,
            landscape_position=_engine.landscape_position,
        ),
    }


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
    while _playing:
        snapshot = _engine.begin_bank()
        bank = _generator.generate(_engine.force_state, bank_idx, _engine.landscape_position)
        _current_bank = bank
        try:
            loop = _get_loop()
            asyncio.run_coroutine_threadsafe(
                _broadcast({"type": "state", **_force_state_dict()}), loop
            )
        except Exception:
            pass
        if _midi is None:
            _playing = False
            break
        _midi.play_bank_blocking(bank, bpm=_bpm)
        _engine.commit_bank(snapshot)
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
        position = float(msg.get("value", 0.0))
        _intent.set_axis(position)
        await _broadcast({"type": "state", **_force_state_dict()})

    elif kind == "play":
        global _playing, _play_thread
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
        await _broadcast({"type": "state", **_force_state_dict()})

    elif kind == "control":
        key = msg.get("key")
        value = float(msg.get("value", 0.5))
        if key and hasattr(_controls, key):
            setattr(_controls, key, value)
        await _broadcast({"type": "state", **_force_state_dict()})

    elif kind == "midi_port":
        port_name = msg.get("value")
        try:
            connected = _open_midi_port(port_name)
            await _broadcast({"type": "state", **_force_state_dict()})
        except RuntimeError as e:
            await _broadcast({"type": "error", "message": str(e)})


@app.get("/api/midi-ports")
async def get_midi_ports():
    return {"ports": list_output_ports()}


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
