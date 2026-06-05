"""Minimal, dependency-free OSC 1.0 encoder + UDP sender for Pulse Field.

The Pulse Field Stage 0 device (field-state.js) listens on a UDP port for OSC
messages of the form::

    /thelmic/field/<dimension> <float>      # one dimension
    /thelmic/field <8 floats>               # whole vector, canonical order

This module hand-rolls just enough OSC to send those — no python-osc dependency
— so the driver is testable in this repo as-is. If python-osc is later added,
nothing here needs to change.

Pulse Field branch — Stage 0 (Python side).
"""

from __future__ import annotations

import socket
import struct
from typing import Sequence


def _pad4(data: bytes) -> bytes:
    """Pad to the next 4-byte boundary (OSC alignment), always adding >=1 nul
    for strings handled by the caller."""
    remainder = len(data) % 4
    if remainder == 0:
        return data
    return data + (b"\x00" * (4 - remainder))


def _osc_string(value: str) -> bytes:
    """OSC-string: nul-terminated, then padded to a 4-byte boundary."""
    raw = value.encode("ascii") + b"\x00"
    return _pad4(raw)


def encode_message(address: str, args: Sequence[float]) -> bytes:
    """Encode one OSC message with an address and zero or more float args.

    Only floats are supported (all Pulse Field values are floats), which keeps
    the type-tag string trivial: "," followed by one 'f' per arg.
    """
    out = bytearray()
    out += _osc_string(address)
    type_tag = "," + ("f" * len(args))
    out += _osc_string(type_tag)
    for a in args:
        out += struct.pack(">f", float(a))
    return bytes(out)


class OSCSender:
    """Fire-and-forget UDP OSC sender.

    Stateless beyond the socket; safe to construct once and reuse. No replies
    are expected (the Stage 0 device is receive-only).
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 7400) -> None:
        self.host = host
        self.port = port
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(self, address: str, *args: float) -> None:
        packet = encode_message(address, args)
        self._sock.sendto(packet, (self.host, self.port))

    def close(self) -> None:
        try:
            self._sock.close()
        except OSError:
            pass

    def __enter__(self) -> "OSCSender":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
