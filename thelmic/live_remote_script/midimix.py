# Akai MIDImix binding for ThelmicLive.
#
# Each of the 8 strips follows a track by NAME, not by position, so moving tracks around never
# re-points a strip. A strip's 3 knobs and its fader drive device parameters over a set range
# (a knob's full turn can cover just the useful part of a parameter). Buttons act on the strip's track:
#   mute     toggles mute; the light is on while the lane is sounding
#   rec arm  cuts the lane while held (a subtraction drop by hand) and restores it on release
#   solo     (SOLO held + mute button) toggles solo
#   bank <   re-enables automation: every knob snaps back to the launched row's settings
#
# Pick-up is done here rather than by Live's Takeover Mode, because the ranges are the script's own.
# After a parameter moves by anything but its control (a row's clip automation, the mouse, Push), the
# control does nothing until it reaches the parameter's value.
#
# The mapping is data (see bind), sent over the bridge and saved beside this file, so changing it never
# needs a Live restart. Pure Python with no Live imports, so it can be tested outside Live.
#
# MIDImix factory map, channel 1, as in Live's own MIDI_Mix script:
#   knobs    row 1: CC 16 20 24 28 46 50 54 58, row 2: CC 17 21 ..., row 3: CC 18 22 ...
#   faders   CC 19 23 27 31 49 53 57 61, master CC 62
#   buttons  (notes) mute 1 4 .. 22, solo 2 5 .. 23, rec arm 3 6 .. 24, bank left 25, bank right 26, solo 27
from __future__ import absolute_import, print_function, unicode_literals

CHANNEL = 0
STRIPS = 8
KNOB_CCS = tuple((b, b + 1, b + 2) for b in (16, 20, 24, 28, 46, 50, 54, 58))
FADER_CCS = (19, 23, 27, 31, 49, 53, 57, 61)
MASTER_CC = 62
MUTE_NOTES = tuple(range(1, 23, 3))
SOLO_NOTES = tuple(range(2, 24, 3))
ARM_NOTES = tuple(range(3, 25, 3))
BANK_LEFT, BANK_RIGHT, SOLO_MODE = 25, 26, 27
ALL_CCS = tuple(cc for row in KNOB_CCS for cc in row) + FADER_CCS + (MASTER_CC,)
ALL_NOTES = MUTE_NOTES + SOLO_NOTES + ARM_NOTES + (BANK_LEFT, BANK_RIGHT, SOLO_MODE)

AKAI_ID = 0x47
MIDIMIX_MODEL = 0x31
ABLETON_MODE = 0x41
IDENTITY_REQUEST = (0xF0, 0x7E, 0x00, 0x06, 0x01, 0xF7)
PICKUP_WINDOW = 2.0 / 127

_KNOB_AT = dict((cc, (strip, k)) for strip, row in enumerate(KNOB_CCS) for k, cc in enumerate(row))
_FADER_AT = dict((cc, strip) for strip, cc in enumerate(FADER_CCS))


def _write(param, v):
    """Set a parameter, clamped to its range (and rounded when it is stepped); returns what was written."""
    v = min(float(param.max), max(float(param.min), v))
    if getattr(param, "is_quantized", False):
        v = float(round(v))
    param.value = v
    return v


def _find(items, name):
    """The first item called `name`: exact match first, then ignoring case."""
    items = list(items)
    for it in items:
        if it.name == name:
            return it
    for it in items:
        if it.name.lower() == name.lower():
            return it
    return None


class Control(object):
    """A knob or fader bound to one parameter over [lo, hi] (raw values; lo > hi turns it round).
    `followers` are (param, lo, hi) moved in lockstep; pick-up follows the main parameter."""

    def __init__(self, param, lo, hi, label, followers=()):
        self.param = param
        self.lo = float(lo)
        self.hi = float(hi)
        self.label = label
        self.followers = [(f, float(a), float(b)) for f, a, b in followers]
        self.caught = False
        self.last = None
        self._written = None

    def position(self):
        """Where the parameter sits along this control's travel, 0..1."""
        span = self.hi - self.lo
        if span == 0:
            return 0.0
        return min(1.0, max(0.0, (float(self.param.value) - self.lo) / span))

    def receive(self, value):
        pos = value / 127.0
        if not self.caught:
            target = self.position()
            near = abs(pos - target) <= PICKUP_WINDOW
            crossed = self.last is not None and (self.last - target) * (pos - target) <= 0
            self.last = pos
            if not (near or crossed):
                return False
            self.caught = True
        self.last = pos
        for param, lo, hi in self.followers:
            _write(param, lo + pos * (hi - lo))
        self._written = _write(self.param, self.lo + pos * (self.hi - self.lo))
        return True

    def param_changed(self):
        """Parameter listener: a value this control didn't write drops the catch."""
        tol = 1e-4 * max(1.0, abs(float(self.param.max) - float(self.param.min)))
        if self._written is not None and abs(float(self.param.value) - self._written) <= tol:
            return
        self.caught = False

    def describe(self):
        try:
            shown = str(self.param)
        except Exception:
            shown = ""
        return {"label": self.label, "param": self.param.name, "value": float(self.param.value),
                "display": shown, "lo": self.lo, "hi": self.hi, "caught": self.caught,
                "followers": [f.name for f, _, _ in self.followers]}


