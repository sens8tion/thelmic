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
COMMAND_TIMEOUT_S = 10.0
RECONNECT_BACKOFF_INITIAL = 0.25
RECONNECT_BACKOFF_MAX = 8.0


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
    last_error: Optional[str]
    commands_sent: int
    commands_dropped: int
    commands_failed: int

    def as_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "connected": self.connected,
            "priority_depth": self.priority_depth,
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
        self._queue: Optional[asyncio.Queue] = None
        self._dispatcher_task: Optional[asyncio.Task] = None
        self._connected = False
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._next_id = 1
        self._last_error: Optional[str] = None
        self._sent = 0
        self._dropped = 0
        self._failed = 0
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
            self._queue = asyncio.Queue(maxsize=PRIORITY_QUEUE_MAX)
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

    def load_device(self, track_index: int, item_uri: str) -> Future:
        return self._enqueue(
            "load_browser_item",
            {"track_index": track_index, "item_uri": item_uri},
        )

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self) -> ChannelStatus:
        depth = self._queue.qsize() if self._queue is not None else 0
        return ChannelStatus(
            enabled=self._enabled,
            connected=self._connected,
            priority_depth=depth,
            last_error=self._last_error,
            commands_sent=self._sent,
            commands_dropped=self._dropped,
            commands_failed=self._failed,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _enqueue(self, cmd_type: str, params: dict) -> Future:
        fut: Future = Future()
        if not self._enabled or self._loop is None:
            fut.set_exception(RuntimeError("LiveChannel disabled or not started"))
            return fut

        def _put():
            assert self._queue is not None
            req_id = self._next_id
            self._next_id += 1
            payload = {"type": cmd_type, "params": params, "request_id": req_id}
            pending = _Pending(req_id, payload, fut)
            try:
                self._queue.put_nowait(pending)
            except asyncio.QueueFull:
                self._dropped += 1
                LOG.warning(
                    "LiveChannel queue full (max=%d), dropping %s",
                    PRIORITY_QUEUE_MAX,
                    cmd_type,
                )
                if not fut.done():
                    fut.set_exception(RuntimeError("LiveChannel queue full"))

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

    async def _dispatcher(self):
        assert self._queue is not None
        while not self._stopped.is_set():
            try:
                pending: _Pending = await self._queue.get()
            except asyncio.CancelledError:
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
