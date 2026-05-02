"""Async LOM side channel.

Talks to the ThelmicLive Remote Script (or upstream ableton-mcp) over a
JSON-newline-ish TCP socket. Hard isolation from the realtime MIDI engine:
the public API is fire-and-forget, bounded-queue, drop-on-overflow.

Off by default. Enable with env var LIVE_CHANNEL_ENABLED=1.

Threading model
---------------
- The channel owns one asyncio event loop on a dedicated daemon thread.
- Public sync methods enqueue commands onto an asyncio.Queue from any thread
  via loop.call_soon_threadsafe.
- A single dispatcher coroutine drains the queue, sends one command at a
  time, awaits the response, fulfils the future.
- Connection lifecycle is lazy: first command triggers connect; drops trigger
  exponential backoff reconnect; in-flight command on a drop fails its future
  but does NOT raise on the caller's thread.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import threading
import time
from concurrent.futures import Future
from dataclasses import dataclass, field
from typing import Any, Optional

from thelmic._priority import lower_process_priority

LOG = logging.getLogger("thelmic.live_channel")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9878  # ThelmicLive Remote Script port
PRIORITY_QUEUE_MAX = 32
BULK_QUEUE_MAX = 256
COMMAND_TIMEOUT_S = 10.0
RECONNECT_BACKOFF_INITIAL = 0.25
RECONNECT_BACKOFF_MAX = 8.0

LANE_PRIORITY = "priority"
LANE_BULK = "bulk"


def is_enabled() -> bool:
    val = os.environ.get("LIVE_CHANNEL_ENABLED", "")
    return val.lower() in ("1", "true", "yes", "on")


@dataclass
class _Pending:
    request_id: int
    payload: dict
    future: Future
    enqueued_at: float = field(default_factory=time.monotonic)


@dataclass
class ChannelStatus:
    enabled: bool
    connected: bool
    priority_depth: int
    bulk_depth: int
    bulk_paused: bool
    last_error: Optional[str]
    commands_sent: int
    commands_dropped: int
    commands_failed: int

    def as_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "connected": self.connected,
            "priority_depth": self.priority_depth,
            "bulk_depth": self.bulk_depth,
            "bulk_paused": self.bulk_paused,
            "last_error": self.last_error,
            "commands_sent": self.commands_sent,
            "commands_dropped": self.commands_dropped,
            "commands_failed": self.commands_failed,
        }


class LiveChannel:
    """Sync facade around an asyncio TCP client.

    Construct, call start() once, then call public command methods from any
    thread. They return concurrent.futures.Future. Most callers fire-and-forget.
    """

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        *,
        enabled: Optional[bool] = None,
        lower_priority: bool = True,
    ):
        self.host = host
        self.port = port
        self._enabled = is_enabled() if enabled is None else enabled
        self._lower_priority = lower_priority

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._priority_q: Optional[asyncio.Queue] = None
        self._bulk_q: Optional[asyncio.Queue] = None
        self._wakeup: Optional[asyncio.Event] = None
        self._dispatcher_task: Optional[asyncio.Task] = None
        self._connected = False
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._next_id = 1
        self._last_error: Optional[str] = None
        self._sent = 0
        self._dropped = 0
        self._failed = 0
        self._bulk_paused = False
        self._stopped = threading.Event()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        if not self._enabled:
            LOG.info("LiveChannel disabled (LIVE_CHANNEL_ENABLED not set).")
            return
        if self._thread is not None:
            return
        if self._lower_priority:
            try:
                lower_process_priority()
            except Exception as e:
                LOG.warning("Could not lower process priority: %s", e)

        ready = threading.Event()

        def _run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            self._priority_q = asyncio.Queue(maxsize=PRIORITY_QUEUE_MAX)
            self._bulk_q = asyncio.Queue(maxsize=BULK_QUEUE_MAX)
            self._wakeup = asyncio.Event()
            self._dispatcher_task = loop.create_task(self._dispatcher())
            ready.set()
            try:
                loop.run_forever()
            finally:
                try:
                    loop.run_until_complete(loop.shutdown_asyncgens())
                except Exception:
                    pass
                loop.close()

        self._thread = threading.Thread(target=_run, name="thelmic-live-channel", daemon=True)
        self._thread.start()
        ready.wait(timeout=2.0)

    def stop(self) -> None:
        if self._loop is None:
            return
        self._stopped.set()

        def _shutdown():
            if self._dispatcher_task:
                self._dispatcher_task.cancel()
            if self._writer:
                try:
                    self._writer.close()
                except Exception:
                    pass
            self._loop.stop()

        try:
            self._loop.call_soon_threadsafe(_shutdown)
        except RuntimeError:
            pass
        if self._thread:
            self._thread.join(timeout=2.0)
        self._thread = None
        self._loop = None

    # ------------------------------------------------------------------
    # Public command surface
    # ------------------------------------------------------------------

    def ping(self) -> Future:
        return self._enqueue("ping", {})

    def set_tempo(self, bpm: float) -> Future:
        return self._enqueue("set_tempo", {"tempo": float(bpm)})

    def fire_clip(self, track_index: int, clip_index: int) -> Future:
        return self._enqueue(
            "fire_clip", {"track_index": track_index, "clip_index": clip_index}
        )

    def stop_clip(self, track_index: int, clip_index: int) -> Future:
        return self._enqueue(
            "stop_clip", {"track_index": track_index, "clip_index": clip_index}
        )

    def create_clip(self, track_index: int, clip_index: int, length_beats: float = 4.0) -> Future:
        return self._enqueue(
            "create_clip",
            {"track_index": track_index, "clip_index": clip_index, "length": float(length_beats)},
        )

    def add_notes_to_clip(
        self,
        track_index: int,
        clip_index: int,
        notes: list,
        *,
        replace: bool = False,
    ) -> Future:
        return self._enqueue(
            "add_notes_to_clip",
            {
                "track_index": track_index,
                "clip_index": clip_index,
                "notes": notes,
                "replace": replace,
            },
        )

    def set_clip_name(self, track_index: int, clip_index: int, name: str) -> Future:
        return self._enqueue(
            "set_clip_name",
            {"track_index": track_index, "clip_index": clip_index, "name": name},
        )

    def clear_clip(self, track_index: int, clip_index: int) -> Future:
        return self._enqueue(
            "clear_clip", {"track_index": track_index, "clip_index": clip_index}
        )

    def get_session_info(self) -> Future:
        return self._enqueue("get_session_info", {})

    def get_track_info(self, track_index: int) -> Future:
        return self._enqueue("get_track_info", {"track_index": track_index})

    def get_device_info(self, track_index: int, device_index: int) -> Future:
        return self._enqueue(
            "get_device_info",
            {"track_index": track_index, "device_index": device_index},
        )

    def set_device_param(
        self,
        track_index: int,
        device_index: int,
        param: int | str,
        value: float,
    ) -> Future:
        params: dict = {
            "track_index": track_index,
            "device_index": device_index,
            "value": float(value),
        }
        if isinstance(param, int):
            params["param_index"] = param
        else:
            params["param_name"] = param
        return self._enqueue("set_device_param", params)

    def get_device_param(
        self,
        track_index: int,
        device_index: int,
        param: int | str,
    ) -> Future:
        params: dict = {"track_index": track_index, "device_index": device_index}
        if isinstance(param, int):
            params["param_index"] = param
        else:
            params["param_name"] = param
        return self._enqueue("get_device_param", params)

    def delete_device(self, track_index: int, device_index: int) -> Future:
        return self._enqueue(
            "delete_device", {"track_index": track_index, "device_index": device_index}
        )

    def load_device(self, track_index: int, item_uri: str, lane: str = LANE_PRIORITY) -> Future:
        return self._enqueue(
            "load_browser_item",
            {"track_index": track_index, "item_uri": item_uri},
            lane,
        )

    def move_device(self, track_index: int, from_index: int, to_index: int) -> Future:
        return self._enqueue(
            "move_device",
            {"track_index": track_index, "from_index": from_index, "to_index": to_index},
        )

    def set_track_name(self, track_index: int, name: str) -> Future:
        return self._enqueue("set_track_name", {"track_index": track_index, "name": name})

    def create_midi_track(self, index: int = -1) -> Future:
        return self._enqueue("create_midi_track", {"index": index})

    def set_track_volume(self, track_index: int, value: float) -> Future:
        return self._enqueue("set_track_volume", {"track_index": track_index, "value": float(value)})

    def set_track_pan(self, track_index: int, value: float) -> Future:
        return self._enqueue("set_track_pan", {"track_index": track_index, "value": float(value)})

    def set_track_mute(self, track_index: int, on: bool) -> Future:
        return self._enqueue("set_track_mute", {"track_index": track_index, "value": bool(on)})

    def set_track_solo(self, track_index: int, on: bool) -> Future:
        return self._enqueue("set_track_solo", {"track_index": track_index, "value": bool(on)})

    def set_send(self, track_index: int, send_index: int, value: float) -> Future:
        return self._enqueue(
            "set_send",
            {"track_index": track_index, "send_index": send_index, "value": float(value)},
        )

    def get_return_tracks(self) -> Future:
        return self._enqueue("get_return_tracks", {})

    def get_master_track(self) -> Future:
        return self._enqueue("get_master_track", {})

    def define_rack_macro(
        self,
        track_index: int,
        device_index: int,
        macro_index: int,
        name: str | None = None,
        mappings: list | None = None,
    ) -> Future:
        return self._enqueue(
            "define_rack_macro",
            {
                "track_index": track_index,
                "device_index": device_index,
                "macro_index": macro_index,
                "name": name,
                "mappings": mappings or [],
            },
        )

    def get_rack_macros(self, track_index: int, device_index: int) -> Future:
        return self._enqueue(
            "get_rack_macros",
            {"track_index": track_index, "device_index": device_index},
        )

    def set_macro_value(self, track_index: int, device_index: int, macro_index: int, value: float) -> Future:
        return self._enqueue(
            "set_macro_value",
            {
                "track_index": track_index,
                "device_index": device_index,
                "macro_index": macro_index,
                "value": float(value),
            },
        )

    def snapshot_track(self, track_index: int) -> Future:
        return self._enqueue("snapshot_track", {"track_index": track_index})

    def restore_track(self, track_index: int, snapshot: dict) -> Future:
        return self._enqueue(
            "restore_track",
            {"track_index": track_index, "snapshot": snapshot},
        )

    def get_browser_tree(self, category: str = "all") -> Future:
        return self._enqueue("get_browser_tree", {"category": category})

    def get_browser_items_at_path(self, path: str) -> Future:
        return self._enqueue("get_browser_items_at_path", {"path": path})

    def set_device_sidechain_source(self, track_index: int, device_index: int, source_track_index: int) -> Future:
        return self._enqueue(
            "set_device_sidechain_source",
            {
                "track_index": track_index,
                "device_index": device_index,
                "source_track_index": source_track_index,
            },
        )

    def get_device_routing_options(self, track_index: int, device_index: int) -> Future:
        return self._enqueue(
            "get_device_routing_options",
            {"track_index": track_index, "device_index": device_index},
        )

    def fire_scene(self, scene_index: int) -> Future:
        return self._enqueue("fire_scene", {"scene_index": scene_index})

    def stop_all_clips(self) -> Future:
        return self._enqueue("stop_all_clips", {})

    def set_track_output_routing(self, track_index: int, target_name: str) -> Future:
        return self._enqueue(
            "set_track_output_routing",
            {"track_index": track_index, "target_name": target_name},
        )

    def get_track_output_options(self, track_index: int) -> Future:
        return self._enqueue("get_track_output_options", {"track_index": track_index})

    def create_audio_track(self, index: int = -1) -> Future:
        return self._enqueue("create_audio_track", {"index": index})

    def set_track_monitoring(self, track_index: int, state: int) -> Future:
        """state: 0=In, 1=Auto, 2=Off"""
        return self._enqueue("set_track_monitoring", {"track_index": track_index, "state": int(state)})

    def set_track_arm(self, track_index: int, on: bool) -> Future:
        return self._enqueue("set_track_arm", {"track_index": track_index, "value": bool(on)})

    def set_clip_envelope(self, clip_track: int, clip_index: int,
                          target_track: int, target_device: int,
                          target_param: int | str, breakpoints: list) -> Future:
        return self._enqueue("set_clip_envelope", {
            "clip_track": clip_track, "clip_index": clip_index,
            "target_track": target_track, "target_device": target_device,
            "target_param": target_param, "breakpoints": breakpoints,
        })

    def clear_clip_envelope(self, clip_track: int, clip_index: int,
                            target_track: int, target_device: int,
                            target_param: int | str) -> Future:
        return self._enqueue("clear_clip_envelope", {
            "clip_track": clip_track, "clip_index": clip_index,
            "target_track": target_track, "target_device": target_device,
            "target_param": target_param,
        })

    def load_item_at_path(self, track_index: int, path: str, item_name: str | None = None,
                          drum_pad_note: int | None = None,
                          drum_device_index: int | None = None) -> Future:
        return self._enqueue("load_item_at_path", {
            "track_index": track_index, "path": path, "item_name": item_name,
            "drum_pad_note": drum_pad_note, "drum_device_index": drum_device_index,
        })

    def set_clip_loop(self, track_index: int, clip_index: int, loop: bool) -> Future:
        return self._enqueue("set_clip_loop", {
            "track_index": track_index, "clip_index": clip_index, "loop": bool(loop),
        })

    def set_clip_loop_region(self, track_index: int, clip_index: int, loop_start: float, loop_end: float) -> Future:
        return self._enqueue("set_clip_loop_region", {
            "track_index": track_index, "clip_index": clip_index,
            "loop_start": float(loop_start), "loop_end": float(loop_end),
        })

    def set_clip_warp(self, track_index: int, clip_index: int,
                      warping: bool | None = None, warp_mode: int | None = None) -> Future:
        return self._enqueue("set_clip_warp", {
            "track_index": track_index, "clip_index": clip_index,
            "warping": warping, "warp_mode": warp_mode,
        })

    def delete_track(self, track_index: int) -> Future:
        return self._enqueue("delete_track", {"track_index": track_index})

    def get_arrangement_loop(self) -> Future:
        return self._enqueue("get_arrangement_loop", {})

    def set_arrangement_loop(self, start: float | None = None, length: float | None = None,
                             on: bool | None = None) -> Future:
        return self._enqueue("set_arrangement_loop", {"start": start, "length": length, "on": on})

    def get_drum_pads(self, track_index: int, device_index: int) -> Future:
        return self._enqueue("get_drum_pads", {"track_index": track_index, "device_index": device_index})

    def set_drum_pad_mute(self, track_index: int, device_index: int, note: int, mute: bool) -> Future:
        return self._enqueue("set_drum_pad_mute", {
            "track_index": track_index, "device_index": device_index, "note": int(note), "mute": bool(mute),
        })

    def set_drum_pad_volume(self, track_index: int, device_index: int, note: int, value: float) -> Future:
        return self._enqueue("set_drum_pad_volume", {
            "track_index": track_index, "device_index": device_index, "note": int(note), "value": float(value),
        })

    def load_master_device(self, uri: str | None = None, path: str | None = None,
                           item_name: str | None = None) -> Future:
        return self._enqueue("load_master_device", {"uri": uri, "path": path, "item_name": item_name})

    def get_master_device_info(self, device_index: int) -> Future:
        return self._enqueue("get_master_device_info", {"device_index": device_index})

    def set_master_device_param(self, device_index: int, param: int | str, value: float) -> Future:
        params = {"device_index": device_index, "value": float(value)}
        if isinstance(param, int): params["param_index"] = param
        else: params["param_name"] = param
        return self._enqueue("set_master_device_param", params)

    def get_master_device_param(self, device_index: int, param: int | str) -> Future:
        params = {"device_index": device_index}
        if isinstance(param, int): params["param_index"] = param
        else: params["param_name"] = param
        return self._enqueue("get_master_device_param", params)

    def delete_master_device(self, device_index: int) -> Future:
        return self._enqueue("delete_master_device", {"device_index": device_index})

    def list_browser_roots(self) -> Future:
        return self._enqueue("list_browser_roots", {})

    def get_track_meter(self, track_index: int) -> Future:
        return self._enqueue("get_track_meter", {"track_index": track_index})

    def get_all_meters(self) -> Future:
        return self._enqueue("get_all_meters", {})

    def set_launch_quantization(self, bars: float) -> Future:
        """bars: 0 (off), 0.0625, 0.125, 0.25, 0.5, 1, 2, 4, 8, 16."""
        return self._enqueue("set_launch_quantization", {"bars": bars})

    def submit_bulk(self, cmd_type: str, params: dict) -> Future:
        """Escape hatch: enqueue any command on the bulk lane.

        Used by sound_design.apply_patch when batching many param writes.
        """
        return self._enqueue(cmd_type, params, lane=LANE_BULK)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self) -> ChannelStatus:
        pd = self._priority_q.qsize() if self._priority_q is not None else 0
        bd = self._bulk_q.qsize() if self._bulk_q is not None else 0
        return ChannelStatus(
            enabled=self._enabled,
            connected=self._connected,
            priority_depth=pd,
            bulk_depth=bd,
            bulk_paused=self._bulk_paused,
            last_error=self._last_error,
            commands_sent=self._sent,
            commands_dropped=self._dropped,
            commands_failed=self._failed,
        )

    def pause_bulk(self) -> None:
        self._bulk_paused = True

    def resume_bulk(self) -> None:
        self._bulk_paused = False
        if self._loop is not None and self._wakeup is not None:
            self._loop.call_soon_threadsafe(self._wakeup.set)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _enqueue(self, cmd_type: str, params: dict, lane: str = LANE_PRIORITY) -> Future:
        fut: Future = Future()
        if not self._enabled or self._loop is None:
            fut.set_exception(RuntimeError("LiveChannel disabled or not started"))
            return fut

        def _put():
            q = self._priority_q if lane == LANE_PRIORITY else self._bulk_q
            assert q is not None and self._wakeup is not None
            req_id = self._next_id
            self._next_id += 1
            payload = {"type": cmd_type, "params": params, "request_id": req_id}
            pending = _Pending(req_id, payload, fut)
            try:
                q.put_nowait(pending)
                self._wakeup.set()
            except asyncio.QueueFull:
                self._dropped += 1
                LOG.warning("LiveChannel %s queue full, dropping %s", lane, cmd_type)
                if not fut.done():
                    fut.set_exception(RuntimeError("LiveChannel " + lane + " queue full"))

        try:
            self._loop.call_soon_threadsafe(_put)
        except RuntimeError as e:
            fut.set_exception(e)
        return fut

    async def _ensure_connected(self) -> bool:
        if self._connected and self._writer is not None:
            return True
        backoff = RECONNECT_BACKOFF_INITIAL
        while not self._stopped.is_set():
            try:
                self._reader, self._writer = await asyncio.open_connection(
                    self.host, self.port
                )
                self._connected = True
                self._last_error = None
                LOG.info("LiveChannel connected to %s:%d", self.host, self.port)
                return True
            except (ConnectionRefusedError, OSError, socket.error) as e:
                self._last_error = str(e)
                self._connected = False
                LOG.debug("Connect failed: %s — backoff %.2fs", e, backoff)
                try:
                    await asyncio.sleep(backoff)
                except asyncio.CancelledError:
                    return False
                backoff = min(backoff * 2, RECONNECT_BACKOFF_MAX)
        return False

    async def _next_pending(self) -> Optional[_Pending]:
        """Priority-first pull. Bulk is starved while priority is non-empty
        or while bulk is paused. Sleeps on the wakeup event when both lanes
        are empty (or only bulk has work and bulk is paused)."""
        assert self._priority_q is not None and self._bulk_q is not None
        assert self._wakeup is not None
        while not self._stopped.is_set():
            if not self._priority_q.empty():
                return self._priority_q.get_nowait()
            if not self._bulk_paused and not self._bulk_q.empty():
                return self._bulk_q.get_nowait()
            self._wakeup.clear()
            try:
                await self._wakeup.wait()
            except asyncio.CancelledError:
                return None
        return None

    async def _dispatcher(self):
        while not self._stopped.is_set():
            pending = await self._next_pending()
            if pending is None:
                return
            ok = await self._ensure_connected()
            if not ok:
                self._failed += 1
                if not pending.future.done():
                    pending.future.set_exception(
                        RuntimeError("LiveChannel: not connected")
                    )
                continue
            try:
                await self._send_and_recv(pending)
            except Exception as e:
                self._last_error = str(e)
                self._connected = False
                if self._writer is not None:
                    try:
                        self._writer.close()
                    except Exception:
                        pass
                    self._writer = None
                    self._reader = None
                self._failed += 1
                if not pending.future.done():
                    pending.future.set_exception(e)

    async def _send_and_recv(self, pending: _Pending):
        assert self._writer is not None and self._reader is not None
        wire = json.dumps(pending.payload).encode("utf-8")
        self._writer.write(wire)
        await self._writer.drain()
        self._sent += 1
        # Upstream framing: server replies with one JSON object per request, no
        # delimiter, but the buffer is reset on each parse. Read until we can
        # parse a complete JSON document.
        buf = b""
        deadline = time.monotonic() + COMMAND_TIMEOUT_S
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("LiveChannel response timeout")
            chunk = await asyncio.wait_for(self._reader.read(8192), timeout=remaining)
            if not chunk:
                raise ConnectionResetError("Remote Script closed connection")
            buf += chunk
            try:
                response = json.loads(buf.decode("utf-8"))
                break
            except (ValueError, UnicodeDecodeError):
                continue
        if response.get("status") == "error":
            err = response.get("message", "remote error")
            if not pending.future.done():
                pending.future.set_exception(RuntimeError(err))
            return
        if not pending.future.done():
            pending.future.set_result(response.get("result", {}))


_singleton: Optional[LiveChannel] = None


def get() -> LiveChannel:
    """Return the process-wide LiveChannel singleton (started lazily)."""
    global _singleton
    if _singleton is None:
        _singleton = LiveChannel()
        _singleton.start()
    return _singleton
