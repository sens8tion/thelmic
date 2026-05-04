"""Clean up audio frequency space across all 19 tracks via EQ8 HP/LP.

Doesn't reprint anything — just dials the existing tracks so they stop
fighting for the same Hz range. Each track gets an EQ8 (added if
missing) with band 1 = HP and band 8 = LP at role-appropriate cutoffs.

Frequency map:
  KICK / DRUMS / PUNK_KIT / HARDCORE_KIT  HP 30   LP open    own 30-200 Hz
  SUB                                       HP 30   LP 700     own 30-100 Hz (sub-only)
  BASS / BASS_AUDIO                         HP 50   LP 400     don't fight sub
  BREAK / BREAK_RACK / BREAK_SLICES         HP 80   LP 12k     full drum range
  WURLY                                     HP 200  LP 5k      warm but not muddy
  HAMMOND                                   HP 200  LP 6k      mids
  STAB                                      HP 200  LP 6k
  GUITAR                                    HP 200  LP 8k
  HOOVER                                    HP 150  LP 8k
  VOX                                       HP 150  LP 8k
  PAD                                       HP 250  LP 8k
  ATMOS                                     HP 250  LP 12k     texture, no rumble
  FX                                        HP 180  LP open
"""
from __future__ import annotations
import os, time
os.environ.setdefault('LIVE_CHANNEL_ENABLED', '1')

from thelmic.live_channel import LiveChannel
from thelmic.bridge.helpers.eq import (
    set_eq_band, EQ8_HP_48_GUESS, EQ8_LP_48_GUESS,
)
from thelmic.bridge.helpers.discovery import ensure_device


EQ8_URI = "query:AudioFx#EQ%20Eight"

# (track_name, hp_hz, lp_hz_or_None)
EQ_BY_NAME = [
    ('DRUMS',         30,    None),
    ('BREAK',         80,    12000),
    ('SUB',           30,    700),
    ('BASS',          50,    400),
    ('STAB',          200,   6000),
    ('PAD',           250,   8000),
    ('VOX',           150,   8000),
    ('FX',            180,   None),
    ('HAMMOND',       200,   6000),
    ('WURLY_SKANK',   200,   5000),
    ('BREAK_RACK',    80,    12000),
    ('ATMOS',         250,   12000),
    ('GUITAR',        200,   8000),
    ('HARDCORE_KIT',  30,    None),
    ('HOOVER',        150,   8000),
    ('BASS_AUDIO',    50,    400),
    ('PUNK_KIT',      30,    None),
    ('KICK_4OTF',     30,    None),
]
# T2 is the BREAK_SLICES track (named after the sample); special-case
SLICES_NAME_PREFIX = 'TSP_IHD_160_drum_break'


def main():
    ch = LiveChannel(); ch.start(); time.sleep(0.7)
    try:
        info = ch.get_session_info().result(timeout=5)
        tc = info.get('track_count', 0)

        # Build name → index map
        name_to_ti = {}
        for ti in range(tc):
            nm = ch.get_track_info(ti).result(timeout=3).get('name', '')
            name_to_ti[nm] = ti
            if nm.startswith(SLICES_NAME_PREFIX):
                name_to_ti['_BREAK_SLICES'] = ti

        # Add BREAK_SLICES to the eq plan
        plan = list(EQ_BY_NAME)
        if '_BREAK_SLICES' in name_to_ti:
            plan.append(('_BREAK_SLICES', 80, 12000))

        for name, hp_hz, lp_hz in plan:
            ti = name_to_ti.get(name)
            if ti is None:
                print(f'  {name}: not found, skipping')
                continue
            try:
                eq_idx = ensure_device(ch, ti, 'Eq8', EQ8_URI)
                # band 1 = HP
                set_eq_band(ch, ti, eq_idx, 1, ftype=EQ8_HP_48_GUESS,
                            hz=float(hp_hz), gain=0.0, q_norm=0.5, on=True)
                # band 8 = LP (or off if lp_hz is None)
                if lp_hz is not None:
                    set_eq_band(ch, ti, eq_idx, 8, ftype=EQ8_LP_48_GUESS,
                                hz=float(lp_hz), gain=0.0, q_norm=0.5, on=True)
                else:
                    set_eq_band(ch, ti, eq_idx, 8, ftype=EQ8_LP_48_GUESS,
                                hz=20000.0, on=False)
                lp_str = f'LP {lp_hz}' if lp_hz else 'LP off'
                print(f'  T{ti:2d} {name:18s}  HP {hp_hz}  {lp_str}')
            except Exception as e:
                print(f'  T{ti:2d} {name:18s}  fail: {e}')

        print('\n=== eq lanes cleaned — listen for the difference at the bottom + mid ===')
    finally:
        ch.stop()


if __name__ == '__main__':
    main()
