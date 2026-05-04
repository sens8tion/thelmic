"""dnb_jungle pack lifecycle — separable phases for the agent loop.

Each phase is independently runnable so the agent can:
  * Build a track from scratch (all phases)
  * Re-compose without changing setup (compose / mix / prepare / preview / print)
  * Just preview existing content (preview)
  * Just commit to print without recompiling (print)

Phase ordering when running everything:
  setup → pull → compose → mix → prepare → preview → print

Each function takes (ch) — the LiveChannel — and is idempotent where
possible.
"""
from __future__ import annotations
import time
from thelmic.bridge.helpers import (
    find_track, find_device, ensure_device, hard_reset, ms_to_beats,
)
from .constants  import (
    KICK, SNARE, HAT_C, CRASH, FREQ_SEPARATION, TRACK_LEVELS,
    OUTRO_LET_REVERB_RING_MS,
)
from .patterns   import (
    amen_4bar, gabber_4bar, breakcore_4bar,
    anticipation_fill, hat_acceleration,
)
from .transforms import (
    breathe_velocity, pull_back_before_drop,
    apply_freq_separation, gain_stage_track,
)


SAT_URI = "query:AudioFx#Saturator"


# ----------------------------------------------------------------------
# Phase: setup_session
# ----------------------------------------------------------------------

def setup_session(ch) -> dict:
    """Phase: setup. Ensure devices required by the pack are present.
    Idempotent — adds Saturator to HARDKIT if missing, etc.

    Returns a dict of {role: track_index} for the lifecycle's downstream use.
    """
    print("\n[setup] ensuring required devices on each role-track...")
    roles = {}
    for role_name, hints in [
        ("drums",        ["HARDKIT"]),
        ("amen",         ["AMEN"]),
        ("break",        ["BREAKBEAST"]),
        ("sub",          ["SUBBONK"]),
        ("mid_bass",     ["TECTONIC"]),
        ("stab",         ["STAB"]),
        ("organ",        ["ORGAN"]),
        ("pad",          ["COLD MIST"]),
        ("vox_call",     ["VOX YO", "VOX"]),
        ("vox_response", ["VOX BIG"]),
        ("vox_chorus",   ["VOX SEL"]),
    ]:
        for h in hints:
            ti = find_track(ch, h)
            if ti is not None:
                roles[role_name] = ti
                break
        else:
            print(f"  - {role_name}: MISSING (hints {hints})")

    # Ensure HARDKIT has a Saturator (drive ramps target it)
    if "drums" in roles:
        sat = find_device(ch, roles["drums"], "Saturator")
        if sat is None:
            sat = ensure_device(ch, roles["drums"], "Saturator", SAT_URI)
            di = ch.get_device_info(roles["drums"], sat).result(timeout=3)
            drive = next((p for p in di["parameters"] if p["name"] == "Drive"), None)
            if drive:
                ch.set_device_param(roles["drums"], sat,
                                      drive["index"], 0.20).result(timeout=2)
            print(f"  + drums Saturator added at device {sat}, drive=0.20")
        else:
            print(f"  - drums Saturator already present at device {sat}")

    print(f"  resolved {len(roles)} role-tracks: {list(roles.keys())}")
    return roles


# ----------------------------------------------------------------------
# Phase: pull_samples (Splice integration)
# ----------------------------------------------------------------------

def pull_samples(ch, splice_mcp=None) -> list:
    """Phase: pull. Optional — pull Splice content via MCP.
    Returns list of pulled asset filenames. Skipped if no MCP supplied."""
    if splice_mcp is None:
        print("\n[pull] skipped — no Splice MCP provided")
        return []
    print("\n[pull] (Splice integration not yet wired into lifecycle hook)")
    return []


# ----------------------------------------------------------------------
# Phase: compose_clips
# ----------------------------------------------------------------------

