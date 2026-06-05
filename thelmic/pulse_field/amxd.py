"""Read/write Max for Live .amxd device files (the supported template path).

Per the Cycling '74 docs, a Max for Live device "always begins from a basic
template". Those templates (Live's "Max Instrument/Audio Effect/MIDI Effect"
starter devices) are UNENCRYPTED: a trivial 3-chunk wrapper around a plaintext
.maxpat JSON patcher (a public, documented format):

    'ampf' <int32 len=4> <4-byte kind: b'iiii'|b'aaaa'|b'mmmm'>   instrument/audio/midi
    'meta' <int32 len=4> <0x00000000>
    'ptch' <int32 len=N> <utf-8 .maxpat JSON + trailing NUL>

This module reads a template, lets us inject objects into the patcher dict, and
re-wraps it. We are NOT cracking the encrypted ('ciph') factory devices — we
build on Live's own editable starter template, only manipulating the documented
maxpat JSON. (Frozen/encrypted devices are out of scope and unsupported.)

Pulse Field branch — M4L device authoring (read the guide, build on the template).
"""

from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Tuple

# Live's default instrument/audio/midi starter templates on this machine.
TEMPLATE_DIR = Path(
    r"C:/ProgramData/Ableton/Live 12 Suite/Resources/Misc/Max Devices"
)
TEMPLATES = {
    "instrument": TEMPLATE_DIR / "Max Instrument.amxd",
    "audio": TEMPLATE_DIR / "Max Audio Effect.amxd",
    "midi": TEMPLATE_DIR / "Max MIDI Effect.amxd",
}
KIND_BYTES = {"instrument": b"iiii", "audio": b"aaaa", "midi": b"mmmm"}


def _chunks(data: bytes):
    """Yield (tag, payload) for each top-level chunk."""
    i = 0
    while i + 8 <= len(data):
        tag = data[i:i + 4].decode("latin1")
        (ln,) = struct.unpack_from("<i", data, i + 4)
        if ln < 0 or i + 8 + ln > len(data):
            break
        yield tag, data[i + 8:i + 8 + ln]
        i += 8 + ln


def read_amxd(path) -> Tuple[bytes, dict]:
    """Return (kind_bytes, patcher_dict). Raises if the device is encrypted."""
    data = Path(path).read_bytes()
    if data[:4] != b"ampf":
        raise ValueError(f"not an .amxd (no 'ampf' magic): {path}")
    kind = b"iiii"
    patcher = None
    for tag, payload in _chunks(data):
        if tag == "ampf":
            kind = payload
        elif tag == "ciph":
            raise ValueError(
                f"{path} is encrypted (frozen) — cannot read patcher. "
                "Use an unencrypted template."
            )
        elif tag == "ptch":
            js = payload.rstrip(b"\x00").decode("utf-8")
            patcher = json.loads(js)
    if patcher is None:
        raise ValueError(f"no 'ptch' chunk in {path}")
    return kind, patcher


def write_amxd(path, patcher: dict, kind: bytes = b"iiii") -> None:
    """Wrap a patcher dict back into an .amxd with the template's chunk layout."""
    js = json.dumps(patcher, indent=1)
    ptch = js.encode("utf-8") + b"\x00"

    out = bytearray()

    def chunk(tag: bytes, payload: bytes):
        out.extend(tag)
        out.extend(struct.pack("<i", len(payload)))
        out.extend(payload)

    chunk(b"ampf", kind)
    chunk(b"meta", b"\x00\x00\x00\x00")
    chunk(b"ptch", ptch)
    Path(path).write_bytes(bytes(out))


def load_template(kind: str = "instrument") -> Tuple[bytes, dict]:
    """Load one of Live's starter templates -> (kind_bytes, patcher_dict)."""
    return read_amxd(TEMPLATES[kind])
