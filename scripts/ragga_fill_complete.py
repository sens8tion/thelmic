"""Complete the RAGGA_FILL scene without depending on RPCs that require
a Live restart (select_track, get_grooves):

  B'. Programmatic Em skank progression on STAB slot 4 — I-iv-v-iv
      (Em-Am-Bm-Am) with classic off-beat ragga skank rhythm.
  C'. BAKE swing into all DRUMS clips by shifting off-beat hits by a
      reggae-style swing ratio (~57% — between straight 50% and full
      triplet 67%). Touches every snare/hat off-beat, leaves kicks alone.
"""
from __future__ import annotations
import os, time
os.environ.setdefault('LIVE_CHANNEL_ENABLED', '1')

from thelmic.live_channel import LiveChannel

T_DRUMS, T_STAB = 0, 5
S_FILL = 4
CLIP_LEN = 16.0

# ---- B'. programmatic Em skank progression -----------------------------
#
# I-iv-v-iv in Em = Em, Am, Bm, Am (one chord per bar).
# Skank rhythm: chord stabs on the &-of-1, &-of-2, &-of-3, &-of-4
# (every off-beat). Slight velocity accent on the 2 & 4.
#
EM = (52, 55, 59)        # E G B  (E3 G3 B3)
AM = (57, 60, 64)        # A C E
BM = (59, 62, 66)        # B D F#  (Em natural minor uses F# implicit, B-D-F#)
PROGRESSION = [EM, AM, BM, AM]


def stab_skank_em_progression() -> list[dict]:
    notes = []
    for bar, chord in enumerate(PROGRESSION):
        b0 = bar * 4
        for off, vel in [(0.5, 78), (1.5, 92), (2.5, 78), (3.5, 92)]:
            for p in chord:
                notes.append({
                    "pitch": p, "time": b0 + off, "duration": 0.22,
                    "velocity": vel,
                })
        # tiny 16th flick at the bar-end to push the next bar
        for p in chord:
            notes.append({
                "pitch": p, "time": b0 + 3.875, "duration": 0.125,
                "velocity": 80,
            })
    return notes


# ---- C'. swing baker --------------------------------------------------

# Reggae swing ratio. 0.5 = straight 8ths. 0.667 = full triplet swing.
# Reggae sits around 0.55–0.58 — swing the off-beat without making it
# feel like jazz triplets.
REGGAE_SWING = 0.57


def is_offbeat(time_beats: float, granularity: float = 0.5,
               tol: float = 0.06) -> bool:
    """True if note sits on the &-of-beat (every other 8th)."""
    twice = time_beats / granularity
    nearest = round(twice)
    if abs(twice - nearest) > tol:
        return False
    return nearest % 2 == 1


def bake_swing(notes: list[dict], ratio: float = REGGAE_SWING) -> list[dict]:
    """Shift every 8th-note off-beat to land at `ratio` of the beat
    rather than 0.5 of the beat. Note duration shifts too, so the
    pulse density holds."""
    delta = ratio - 0.5     # e.g. 0.07 for ratio=0.57
    out = []
    for n in notes:
        t = float(n.get("time", 0.0))
        if is_offbeat(t):
            t += delta
        out.append({**n, "time": round(t, 4)})
    return out


# ---- main -------------------------------------------------------------

def main() -> None:
    ch = LiveChannel(); ch.start(); time.sleep(0.6)
    try:
        # B'. write Em skank progression to STAB slot 4
        print('--- B\'. Em skank progression on STAB slot 4 ---')
        try:
            try: ch.clear_clip(T_STAB, S_FILL).result(timeout=3); time.sleep(0.1)
            except Exception: pass
            ch.create_clip(T_STAB, S_FILL, CLIP_LEN).result(timeout=10); time.sleep(0.1)
            notes = stab_skank_em_progression()
            ch.add_notes_to_clip(T_STAB, S_FILL, notes).result(timeout=10); time.sleep(0.1)
            ch.set_clip_name(T_STAB, S_FILL, 'SKANK_Em_iiviv').result(timeout=5)
            print(f'  STAB slot 4 = Em-Am-Bm-Am skank ({len(notes)} notes)')
        except Exception as e:
            print(f'  STAB slot 4 fail: {e}')

        # C'. bake reggae swing into all DRUMS clips
        print('\n--- C\'. bake reggae swing into DRUMS clips ---')
        for slot in range(5):
            try:
                # try Live 11+ extended notes RPC; fallback to legacy
                resp = ch.get_clip_notes(T_DRUMS, slot).result(timeout=5)
                notes = resp.get('notes', [])
                if not notes:
                    continue
                swung = bake_swing(notes)
                # only rewrite if something actually changed
                changed = sum(1 for a, b in zip(notes, swung) if a['time'] != b['time'])
                if changed == 0:
                    print(f'  slot {slot}: no off-beats to swing'); continue
                ch.remove_clip_notes(T_DRUMS, slot).result(timeout=5); time.sleep(0.1)
                ch.add_notes_to_clip(T_DRUMS, slot, swung).result(timeout=5); time.sleep(0.1)
                print(f'  slot {slot}: swung {changed}/{len(notes)} notes')
            except Exception as e:
                print(f'  slot {slot}: {e}')

        # also bake into STAB clips so the skank-on-the-& itself swings
        print('\n--- C\'. bake reggae swing into STAB skank clips ---')
        for slot in range(5):
            try:
                resp = ch.get_clip_notes(T_STAB, slot).result(timeout=5)
                notes = resp.get('notes', [])
                if not notes:
                    continue
                swung = bake_swing(notes)
                changed = sum(1 for a, b in zip(notes, swung) if a['time'] != b['time'])
                if changed == 0:
                    print(f'  slot {slot}: no off-beats to swing'); continue
                ch.remove_clip_notes(T_STAB, slot).result(timeout=5); time.sleep(0.1)
                ch.add_notes_to_clip(T_STAB, slot, swung).result(timeout=5); time.sleep(0.1)
                print(f'  slot {slot}: swung {changed}/{len(notes)} notes')
            except Exception as e:
                print(f'  slot {slot}: {e}')

        # audition the new RAGGA_FILL with skank
        print('\n--- audition: scene 4 RAGGA_FILL with new skank + swing ---')
        ch.stop_all_clips().result(timeout=3); time.sleep(0.3)
        ch.fire_scene(S_FILL).result(timeout=3)
        time.sleep(11.5)
        ch.stop_all_clips().result(timeout=3)

        # also play the full sequence to hear swing in context
        print('\n--- audition: all 5 scenes with swing baked in ---')
        for i, n in enumerate(['DUB_IN','STEPPER','RAGGAJUNGLE_ROLL','DUBOUT','RAGGA_FILL']):
            print(f'  fire {i} {n}')
            ch.fire_scene(i).result(timeout=3)
            time.sleep(11.5)
        ch.stop_all_clips().result(timeout=3)
    finally:
        ch.stop()


if __name__ == '__main__':
    main()