def _ragga_jungle_4bar(offset=0.0, hat_density="16th"):
    """Local copy of ragga jungle break — kept inline for self-containment."""
    notes = []
    RIDE = 51
    for bar in range(4):
        bs = bar * 4 + offset
        notes.append((KICK,  bs + 0.0, 0.40, 118))
        notes.append((KICK,  bs + 2.5, 0.40, 105))
        notes.append((SNARE, bs + 1.0, 0.30, 110))
        notes.append((SNARE, bs + 3.0, 0.30, 115))
        notes.append((SNARE, bs + 3.75, 0.18, 72))
        if bar % 2 == 1:
            notes.append((RIDE, bs + 0.0, 0.60, 95))
            notes.append((RIDE, bs + 2.0, 0.50, 88))
        if hat_density == "16th":
            for i in range(16):
                t = bs + i * 0.25
                vel = 92 if i % 4 == 0 else 65 if i % 2 == 0 else 72
                notes.append((HAT_C, t, 0.16, vel))
        else:
            for i in range(32):
                t = bs + i * 0.125
                vel = 88 - (i % 8) * 3
                notes.append((HAT_C, t, 0.08, vel))
    return notes


def _rotterdam_gabber_4bar(offset=0.0, double_time=False, hat_density="16th"):
    notes = []
    for bar in range(4):
        bs = bar * 4 + offset
        n_kicks = 8 if double_time else 4
        rate = 0.5 if double_time else 1.0
        for k in range(n_kicks):
            t = bs + k * rate
            vel = 127 if (k * rate) % 1 == 0 else 122
            notes.append((KICK, t, 0.20 if double_time else 0.30, vel))
        notes.append((SNARE, bs + 1.0, 0.25, 122))
        notes.append((SNARE, bs + 3.0, 0.25, 122))
        if hat_density == "16th":
            for i in range(16):
                notes.append((HAT_C, bs + i * 0.25, 0.10, 90 if i%4==0 else 68))
        elif hat_density == "32nd":
            for i in range(32):
                notes.append((HAT_C, bs + i * 0.125, 0.07, 85 if i%8==0 else 62))
        elif hat_density == "64th":
            for i in range(64):
                notes.append((HAT_C, bs + i * 0.0625, 0.04, 80 if i%16==0 else 55))
        if bar == 0:
            notes.append((CRASH, bs, 2.0, 115))
    return notes


def _is_midi(ch, t):
    info = ch.get_track_info(t).result(timeout=3)
    return bool(info.get("is_midi_track"))


def _write_clip(ch, track, slot, length_beats, name, notes, breathe=False, pull_back=True):
    if not _is_midi(ch, track):
        return -1
    if breathe:
        notes = breathe_velocity(notes, amplitude=8, period_beats=8.0)
    if pull_back:
        notes = pull_back_before_drop(notes, drop_at_beat=length_beats - 0.125,
                                       pull_window_beats=4.0, min_factor=0.65)
    notes_dicts = [{"pitch": p, "start_time": float(t), "duration": float(dur), "velocity": int(vel)}
                   for (p, t, dur, vel) in notes if 0.0 <= t < length_beats]
    try: ch.clear_clip(track, slot).result(timeout=3)
    except Exception: pass
    ch.create_clip(track, slot, float(length_beats)).result(timeout=10)
    ch.set_clip_name(track, slot, name).result(timeout=3)
    ch.add_notes_to_clip(track, slot, notes_dicts).result(timeout=10)
    return len(notes_dicts)


