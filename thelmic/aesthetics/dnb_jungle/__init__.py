"""dnb_jungle aesthetic pack — ragga jungle / dnb / breakcore / gabber arc.

The pack that the Live session is set up around. Encodes:
  - 165 bpm, 4/4, C natural minor
  - Track-role mapping: drums, sub, mid_bass, stab, pad, organ, vox
  - BuildDropRelease grammar (intro/build/riser/drop/breakdown/outro)
  - Anticipation: tightening hats → silence → sacred impact
  - Mix: heavy sidechain, master glue compression, saturator drive ramps
  - Vocabulary: "drop", "rotterdam", "ragga", "breakcore"
"""
from .constants    import (
    KICK, SNARE, HAT_C, HAT_O, RIDE, CRASH,
    SIDESTICK, HAND_CLAP, LOW_TOM, HI_TOM,
    DEFAULT_ARRANGEMENT, TRACK_LEVELS, FREQ_SEPARATION,
)
from .patterns     import (
    amen_4bar, gabber_4bar, breakcore_4bar,
    anticipation_fill, hat_acceleration,
)
from .transforms   import (
    breathe_velocity, pull_back_before_drop,
    crash_decay_tail, low_kick_decay_tail,
    smooth_clip_entry, gain_stage_track, apply_freq_separation,
    midbass_thump_recipe, sub_track_recipe, drop_anticipation_recipe,
    configure_master_glue, soft_outro_offsets, take_start_bar,
    thin_build_for_massive_drop,
)
from thelmic.bridge.grammars import BuildDropRelease

PACK_NAME = "dnb_jungle"
PACK_GRAMMAR = BuildDropRelease()
PACK_BPM = 165.0
PACK_KEY_ROOT = 36                # C2 MIDI

from .arrangement import build_timeline


def prepare_clips(ch):
    """Pack-specific clip prep called before the print starts.
    For dnb_jungle: writes anticipation fills into HARDKIT slots 3, 6, 13."""
    from thelmic.bridge.helpers import find_track, to_clip_notes
    from .patterns import amen_4bar
    from .transforms import (
        breathe_velocity, pull_back_before_drop,
    )
    hk = find_track(ch, "HARDKIT")
    if hk is None:
        print("    [pack-prep] HARDKIT not found; skipping anticipation fills")
        return
    for slot in (3, 6, 13):
        notes = []
        for rep in range(3):
            notes.extend(amen_4bar(rep * 16.0))
        for n in amen_4bar(48.0):
            p, t, _, _ = n
            if t < 62.0 or (p == HAT_C and t < 63.875):
                notes.append(n)
        notes.append((KICK,  60 + 3.875, 0.20, 127))
        notes.append((SNARE, 60 + 3.875, 0.20, 127))
        notes.append((CRASH, 60 + 3.875, 4.00, 127))
        notes = breathe_velocity(notes, amplitude=8, period_beats=8.0)
        notes = pull_back_before_drop(notes, drop_at_beat=63.875,
                                        pull_window_beats=4.0, min_factor=0.6)
        notes_dicts = to_clip_notes([(p, t, dur, vel)
                                      for (p, t, dur, vel) in notes
                                      if 0.0 <= t < 64.0])
        try: ch.clear_clip(hk, slot).result(timeout=3)
        except Exception: pass
        ch.create_clip(hk, slot, 64.0).result(timeout=10)
        ch.set_clip_name(hk, slot, f"anticipation_S{slot}").result(timeout=3)
        ch.add_notes_to_clip(hk, slot, notes_dicts).result(timeout=10)
        print(f"    [pack-prep] HARDKIT S{slot}: anticipation fill ({len(notes_dicts)} notes)")
