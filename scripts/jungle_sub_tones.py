"""JUNGLE SUB TONES - each section row's bassline clip sets its own sub tone.

A canonical rule (tracks/2026-09-16_reaper/bass.md section 10): the sub's tone and harmonics change per section
and hold inside it. F-HOLE is one Operator, so each row's clip carries a clip envelope, constant for the whole
clip, on the three things the MIDImix sub knobs turn:
  drop   Pe Amount     how far each note's pitch falls in (100% = from +30 st)
  bell   Osc-B Level   FM from oscillator B, whose own envelope decays: a bell at the front of each note
  grit   Shaper Mix    Operator's soft shaper (drive +6 dB) mixed in

  row  scene                drop    bell      grit
  1    TRAPDOOR             100%    off       0%     clean
  2    ARRIVALS             100%    -20 dB    0%     a little bell
  3    SUB-POENA SERVED     100%    off       60%    driven
  4    DEPARTURES           50%     -26 dB    20%    short drop, faint colour
  5    SUBLIMINAL MESSAGE   0%      -14 dB    0%     no drop, round and bright
  6    COMING DOWN          75%     -18 dB    35%    bell and grit

Launching a row sets its tone; a knob moved by hand overrides it until automation is re-enabled.
Writes envelopes only, so it is safe to run while the grid is playing.

    python scripts/jungle_sub_tones.py
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(SCRIPTS_DIR))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from jungle_reset import index_of  # noqa: E402
from jungle_sections import ROWS  # noqa: E402

OFF = None
AMP_ENVELOPE = [("Ae Attack", 3.0), ("Ae Release", 80.0)]      # ms
TONES = [  # (drop: Pe Amount raw, bell: Osc-B Level dB or OFF, grit: Shaper Mix %)
    (1.0, OFF, 0.0),
    (1.0, -20.0, 0.0),
    (1.0, OFF, 60.0),
    (0.5, -26.0, 20.0),
    (0.0, -14.0, 0.0),
    (0.75, -18.0, 35.0),
]


def bell_raw(db):
    """Operator's level scale: 0 dB at raw 1.0, 40 dB per unit (Be Sustain reads -24 dB at 0.4; Osc-B Level
    read -20 dB at 0.4875, inside its display rounding), -inf at 0."""
    return 0.0 if db is None else max(0.0, 1.0 + db / 40.0)


def main():
    """Writes the envelopes only: no launching, no stopping, safe while the user plays. The device's own
    values are set back to the clean tone first, since a parameter touched after its envelopes exist would
    override them."""
    from thelmic.live_channel import LiveChannel
    from jungle_space import _param
    ch = LiveChannel(lower_priority=False)
    ch.start()
    try:
        t = index_of(ch, "F-HOLE")
        # a 1 ms attack and 40 ms release clicked at note ends (under two cycles of F#0): soften both a little
        from jungle_space import set_number
        for pname, ms in AMP_ENVELOPE:
            set_number(ch, t, 0, pname, ms)
        for pname, v in (("Osc-B Level", 0.0), ("Pe Amount", 1.0), ("Shaper Mix", 0.0)):
            if abs(float(_param(ch, t, 0, pname)["value"]) - v) > 1e-4:
                ch.set_device_param(t, 0, _param(ch, t, 0, pname)["index"], v).result(timeout=5)
        for row, ((scene, _, _), (drop, bell, grit)) in enumerate(zip(ROWS, TONES)):
            length = float(ch.get_clip_props(t, row).result(timeout=5)["length"])
            values = {"Pe Amount": drop, "Osc-B Level": bell_raw(bell), "Shaper Mix": grit}
            for pname, v in values.items():
                ch.set_clip_envelope(t, row, t, 0, pname, [[0.0, v], [length - 1.0, v]]).result(timeout=10)
            env = ch.inspect_clip_envelopes(t, row).result(timeout=10)
            print(f"  row {row + 1} {scene:<19} drop {drop:.0%}  bell {'off' if bell is None else f'{bell:g} dB':<7} "
                  f"grit {grit:.0f}%  | envelopes on the clip: {env.get('automation_envelopes_count')}")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