def compose_clips(ch, roles: dict | None = None) -> dict:
    """Phase: compose. Write the pack's MIDI patterns into session-view clips.
    Returns count summary."""
    print("\n[compose] writing dnb_jungle MIDI patterns into session view...")
    if roles is None:
        roles = setup_session(ch)

    counts = {}

    # HARDKIT slot 4 — ragga jungle drop
    if "drums" in roles:
        notes = []
        for r in range(6):
            notes.extend(_ragga_jungle_4bar(r * 4, hat_density="16th"))
        notes.extend(_ragga_jungle_4bar(24, hat_density="32nd"))
        impact_t = 32 - 0.125
        notes.append((KICK,  impact_t, 0.20, 127))
        notes.append((SNARE, impact_t, 0.20, 127))
        notes.append((CRASH, impact_t, 4.00, 127))
        n = _write_clip(ch, roles["drums"], 4, 32.0, "drop_ragga", notes, breathe=True)
        counts["drums S4 (ragga drop)"] = n
        print(f"  drums S4: {n} notes (ragga jungle drop)")

    # HARDKIT slot 7 — Rotterdam gabber
    if "drums" in roles:
        notes = []
        notes.extend(_rotterdam_gabber_4bar(0,  hat_density="16th"))
        notes.extend(_rotterdam_gabber_4bar(16, hat_density="32nd"))
        notes.extend(_rotterdam_gabber_4bar(28, double_time=True, hat_density="64th"))
        impact_t = 32 - 0.125
        notes.append((KICK,  impact_t, 0.20, 127))
        notes.append((CRASH, impact_t, 4.00, 127))
        n = _write_clip(ch, roles["drums"], 7, 32.0, "drop_rotterdam", notes)
        counts["drums S7 (Rotterdam)"] = n
        print(f"  drums S7: {n} notes (Rotterdam gabber)")

    # HARDKIT slot 9 — breakcore peak
    if "drums" in roles:
        notes = []
        for r in range(8):
            notes.extend(breakcore_4bar(r * 4))
        n = _write_clip(ch, roles["drums"], 9, 32.0, "breakcore_peak", notes,
                          pull_back=False)
        counts["drums S9 (breakcore)"] = n
        print(f"  drums S9: {n} notes (breakcore peak)")

    # HARDKIT slot 11 — quiet outro
    if "drums" in roles:
        notes = []
        RIDE = 51
        for bar in range(16):
            bs = bar * 4
            kvel = max(35, 95 - bar)
            notes.append((KICK, bs, 0.40, kvel))
            notes.append((RIDE, bs, 4.0,  max(40, 70 - bar)))
            if bar % 4 in (1, 3):
                notes.append((SNARE, bs + 2.5, 0.20, max(30, 50 - bar)))
        n = _write_clip(ch, roles["drums"], 11, 64.0, "outro_quiet", notes,
                          pull_back=False)
        counts["drums S11 (outro)"] = n
        print(f"  drums S11: {n} notes (quiet outro)")

    # AMEN — parallel breakcore
    if "amen" in roles:
        notes = []
        for r in range(8):
            notes.extend(breakcore_4bar(r * 4))
        n = _write_clip(ch, roles["amen"], 9, 32.0, "amen_breakcore", notes,
                          pull_back=False)
        counts["amen S9 (breakcore)"] = n
        print(f"  amen S9: {n} notes (parallel breakcore)")

    # TECTONIC — multi-octave arps
    if "mid_bass" in roles:
        SCALE_ROOT = 36
        ARP = [0, 7, 12, 15]
        for slot, length, oct_shift, density in [
            (1, 16.0, -12, "8th"),
            (2, 16.0,   0, "8th"),
            (3, 16.0,   0, "16th"),
            (4, 32.0,  12, "16th"),
            (6, 16.0,  12, "16th"),
            (7, 32.0,  12, "16th"),
            (9, 32.0,   0, "16th"),
        ]:
            step = 0.5 if density == "8th" else 0.25
            n_per_bar = int(4 / step)
            n_reps = int(length / 4)
            notes = []
            for bar in range(n_reps):
                bs = bar * 4
                for i in range(n_per_bar):
                    t = bs + i * step
                    pitch = SCALE_ROOT + ARP[i % len(ARP)] + oct_shift
                    vel = 95 if i % 4 == 0 else 80
                    notes.append((pitch, t, step * 0.85, vel))
            n = _write_clip(ch, roles["mid_bass"], slot, length, f"mid_arp_S{slot}",
                              notes, breathe=(slot < 4))
            counts[f"mid_bass S{slot}"] = n
            print(f"  mid_bass S{slot}: {n} notes (octave_shift={oct_shift}, {density})")

    # STAB — chord progression
    if "stab" in roles:
        for slot, length, root_shift in [
            (0, 16.0,  0),    # intro pad
            (1, 16.0,  0),    # Cm
            (2, 16.0, -2),    # Bbm
            (3, 16.0, -1),    # Bm tension
            (4, 32.0,  0),    # back to Cm at drop
            (6, 16.0,  3),    # Ebm rebuild
            (7, 32.0,  0),    # Cm rotterdam
            (9, 32.0, -1),    # Bm chaos
            (11, 16.0, 0),    # outro pad
        ]:
            notes = []
            chord = [60 + root_shift, 63 + root_shift, 67 + root_shift]
            if slot in (0, 11):
                # Long sustained pad
                for bar in range(int(length / 4)):
                    bs = bar * 4
                    for p in chord:
                        notes.append((p, bs, 4.0, max(35, 60 - bar * 4)))
            else:
                for bar in range(int(length / 4)):
                    bs = bar * 4
                    for beat in (1.0, 3.0):
                        for p in chord:
                            notes.append((p, bs + beat, 0.30, 100))
                    for p in chord:
                        notes.append((p, bs + 3.75, 0.15, 75))
            n = _write_clip(ch, roles["stab"], slot, length, f"stab_S{slot}", notes,
                              breathe=(slot not in (0, 11)),
                              pull_back=(slot in (3, 6)))
            counts[f"stab S{slot}"] = n
            print(f"  stab S{slot}: {n} notes (root_shift={root_shift})")

    # VOX triggers (pulse single MIDI note 60 to fire the Simpler)
    for vox_role, slot_hits in [
        ("vox_call",      [(1, 16.0, [0.0, 8.0]),
                            (2, 16.0, [0.0, 4.0, 8.0, 12.0]),
                            (3, 16.0, [0.0, 4.0, 8.0, 12.0, 14.0, 15.0]),
                            (6, 16.0, [0.0, 4.0, 8.0, 12.0, 14.0, 15.0]),
                            (7, 32.0, [0.0, 16.0]),
                            (9, 32.0, [0.0, 8.0, 16.0, 24.0])]),
        ("vox_response",  [(4, 32.0, [0.0]),
                            (7, 32.0, [0.0, 16.0]),
                            (9, 32.0, [0.0, 8.0, 16.0, 24.0])]),
        ("vox_chorus",    [(7, 32.0, [0.0, 4.0, 8.0, 12.0, 16.0, 20.0, 24.0, 28.0]),
                            (9, 32.0, [0.0, 8.0, 16.0, 24.0])]),
    ]:
        if vox_role not in roles: continue
        for slot, length, hits in slot_hits:
            notes = [(60, t, 0.5, 110) for t in hits]
            n = _write_clip(ch, roles[vox_role], slot, length,
                              f"{vox_role}_S{slot}", notes, pull_back=False)
            counts[f"{vox_role} S{slot}"] = n
            print(f"  {vox_role} S{slot}: {n} hits")

    print(f"\n  composed {len(counts)} clip-writes total")
    return counts


