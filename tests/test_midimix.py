"""The ThelmicLive MIDImix binding (thelmic/live_remote_script/midimix.py), against fake Live objects.

The module is loaded from its file: importing the live_remote_script package needs Live's _Framework.
"""
import importlib.util
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parent.parent / "thelmic" / "live_remote_script" / "midimix.py"
_spec = importlib.util.spec_from_file_location("midimix", _PATH)
mm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mm)


class Listenable:
    """add_<prop>_listener / remove_<prop>_listener / <prop>_has_listener, as Live objects have them."""

    def __init__(self):
        self._listeners = {}

    def __getattr__(self, name):
        if name.startswith("add_") and name.endswith("_listener"):
            return lambda cb: self._listeners.setdefault(name[4:-9], []).append(cb)
        if name.startswith("remove_") and name.endswith("_listener"):
            return lambda cb: self._listeners[name[7:-9]].remove(cb)
        if name.endswith("_has_listener"):
            return lambda cb: cb in self._listeners.get(name[:-13], [])
        raise AttributeError(name)

    def _fire(self, prop):
        for cb in list(self._listeners.get(prop, [])):
            cb()


class Param(Listenable):
    def __init__(self, name, value, lo=0.0, hi=1.0, quantized=False):
        super().__init__()
        self.name, self._value, self.min, self.max, self.is_quantized = name, value, lo, hi, quantized

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        assert self.min <= v <= self.max, (self.name, v)
        self._value = v
        self._fire("value")


class Device:
    def __init__(self, name, *params):
        self.name, self.parameters = name, list(params)


class Mixer:
    def __init__(self):
        self.volume = Param("Track Volume", 0.6)
        self.panning = Param("Track Panning", 0.0, -1.0, 1.0)


class Track(Listenable):
    def __init__(self, name, *devices):
        super().__init__()
        self.name, self.devices, self.mixer_device = name, list(devices), Mixer()
        self._mute = self._solo = False

    @property
    def mute(self):
        return self._mute

    @mute.setter
    def mute(self, v):
        self._mute = bool(v)
        self._fire("mute")

    @property
    def solo(self):
        return self._solo

    @solo.setter
    def solo(self, v):
        self._solo = bool(v)
        self._fire("solo")


class Song(Listenable):
    def __init__(self, *tracks):
        super().__init__()
        self.tracks = list(tracks)
        self.master_track = Track("Main")
        self.re_enabled = 0

    def re_enable_automation(self):
        self.re_enabled += 1


def cc(number, value):
    return (0xB0, number, value)


def note(number, pressed):
    return (0x90, number, 127) if pressed else (0x80, number, 0)


@pytest.fixture
def rig():
    drop = Param("Pe Amount", 1.0, -1.0, 1.0)
    shaper = Param("Shaper Mix", 0.0, 0.0, 100.0)
    sub = Track("F-HOLE", Device("Operator", drop, shaper))
    lowcut = Param("1 Frequency A", 0.3223)
    amen = Track("AMEN-DMENT", Device("EQ Eight", lowcut))
    song = Song(amen, sub)
    sent, scheduled = [], []
    mix = mm.MidiMix(sent.append, schedule=scheduled.append, version=(12, 4, 6))
    spec = {"strips": [
        {"track": "AMEN-DMENT", "knobs": [{"device": "EQ Eight", "param": "1 Frequency A", "lo": 0.1429, "hi": 0.5973}],
         "fader": {"mixer": "volume", "lo": 0.0, "hi": 0.85}},
        {"track": "F-HOLE", "knobs": [{"device": "Operator", "param": "Pe Amount", "lo": 0.0, "hi": 1.0, "label": "drop"},
                                     None,
                                     {"device": "Operator", "param": "Shaper Mix", "lo": 0.0, "hi": 100.0}]},
    ], "master": {"mixer": "volume", "lo": 0.0, "hi": 0.85}}
    state = mix.bind(song, spec)
    return dict(mix=mix, song=song, sub=sub, amen=amen, drop=drop, shaper=shaper, lowcut=lowcut,
                sent=sent, scheduled=scheduled, state=state)


