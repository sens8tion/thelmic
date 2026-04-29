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
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from thelmic.bank_generator import Bank, BARS_PER_PHRASE, PHRASES_PER_BANK
from thelmic.midi_out import LAYER_CHANNELS, MIDIOut, list_output_ports
from thelmic.note_generation_chain import VERSION as NOTE_GENERATION_VERSION
from thelmic.note_generation_chain import BANK_STEPS, generate_bank, structure_frames
from thelmic.stream_engine import VERSION as STREAM_ENGINE_VERSION


THELMIC_VERSION = "v1.01"
MUSIC_RULES_VERSION = "v1.0"
MOTIF_ENGINE_VERSION = "v1.0"
PRESSION_ENGINE_VERSION = "v0.9-disabled"
TEST_CONTRACT_VERSION = "v1.0"

_ROOT = Path(__file__).resolve().parent
_STATIC = _ROOT / "static"

app = FastAPI()
app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")

_log = logging.getLogger(__name__)

_clients: set[WebSocket] = set()
_playing = False
_bpm = 174.0
_bank_index = 0
_playhead_step = 0
_bank_started_at_ms = 0.0
_current_bank: Bank = generate_bank(0)
_midi: MIDIOut | None = None
_midi_port_name: str | None = None
_play_thread: threading.Thread | None = None
_stop_event = threading.Event()
_state_lock = threading.Lock()
_broadcast_loop: asyncio.AbstractEventLoop | None = None


def _state(include_bank: bool = True) -> dict:
    with _state_lock:
        bank = _current_bank
        bank_index = _bank_index
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
        "selected_archetype": "v1-rule-driven",
        "active_archetype": "v1-rule-driven",
        "archetype": "v1-rule-driven",
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
        "structure_frames": [frame.to_dict() for frame in structure_frames(bank_index)],
    }
    if include_bank:
        state["bank_events"] = _bank_events_list(bank)
    return state


def _bank_events_list(bank: Bank) -> list[dict]:
    events = []
    for event in bank.all_events():
        if not event.active:
            continue
        events.append({
            "time": event.time,
            "note": event.note,
            "velocity": event.velocity,
            "duration": event.duration,
            "layer": event.layer,
            "role": event.role,
            "source": event.source,
            "reason": event.reason,
            "origin_source": event.origin_source,
            "origin_reason": event.origin_reason,
            "resolution_reason": event.resolution_reason,
            "intent_id": event.intent_id,
            "resolved_event_id": event.resolved_event_id,
            "global_step": event.global_step,
            "musical_step": event.musical_step,
            "phrase_index": event.phrase_index,
            "bar_index": event.bar_index,
            "structural_authority": event.structural_authority,
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


def _play_loop() -> None:
    global _bank_index, _current_bank, _playhead_step, _bank_started_at_ms
    next_start = time.perf_counter()
    while not _stop_event.is_set():
        with _state_lock:
            bank = _current_bank
            _playhead_step = 0
        if _midi is not None:
            try:
                next_start = _midi.play_bank_blocking(bank, bpm=_bpm, start_time=next_start)
            except Exception:
                _log.exception("MIDI playback failed")
                next_start = time.perf_counter()
        else:
            seconds_per_bank = (60.0 / _bpm) * 4 * BARS_PER_PHRASE * PHRASES_PER_BANK
            end_time = next_start + seconds_per_bank
            while time.perf_counter() < end_time and not _stop_event.is_set():
                time.sleep(0.02)
            next_start = end_time
        with _state_lock:
            _bank_index += 1
            _current_bank = generate_bank(_bank_index)
            _playhead_step = 0
            _bank_started_at_ms = time.time() * 1000
        _queue_broadcast(include_bank=True)


def _start_playback() -> None:
    global _playing, _play_thread, _bank_started_at_ms
    if _playing:
        return
    _stop_event.clear()
    _playing = True
    _bank_started_at_ms = time.time() * 1000
    _play_thread = threading.Thread(target=_play_loop, daemon=True)
    _play_thread.start()


def _stop_playback() -> None:
    global _playing, _playhead_step, _bank_started_at_ms
    _playing = False
    _stop_event.set()
    _playhead_step = 0
    _bank_started_at_ms = 0.0


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return (_STATIC / "index.html").read_text(encoding="utf-8")


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    global _bpm, _current_bank, _bank_index, _midi, _midi_port_name, _broadcast_loop
    _broadcast_loop = asyncio.get_running_loop()
    await ws.accept()
    _clients.add(ws)
    await ws.send_text(json.dumps(_state(include_bank=True)))
    try:
        while True:
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
                if port_name:
                    _midi = MIDIOut(port_name)
                    _midi_port_name = _midi.port_name
                else:
                    _midi_port_name = None
            elif kind == "pression_mapping_lane":
                pass
            elif kind == "set_archetype":
                pass
            with _state_lock:
                if not _playing:
                    _bank_index = 0
                    _current_bank = generate_bank(0)
            await _broadcast_state(include_bank=True)
    except WebSocketDisconnect:
        _clients.discard(ws)


@app.get("/api/midi-ports")
async def api_midi_ports() -> dict:
    try:
        ports = list_output_ports()
    except Exception:
        ports = []
    return {"ports": ports}


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
