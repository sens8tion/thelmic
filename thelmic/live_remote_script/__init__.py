# ThelmicLive Remote Script for Ableton Live
#
# Derived from ahujasid/ableton-mcp (MIT, Copyright (c) 2025 Siddharth Ahuja).
# Upstream: https://github.com/ahujasid/ableton-mcp
# Modifications: device-parameter read/write, delete_device, ping; namespaced
# class + port to coexist with upstream.
#
# This file is meant to be installed into Ableton's MIDI Remote Scripts
# directory. Live discovers it as a folder named "ThelmicLive" containing
# this __init__.py. See README for install steps.
from __future__ import absolute_import, print_function, unicode_literals

from _Framework.ControlSurface import ControlSurface
import socket
import json
import threading
import time
import traceback

try:
    import Queue as queue
except ImportError:
    import queue

DEFAULT_PORT = 9878  # one above upstream (9877) so both can run side-by-side
HOST = "localhost"


def create_instance(c_instance):
    return ThelmicLive(c_instance)


# Commands that mutate / read live state and must be scheduled on UI thread.
_UI_THREAD_COMMANDS = {
    "set_tempo",
    "fire_clip",
    "stop_clip",
    "start_playback",
    "stop_playback",
    "load_browser_item",
    "create_midi_track",
    "set_track_name",
    # thelmic extensions
    "get_device_info",
    "set_device_param",
    "get_device_param",
    "delete_device",
    "move_device",
    "set_track_volume",
    "set_track_pan",
    "set_track_mute",
    "set_track_solo",
    "set_send",
    "get_return_tracks",
    "get_master_track",
    "define_rack_macro",
    "get_rack_macros",
    "set_macro_value",
    "snapshot_track",
    "restore_track",
    "get_browser_tree",
    "get_browser_items_at_path",
}


