"""Rewrite slot 4 (DROP OPENER) with a fake drop at the 8-bar mark.

Structure:
  bars 1-7:  full amen + sub + stabs (energy in)
  bar 8:     snare roll fill -> climax hit on the and-of-4
  bars 9-9.5: SILENCE (the fake — listener thinks track stopped)
  bars 9.5-10: tension rebuild — kick pulse, riser-crash
  bars 10-16: full amen + sub + stabs (real continuation)
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from thelmic.live_channel import LiveChannel

KICK, SNARE, HAT_C, HAT_O, RIDE, CRASH = 36, 38, 42, 46, 51, 49


def amen_4bar(start_offset=0.0):
    notes = []
    base = [
        (KICK, 0.0, 0.4, 110), (SNARE, 1.0, 0.35, 100),
        (KICK, 1.5, 0.4, 95),  (SNARE, 3.0, 0.35, 105),
        (KICK, 4.0, 0.4, 110), (SNARE, 5.0, 0.35, 100),
        (SNARE, 5.5, 0.2, 75), (SNARE, 6.5, 0.3, 95),
        (KICK, 7.5, 0.35, 90),
        (KICK, 8.0, 0.4, 110), (SNARE, 9.0, 0.35, 100),
        (KICK, 10.5, 0.35, 95),(SNARE, 11.0, 0.35, 105),
        (KICK, 12.0, 0.4, 110),(SNARE, 13.0, 0.3, 95),
        (SNARE, 13.5, 0.2, 75),(SNARE, 14.0, 0.35, 100),
        (KICK, 14.5, 0.35, 90),(SNARE, 15.0, 0.3, 95),
        (SNARE, 15.5, 0.25, 80),
    ]
    for p, t, dur, vel in base:
        notes.append((p, t + start_offset, dur, vel))
    for i in range(64):
        t = i * 0.25 + start_offset
        slot = i % 4
        vel = {0: 92, 1: 65, 2: 78, 3: 65}[slot]
        notes.append((HAT_C, t, 0.18, vel))
    for off in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5,
                8.5, 9.5, 10.5, 11.5, 12.5, 13.5, 14.5, 15.5]:
        notes.append((HAT_O, off + start_offset, 0.25, 78))
    return notes


def main():
    ch = LiveChannel(lower_priority=False); ch.start()
    try:
        # ---------------- DRUMS ----------------
        drums = []

        # bars 1-7 (beats 0-27): play first 7 bars of an amen pattern
        # start a fresh 16-bar amen but drop the last bar so we can place the fill
        full_16 = []
        for rep in range(4):
            for p, t, dur, vel in amen_4bar(rep * 16.0):
                full_16.append((p, t, dur, vel))
        # keep notes with start_time < 28 (bars 1-7)
        bars_1_7 = [(p, t, dur, vel) for (p, t, dur, vel) in full_16 if t < 28.0]
        drums.extend(bars_1_7)

        # bar 8 (beats 28-31): snare-roll fill rising, no kick/snare on grid
        # 16th-note snare roll with rising velocity
        for i in range(16):
            t = 28.0 + i * 0.25
            vel = 60 + int(i * 2.5)   # rises 60 -> 97
            drums.append((SNARE, t, 0.18, vel))
        # 16th hats also continue
        for i in range(16):
            t = 28.0 + i * 0.25
            slot = i % 4
            vel = {0: 92, 1: 65, 2: 78, 3: 65}[slot]
            drums.append((HAT_C, t, 0.18, vel))
        # climax hit on the AND of beat 4 of bar 8 (beat 31.75)
        drums.append((CRASH, 31.75, 0.5, 120))
        drums.append((KICK, 31.75, 0.45, 118))
        drums.append((SNARE, 31.75, 0.4, 115))

        # bars 9-9.5 (beats 32-34): SILENCE — the fake
        # (no notes)

        # bars 9.5-10 (beats 34-36): tension rebuild — kick pulse
        drums.append((KICK, 34.0, 0.45, 100))
        drums.append((HAT_C, 34.5, 0.18, 65))
        drums.append((KICK, 35.0, 0.45, 105))
        drums.append((HAT_C, 35.5, 0.18, 70))
        drums.append((CRASH, 35.75, 1.0, 110))   # rising crash into the return

        # bars 10-16 (beats 36-64): full amen returns
        for rep in range(2):
            for p, t, dur, vel in amen_4bar(36.0 + rep * 16.0):
                if t < 64.0:
                    drums.append((p, t, dur, vel))
        # Note: rep=2 would push past 64 — last 4 bars actually beats 36-52 + 52-64
        # We've laid 8 bars (36-52, 52-64). Wait, 36..52 is 4 bars, 52..68 is past — clip is 64 beats.
        # Keep within bounds
        drums = [(p, t, dur, vel) for (p, t, dur, vel) in drums if 0.0 <= t < 64.0]

        # ---------------- SUB ----------------
        # Sub follows G minor chord progression Gm Eb F Gm (4 bars each).
        # Cut sub during beats 32-36 (the fake silence)
        SUB_ROOTS = [43, 39, 41, 43]
        sub = []
        for chord_idx, root in enumerate(SUB_ROOTS):
            chord_start = chord_idx * 16.0
            for bar in range(4):
                bar_start = chord_start + bar * 4.0
                # skip if within the fake-silence window
                if 32.0 <= bar_start < 36.0:
                    continue
                sub.append((root, bar_start, 3.95, 110))
        # Add a giant sub bomb returning at beat 36 (slightly held over to make impact)
        sub.append((SUB_ROOTS[2], 36.0, 4.0, 122))   # F2 hit on the return

        # ---------------- STAB ----------------
        TRIADS = [[55, 58, 62], [51, 55, 58], [53, 57, 60], [55, 58, 62]]
        stab = []
        for chord_idx, triad in enumerate(TRIADS):
            chord_start = chord_idx * 16.0
            for bar in range(4):
                bar_start = chord_start + bar * 4.0
                # skip stabs during the fake silence + part of the rebuild
                if 32.0 <= bar_start < 36.0:
                    continue
                for off in [0.5, 1.5, 2.5, 3.5]:
                    t = bar_start + off
                    if 32.0 <= t < 36.0:
                        continue
                    vel_main = 95 if off == 0.5 else 88
                    for pitch in triad:
                        stab.append((pitch, t, 0.22, vel_main))

        # ---------------- PAD ----------------
        # Keep pad continuous as atmospheric glue
        pad = []
        for chord_idx, triad in enumerate(TRIADS):
            chord_start = chord_idx * 16.0
            for pitch in triad:
                pad.append((pitch, chord_start, 15.5, 75))

        # Add a HUGE crash + kick stab on beat 36 across all melodic for the return impact
        # (already added in drums; sub got the bomb; pad continues)

        # Convert to dict format
        def to_dicts(quads):
            return [{"pitch": p, "start_time": t, "duration": dur, "velocity": vel}
                    for (p, t, dur, vel) in quads]

        # ---------------- write ----------------
        def write(track, slot, name, quads):
            ch.create_clip(track, slot, 64.0).result(timeout=10)
            ch.set_clip_name(track, slot, name).result(timeout=5)
            ch.add_notes_to_clip(track, slot, to_dicts(quads)).result(timeout=10)
            print(f"  T{track} S{slot}: {name} ({len(quads)} notes)")

        print("Rewriting scene 4 with FAKE DROP at bar 9:")
        write(0, 4, "drop_FAKE_at_9", drums)
        write(1, 4, "sub_with_FAKE", sub)
        write(4, 4, "stab_with_FAKE", stab)
        write(5, 4, "pad_through_FAKE", pad)
        print("\nfake drop wired in at beat 32 (bar 9). Real drop returns at beat 36 (bar 10).")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