def test_binds_by_track_name_and_reports_what_it_cannot_find(rig):
    assert [s["track"] for s in rig["state"]["strips"]] == ["AMEN-DMENT", "F-HOLE"]
    assert rig["state"]["unresolved"] == []
    state = rig["mix"].bind(rig["song"], {"strips": [
        {"track": "NOPE"},
        {"track": "F-HOLE", "knobs": [{"device": "Reverb", "param": "Dry/Wet"},
                                      {"device": "Operator", "param": "Nonsense"}]}]})
    assert state["unresolved"] == ["strip 1: no track 'NOPE'",
                                   "strip 2 knob 1: no device 'Reverb' on F-HOLE",
                                   "strip 2 knob 2: no parameter 'Nonsense' on F-HOLE"]
    assert [s["track"] for s in state["strips"]] == ["F-HOLE"]


def test_knob_does_nothing_until_it_picks_up_the_parameter(rig):
    mix, shaper = rig["mix"], rig["shaper"]
    shaper.value = 50.0                                 # the row set it: knob 3 must reach the middle first
    mix.receive(cc(18 + 4, 10))
    mix.receive(cc(18 + 4, 40))
    assert shaper.value == 50.0
    mix.receive(cc(18 + 4, 70))                         # crossed the middle: caught
    assert shaper.value == pytest.approx(70 / 127 * 100)
    mix.receive(cc(18 + 4, 127))
    assert shaper.value == 100.0


def test_a_control_already_at_the_value_picks_up_straight_away(rig):
    rig["mix"].receive(cc(20, 127))                     # drop sits at 1.0 = the top of the knob's range
    rig["mix"].receive(cc(20, 100))
    assert rig["drop"].value == pytest.approx(100 / 127)


def test_a_change_from_elsewhere_drops_the_catch(rig):
    mix, drop = rig["mix"], rig["drop"]
    mix.receive(cc(20, 127))
    mix.receive(cc(20, 64))
    assert drop.value == pytest.approx(64 / 127)
    drop.value = 0.0                                    # clip automation on the next row
    mix.receive(cc(20, 70))
    assert drop.value == 0.0
    mix.receive(cc(20, 0))                              # swept through it: follows again
    mix.receive(cc(20, 30))
    assert drop.value == pytest.approx(30 / 127)


def test_range_can_run_backwards_and_is_clamped_to_the_parameter():
    p = Param("Lowest", 100.0, 1.0, 127.0, quantized=True)
    t = Track("THROW-UP", Device("Velocity", p))
    mix = mm.MidiMix(lambda b: None)
    mix.bind(Song(t), {"strips": [{"track": "THROW-UP", "knobs": [{"device": "Velocity", "param": "Lowest",
                                                                  "lo": 100.0, "hi": 0.0}]}]})
    mix.receive(cc(16, 0))                              # at 100 already: caught
    mix.receive(cc(16, 127))
    assert p.value == 1.0                               # 0 wanted, clamped to the parameter's minimum
    mix.receive(cc(16, 64))
    assert p.value == float(round(100 - 64 / 127 * 100))


def test_faders_and_master(rig):
    mix = rig["mix"]
    vol = rig["amen"].mixer_device.volume              # 0.6 of a 0..0.85 travel
    mix.receive(cc(19, round(0.6 / 0.85 * 127)))
    mix.receive(cc(19, 127))
    assert vol.value == pytest.approx(0.85)
    master = rig["song"].master_track.mixer_device.volume
    mix.receive(cc(62, round(0.6 / 0.85 * 127)))
    mix.receive(cc(62, 0))
    assert master.value == 0.0