class ThelmicLive(ControlSurface):
    def __init__(self, c_instance):
        ControlSurface.__init__(self, c_instance)
        self.log_message("ThelmicLive initializing on port " + str(DEFAULT_PORT))
        self.server = None
        self.client_threads = []
        self.server_thread = None
        self.running = False
        self._song = self.song()
        self._start_server()
        self.show_message("ThelmicLive listening on " + str(DEFAULT_PORT))

    def disconnect(self):
        self.running = False
        if self.server:
            try:
                self.server.close()
            except Exception:
                pass
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(1.0)
        ControlSurface.disconnect(self)

    def _start_server(self):
        try:
            self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server.bind((HOST, DEFAULT_PORT))
            self.server.listen(5)
            self.running = True
            self.server_thread = threading.Thread(target=self._server_loop)
            self.server_thread.daemon = True
            self.server_thread.start()
        except Exception as e:
            self.log_message("ThelmicLive server start error: " + str(e))
            self.show_message("ThelmicLive: server start failed - " + str(e))

    def _server_loop(self):
        self.server.settimeout(1.0)
        while self.running:
            try:
                client, _ = self.server.accept()
                t = threading.Thread(target=self._handle_client, args=(client,))
                t.daemon = True
                t.start()
                self.client_threads.append(t)
                self.client_threads = [x for x in self.client_threads if x.is_alive()]
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    self.log_message("accept error: " + str(e))
                time.sleep(0.5)

    def _handle_client(self, client):
        client.settimeout(None)
        buffer = ""
        try:
            while self.running:
                data = client.recv(8192)
                if not data:
                    break
                try:
                    buffer += data.decode("utf-8")
                except AttributeError:
                    buffer += data
                # framing: try to parse; if incomplete, recv more
                try:
                    command = json.loads(buffer)
                    buffer = ""
                except ValueError:
                    continue
                response = self._process(command)
                payload = json.dumps(response)
                try:
                    client.sendall(payload.encode("utf-8"))
                except AttributeError:
                    client.sendall(payload)
        except Exception as e:
            self.log_message("client handler error: " + str(e))
            self.log_message(traceback.format_exc())
        finally:
            try:
                client.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def _process(self, command):
        cmd_type = command.get("type", "")
        params = command.get("params", {}) or {}
        request_id = command.get("request_id")
        response = {"status": "success", "result": {}}
        if request_id is not None:
            response["request_id"] = request_id

        try:
            if cmd_type == "ping":
                response["result"] = {"pong": True, "port": DEFAULT_PORT}
            elif cmd_type == "get_session_info":
                response["result"] = self._get_session_info()
            elif cmd_type == "get_track_info":
                response["result"] = self._get_track_info(params.get("track_index", 0))
            elif cmd_type in _UI_THREAD_COMMANDS:
                response = self._dispatch_ui_thread(cmd_type, params, response)
            else:
                response["status"] = "error"
                response["message"] = "Unknown command: " + cmd_type
        except Exception as e:
            self.log_message("error processing " + cmd_type + ": " + str(e))
            self.log_message(traceback.format_exc())
            response["status"] = "error"
            response["message"] = str(e)
        return response

    def _dispatch_ui_thread(self, cmd_type, params, response):
        rq = queue.Queue()

        def task():
            try:
                result = self._run_ui_command(cmd_type, params)
                rq.put({"status": "success", "result": result})
            except Exception as e:
                self.log_message("ui task error: " + str(e))
                self.log_message(traceback.format_exc())
                rq.put({"status": "error", "message": str(e)})

        try:
            self.schedule_message(0, task)
        except AssertionError:
            task()

        try:
            r = rq.get(timeout=10.0)
        except queue.Empty:
            response["status"] = "error"
            response["message"] = "Timeout waiting for UI thread"
            return response
        if r.get("status") == "error":
            response["status"] = "error"
            response["message"] = r.get("message", "unknown")
        else:
            response["result"] = r.get("result", {})
        return response

    def _run_ui_command(self, cmd_type, params):
        if cmd_type == "set_tempo":
            return self._set_tempo(params.get("tempo", 120.0))
        if cmd_type == "fire_clip":
            return self._fire_clip(params["track_index"], params["clip_index"])
        if cmd_type == "stop_clip":
            return self._stop_clip(params["track_index"], params["clip_index"])
        if cmd_type == "start_playback":
            self._song.start_playing()
            return {"playing": self._song.is_playing}
        if cmd_type == "stop_playback":
            self._song.stop_playing()
            return {"playing": self._song.is_playing}
        if cmd_type == "load_browser_item":
            return self._load_browser_item(params["track_index"], params["item_uri"])
        if cmd_type == "create_midi_track":
            return self._create_midi_track(params.get("index", -1))
        if cmd_type == "set_track_name":
            return self._set_track_name(params["track_index"], params["name"])
        if cmd_type == "get_device_info":
            return self._get_device_info(params["track_index"], params["device_index"])
        if cmd_type == "set_device_param":
            return self._set_device_param(
                params["track_index"],
                params["device_index"],
                params.get("param_index"),
                params.get("param_name"),
                params["value"],
            )
        if cmd_type == "get_device_param":
            return self._get_device_param(
                params["track_index"],
                params["device_index"],
                params.get("param_index"),
                params.get("param_name"),
            )
        if cmd_type == "delete_device":
            return self._delete_device(params["track_index"], params["device_index"])
        if cmd_type == "move_device":
            return self._move_device(
                params["track_index"], params["from_index"], params["to_index"]
            )
        if cmd_type == "set_track_volume":
            return self._set_mixer(params["track_index"], "volume", params["value"])
        if cmd_type == "set_track_pan":
            return self._set_mixer(params["track_index"], "panning", params["value"])
        if cmd_type == "set_track_mute":
            return self._set_track_flag(params["track_index"], "mute", params["value"])
        if cmd_type == "set_track_solo":
            return self._set_track_flag(params["track_index"], "solo", params["value"])
        if cmd_type == "set_send":
            return self._set_send(
                params["track_index"], params["send_index"], params["value"]
            )
        if cmd_type == "get_return_tracks":
            return self._get_return_tracks()
        if cmd_type == "get_master_track":
            return self._get_master_track()
        if cmd_type == "define_rack_macro":
            return self._define_rack_macro(
                params["track_index"],
                params["device_index"],
                params["macro_index"],
                params.get("name"),
                params.get("mappings", []),
            )
        if cmd_type == "get_rack_macros":
            return self._get_rack_macros(params["track_index"], params["device_index"])
        if cmd_type == "set_macro_value":
            return self._set_macro_value(
                params["track_index"],
                params["device_index"],
                params["macro_index"],
                params["value"],
            )
        if cmd_type == "snapshot_track":
            return self._snapshot_track(params["track_index"])
        if cmd_type == "restore_track":
            return self._restore_track(params["track_index"], params["snapshot"])
        if cmd_type == "get_browser_tree":
            return self._get_browser_tree(params.get("category", "all"))
        if cmd_type == "get_browser_items_at_path":
            return self._get_browser_items_at_path(params["path"])
        raise ValueError("unhandled UI command: " + cmd_type)

    # ------------------------------------------------------------------
    # Live API helpers
    # ------------------------------------------------------------------

    def _track(self, track_index):
        if track_index < 0 or track_index >= len(self._song.tracks):
            raise IndexError("Track index out of range: " + str(track_index))
        return self._song.tracks[track_index]

    def _device(self, track_index, device_index):
        track = self._track(track_index)
        if device_index < 0 or device_index >= len(track.devices):
            raise IndexError("Device index out of range: " + str(device_index))
        return track.devices[device_index]

    def _resolve_param(self, device, param_index, param_name):
        params = list(device.parameters)
        if param_index is not None:
            if param_index < 0 or param_index >= len(params):
                raise IndexError("Param index out of range: " + str(param_index))
            return params[param_index], param_index
        if param_name is None:
            raise ValueError("Must supply param_index or param_name")
        # exact match first, then case-insensitive
        for i, p in enumerate(params):
            if p.name == param_name:
                return p, i
        for i, p in enumerate(params):
            if p.name.lower() == param_name.lower():
                return p, i
        raise ValueError("Unknown parameter '" + param_name + "' on " + device.name)

    def _get_session_info(self):
        return {
            "tempo": self._song.tempo,
            "signature_numerator": self._song.signature_numerator,
            "signature_denominator": self._song.signature_denominator,
            "track_count": len(self._song.tracks),
            "return_track_count": len(self._song.return_tracks),
        }

    def _get_track_info(self, track_index):
        track = self._track(track_index)
        devices = []
        for i, d in enumerate(track.devices):
            devices.append({"index": i, "name": d.name, "class_name": d.class_name})
        return {
            "index": track_index,
            "name": track.name,
            "is_midi_track": track.has_midi_input,
            "device_count": len(track.devices),
            "devices": devices,
        }

    def _create_midi_track(self, index):
        self._song.create_midi_track(index)
        new_idx = len(self._song.tracks) - 1 if index == -1 else index
        return {"index": new_idx, "name": self._song.tracks[new_idx].name}

    def _set_track_name(self, track_index, name):
        t = self._track(track_index)
        t.name = name
        return {"name": t.name}

    def _set_tempo(self, tempo):
        self._song.tempo = tempo
        return {"tempo": self._song.tempo}

    def _fire_clip(self, track_index, clip_index):
        track = self._track(track_index)
        if clip_index < 0 or clip_index >= len(track.clip_slots):
            raise IndexError("Clip index out of range")
        slot = track.clip_slots[clip_index]
        if not slot.has_clip:
            raise ValueError("No clip in slot")
        slot.fire()
        return {"fired": True}

    def _stop_clip(self, track_index, clip_index):
        track = self._track(track_index)
        if clip_index < 0 or clip_index >= len(track.clip_slots):
            raise IndexError("Clip index out of range")
        track.clip_slots[clip_index].stop()
        return {"stopped": True}

    def _load_browser_item(self, track_index, item_uri):
        track = self._track(track_index)
        app = self.application()
        item = self._find_browser_item_by_uri(app.browser, item_uri)
        if not item:
            raise ValueError("Browser item not found: " + item_uri)
        self._song.view.selected_track = track
        app.browser.load_item(item)
        return {"loaded": True, "item_name": item.name, "track_name": track.name}

    def _find_browser_item_by_uri(self, node, uri, depth=0, max_depth=10):
        if hasattr(node, "uri") and node.uri == uri:
            return node
        if depth >= max_depth:
            return None
        if hasattr(node, "instruments"):
            for cat in (
                node.instruments,
                node.sounds,
                node.drums,
                node.audio_effects,
                node.midi_effects,
            ):
                hit = self._find_browser_item_by_uri(cat, uri, depth + 1, max_depth)
                if hit:
                    return hit
            return None
        if hasattr(node, "children") and node.children:
            for c in node.children:
                hit = self._find_browser_item_by_uri(c, uri, depth + 1, max_depth)
                if hit:
                    return hit
        return None

    # ---- thelmic extensions -----------------------------------------

    def _get_device_info(self, track_index, device_index):
        device = self._device(track_index, device_index)
        params = []
        for i, p in enumerate(device.parameters):
            params.append({
                "index": i,
                "name": p.name,
                "value": p.value,
                "min": p.min,
                "max": p.max,
                "is_quantized": p.is_quantized,
            })
        return {
            "track_index": track_index,
            "device_index": device_index,
            "name": device.name,
            "class_name": device.class_name,
            "parameter_count": len(params),
            "parameters": params,
        }

    def _set_device_param(self, track_index, device_index, param_index, param_name, value):
        device = self._device(track_index, device_index)
        param, idx = self._resolve_param(device, param_index, param_name)
        # Clamp to declared range; Live raises on out-of-range writes.
        v = float(value)
        if v < param.min:
            v = param.min
        elif v > param.max:
            v = param.max
        param.value = v
        return {
            "track_index": track_index,
            "device_index": device_index,
            "param_index": idx,
            "param_name": param.name,
            "value": param.value,
        }

    def _get_device_param(self, track_index, device_index, param_index, param_name):
        device = self._device(track_index, device_index)
        param, idx = self._resolve_param(device, param_index, param_name)
        return {
            "track_index": track_index,
            "device_index": device_index,
            "param_index": idx,
            "param_name": param.name,
            "value": param.value,
            "min": param.min,
            "max": param.max,
        }

    def _delete_device(self, track_index, device_index):
        track = self._track(track_index)
        if device_index < 0 or device_index >= len(track.devices):
            raise IndexError("Device index out of range")
        track.delete_device(device_index)
        return {"deleted": True, "track_index": track_index, "device_index": device_index}

    def _move_device(self, track_index, from_index, to_index):
        track = self._track(track_index)
        n = len(track.devices)
        if from_index < 0 or from_index >= n:
            raise IndexError("from_index out of range")
        if to_index < 0 or to_index >= n:
            raise IndexError("to_index out of range")
        # Live API: Track.move_device(insert_index, device_index)
        # Using the wider Live.Song.move_device path through track for safety.
        track.move_device(from_index, to_index)
        return {"moved": True, "from_index": from_index, "to_index": to_index}

    # ---- mixer ------------------------------------------------------

    def _set_mixer(self, track_index, attr, value):
        track = self._track(track_index)
        param = getattr(track.mixer_device, attr)
        v = float(value)
        if v < param.min:
            v = param.min
        elif v > param.max:
            v = param.max
        param.value = v
        return {"track_index": track_index, "attr": attr, "value": param.value}

    def _set_track_flag(self, track_index, attr, value):
        track = self._track(track_index)
        setattr(track, attr, bool(value))
        return {"track_index": track_index, "attr": attr, "value": getattr(track, attr)}

    def _set_send(self, track_index, send_index, value):
        track = self._track(track_index)
        sends = list(track.mixer_device.sends)
        if send_index < 0 or send_index >= len(sends):
            raise IndexError("send_index out of range")
        param = sends[send_index]
        v = float(value)
        if v < param.min:
            v = param.min
        elif v > param.max:
            v = param.max
        param.value = v
        return {"track_index": track_index, "send_index": send_index, "value": param.value}

    def _get_return_tracks(self):
        out = []
        for i, t in enumerate(self._song.return_tracks):
            out.append({
                "index": i,
                "name": t.name,
                "volume": t.mixer_device.volume.value,
                "panning": t.mixer_device.panning.value,
                "device_count": len(t.devices),
            })
        return {"return_tracks": out}

    def _get_master_track(self):
        m = self._song.master_track
        return {
            "name": m.name,
            "volume": m.mixer_device.volume.value,
            "panning": m.mixer_device.panning.value,
            "device_count": len(m.devices),
        }

    # ---- rack macros ------------------------------------------------

    def _ensure_rack(self, track_index, device_index):
        device = self._device(track_index, device_index)
        if not getattr(device, "can_have_chains", False):
            raise ValueError("Device is not a rack: " + device.name)
        return device

    def _get_rack_macros(self, track_index, device_index):
        rack = self._ensure_rack(track_index, device_index)
        # Macros 1..16 live as rack.parameters (param 0 = Device On).
        macros = []
        for i in range(1, len(rack.parameters)):
            p = rack.parameters[i]
            if not p.name.startswith("Macro"):
                # Stop at non-Macro params (e.g. "Chain Selector" comes after).
                continue
            macros.append({
                "macro_index": i - 1,
                "name": p.name,
                "value": p.value,
                "min": p.min,
                "max": p.max,
            })
        return {"track_index": track_index, "device_index": device_index, "macros": macros}

    def _macro_param(self, rack, macro_index):
        # macro_index 0..15 -> rack.parameters[macro_index + 1]
        idx = macro_index + 1
        if idx < 1 or idx >= len(rack.parameters):
            raise IndexError("macro_index out of range: " + str(macro_index))
        p = rack.parameters[idx]
        if not p.name.startswith("Macro"):
            raise ValueError("Parameter at slot " + str(idx) + " is not a Macro")
        return p

    def _set_macro_value(self, track_index, device_index, macro_index, value):
        rack = self._ensure_rack(track_index, device_index)
        p = self._macro_param(rack, macro_index)
        v = float(value)
        if v < p.min:
            v = p.min
        elif v > p.max:
            v = p.max
        p.value = v
        return {
            "track_index": track_index,
            "device_index": device_index,
            "macro_index": macro_index,
            "value": p.value,
        }

    def _define_rack_macro(self, track_index, device_index, macro_index, name, mappings):
        """Best-effort macro definition.

        Live's API does not expose programmatic macro mapping (mappings are
        edited in the rack UI's Map mode). What we CAN do safely from the
        Remote Script is rename the macro and seed its initial value. The
        `mappings` payload is acknowledged and returned for client-side
        record-keeping (Patch JSON), but actual parameter targeting must be
        done by the user in Map mode, OR by setting the underlying
        parameters directly via set_device_param. This is documented behaviour
        for the MVP; revisit if Live exposes a mapping API later.
        """
        rack = self._ensure_rack(track_index, device_index)
        p = self._macro_param(rack, macro_index)
        if name:
            p.name = name
        return {
            "track_index": track_index,
            "device_index": device_index,
            "macro_index": macro_index,
            "name": p.name,
            "mappings_recorded": len(mappings or []),
            "note": "macro renamed; programmatic mapping not exposed by Live API",
        }

    # ---- snapshots --------------------------------------------------

    def _snapshot_track(self, track_index):
        """Capture parameter values for every device on the track, plus mixer.

        Output is opaque-ish JSON suitable for restore_track. We do NOT capture
        chain shape here — restore is parameter-only. If devices were added or
        removed between snapshot and restore, restore will skip the diff and
        only re-apply parameters by (device_index, param_index) where they
        still exist.
        """
        track = self._track(track_index)
        devices = []
        for di, dev in enumerate(track.devices):
            params = []
            for pi, p in enumerate(dev.parameters):
                params.append({"i": pi, "n": p.name, "v": p.value})
            devices.append({
                "index": di,
                "name": dev.name,
                "class_name": dev.class_name,
                "params": params,
            })
        snap = {
            "track_index": track_index,
            "name": track.name,
            "mixer": {
                "volume": track.mixer_device.volume.value,
                "panning": track.mixer_device.panning.value,
                "mute": track.mute,
            },
            "devices": devices,
        }
        return snap

    def _restore_track(self, track_index, snapshot):
        track = self._track(track_index)
        applied = 0
        skipped = 0
        # mixer
        try:
            mx = snapshot.get("mixer", {})
            if "volume" in mx:
                track.mixer_device.volume.value = float(mx["volume"])
            if "panning" in mx:
                track.mixer_device.panning.value = float(mx["panning"])
            if "mute" in mx:
                track.mute = bool(mx["mute"])
        except Exception as e:
            self.log_message("restore mixer skipped: " + str(e))
        for d in snapshot.get("devices", []):
            di = d.get("index")
            if di is None or di < 0 or di >= len(track.devices):
                skipped += len(d.get("params", []))
                continue
            dev = track.devices[di]
            if dev.class_name != d.get("class_name"):
                skipped += len(d.get("params", []))
                continue
            for ent in d.get("params", []):
                pi = ent.get("i")
                if pi is None or pi < 0 or pi >= len(dev.parameters):
                    skipped += 1
                    continue
                try:
                    p = dev.parameters[pi]
                    v = float(ent.get("v"))
                    if v < p.min:
                        v = p.min
                    elif v > p.max:
                        v = p.max
                    p.value = v
                    applied += 1
                except Exception:
                    skipped += 1
        return {"track_index": track_index, "applied": applied, "skipped": skipped}

    # ---- browser ----------------------------------------------------

    def _browser(self):
        app = self.application()
        if not app or not getattr(app, "browser", None):
            raise RuntimeError("Live browser not available")
        return app.browser

    def _get_browser_tree(self, category):
        b = self._browser()
        # Shallow tree: top-level categories + their immediate children's names/uris.
        roots = {
            "instruments": getattr(b, "instruments", None),
            "sounds": getattr(b, "sounds", None),
            "drums": getattr(b, "drums", None),
            "audio_effects": getattr(b, "audio_effects", None),
            "midi_effects": getattr(b, "midi_effects", None),
        }
        categories = []
        wanted = list(roots.keys()) if category == "all" else [category]
        for cat_name in wanted:
            node = roots.get(cat_name)
            if node is None:
                continue
            children = []
            try:
                for c in node.children:
                    children.append({
                        "name": getattr(c, "name", "?"),
                        "uri": getattr(c, "uri", None),
                        "is_folder": bool(getattr(c, "children", None)),
                        "is_loadable": bool(getattr(c, "is_loadable", False)),
                    })
            except Exception:
                pass
            categories.append({"name": cat_name, "children": children})
        return {"categories": categories}

    def _get_browser_items_at_path(self, path):
        b = self._browser()
        parts = [p for p in path.split("/") if p]
        if not parts:
            raise ValueError("empty path")
        roots = {
            "instruments": getattr(b, "instruments", None),
            "sounds": getattr(b, "sounds", None),
            "drums": getattr(b, "drums", None),
            "audio_effects": getattr(b, "audio_effects", None),
            "midi_effects": getattr(b, "midi_effects", None),
        }
        head = parts[0].lower()
        cur = roots.get(head)
        if cur is None:
            raise ValueError("unknown root category: " + parts[0])
        for p in parts[1:]:
            children = list(getattr(cur, "children", []) or [])
            nxt = None
            for c in children:
                if getattr(c, "name", "").lower() == p.lower():
                    nxt = c
                    break
            if nxt is None:
                raise ValueError("path part not found: " + p)
            cur = nxt
        items = []
        for c in getattr(cur, "children", []) or []:
            items.append({
                "name": getattr(c, "name", "?"),
                "uri": getattr(c, "uri", None),
                "is_folder": bool(getattr(c, "children", None)),
                "is_loadable": bool(getattr(c, "is_loadable", False)),
            })
        return {
            "path": path,
            "name": getattr(cur, "name", "?"),
            "uri": getattr(cur, "uri", None),
            "items": items,
        }
