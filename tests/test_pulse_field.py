"""Tests for the Pulse Field Python upstream (field vector + OSC).

These cover the pure mapping and the dependency-free OSC encoder. The Max
devices are tested separately via node (thelmic/devices/test/*.js).
"""

from __future__ import annotations

import socket
import struct

import pytest

from thelmic.landscape_map import ANCHORS
from thelmic.pulse_field import (
    DIMENSION_NAMES,
    FieldDriver,
    FieldVector,
    TERRITORY_PROFILES,
    OSCSender,
    encode_message,
    field_from_sample,
    nearest_territory,
)
from thelmic.pulse_field.field_vector import _clamp01


# --------------------------------------------------------------------------- #
# OSC encoder
# --------------------------------------------------------------------------- #

def _decode(packet: bytes):
    """Minimal OSC decoder for round-trip testing."""
    def read_str(buf, i):
        end = buf.index(b"\x00", i)
        s = buf[i:end].decode("ascii")
        # advance past the nul, then pad to 4-byte boundary
        j = end + 1
        while j % 4 != 0:
            j += 1
        return s, j

    addr, i = read_str(packet, 0)
    tags, i = read_str(packet, i)
    assert tags[0] == ","
    args = []
    for t in tags[1:]:
        assert t == "f"
        (val,) = struct.unpack_from(">f", packet, i)
        args.append(val)
        i += 4
    return addr, args


def test_osc_single_float_roundtrip():
    pkt = encode_message("/thelmic/field/pressure", [0.7])
    addr, args = _decode(pkt)
    assert addr == "/thelmic/field/pressure"
    assert args == pytest.approx([0.7], abs=1e-6)
    assert len(pkt) % 4 == 0


def test_osc_whole_vector_roundtrip():
    vals = [i / 10 for i in range(8)]
    pkt = encode_message("/thelmic/field", vals)
    addr, args = _decode(pkt)
    assert addr == "/thelmic/field"
    assert args == pytest.approx(vals, abs=1e-6)
    assert len(pkt) % 4 == 0


def test_osc_address_alignment_varied_lengths():
    # addresses of different lengths must all stay 4-byte aligned
    for addr in ["/a", "/ab", "/abc", "/abcd", "/thelmic/field/momentum"]:
        pkt = encode_message(addr, [1.0])
        assert len(pkt) % 4 == 0
        got, _ = _decode(pkt)
        assert got == addr


def test_osc_sender_over_real_udp_socket():
    """The sender's bytes must traverse a real loopback UDP socket and decode —
    proves the Python -> Max wire path, not just in-memory encoding."""
    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx.bind(("127.0.0.1", 0))
    rx.settimeout(2.0)
    port = rx.getsockname()[1]
    try:
        with OSCSender("127.0.0.1", port) as tx:
            vals = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
            tx.send("/thelmic/field", *vals)
            data, _ = rx.recvfrom(4096)
        addr, args = _decode(data)
        assert addr == "/thelmic/field"
        assert args == pytest.approx(vals, abs=1e-6)
    finally:
        rx.close()


# --------------------------------------------------------------------------- #
# FieldVector
# --------------------------------------------------------------------------- #

def test_field_vector_canonical_order():
    fv = FieldVector(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8)
    assert fv.as_tuple() == (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8)
    assert tuple(fv.as_dict().keys()) == DIMENSION_NAMES


def test_clamp01():
    assert _clamp01(-1) == 0.0
    assert _clamp01(2) == 1.0
    assert _clamp01(0.5) == 0.5
    assert _clamp01(float("nan")) == 0.0


# --------------------------------------------------------------------------- #
# Territory matching
# --------------------------------------------------------------------------- #

def test_profiles_match_themselves():
    for name, prof in TERRITORY_PROFILES.items():
        matched, conf = nearest_territory(prof)
        assert matched == name
        assert conf > 0.5


def test_all_dimensions_in_unit_range_across_landscape():
    driver = FieldDriver(seed=3)
    # sweep a grid of positions; every dimension must stay in [0, 1]
    for ix in range(-3, 4):
        for iy in range(-3, 4):
            fv = driver.update(ix / 2.0, iy / 2.0)
            for n in DIMENSION_NAMES:
                v = getattr(fv, n)
                assert 0.0 <= v <= 1.0, f"{n}={v} out of range at ({ix},{iy})"


# --------------------------------------------------------------------------- #
# Landscape -> field mapping behaviour
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("anchor", ["oak", "chaos", "nott"])
def test_anchor_positions_land_in_their_territory(anchor):
    """Standing on a territory anchor should classify as that territory."""
    driver = FieldDriver(seed=0)
    x, y = ANCHORS[anchor]
    fv = driver.update(x, y)
    matched, _ = nearest_territory(fv)
    assert matched == anchor


def test_oak_is_stable_nott_is_uncomfortable():
    driver = FieldDriver(seed=0)
    oak = driver.update(*ANCHORS["oak"])
    driver2 = FieldDriver(seed=0)
    nott = driver2.update(*ANCHORS["nott"])
    assert oak.stability > nott.stability
    assert nott.discomfort > oak.discomfort
    assert nott.silence > oak.silence


def test_chaos_is_novel():
    driver = FieldDriver(seed=0)
    chaos = driver.update(*ANCHORS["chaos"])
    driver2 = FieldDriver(seed=0)
    oak = driver2.update(*ANCHORS["oak"])
    assert chaos.novelty > oak.novelty


def test_motion_raises_pressure_and_urgency():
    """Moving fast through the field should read as more pressure/urgency than
    sitting still at the same point."""
    still = FieldDriver(seed=0)
    sx, sy = 0.0, 0.0
    still.update(sx, sy)
    still_fv = still.update(sx, sy)  # zero displacement => speed 0

    moving = FieldDriver(seed=0)
    moving.update(-0.5, -0.5)
    moving_fv = moving.update(0.5, 0.5)  # big jump => high speed

    assert moving_fv.pressure > still_fv.pressure
    assert moving_fv.urgency > still_fv.urgency


def test_momentum_builds_with_sustained_motion():
    driver = FieldDriver(seed=0)
    # sustained steady steps build smoothed speed -> momentum rises then plateaus
    prev = 0.0
    rising = 0
    x = -1.0
    for _ in range(20):
        x += 0.1
        fv = driver.update(x, 0.0)
        if fv.momentum >= prev:
            rising += 1
        prev = fv.momentum
    assert rising >= 15  # mostly monotonic increase toward plateau


def test_field_from_sample_pure_is_deterministic():
    sample = {"oak_influence": 0.2, "chaos_influence": 0.7,
              "nott_influence": 0.1, "volatility": 0.6}
    a = field_from_sample(sample, speed=0.1)
    b = field_from_sample(sample, speed=0.1)
    assert a == b
