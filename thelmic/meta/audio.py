"""Audio meta — what 'level check' and 'frequency region' mean.

Pack-agnostic dataclasses that packs realize per role. The agent reads
these to (a) generate EQ/HP/LP settings, (b) audit current Live state for
drift, and (c) avoid overdriving a stage during composition.

Two layers:
  FreqRegion   — where an instrument's energy is supposed to live
  LevelTarget  — how loud each stage is allowed to be

ChannelAudio bundles them per role.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


# ---- Frequency region --------------------------------------------------

@dataclass
class FreqRegion:
    """Spectral territory for one role.

    hp_hz / lp_hz  — filters declared on the role's EQ8. None = no cut.
    peak_band_hz   — (lo, hi) of the band carrying the instrument's identity
                     (e.g. kick fundamental ~50–80 Hz). Used for sanity
                     checking that other roles aren't masking it.
    exclusive      — if True, other roles must avoid peak_band_hz; the mix
                     pass enforces this by HP/LP-ing competitors out.
    """
    hp_hz: float | None = None
    lp_hz: float | None = None
    peak_band_hz: tuple[float, float] | None = None
    exclusive: bool = False


# ---- Gain staging ------------------------------------------------------

@dataclass
class StageCheckpoint:
    """Input ceiling at one point in a device chain.

    The whole gain-staging rule: every stage's INPUT must stay below clip
    — not just the final sum. A cap applies to whatever feeds the named
    device. Cap an instrument BEFORE the saturator; cap the saturator
    BEFORE the compressor; cap the compressor BEFORE the bus. Stacking
    hot signal through any of those is the failure mode.

    after_device matches the device's name OR class (case-insensitive).
    Special name "input" = the pre-chain track input.
    Special name "output" = the post-chain track output (= LevelTarget.peak_db).
    """
    after_device: str
    peak_db: float


@dataclass
class LevelTarget:
    """Per-stage level discipline for one role.

    peak_db
        Max true-peak at the CHANNEL OUTPUT (post-device-chain).

    rms_db
        Target program loudness (rough, not LUFS).

    headroom_db
        Reserve below peak_db that mix decisions leave for transients.
        peak_db - headroom_db = soft ceiling for sustained content.

    chain_caps
        Per-stage input caps inside the channel's device chain. Each
        StageCheckpoint sets a ceiling at one point in the chain so the
        agent doesn't drive the next device into clip. Empty = no
        intermediate caps declared (channel relies on peak_db alone).

    sidechain_source
        Where this role gets its sidechain key from, BY NAME. The
        canonical jungle case: melodic stack keys from "perc_bus" — NOT
        raw kick (which over-triggers on every hat). None = no sidechain.
    """
    peak_db: float = -6.0
    rms_db: float = -18.0
    headroom_db: float = 6.0
    chain_caps: list[StageCheckpoint] = field(default_factory=list)
    sidechain_source: str | None = None


# ---- Channel audio bundle ---------------------------------------------

@dataclass
class ChannelAudio:
    freq: FreqRegion = field(default_factory=FreqRegion)
    level: LevelTarget = field(default_factory=LevelTarget)