class Strip(object):
    def __init__(self, index):
        self.index = index
        self.track = None
        self.knobs = [None, None, None]
        self.fader = None
        self.cutting = False
        self.mute_before_cut = False


class MidiMix(object):
    def __init__(self, send_midi, log=None, schedule=None, version=(12, 0, 0)):
        self._send = send_midi
        self._log = log or (lambda msg: None)
        self._schedule = schedule or (lambda fn: fn())
        self._version = tuple(int(v) & 0x7F for v in version)
        self.song = None
        self.spec = {}
        self.strips = [Strip(i) for i in range(STRIPS)]
        self.master = None
        self.unresolved = []
        self.device_id = 0
        self._listeners = []
        self._rebind_pending = False

    # ---------------------------------------------------------------- binding
    def bind(self, song, spec):
        """Bind to `spec`:
            {"strips": [{"track": "F-HOLE",
                         "knobs": [{"device": "Operator", "param": "Pe Amount", "lo": 0.0, "hi": 1.0,
                                    "label": "drop", "with": [{"device": ..., "param": ..., "lo": ..., "hi": ...}]},
                                   null, ...],
                         "fader": {"mixer": "volume", "lo": 0.0, "hi": 0.85}}, null, ...],
             "master": {"mixer": "volume", "lo": 0.0, "hi": 0.85}}
        Anything that can't be found is listed in `unresolved`; the rest still binds."""
        self.unbind()
        self.song = song
        self.spec = spec or {}
        self.strips = [Strip(i) for i in range(STRIPS)]
        self.master = None
        self.unresolved = []
        self._listen(song, "tracks", self.request_rebind)
        for i, entry in enumerate((self.spec.get("strips") or [])[:STRIPS]):
            if not entry:
                continue
            strip = self.strips[i]
            track = _find(song.tracks, entry.get("track", ""))
            if track is None:
                self.unresolved.append("strip %d: no track %r" % (i + 1, entry.get("track")))
                continue
            strip.track = track
            self._listen(track, "devices", self.request_rebind)
            self._listen(track, "name", self.request_rebind)
            self._listen(track, "mute", self.refresh_leds)
            self._listen(track, "solo", self.refresh_leds)
            for k, target in enumerate((entry.get("knobs") or [])[:3]):
                if target:
                    strip.knobs[k] = self._control(track, target, "strip %d knob %d" % (i + 1, k + 1))
            if entry.get("fader"):
                strip.fader = self._control(track, entry["fader"], "strip %d fader" % (i + 1))
        if self.spec.get("master"):
            self.master = self._control(song.master_track, self.spec["master"], "master fader")
        self.refresh_leds()
        return self.state()

    def _control(self, track, target, where):
        param = self._param(track, target, where)
        if param is None:
            return None
        followers = []
        for extra in target.get("with") or []:
            f = self._param(track, extra, where)
            if f is None:
                return None
            followers.append((f, extra.get("lo", f.min), extra.get("hi", f.max)))
        control = Control(param, target.get("lo", param.min), target.get("hi", param.max),
                          target.get("label") or param.name, followers)
        self._listen(param, "value", control.param_changed)
        return control

    def _param(self, track, target, where):
        if target.get("mixer"):
            param = getattr(track.mixer_device, target["mixer"], None)
        else:
            device = _find(track.devices, target.get("device", ""))
            if device is None:
                self.unresolved.append("%s: no device %r on %s" % (where, target.get("device"), track.name))
                return None
            param = _find(device.parameters, target.get("param", ""))
        if param is None:
            self.unresolved.append("%s: no parameter %r on %s" % (
                where, target.get("param") or target.get("mixer"), track.name))
        return param

    def _listen(self, subject, prop, callback):
        try:
            getattr(subject, "add_%s_listener" % prop)(callback)
            self._listeners.append((subject, prop, callback))
        except Exception as e:
            self._log("MidiMix: can't listen to %s: %s" % (prop, e))

    def unbind(self):
        for subject, prop, callback in self._listeners:
            try:
                if getattr(subject, "%s_has_listener" % prop)(callback):
                    getattr(subject, "remove_%s_listener" % prop)(callback)
            except Exception:
                pass
        self._listeners = []

    def request_rebind(self):
        """Tracks or devices changed: rebind once, outside the notification that asked."""
        if self._rebind_pending or self.song is None:
            return
        self._rebind_pending = True

        def rebind():
            self._rebind_pending = False
            self.bind(self.song, self.spec)
        self._schedule(rebind)

    # ---------------------------------------------------------------- MIDI in
    def receive(self, midi_bytes):
        """Handle one incoming message; True when it belongs to the MIDImix."""
        if not midi_bytes:
            return False
        status = midi_bytes[0]
        if status == 0xF0:
            return self._sysex(midi_bytes)
        if len(midi_bytes) != 3 or status & 0x0F != CHANNEL:
            return False
        kind, number, value = status & 0xF0, midi_bytes[1], midi_bytes[2]
        if kind == 0xB0 and number in ALL_CCS:
            self._cc(number, value)
            return True
        if kind in (0x90, 0x80) and number in ALL_NOTES:
            self._button(number, value > 0 and kind == 0x90)
            return True
        return False

    def _cc(self, number, value):
        if number == MASTER_CC:
            control = self.master
        elif number in _FADER_AT:
            control = self.strips[_FADER_AT[number]].fader
        else:
            strip, k = _KNOB_AT[number]
            control = self.strips[strip].knobs[k]
        if control is not None:
            try:
                control.receive(value)
            except Exception as e:
                self._log("MidiMix: %s: %s" % (control.label, e))

    def _button(self, note, pressed):
        if note == BANK_LEFT:
            if pressed and self.song is not None:
                self.song.re_enable_automation()
            return
        if note in (BANK_RIGHT, SOLO_MODE):
            return
        if note in MUTE_NOTES:
            strip = self.strips[MUTE_NOTES.index(note)]
            if pressed and strip.track is not None and not strip.cutting:
                strip.track.mute = not strip.track.mute
        elif note in SOLO_NOTES:
            strip = self.strips[SOLO_NOTES.index(note)]
            if pressed and strip.track is not None:
                strip.track.solo = not strip.track.solo
        elif note in ARM_NOTES:
            strip = self.strips[ARM_NOTES.index(note)]
            if strip.track is None:
                return
            if pressed and not strip.cutting:
                strip.cutting = True
                strip.mute_before_cut = bool(strip.track.mute)
                strip.track.mute = True
            elif not pressed and strip.cutting:
                strip.cutting = False
                strip.track.mute = strip.mute_before_cut
        self.refresh_leds()

    def _sysex(self, midi_bytes):
        # identity reply: F0 7E <id> 06 02 <manufacturer> <model> ... <device id at 13> ... F7
        b = midi_bytes
        if len(b) > 13 and b[1] == 0x7E and b[3] == 0x06 and b[4] == 0x02 \
                and b[5] == AKAI_ID and b[6] == MIDIMIX_MODEL:
            self.device_id = b[13]
            # Ableton mode, as Live's own MIDI_Mix script sends it: the lights then follow the host
            self._send((0xF0, AKAI_ID, self.device_id, MIDIMIX_MODEL, 0x60, 0x00, 0x04, ABLETON_MODE)
                       + self._version + (0xF7,))
            self.refresh_leds()
            return True
        return False

    # ---------------------------------------------------------------- MIDI out
    def identity_request(self):
        self._send(IDENTITY_REQUEST)

    def refresh_leds(self):
        for s in self.strips:
            t = s.track
            self._led(MUTE_NOTES[s.index], t is not None and not t.mute)
            self._led(SOLO_NOTES[s.index], t is not None and bool(t.solo))
            self._led(ARM_NOTES[s.index], s.cutting)

    def leds_off(self):
        for note in MUTE_NOTES + SOLO_NOTES + ARM_NOTES:
            self._led(note, False)

    def _led(self, note, on):
        try:
            self._send((0x90 | CHANNEL, note, 127 if on else 0))
        except Exception:
            pass

    # ---------------------------------------------------------------- report
    def state(self):
        strips = []
        for s in self.strips:
            if s.track is None:
                continue
            strips.append({"strip": s.index + 1, "track": s.track.name, "mute": bool(s.track.mute),
                           "solo": bool(s.track.solo), "cutting": s.cutting,
                           "knobs": [c.describe() if c else None for c in s.knobs],
                           "fader": s.fader.describe() if s.fader else None})
        return {"strips": strips, "master": self.master.describe() if self.master else None,
                "unresolved": list(self.unresolved), "device_id": self.device_id}
