"""Frequency-zone + stereo-placement pass for ROTTERDAM_CHAIN.

Adds EQ Eight to each lane with band 1 = HP and band 8 = LP set to
role-appropriate cutoffs so lanes stop fighting for the same Hz range.
Then pans the lanes across the stereo field — bass and impact mono in
the center, melodic/high content spread left and right so the mix
opens up out of "wall of centre-noise" territory.

The plan (Hz cutoffs + pan -1.0 to +1.0):

  KICK_ROTTERDAM       HP 30   LP open    pan  0.00   center
  KICK_VEIN            HP 30   LP open    pan  0.00   center
  SUB_PUNCH            HP 30   LP 200     pan  0.00   center (sub MUST be mono)
  PERC_INDUSTRIAL      HP 120  LP 14000   pan  0.00   center
  VOX_SHOUT            HP 200  LP 8000    pan  0.00   center

  HOOVER_LEAD          HP 180  LP 7000    pan -0.10   slight left
  STAB_HARDCORE        HP 200  LP 5500    pan +0.10   slight right
  ACID_TONGUE          HP 50   LP 700     pan -0.25   left (low-mid)

  STAB_BWAAH           HP 200  LP 4500    pan +0.40   right wide
  SCREAM_BLEACH        HP 250  LP 9000    pan -0.40   left wide
  CHOIR_NECRO          HP 250  LP 6500    pan +0.30   right of center
  SIREN_FX             HP 300  LP open    pan -0.55   wide left
  REVERSE_VOID         HP 200  LP open    pan +0.55   wide right
  DRONE_CRYPT          HP 60   LP 1500    pan -0.65   wide left (atmospheric)
  NOISE_OSSUARY        HP 500  LP open    pan +0.65   wide right (atmospheric)
"""
from __future__ import annotations
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")

from thelmic.live_channel import LiveChannel
from thelmic.bridge.helpers.eq import (
    set_eq_band, EQ8_HP_48_GUESS, EQ8_LP_48_GUESS,
)
from thelmic.bridge.helpers.discovery import ensure_device


EQ8_URI = "query:AudioFx#EQ%20Eight"

# (name, hp_hz, lp_hz | None for open, pan_value [-1.0 to +1.0])
ZONES = [
    # --- BASS / IMPACT — mono center ---
    ("KICK_ROTTERDAM",  30,   None,  0.00),
    ("KICK_VEIN",       30,   None,  0.00),
    ("SUB_PUNCH",       30,   200,   0.00),
    ("PERC_INDUSTRIAL", 120,  14000, 0.00),
    ("VOX_SHOUT",       200,  8000,  0.00),

    # --- MID-LOW + LEADS — slight off-center ---
    ("ACID_TONGUE",     50,   700,  -0.25),
    ("HOOVER_LEAD",     180,  7000, -0.10),
    ("STAB_HARDCORE",   200,  5500, +0.10),

    # --- MID-HIGH PUNCTUATION — wider stereo ---
    ("CHOIR_NECRO",     250,  6500, +0.30),
    ("SCREAM_BLEACH",   250,  9000, -0.40),
    ("STAB_BWAAH",      200,  4500, +0.40),

    # --- HIGH / FX / ATMOS — widest stereo ---
    ("SIREN_FX",        300,  None, -0.55),
    ("REVERSE_VOID",    200,  None, +0.55),
    ("DRONE_CRYPT",     60,   1500, -0.65),
    ("NOISE_OSSUARY",   500,  None, +0.65),
]


def main():
    ch = LiveChannel(enabled=True); ch.start()
    try:
        info = ch.get_session_info().result(timeout=5)
        tc = info.get("track_count") or 0

        # Single-pass name -> idx scan
        futs = [ch.get_track_info(t) for t in range(tc)]
        name_to_idx: dict[str, int] = {}
        for t, f in enumerate(futs):
            try:
                ti = f.result(timeout=5)
                nm = ti.get("name", "")
                if nm:
                    name_to_idx[nm] = t
            except Exception:
                pass

        print(f"=== ROTTERDAM_CHAIN frequency-zone + stereo-pan pass ===")
        for name, hp_hz, lp_hz, pan in ZONES:
            t = name_to_idx.get(name)
            if t is None:
                print(f"  {name}: NOT FOUND")
                continue
            try:
                eq_idx = ensure_device(ch, t, "Eq8", EQ8_URI)
                # HP (band 1)
                set_eq_band(ch, t, eq_idx, 1, ftype=EQ8_HP_48_GUESS,
                            hz=float(hp_hz), gain=0.0, q_norm=0.5, on=True)
                # LP (band 8) — set open or to lp_hz
                if lp_hz is not None:
                    set_eq_band(ch, t, eq_idx, 8, ftype=EQ8_LP_48_GUESS,
                                hz=float(lp_hz), gain=0.0, q_norm=0.5, on=True)
                else:
                    set_eq_band(ch, t, eq_idx, 8, ftype=EQ8_LP_48_GUESS,
                                hz=20000.0, on=False)
                # Stereo pan
                ch.set_track_pan(t, pan).result(timeout=5)
                lp_str = f"LP {lp_hz}" if lp_hz is not None else "LP open"
                print(f"  T{t:2d} {name:17s}  HP {hp_hz:>4d}  {lp_str:<10s}  pan {pan:+.2f}")
            except Exception as e:
                print(f"  T{t:2d} {name:17s}  FAILED: {e}")

        print()
        print("Done. The wall-of-centre-noise should now have shape:")
        print("  - Bass + impact at center (mono summing for translation)")
        print("  - Leads slightly off-center for definition")
        print("  - High punctuation wider for stereo theatre")
        print("  - Atmos/FX wide-spread for spatial frame")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