# ----------------------------------------------------------------------
# Phase: configure_mix
# ----------------------------------------------------------------------

def configure_mix(ch, roles: dict | None = None) -> dict:
    """Phase: mix. Apply freq separation HP/LP per role, gain staging,
    fade-ins on audio clips, loop=False on SUBBONK so it doesn't get
    cut mid-sample."""
    if roles is None:
        roles = setup_session(ch)

    print("\n[mix] applying frequency separation per role...")
    role_to_freq_role = {
        "drums":    "drums_bus",
        "amen":     "drums_bus",
        "break":    "drums_bus",
        "sub":      "sub",
        "mid_bass": "mid_bass",
        "stab":     "stab",
        "organ":    "organ",
        "pad":      "pad",
        "vox_call": "vox", "vox_response": "vox", "vox_chorus": "vox",
    }
    n_freq = 0
    for role, ti in roles.items():
        fr = role_to_freq_role.get(role)
        if fr is None: continue
        try:
            apply_freq_separation(ch, ti, fr)
            n_freq += 1
        except Exception as e:
            print(f"    {role}: freq sep fail {e}")
    print(f"  applied freq separation to {n_freq} tracks")

    # Audio clip fades + SUBBONK loop=False
    print("\n[mix] applying audio clip fades + SUBBONK loop=False...")
    DROP_SLOTS = {4, 7, 9}
    n_fades = 0
    for role, ti in roles.items():
        try:
            info = ch.get_track_info(ti).result(timeout=3)
            if info.get("is_midi_track"): continue
        except Exception: continue
        for slot in range(17):
            fade_in = 0.06 if slot in DROP_SLOTS else 0.5
            try:
                ch.set_clip_fades(ti, slot, fade_in=fade_in, fade_out=0.0).result(timeout=2)
                n_fades += 1
            except Exception: pass
    if "sub" in roles:
        for slot in range(17):
            try: ch.set_clip_loop(roles["sub"], slot, False).result(timeout=2)
            except Exception: pass
    print(f"  applied fade-ins to {n_fades} audio clips, SUBBONK looping=False")
    return {"freq_separation": n_freq, "fades": n_fades}


