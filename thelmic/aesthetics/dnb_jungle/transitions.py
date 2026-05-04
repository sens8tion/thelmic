"""Transition / anticipation techniques for the dnb_jungle pack.

These are pattern generators that go BETWEEN scenes (or in the last bar
of a scene) to set up the next move. They're not tonal patterns per se —
they're rhythmic / pitched gestures designed to create anticipation.

Catalogue of moves:

  vox_pitched_riser
    Fire the same vocal one-shot once per bar, each repeat raised by N
    semitones. The accumulating upward motion creates anticipation
    without needing extra production work. Works equally well leading
    into a DROP or into a BREAK — the listener hears "something is
    coming" but the resolution can be either lift-off or fall-away.

  hat_acceleration
    16th hats → 16th triplets → 32nds across the bar. Standard jungle
    riser move; pure tension via subdivision density.

  reverse_crash_pickup
    Reverse cymbal sample under a snare-roll lead-in. Implemented at
    the audio-clip level (set_clip_reverse on the crash slot during
    the bar before).
"""
from __future__ import annotations


def _note(pitch: int, t: float, dur: float, vel: int) -> dict:
    return {
        "pitch": int(pitch),
        "start_time": float(t),
        "duration": float(dur),
        "velocity": float(vel),
    }


def vox_pitched_riser(
    trigger_note: int = 62,         # D3 — native pitch of dv_vocal_rasta
    n_bars: int = 4,
    semitone_step: int = 1,
    velocity_floor: int = 95,
    velocity_step: int = 5,
    duration_beats: float = 4.0,
) -> list[dict]:
    """The 'pitched riser' transition. Trigger the same vox one-shot
    once per bar, each repeat raised by `semitone_step` semitones, with
    a small velocity crescendo. Place 1-4 bars before a DROP or BREAK.

    Returns a list of notes spanning n_bars × 4 beats.

    Use semitone_step=1 for subtle (chromatic walk-up — works in any
    key), 2 for whole-tone (more obvious), 3 for minor-third (very
    triumphant). semitone_step=1 is the safest because it touches every
    pitch and never sounds out-of-key against any harmonic context.
    """
    notes = []
    for bar in range(n_bars):
        notes.append(_note(
            pitch=trigger_note + bar * semitone_step,
            t=bar * 4.0,
            dur=duration_beats,
            vel=min(127, velocity_floor + bar * velocity_step),
        ))
    return notes


def hat_acceleration(hat_pad: int = 42, n_bars: int = 4) -> list[dict]:
    """Hat density crescendo — 8ths → 16ths → 16th-triplets → 32nds.
    Each bar doubles the subdivision rate. Pure tension via density."""
    notes: list[dict] = []
    schedule = [8, 16, 24, 32]   # divisions per bar
    schedule = schedule[:n_bars]
    for bar, divisions in enumerate(schedule):
        b0 = bar * 4.0
        step = 4.0 / divisions
        for i in range(divisions):
            v = 60 + bar * 8 + (10 if i % 2 == 0 else 0)
            notes.append(_note(hat_pad, b0 + i * step,
                               max(0.05, step * 0.6), min(120, v)))
    return notes


# ---- registry ----------------------------------------------------------

TRANSITIONS: dict[str, callable] = {
    "vox_pitched_riser":   vox_pitched_riser,
    "hat_acceleration":    hat_acceleration,
}

TRANSITION_NOTES = {
    "vox_pitched_riser": (
        "VOX one-shot retriggered once per bar, each repeat +N semitones. "
        "Use 1-4 bars before DROP or BREAK. semitone_step=1 is universally safe "
        "(touches every pitch, never out-of-key)."
    ),
    "hat_acceleration": (
        "Subdivision crescendo (8th → 16th → 16th-triplet → 32nd). "
        "Use as the final bar before a drop. Pure density tension."
    ),
    "reverse_crash_pickup": (
        "Sample-level technique (no MIDI generator). Drop a reversed crash "
        "sample on slot N-1 with set_clip_reverse(reverse=True). The build "
        "of the reversed sample lands on the 1 of the next scene."
    ),
}
