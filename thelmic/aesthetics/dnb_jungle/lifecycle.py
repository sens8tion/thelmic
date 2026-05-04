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
from thelmic.bridge.helpers.splice import (
    RoleSampleSpec, scan_library, find_best_matches,
    load_audio_clip_into_slot, load_simpler_sample, load_drum_pad_samples,
    DEFAULT_SPLICE_ROOT,
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


SAT_URI       = "query:AudioFx#Saturator"
EQ8_URI       = "query:AudioFx#EQ%20Eight"
OPERATOR_URI  = "query:Synths#Operator"
DRUM_RACK_URI = "query:Synths#Drum%20Rack"
SIMPLER_URI   = "query:Synths#Simpler"


# 16-track instrument basis. DRUMS is a single Drum Rack — `bulk_load_drum_pads`
# does load samples per-pad correctly, but only when the rack is FRESH.
# A pad already populated causes Live's load_item to redirect into the
# active chain. Pull therefore deletes + recreates the Drum Rack device
# before each bulk load to guarantee an empty starting state.
TRACK_TEMPLATE = [
    # Drums (single rack, multi-pad)
    ("DRUMS",      "midi",  DRUM_RACK_URI),
    # Drum rack for breakcore / amen variation
    ("AMEN",       "midi",  DRUM_RACK_URI),
    # Additional percussion drum rack
    ("PERC",       "midi",  DRUM_RACK_URI),
    # Audio sample tracks
    ("BREAK",      "audio", None),
    ("SUB",        "audio", None),
    ("ORGAN",      "audio", None),
    ("PAD",        "audio", None),
    # MIDI synths
    ("MID_BASS",   "midi",  OPERATOR_URI),
    ("STAB",       "midi",  OPERATOR_URI),
    ("REESE",      "midi",  OPERATOR_URI),
    ("LEAD",       "midi",  OPERATOR_URI),
    ("SHIMMER",    "midi",  OPERATOR_URI),
    # Vocal Simplers
    ("VOX_CALL",   "midi",  SIMPLER_URI),
    ("VOX_RESP",   "midi",  SIMPLER_URI),
    ("VOX_CHOR",   "midi",  SIMPLER_URI),
    # FX
    ("FX",         "midi",  OPERATOR_URI),
]


# ----------------------------------------------------------------------
# Phase: setup_session
# ----------------------------------------------------------------------

def _track_exists(ch, name: str) -> bool:
    return find_track(ch, name) is not None


def _is_default_empty_track(info) -> bool:
    """Live's default-fresh tracks (1 MIDI / 2 MIDI / 3 Audio / 4 Audio)
    have a recognisable name pattern AND no devices beyond the mixer."""
    import re
    name = (info.get("name") or "").strip()
    if not re.match(r"^\d+\s*[-_ ]?\s*(MIDI|Audio)$", name, re.IGNORECASE):
        return False
    # Default tracks have only their type-default device chain
    devs = info.get("devices") or []
    # Any user-loaded device disqualifies; an audio track default has 0 devices,
    # MIDI default has 0 (no instrument). Either way, devs is empty.
    if devs:
        return False
    return True


def cleanup_default_tracks(ch) -> int:
    """Delete Live's default empty tracks (1 MIDI, 2 MIDI, 3 Audio, 4 Audio)
    if they're still present and untouched. Iterates from the end so indices
    don't shift mid-iteration."""
    sess = ch.get_session_info().result(timeout=3)
    n = sess["track_count"]
    to_delete = []
    for ti in range(n):
        try: info = ch.get_track_info(ti).result(timeout=3)
        except Exception: continue
        if _is_default_empty_track(info):
            to_delete.append((ti, info.get("name", "")))
    if not to_delete:
        return 0
    for ti, name in reversed(to_delete):
        try:
            ch.delete_track(ti).result(timeout=5)
            print(f"  - removed default track T{ti} {name!r}")
        except Exception as e:
            print(f"  - delete T{ti} {name!r} fail: {e}")
    return len(to_delete)


# Legacy → role-name renames applied during bootstrap if a legacy-named
# track is found. Lets us migrate old sessions to the role-named scheme.
LEGACY_RENAMES = {
    "HARDKIT":      "DRUMS",
    "AMEN CHOPPED": "AMEN",
    "BREAKBEAST":   "BREAK",
    "SUBBONK":      "SUB",
    "TECTONIC":     "MID_BASS",
    "COLD MIST":    "PAD",
    "VOX YO":       "VOX_CALL",
    "VOX BIG":      "VOX_RESP",
    "VOX SEL":      "VOX_CHOR",
}


def rename_legacy_tracks(ch) -> int:
    """Rename any legacy-named tracks to the role-based scheme.
    Idempotent — skips tracks already named per role."""
    n_renamed = 0
    sess = ch.get_session_info().result(timeout=3)
    n = sess["track_count"]
    for ti in range(n):
        try: info = ch.get_track_info(ti).result(timeout=3)
        except Exception: continue
        name = (info.get("name") or "").strip()
        if name in LEGACY_RENAMES:
            new_name = LEGACY_RENAMES[name]
            try:
                ch.set_track_name(ti, new_name).result(timeout=3)
                print(f"  ↻ renamed T{ti} {name!r} → {new_name!r}")
                n_renamed += 1
            except Exception as e:
                print(f"  ! rename T{ti} {name!r} fail: {e}")
    return n_renamed


def bootstrap_tracks(ch) -> int:
    """Create the 16-track instrument basis from scratch.

    For each entry in TRACK_TEMPLATE that doesn't already exist as a
    track in the session, creates a track of the right type, names it,
    and (for MIDI tracks) loads the configured instrument.

    Idempotent — also renames any legacy-named tracks (HARDKIT → DRUMS,
    etc.) before creating, so re-running on a legacy session migrates it.

    Returns count of tracks newly created.
    """
    # Pass 0: migrate legacy names so the existence check below matches
    print("[setup] migrating any legacy track names to role-based scheme...")
    rename_legacy_tracks(ch)

    print("[setup] bootstrapping 16-track basis from scratch...")
    n_created = 0
    for tname, ttype, instr_uri in TRACK_TEMPLATE:
        if _track_exists(ch, tname):
            continue
        try:
            if ttype == "midi":
                r = ch.create_midi_track(-1).result(timeout=10)
            else:
                r = ch.create_audio_track(-1).result(timeout=10)
        except Exception as e:
            print(f"  ! create_{ttype}_track({tname}) fail: {e}")
            continue
        ti = r.get("index", r.get("track_index"))
        if ti is None:
            print(f"  ! created {tname} but couldn't read index from {r}")
            continue
        try: ch.set_track_name(ti, tname).result(timeout=3)
        except Exception as e: print(f"    rename fail: {e}")
        if instr_uri is not None:
            try:
                ch.load_device(ti, instr_uri).result(timeout=15)
            except Exception as e:
                print(f"    instrument load fail ({instr_uri}): {e}")
        n_created += 1
        print(f"  + T{ti} {tname:<14} ({ttype}{', ' + instr_uri.split('#')[-1] if instr_uri else ''})")
    print(f"  bootstrap complete — {n_created} new tracks created")
    return n_created


REQUIRED_SCENES = 17        # the pack uses slots 0..13; round up for safety


def ensure_scenes(ch, n_required: int = REQUIRED_SCENES) -> int:
    """Ensure the session has at least n_required scenes (clip slots per track).
    Newly-bootstrapped sessions usually start with only 8."""
    try:
        info = ch.get_scene_count().result(timeout=3)
        n_scenes = info if isinstance(info, int) else info.get("count", info.get("scene_count", 0))
    except Exception:
        n_scenes = 0
    n_create = max(0, n_required - n_scenes)
    if n_create == 0:
        return 0
    for _ in range(n_create):
        try: ch.create_scene(-1).result(timeout=3)
        except Exception as e:
            print(f"  ! create_scene fail: {e}")
            break
    print(f"  + ensured {n_required} scenes (created {n_create})")
    return n_create


def setup_session(ch, bootstrap: bool = True) -> dict:
    """Phase: setup. Ensure required tracks + scenes + devices are present.
    Idempotent — bootstraps missing tracks if `bootstrap=True`, ensures
    enough scenes, adds device shape (Saturator on drums for drive ramps).

    Returns dict of {role_name: track_index}."""
    print("\n[setup] ensuring 16-track basis + scenes + required devices...")
    sess = ch.get_session_info().result(timeout=3)
    n = sess["track_count"]
    print(f"  session has {n} tracks before setup")

    if bootstrap:
        bootstrap_tracks(ch)
        ensure_scenes(ch)
        cleanup_default_tracks(ch)         # remove Live's default 4 stub tracks

    roles = {}
    for role_name, hints in [
        ("drums",        ["DRUMS",     "HARDKIT"]),
        ("amen",         ["AMEN",      "AMEN CHOPPED"]),
        ("perc",         ["PERC"]),
        ("break",        ["BREAK",     "BREAKBEAST"]),
        ("sub",          ["SUB",       "SUBBONK"]),
        ("mid_bass",     ["MID_BASS",  "TECTONIC"]),
        ("stab",         ["STAB"]),
        ("organ",        ["ORGAN"]),
        ("pad",          ["PAD",       "COLD MIST"]),
        ("reese",        ["REESE"]),
        ("lead",         ["LEAD"]),
        ("shimmer",      ["SHIMMER"]),
        ("fx",           ["FX"]),
        ("vox_call",     ["VOX_CALL",  "VOX YO", "VOX"]),
        ("vox_response", ["VOX_RESP",  "VOX BIG"]),
        ("vox_chorus",   ["VOX_CHOR",  "VOX SEL"]),
    ]:
        for h in hints:
            ti = find_track(ch, h)
            if ti is not None:
                roles[role_name] = ti
                break

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

    # Ensure each MIDI track has an EQ8 (so freq separation has something to work with)
    for role, ti in roles.items():
        try:
            ensure_device(ch, ti, "Eq8", EQ8_URI)
        except Exception as e:
            print(f"    {role}: EQ8 ensure fail {e}")

    print(f"  resolved {len(roles)} roles: {list(roles.keys())}")
    return roles


# ----------------------------------------------------------------------
# Phase: pull_samples (Splice integration)
# ----------------------------------------------------------------------

# Role → sample-search spec for the dnb_jungle pack
DNB_JUNGLE_SAMPLE_SPECS = {
    # Drum-rack pads — match individual hits
    "kick":   RoleSampleSpec("kick",
                              should_match=["kick", "808", "909", "boom"],
                              must_not_match=["loop", "fill", "reverse"],
                              one_shot_preferred=True),
    "snare":  RoleSampleSpec("snare",
                              should_match=["snare", "snr", "rim", "clap"],
                              must_not_match=["loop", "reverse"],
                              one_shot_preferred=True),
    "hat_c":  RoleSampleSpec("hat_c",
                              should_match=["hat_c", "closed", "hihat", "hh_c", "ch_"],
                              must_not_match=["open", "loop", "reverse"],
                              one_shot_preferred=True),
    "hat_o":  RoleSampleSpec("hat_o",
                              should_match=["hat_o", "open", "hh_o", "oh_"],
                              must_not_match=["closed", "loop"],
                              one_shot_preferred=True),
    "crash":  RoleSampleSpec("crash",
                              should_match=["crash", "cymbal", "cym"],
                              must_not_match=["loop", "ride"],
                              one_shot_preferred=True),
    # Audio sample tracks
    "break":  RoleSampleSpec("break",
                              should_match=["break", "amen", "drum_break", "loop"],
                              bpm_range=(160, 180),
                              loop_preferred=True),
    "sub":    RoleSampleSpec("sub",
                              should_match=["sub", "808", "bass_sub", "bonk"],
                              must_not_match=["mid", "high"],
                              loop_preferred=False),
    "organ":  RoleSampleSpec("organ",
                              should_match=["organ", "rhodes", "wurli"],
                              loop_preferred=True),
    "pad":    RoleSampleSpec("pad",
                              should_match=["pad", "texture", "ambient", "drone"],
                              loop_preferred=True),
    # Vocal one-shots — using historical character markers (bigup, yo, selassie)
    "vox_call":      RoleSampleSpec("vox_call",
                                     should_match=["yo", "ay", "oi", "intro", "vocal_chop"],
                                     must_match=["vocal"]),
    "vox_response":  RoleSampleSpec("vox_response",
                                     should_match=["big_up", "bigup", "shout"],
                                     must_match=["vocal"]),
    "vox_chorus":    RoleSampleSpec("vox_chorus",
                                     should_match=["selassie", "chorus", "hook"],
                                     must_match=["vocal"]),
}


def pull_samples(ch, splice_root=None, library_assignments=None) -> dict:
    """Phase: pull. Scan local Splice library + load matched samples
    into role tracks.

    splice_root:         Path to Splice library (default ~/Documents/Splice/Samples)
    library_assignments: optional pre-resolved {role: Path} override; if given,
                          skips the local scan and loads exactly these.

    For agent-driven Splice MCP fetching: call prompt_to_stack +
    download_asset upstream of this, save to ~/Documents/Splice/Samples/,
    then this function picks up the new content automatically.
    """
    print("\n[pull] scanning Splice library + loading matched samples...")
    if splice_root is None:
        splice_root = DEFAULT_SPLICE_ROOT

    library = scan_library(splice_root)
    if not library:
        print(f"  no samples found at {splice_root}")
        return {}
    print(f"  scanned {len(library)} samples")

    # Resolve which sample to use for each role
    if library_assignments is None:
        library_assignments = {}
        for role, spec in DNB_JUNGLE_SAMPLE_SPECS.items():
            matches = find_best_matches(library, spec, top_n=1)
            if matches:
                _, entry = matches[0]
                library_assignments[role] = entry.path

    if not library_assignments:
        print("  no role matches in library; skipping")
        return {}

    # Map sample roles to track roles + load
    roles = setup_session(ch, bootstrap=False)
    counts = {"loaded": 0, "skipped": 0}

    # Drum Rack: empty rack + per-pad hotswap loads. selected_drum_pad path
    # routes every load to pad 36, but Browser.hotswap_target = pad works.
    DRUM_PADS = [
        (36, "tp_nh_cjb_kick_one_shot_low_punchy.wav"),
        (38, "BOS_AJ_Drum_Snare_One_Shot_Press_A_sharp.wav"),
        (42, "ZEN_PDB_hi_hat_closed_one_shot_tight.wav"),
        (46, "shs_ins_hat_open_one_shot_Fit.wav"),
        (49, "cj_cymbal_one_shot_live_ahman.wav"),
    ]
    SPLICE_USER_LIB = "user_library/Samples/Splice"

    if "drums" in roles:
        t_drums = roles["drums"]
        info = ch.get_track_info(t_drums).result(timeout=3)
        for di in reversed(range(len(info.get("devices", [])))):
            cls = info["devices"][di].get("class_name", "")
            if cls in ("DrumGroupDevice", "InstrumentGroupDevice"):
                try: ch.delete_device(t_drums, di).result(timeout=5)
                except Exception: pass
        try:
            ch.load_item_at_path(t_drums, "instruments", "Drum Rack").result(timeout=15)
            time.sleep(1.2)
            for note, fname in DRUM_PADS:
                try:
                    ch.load_sample_to_pad(t_drums, 0, note, SPLICE_USER_LIB, fname).result(timeout=15)
                    counts["loaded"] += 1
                except Exception as e:
                    print(f"  drums: pad {note} ({fname}) fail: {e}")
                    counts["skipped"] += 1
                time.sleep(0.3)
            print(f"  drums: per-pad hotswap loaded {counts['loaded']} hits")
        except Exception as e:
            print(f"  drums: rack load fail: {e}")

    # Audio tracks: break, sub, organ, pad — load into slot 0 of each
    for role_name, track_role in [("break", "break"), ("sub", "sub"),
                                    ("organ", "organ"), ("pad", "pad")]:
        path = library_assignments.get(role_name)
        ti = roles.get(track_role)
        if path is None or ti is None: continue
        if load_audio_clip_into_slot(ch, ti, 0, path):
            print(f"  {track_role}: loaded {path.name}")
            counts["loaded"] += 1
        else:
            counts["skipped"] += 1

    # Simpler tracks: vox_call, vox_response, vox_chorus
    for role_name, track_role in [("vox_call", "vox_call"),
                                    ("vox_response", "vox_response"),
                                    ("vox_chorus", "vox_chorus")]:
        path = library_assignments.get(role_name)
        ti = roles.get(track_role)
        if path is None or ti is None: continue
        if load_simpler_sample(ch, ti, path):
            print(f"  {track_role}: loaded {path.name}")
            counts["loaded"] += 1
        else:
            counts["skipped"] += 1

    print(f"\n  pull complete: {counts['loaded']} loaded, {counts['skipped']} skipped")
    return counts


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


def _split_drum_notes_by_track(notes: list, roles: dict) -> dict:
    """Take a unified GM-pitched drum pattern and split into per-track clips.

    Drum hit pitches (KICK=36, SNARE=38, HAT_C=42, HAT_O=46, CRASH=49) get
    routed to their respective per-instrument Simpler tracks. The pitch
    on each track is normalized to 60 (C5) since Simpler plays its sample
    on any note.

    Returns: {role: [(60, t, dur, vel), ...]}
    """
    from .constants import KICK, SNARE, HAT_C, HAT_O, CRASH
    PITCH_TO_ROLE = {KICK: "kick", SNARE: "snare", HAT_C: "hat_c",
                      HAT_O: "hat_o", CRASH: "crash"}
    by_role: dict = {}
    for p, t, dur, vel in notes:
        role = PITCH_TO_ROLE.get(p)
        if role and role in roles:
            by_role.setdefault(role, []).append((60, t, dur, vel))
    return by_role


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

    # Drum patterns write to the single DRUMS rack at GM pitches.
    if "drums" in roles:
        # Slot 4 — ragga jungle drop
        notes = []
        for r in range(6):
            notes.extend(_ragga_jungle_4bar(r * 4, hat_density="16th"))
        notes.extend(_ragga_jungle_4bar(24, hat_density="32nd"))
        impact_t = 32 - 0.125
        notes.append((KICK,  impact_t, 0.20, 127))
        notes.append((SNARE, impact_t, 0.20, 127))
        notes.append((CRASH, impact_t, 4.00, 127))
        n = _write_clip(ch, roles["drums"], 4, 32.0, "drop_ragga", notes, breathe=True)
        counts["drums S4"] = n
        print(f"  drums S4: {n} notes (ragga drop)")

        # Slot 7 — Rotterdam gabber
        notes = []
        notes.extend(_rotterdam_gabber_4bar(0,  hat_density="16th"))
        notes.extend(_rotterdam_gabber_4bar(16, hat_density="32nd"))
        notes.extend(_rotterdam_gabber_4bar(28, double_time=True, hat_density="64th"))
        impact_t = 32 - 0.125
        notes.append((KICK,  impact_t, 0.20, 127))
        notes.append((CRASH, impact_t, 4.00, 127))
        n = _write_clip(ch, roles["drums"], 7, 32.0, "drop_rotterdam", notes)
        counts["drums S7"] = n
        print(f"  drums S7: {n} notes (Rotterdam)")

        # Slot 9 — breakcore peak
        notes = []
        for r in range(8):
            notes.extend(breakcore_4bar(r * 4))
        n = _write_clip(ch, roles["drums"], 9, 32.0, "breakcore_peak", notes,
                          pull_back=False)
        counts["drums S9"] = n
        print(f"  drums S9: {n} notes (breakcore)")

        # Slot 11 — quiet outro
        notes = []
        for bar in range(16):
            bs = bar * 4
            kvel = max(35, 95 - bar)
            notes.append((KICK, bs, 0.40, kvel))
            if bar % 4 in (1, 3):
                notes.append((SNARE, bs + 2.5, 0.20, max(30, 50 - bar)))
        n = _write_clip(ch, roles["drums"], 11, 64.0, "outro_quiet", notes,
                          pull_back=False)
        counts["drums S11"] = n
        print(f"  drums S11: {n} notes (outro)")

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

    # PERC — additional percussion alongside DRUMS (toms / claps / ghost hits)
    if "perc" in roles:
        for slot, length in [(2, 16), (3, 16), (4, 32), (6, 16), (7, 32), (9, 32)]:
            notes = []
            for bar in range(int(length / 4)):
                bs = bar * 4
                # Tom hit on bar boundary every 4th bar
                if bar % 4 == 3:
                    notes.append((41, bs + 3.5, 0.18, 100))   # low tom
                    notes.append((50, bs + 3.75, 0.15, 95))    # high tom
                # Hand-claps doubling snares
                notes.append((39, bs + 1.0, 0.20, 80))
                notes.append((39, bs + 3.0, 0.20, 90))
                # Ghost shaker on offbeats (closed hat alt)
                for off in (0.5, 2.5):
                    notes.append((44, bs + off, 0.10, 55))    # pedal hi-hat MIDI 44
            n = _write_clip(ch, roles["perc"], slot, length, f"perc_S{slot}", notes,
                              pull_back=False, breathe=True)
            counts[f"perc S{slot}"] = n
            print(f"  perc S{slot}: {n} notes (parallel percussion)")

    # REESE — classic mid-bass reese pattern (sustained notes, harmonic motion)
    if "reese" in roles:
        # Reese is long sustained notes that move with the chord progression
        for slot, length, root in [(4, 32, 36), (7, 32, 36), (9, 32, 35)]:
            notes = []
            # Root note held 1 bar at a time, varying octave
            for bar in range(int(length / 4)):
                bs = bar * 4
                pitch = root + (12 if bar % 4 == 2 else 0)
                notes.append((pitch, bs, 4.0, 105))
            n = _write_clip(ch, roles["reese"], slot, length, f"reese_S{slot}", notes,
                              pull_back=False, breathe=False)
            counts[f"reese S{slot}"] = n
            print(f"  reese S{slot}: {n} notes (sustained reese bass)")

    # LEAD — melodic motif on drops
    if "lead" in roles:
        # Simple ascending motif: Cm pentatonic-ish
        MOTIF = [0, 3, 5, 7, 10, 7, 5, 3]    # semitones from root
        ROOT = 60                             # middle C
        for slot, length, octave_offset in [(4, 32, 0), (7, 32, 12), (9, 32, 0)]:
            notes = []
            for bar in range(int(length / 4)):
                bs = bar * 4
                # Play motif over 2 beats, rest 2 beats, repeat
                if bar % 2 == 0:
                    for i, iv in enumerate(MOTIF):
                        t = bs + i * 0.25
                        notes.append((ROOT + iv + octave_offset, t, 0.20, 95))
            n = _write_clip(ch, roles["lead"], slot, length, f"lead_S{slot}", notes,
                              pull_back=True, breathe=False)
            counts[f"lead S{slot}"] = n
            print(f"  lead S{slot}: {n} notes (melodic motif)")

    # SHIMMER — high-pitched arpeggios for peak/breakcore
    if "shimmer" in roles:
        # High Cm triad arpeggio at 16ths
        TRIAD = [72, 75, 79, 84]    # Cm spread across two octaves
        for slot, length in [(7, 32), (9, 32)]:
            notes = []
            n_per_bar = 16
            for bar in range(int(length / 4)):
                bs = bar * 4
                for i in range(n_per_bar):
                    t = bs + i * 0.25
                    pitch = TRIAD[i % len(TRIAD)]
                    vel = 80 if i % 4 == 0 else 60
                    notes.append((pitch, t, 0.15, vel))
            n = _write_clip(ch, roles["shimmer"], slot, length, f"shimmer_S{slot}",
                              notes, pull_back=False, breathe=True)
            counts[f"shimmer S{slot}"] = n
            print(f"  shimmer S{slot}: {n} notes (high arp)")

    # FX — risers / transition moments at scene boundaries
    if "fx" in roles:
        # Long sustained low note that rises in pitch as a riser
        # Operator's Volume modulation on a long note creates the swell
        for slot, length, fx_type in [(3, 16, "riser"), (6, 16, "riser"),
                                        (13, 16, "riser"), (10, 8, "drop_fx")]:
            notes = []
            if fx_type == "riser":
                # Single long note, increasing velocity steps create build feel
                for bar in range(int(length / 4)):
                    bs = bar * 4
                    vel = min(127, 50 + bar * 20)
                    notes.append((48, bs, 4.0, vel))
            elif fx_type == "drop_fx":
                # FX hit at bar boundary
                notes.append((48, 0, 1.0, 100))
                notes.append((60, 4, 1.0, 90))
            n = _write_clip(ch, roles["fx"], slot, length, f"fx_S{slot}_{fx_type}",
                              notes, pull_back=(fx_type == "riser"),
                              breathe=False)
            counts[f"fx S{slot}"] = n
            print(f"  fx S{slot}: {n} notes ({fx_type})")

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
        return {}
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
        print(f"  drums S{slot}: {len(n_dicts)} notes")
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