# ----------------------------------------------------------------------
# Phase: prepare_clips (anticipation transforms)
# ----------------------------------------------------------------------

def prepare_clips(ch, roles: dict | None = None) -> dict:
    """Phase: prepare. Write anticipation fills + decay tails.
    Run AFTER compose so the fills replace any base patterns on those slots."""
    if roles is None:
        roles = setup_session(ch)

    print("\n[prepare] writing anticipation fills on pre-drop slots...")
    if "drums" not in roles:
        return {"anticipation_slots": 0}
    hk = roles["drums"]
    counts = {}
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
        n_dicts = [{"pitch": p, "start_time": t, "duration": dur, "velocity": vel}
                   for (p, t, dur, vel) in notes if 0.0 <= t < 64.0]
        try: ch.clear_clip(hk, slot).result(timeout=3)
        except Exception: pass
        ch.create_clip(hk, slot, 64.0).result(timeout=10)
        ch.set_clip_name(hk, slot, f"anticipation_S{slot}").result(timeout=3)
        ch.add_notes_to_clip(hk, slot, n_dicts).result(timeout=10)
        counts[f"S{slot}"] = len(n_dicts)
        print(f"  drums S{slot}: anticipation fill ({len(n_dicts)} notes)")
    return counts


# ----------------------------------------------------------------------
# Phase: preview_session — interactive scene firing in session view, NO record
# ----------------------------------------------------------------------

def preview_session(ch, hold_bars_per_scene: float = 8.0,
                    skip_drops: bool = False) -> None:
    """Phase: preview. Walk through the timeline's scene events firing
    each one in session view (no session_record). Lets you audition the
    composition before committing to a print.

    hold_bars_per_scene: cap each scene's preview hold to this many bars
                         (the timeline's natural hold is honoured up to
                         this cap so previews don't take forever).
    skip_drops: if True, skip drop scenes entirely (audition the structure
                without the heavy slams).
    """
    from .arrangement import build_timeline
    print("\n[preview] firing scenes in session view (no record)...")

    sess = ch.get_session_info().result(timeout=3)
    bpm = sess["tempo"]
    bar_seconds = 60.0 / bpm * 4

    # Hard reset BUT do NOT enable session_record / record_mode
    hard_reset(ch)
    ch.set_launch_quantization(1).result(timeout=2)

    timeline = build_timeline()
    DROPS = {4, 7, 9}

    # Walk only scene events for a quick audition; skip ramps/silence/tempo
    fired = 0
    for ev in timeline.events:
        if ev[0] != "scene": continue
        slot = ev[1]
        bars = min(ev[2], hold_bars_per_scene)
        if skip_drops and slot in DROPS: continue
        try:
            ch.fire_scene(slot).result(timeout=3)
        except Exception as e:
            print(f"    fire_scene({slot}) fail: {e}")
            continue
        if fired == 0:
            time.sleep(0.1)
            ch.start_playback().result(timeout=3)
        tag = ev[3] if len(ev) > 3 else ""
        print(f"  S{slot:>2} ({bars}b): {tag}")
        time.sleep(bars * bar_seconds)
        fired += 1

    time.sleep(0.5)
    ch.stop_playback().result(timeout=3)
    ch.stop_all_clips().result(timeout=3)
    print(f"  previewed {fired} scenes")