def test_mute_toggles_and_lights_while_the_lane_sounds(rig):
    mix, sub, sent = rig["mix"], rig["sub"], rig["sent"]
    sent.clear()
    mix.receive(note(4, True))
    mix.receive(note(4, False))
    assert sub.mute is True
    assert (0x90, 4, 0) in sent
    sent.clear()
    mix.receive(note(4, True))
    assert sub.mute is False
    assert (0x90, 4, 127) in sent


def test_rec_arm_cuts_the_lane_while_held(rig):
    mix, sub, sent = rig["mix"], rig["sub"], rig["sent"]
    mix.receive(note(6, True))
    assert sub.mute is True and (0x90, 6, 127) in sent
    mix.receive(note(4, True))                          # mute ignored mid-cut
    assert sub.mute is True
    mix.receive(note(6, False))
    assert sub.mute is False and (0x90, 6, 0) in sent


def test_solo_and_bank_left(rig):
    mix = rig["mix"]
    mix.receive(note(2, True))
    assert rig["amen"].solo is True
    mix.receive(note(25, True))
    mix.receive(note(25, False))
    assert rig["song"].re_enabled == 1


def test_identity_reply_puts_the_midimix_in_ableton_mode(rig):
    mix, sent = rig["mix"], rig["sent"]
    mix.identity_request()
    assert sent[-1] == mm.IDENTITY_REQUEST
    reply = (0xF0, 0x7E, 0x00, 0x06, 0x02, 0x47, 0x31, 0x00, 0x19, 0x00, 0x01, 0x00, 0x00, 0x05, 0x00, 0xF7)
    assert mix.receive(reply) is True
    assert (0xF0, 0x47, 0x05, 0x31, 0x60, 0x00, 0x04, 0x41, 12, 4, 6, 0xF7) in rig["sent"]
    assert mix.receive((0xF0, 0x7E, 0x00, 0x06, 0x02, 0x00, 0x20, 0x29, 0xF7)) is False


def test_leaves_other_messages_alone(rig):
    mix = rig["mix"]
    assert mix.receive(cc(7, 100)) is False             # not a MIDImix control
    assert mix.receive((0xB1, 16, 100)) is False        # another channel
    assert mix.receive((0x90, 60, 100)) is False
    assert mix.receive(cc(58, 10)) is True              # an unbound MIDImix knob is still the MIDImix's


def test_track_changes_rebind_once_outside_the_notification(rig):
    mix, song, scheduled = rig["mix"], rig["song"], rig["scheduled"]
    song.tracks.insert(0, Track("SPINE-TINGLER"))
    song._fire("tracks")
    song._fire("tracks")
    assert len(scheduled) == 1
    scheduled.pop()()
    assert [s["track"] for s in mix.state()["strips"]] == ["AMEN-DMENT", "F-HOLE"]
    assert rig["sub"]._listeners["mute"] == [mix.refresh_leds]     # old listeners removed, not stacked


def test_followers_move_in_lockstep_with_the_main_parameter():
    lowest = Param("Lowest", 1.0, 1.0, 127.0, quantized=True)
    out_low = Param("Out Low", 1.0, 1.0, 127.0, quantized=True)
    t = Track("CHOPPER", Device("Velocity", lowest, out_low))
    mix = mm.MidiMix(lambda b: None)
    state = mix.bind(Song(t), {"strips": [{"track": "CHOPPER", "knobs": [
        {"device": "Velocity", "param": "Lowest", "lo": 100.0, "hi": 1.0,
         "with": [{"device": "Velocity", "param": "Out Low", "lo": 100.0, "hi": 1.0}]}]}]})
    assert state["strips"][0]["knobs"][0]["followers"] == ["Out Low"]
    mix.receive(cc(16, 127))
    mix.receive(cc(16, 0))
    assert lowest.value == 100.0 and out_low.value == 100.0
    out_low.value = 50.0                                # a follower moved elsewhere doesn't drop the catch
    mix.receive(cc(16, 127))
    assert lowest.value == 1.0 and out_low.value == 1.0
