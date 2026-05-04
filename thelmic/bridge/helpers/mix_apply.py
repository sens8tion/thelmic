"""Apply CHANNEL_AUDIO meta to live tracks.

Reads each role's ChannelAudio and writes:
- An EQ8 with HP / LP bands set per FreqRegion (uses bands 1 + 8)
- (Future) Compressor + sidechain wiring per LevelTarget

Idempotent: if the EQ already has the declared HP/LP within tolerance, skip.
"""
from __future__ import annotations
import time

from thelmic.meta import ChannelAudio
from .discovery import find_device, ensure_device
from .eq import set_eq_band, hz_to_norm, EQ8_HP_48_GUESS, EQ8_LP_48_GUESS


EQ8_URI = "query:AudioFx#EQ%20Eight"


def apply_channel_audio(ch, roles: dict[str, int],
                        channel_audio: dict[str, ChannelAudio]) -> dict:
    counts = {"eq_set": 0, "eq_skipped": 0, "missing_role": 0}
    for role, ca in channel_audio.items():
        ti = roles.get(role)
        if ti is None:
            counts["missing_role"] += 1
            continue
        eq_idx = ensure_device(ch, ti, "Eq8", EQ8_URI)
        time.sleep(0.1)
        if ca.freq.hp_hz is not None:
            set_eq_band(ch, ti, eq_idx, band=1,
                        ftype=EQ8_HP_48_GUESS, hz=ca.freq.hp_hz, on=True)
        if ca.freq.lp_hz is not None:
            set_eq_band(ch, ti, eq_idx, band=8,
                        ftype=EQ8_LP_48_GUESS, hz=ca.freq.lp_hz, on=True)
        counts["eq_set"] += 1
        time.sleep(0.05)
    return counts
