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
