"""ALS MAPPINGS - list the MIDI mappings saved in a Live set (read-only).

Live keeps each manual MIDI mapping in the .als (gzipped XML) as a <KeyMidi> element on the mapped parameter,
with the parameter's <MidiControllerRange> (Min/Max, raw values) beside it. This walks the XML and reports each
mapping with its track, device, parameter, channel, CC or note, and range.

    python scripts/als_mappings.py "C:\\path\\to\\set.als"
"""
from __future__ import annotations

import gzip
import sys
import xml.etree.ElementTree as ET

DEVICE_TAGS = {"OriginalSimpler", "MultiSampler", "Operator", "InstrumentGroupDevice", "DrumGroupDevice",
               "AudioEffectGroupDevice", "MidiEffectGroupDevice", "Eq8", "DrumBuss", "Reverb", "Redux2", "Echo",
               "GlueCompressor", "Compressor2", "StereoGain", "BeatRepeat", "Amp", "Cabinet", "Saturator",
               "AutoFilter", "Roar", "Pedal", "Delay", "Chorus2", "PhaserNew", "Hybrid", "Drift", "InstrumentVector",
               "MxDeviceAudioEffect", "MxDeviceInstrument", "MxDeviceMidiEffect", "Limiter", "Utility"}
TRACK_TAGS = {"MidiTrack", "AudioTrack", "ReturnTrack", "MainTrack", "MasterTrack", "GroupTrack", "PreHearTrack"}


def name_of(el):
    for path in ("Name/EffectiveName", "Name/UserName", "UserName"):
        n = el.find(path)
        if n is not None and n.get("Value"):
            return n.get("Value")
    return ""


def main(path):
    root = ET.fromstring(gzip.open(path).read())
    parent = {c: p for p in root.iter() for c in p}

    def chain(el):
        out = []
        while el in parent:
            el = parent[el]
            out.append(el)
        return out

    rows = []
    for km in root.iter("KeyMidi"):
        param = parent[km]
        ancestors = chain(param)
        track = next((a for a in ancestors if a.tag in TRACK_TAGS), None)
        device = next((a for a in ancestors if a.tag in DEVICE_TAGS), None)
        in_rack = sum(1 for a in ancestors if a.tag in DEVICE_TAGS) > 1
        clip_slot = next((a for a in ancestors if a.tag in ("ClipSlot", "Scene")), None)
        rng = param.find("MidiControllerRange")
        onoff = param.find("MidiCCOnOffThresholds")
        v = {c.tag: c.get("Value") for c in km}
        is_note = v.get("IsNote") == "true"
        ch = int(v.get("Channel", "-1"))
        rows.append({
            "track": name_of(track) if track is not None else (track.tag if track is not None else "(song)"),
            "device": ((name_of(device) or device.tag) if device is not None else ("clip slot" if clip_slot is not None else "mixer/song"))
                      + (" (inside a rack)" if in_rack else ""),
            "param": param.tag,
            "msg": ("note " if is_note else "CC ") + v.get("NoteOrController", "?"),
            "channel": "any/keys" if ch >= 16 else str(ch + 1),
            "range": (f"{rng.find('Min').get('Value')}..{rng.find('Max').get('Value')}" if rng is not None
                      else f"on/off at {onoff.find('Min').get('Value')}" if onoff is not None else ""),
            "key": v.get("PersistentKeyString", ""),
        })
    for r in rows:
        print(f"  {r['track']:<14} {r['device']:<34} {r['param']:<24} {r['msg']:<9} ch {r['channel']:<8} "
              f"range {r['range']:<18} {('key ' + r['key']) if r['key'] else ''}")
    print(f"{len(rows)} mappings")


if __name__ == "__main__":
    main(sys.argv[1])
