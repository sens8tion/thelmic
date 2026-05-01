# thelmic

> An instrument you ride, not configure.

A performance instrument for shaping anticipation → tension → release over time.
MIDI out. Python. No DAW dependency at this stage.

See [ARCHITECTURE.md](ARCHITECTURE.md) for full system design and session guide.

## Quick start

```bash
pip install -e ".[dev]"
python examples/kick_only.py
```

Open Ableton (or any DAW) and select the `thelmic` virtual MIDI port as input.

## LOM side channel (optional)

Asynchronous, fire-and-forget control path that sits next to MIDI for structural
moves: device parameter changes, device loads, tempo, clip firing. Hard-isolated
from the realtime sequencer — the MIDI engine runs identically with the channel
disabled, disconnected, or saturated.

**Off by default.** Enable with:

```bash
export LIVE_CHANNEL_ENABLED=1     # macOS / Linux
$env:LIVE_CHANNEL_ENABLED = "1"   # Windows PowerShell
```

### Install the Remote Script (one-time)

The channel talks to a small Remote Script that runs inside Ableton Live on the
UI thread. It's namespaced (port 9878, class `ThelmicLive`) so it coexists with
upstream `ableton-mcp` (9877) if you have that installed.

1. Find Live's MIDI Remote Scripts directory:
   - **Windows:** `%PROGRAMDATA%\Ableton\Live <ver>\Resources\MIDI Remote Scripts\`
     (Live can also load from `%USERPROFILE%\Documents\Ableton\User Library\Remote Scripts\`)
   - **macOS:** `/Applications/Ableton Live <ver>.app/Contents/App-Resources/MIDI Remote Scripts/`
2. Copy `thelmic/live_remote_script/` into that directory, renaming the folder
   to `ThelmicLive` (Live discovers scripts by folder name).
3. Restart Live.
4. Preferences → Link/Tempo/MIDI → set one Control Surface slot to `ThelmicLive`.
   You should see "ThelmicLive listening on 9878" in Live's status bar.

### Smoke test

```python
from thelmic.live_channel import LiveChannel
ch = LiveChannel()       # reads LIVE_CHANNEL_ENABLED
ch.start()
print(ch.ping().result(timeout=3))     # → {'pong': True, 'port': 9878}
print(ch.get_session_info().result(timeout=3))
ch.set_device_param(0, 0, "Volume", 0.7).result()
ch.stop()
```

### Process priority

When the channel starts it lowers the Python process priority (BELOW_NORMAL on
Windows, `nice +10` elsewhere) so Live's UI thread stays responsive under load.
Disable by passing `lower_priority=False` to `LiveChannel(...)`.

### Troubleshoot

- **`ConnectionRefusedError` / `commands_dropped` climbing**: Live isn't running,
  the Remote Script isn't selected in Preferences, or the script crashed.
  Check Live's Log.txt (`Help → Open Log Folder`).
- **Port collision**: If port 9878 is already bound, edit `DEFAULT_PORT` in both
  `thelmic/live_remote_script/__init__.py` (in Live's scripts dir) and
  `thelmic/live_channel.py`.
- **Status surface**: `LiveChannel(...).status().as_dict()` returns
  `{enabled, connected, priority_depth, last_error, commands_sent,
  commands_dropped, commands_failed}`.
- **Verify isolation**: with `LIVE_CHANNEL_ENABLED` unset, the sequencer runs
  identically — `ch.ping()` returns a future that fails with
  `RuntimeError("LiveChannel disabled")`, no socket activity.

