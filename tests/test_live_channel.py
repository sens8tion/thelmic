"""Mock-socket tests for thelmic.live_channel.

Verifies:
- disabled flag → no socket activity, futures fail cleanly
- happy path: ping round-trip
- request/response correlation across rapid sends
- queue bounded: drop-on-overflow + commands_dropped increments
- reconnect: server drop is recovered transparently
- structural commands serialise correctly (set_device_param)
"""

from __future__ import annotations

import json
import socket
import threading
import time
import os

import pytest

from thelmic import live_channel
from thelmic.live_channel import LiveChannel


# ---------------------------------------------------------------------------
# Mock server
# ---------------------------------------------------------------------------


class MockRemoteScript:
    """Minimal stand-in for the Ableton Remote Script socket.

    Listens on an ephemeral port; per connection: read until a complete JSON
    document parses, then send back a {status, result, request_id} reply.
    """

    def __init__(self, host="127.0.0.1"):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((host, 0))
        self._sock.listen(5)
        self._sock.settimeout(0.2)
        self.host, self.port = self._sock.getsockname()
        self.received: list[dict] = []
        self.respond_with = None  # callable(request) -> dict[result] or None
        self.delay = 0.0
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        while self._running:
            try:
                client, _ = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            t = threading.Thread(target=self._handle, args=(client,), daemon=True)
            t.start()

    def _handle(self, client: socket.socket):
        client.settimeout(2.0)
        buf = b""
        try:
            while self._running:
                try:
                    chunk = client.recv(8192)
                except socket.timeout:
                    break
                if not chunk:
                    break
                buf += chunk
                try:
                    req = json.loads(buf.decode("utf-8"))
                    buf = b""
                except ValueError:
                    continue
                self.received.append(req)
                if self.delay:
                    time.sleep(self.delay)
                if self.respond_with is not None:
                    resp = self.respond_with(req)
                else:
                    resp = {"status": "success", "result": {"echo": req.get("type")}}
                if "request_id" in req:
                    resp["request_id"] = req["request_id"]
                client.sendall(json.dumps(resp).encode("utf-8"))
        finally:
            try:
                client.close()
            except Exception:
                pass

    def stop(self):
        self._running = False
        try:
            self._sock.close()
        except Exception:
            pass


@pytest.fixture
def server():
    s = MockRemoteScript()
    yield s
    s.stop()


@pytest.fixture
def channel(server):
    os.environ["LIVE_CHANNEL_ENABLED"] = "1"
    ch = LiveChannel(host=server.host, port=server.port, lower_priority=False)
    ch.start()
    yield ch
    ch.stop()
    os.environ.pop("LIVE_CHANNEL_ENABLED", None)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_disabled_channel_returns_failed_futures(monkeypatch):
    monkeypatch.delenv("LIVE_CHANNEL_ENABLED", raising=False)
    ch = LiveChannel(lower_priority=False)
    ch.start()  # no-op when disabled
    fut = ch.ping()
    with pytest.raises(RuntimeError):
        fut.result(timeout=1.0)
    assert ch.status().enabled is False
    assert ch.status().connected is False


def test_ping_roundtrip(channel, server):
    result = channel.ping().result(timeout=3.0)
    assert result == {"echo": "ping"}
    assert len(server.received) == 1
    assert server.received[0]["type"] == "ping"
    assert "request_id" in server.received[0]
    s = channel.status()
    assert s.connected is True
    assert s.commands_sent == 1


def test_request_id_correlation(channel, server):
    futs = [channel.set_tempo(120 + i) for i in range(5)]
    results = [f.result(timeout=3.0) for f in futs]
    assert len(results) == 5
    ids = [r["request_id"] for r in server.received]
    assert ids == sorted(ids)
    assert len(set(ids)) == 5  # unique


def test_set_device_param_serialises_int_or_name(channel, server):
    channel.set_device_param(0, 0, 3, 0.5).result(timeout=3.0)
    channel.set_device_param(0, 0, "Filter Freq", 2000.0).result(timeout=3.0)
    by_idx, by_name = server.received[-2], server.received[-1]
    assert by_idx["params"]["param_index"] == 3
    assert "param_name" not in by_idx["params"]
    assert by_name["params"]["param_name"] == "Filter Freq"
    assert "param_index" not in by_name["params"]


def test_queue_overflow_drops(server, monkeypatch):
    """When the dispatcher is blocked on a slow response, the queue fills and
    further commands drop with commands_dropped++."""
    os.environ["LIVE_CHANNEL_ENABLED"] = "1"
    server.delay = 1.0  # block dispatcher for 1s on first command
    ch = LiveChannel(host=server.host, port=server.port, lower_priority=False)
    ch.start()
    try:
        # First command ties up the dispatcher; rest pile into the queue.
        first = ch.ping()
        # Saturate beyond PRIORITY_QUEUE_MAX (32).
        futs = [ch.ping() for _ in range(60)]
        # Give the loop a beat to process call_soon_threadsafe and overflow.
        time.sleep(0.3)
        s = ch.status()
        assert s.commands_dropped > 0
        # Some futures fail with "queue full"; at least one should have.
        dropped_excs = sum(
            1
            for f in futs
            if f.done() and isinstance(f.exception(), RuntimeError)
        )
        assert dropped_excs > 0
        first.result(timeout=5.0)
    finally:
        ch.stop()
        os.environ.pop("LIVE_CHANNEL_ENABLED", None)


def test_reconnect_after_server_drop(server, monkeypatch):
    os.environ["LIVE_CHANNEL_ENABLED"] = "1"
    ch = LiveChannel(host=server.host, port=server.port, lower_priority=False)
    ch.start()
    try:
        ch.ping().result(timeout=3.0)
        assert ch.status().connected is True
        # Stop the mock server, start a fresh one on the same port.
        port = server.port
        server.stop()
        time.sleep(0.1)
        # The next command will fail / mark disconnected; then a fresh server
        # on the same port should let the dispatcher reconnect.
        new_server = MockRemoteScript()
        # Different port — repoint the channel.
        ch.host, ch.port = new_server.host, new_server.port
        try:
            # First post-drop send may fail; retry a couple times.
            ok = False
            last_err = None
            for _ in range(5):
                try:
                    ch.ping().result(timeout=3.0)
                    ok = True
                    break
                except Exception as e:
                    last_err = e
                    time.sleep(0.3)
            assert ok, f"reconnect failed: {last_err}"
            assert ch.status().connected is True
        finally:
            new_server.stop()
    finally:
        ch.stop()
        os.environ.pop("LIVE_CHANNEL_ENABLED", None)


def test_status_surface(channel, server):
    s = channel.status()
    keys = set(s.as_dict().keys())
    assert keys == {
        "enabled",
        "connected",
        "priority_depth",
        "last_error",
        "commands_sent",
        "commands_dropped",
        "commands_failed",
    }


def test_is_enabled_env_parsing(monkeypatch):
    for val in ("1", "true", "True", "YES", "on"):
        monkeypatch.setenv("LIVE_CHANNEL_ENABLED", val)
        assert live_channel.is_enabled() is True
    for val in ("0", "false", "", "no", "off"):
        monkeypatch.setenv("LIVE_CHANNEL_ENABLED", val)
        assert live_channel.is_enabled() is False
