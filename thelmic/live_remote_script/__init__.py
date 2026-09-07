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
    "create_clip",
    "add_notes_to_clip",
    "set_clip_name",
    "clear_clip",
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
    "get_sample_info",
    "set_sample_property",
    "set_sample_slices",
    "set_device_sidechain_source",
    "set_device_sidechain_channel",
    "get_device_routing_options",
    "fire_scene",
    "set_scene_tempo",
    "get_scene_tempo",
    "stop_all_clips",
    "set_track_output_routing",
    "get_track_output_options",
    "create_audio_track",
    "set_track_monitoring",
    "set_track_arm",
    "set_clip_envelope",
    "clear_clip_envelope",
    "set_launch_quantization",
    "get_track_meter",
    "get_all_meters",
    "list_browser_roots",
    "load_item_at_path",
    "set_clip_loop",
    "fire_clip_at_beat",
    "set_clip_loop_region",
    "set_clip_warp",
    "delete_track",
    "get_arrangement_loop",
    "set_arrangement_loop",
    "get_drum_pads",
    "set_drum_pad_mute",
    "set_drum_pad_volume",
    "load_master_device",
    "get_master_device_info",
    "set_master_device_param",
    "get_master_device_param",
    "delete_master_device",
    "duplicate_clip",
    "bulk_load_drum_pads",
    "set_clip_reverse",
    "set_clip_pitch",
    "set_clip_gain",
    "set_clip_fades",
    "get_clip_props",
    "clear_arrangement_clips",
    "inspect_clip_envelopes",
    "re_enable_automation",
    "get_device_property",
    "create_scene",
    "delete_scene",
    "get_scene_count",
    "get_drum_pad_chain_info",
    "set_drum_pad_chain_audio_output",
    "set_drum_pad_chain_send",
    "set_drum_pad_chain_volume",
    "load_into_drum_pad_chain",
    "load_sample_to_pad",
    "set_selected_clip_slot",
    "set_device_property",
    "load_audio_to_slot",
    "set_session_record",
    "get_song_time",
    "set_song_time",
    "back_to_arrangement",
    "set_record_mode",
    "set_metronome",
    "set_overdub",
    "set_clip_mixer_envelope",
    "get_track_clips",
    "set_track_color",
    "move_track",
    "get_track_input_options",
    "set_track_input_routing",
    "freeze_track",
    "flatten_track",
    "duplicate_track",
    # New: per-clip MIDI note manipulation, follow actions, view, grooves,
    # capture, listener snapshot.
    "get_clip_notes",
    "remove_clip_notes",
    "set_clip_follow_action",
    "get_clip_follow_action",
    "select_track",
    "select_scene",
    "show_view",
    "capture_midi",
    "get_grooves",
    "set_clip_groove",
    "clear_clip_groove",
    "get_listener_snapshot",
    "set_drum_pad_chain_device_property",
    "set_drum_pad_chain_device_param",
    "get_drum_pad_chain_device_info",
    # Scene/clip color + scene name (visual shading of rows)
    "set_scene_color",
    "set_scene_name",
    "set_clip_color",
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
        if cmd_type == "create_clip":
            return self._create_clip(
                params["track_index"], params["clip_index"], params.get("length", 4.0)
            )
        if cmd_type == "add_notes_to_clip":
            return self._add_notes_to_clip(
                params["track_index"], params["clip_index"], params["notes"], params.get("replace", False)
            )
        if cmd_type == "set_clip_name":
            return self._set_clip_name(params["track_index"], params["clip_index"], params["name"])
        if cmd_type == "clear_clip":
            return self._clear_clip(params["track_index"], params["clip_index"])
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
        if cmd_type == "set_device_sidechain_source":
            return self._set_device_sidechain_source(
                params["track_index"],
                params["device_index"],
                params["source_track_index"],
            )
        if cmd_type == "set_device_sidechain_channel":
            return self._set_device_sidechain_channel(
                params["track_index"],
                params["device_index"],
                params["channel"],
            )
        if cmd_type == "get_device_routing_options":
            return self._get_device_routing_options(
                params["track_index"], params["device_index"]
            )
        if cmd_type == "fire_scene":
            return self._fire_scene(params["scene_index"])
        if cmd_type == "set_scene_tempo":
            return self._set_scene_tempo(
                params["scene_index"], params["tempo"]
            )
        if cmd_type == "get_scene_tempo":
            return self._get_scene_tempo(params["scene_index"])
        if cmd_type == "stop_all_clips":
            return self._stop_all_clips()
        if cmd_type == "set_track_output_routing":
            return self._set_track_output_routing(
                params["track_index"], params["target_name"]
            )
        if cmd_type == "get_track_output_options":
            return self._get_track_output_options(params["track_index"])
        if cmd_type == "create_audio_track":
            return self._create_audio_track(params.get("index", -1))
        if cmd_type == "set_track_monitoring":
            return self._set_track_monitoring(params["track_index"], params["state"])
        if cmd_type == "set_track_arm":
            return self._set_track_flag(params["track_index"], "arm", params["value"])
        if cmd_type == "set_clip_envelope":
            return self._set_clip_envelope(
                params["clip_track"], params["clip_index"],
                params["target_track"], params["target_device"], params["target_param"],
                params["breakpoints"],
            )
        if cmd_type == "clear_clip_envelope":
            return self._clear_clip_envelope(
                params["clip_track"], params["clip_index"],
                params["target_track"], params["target_device"], params["target_param"],
            )
        if cmd_type == "set_launch_quantization":
            return self._set_launch_quantization(params["bars"])
        if cmd_type == "get_track_meter":
            return self._get_track_meter(params["track_index"])
        if cmd_type == "get_all_meters":
            return self._get_all_meters()
        if cmd_type == "list_browser_roots":
            return self._list_browser_roots()
        if cmd_type == "load_item_at_path":
            return self._load_item_at_path(
                params["track_index"], params["path"], params.get("item_name"),
                params.get("drum_pad_note"), params.get("drum_device_index"),
            )
        if cmd_type == "set_clip_loop":
            return self._set_clip_loop(
                params["track_index"], params["clip_index"], params["loop"],
            )
        if cmd_type == "set_clip_loop_region":
            return self._set_clip_loop_region(
                params["track_index"], params["clip_index"],
                params["loop_start"], params["loop_end"],
            )
        if cmd_type == "set_clip_warp":
            return self._set_clip_warp(
                params["track_index"], params["clip_index"],
                params.get("warping"), params.get("warp_mode"),
            )
        if cmd_type == "delete_track":
            return self._delete_track(params["track_index"])
        if cmd_type == "get_arrangement_loop":
            return self._get_arrangement_loop()
        if cmd_type == "set_arrangement_loop":
            return self._set_arrangement_loop(
                params.get("start"), params.get("length"), params.get("on"),
            )
        if cmd_type == "get_drum_pads":
            return self._get_drum_pads(params["track_index"], params["device_index"])
        if cmd_type == "set_drum_pad_mute":
            return self._set_drum_pad_mute(
                params["track_index"], params["device_index"], params["note"], params["mute"],
            )
        if cmd_type == "set_drum_pad_volume":
            return self._set_drum_pad_volume(
                params["track_index"], params["device_index"], params["note"], params["value"],
            )
        if cmd_type == "load_master_device":
            return self._load_master_device(params.get("uri"), params.get("path"), params.get("item_name"))
        if cmd_type == "get_master_device_info":
            return self._get_master_device_info(params["device_index"])
        if cmd_type == "set_master_device_param":
            return self._set_master_device_param(
                params["device_index"], params.get("param_index"),
                params.get("param_name"), params["value"],
            )
        if cmd_type == "get_master_device_param":
            return self._get_master_device_param(
                params["device_index"], params.get("param_index"), params.get("param_name"),
            )
        if cmd_type == "delete_master_device":
            return self._delete_master_device(params["device_index"])
        if cmd_type == "duplicate_clip":
            return self._duplicate_clip(
                params["track_index"], params["src_slot"], params["dst_slot"],
            )
        if cmd_type == "bulk_load_drum_pads":
            return self._bulk_load_drum_pads(
                params["track_index"], params["device_index"],
                params["browser_path"], params["items"],
            )
        if cmd_type == "set_clip_reverse":
            return self._set_clip_reverse(
                params["track_index"], params["clip_index"], params["reverse"],
            )
        if cmd_type == "set_clip_pitch":
            return self._set_clip_pitch(
                params["track_index"], params["clip_index"],
                params.get("coarse"), params.get("fine"),
            )
        if cmd_type == "set_clip_gain":
            return self._set_clip_gain(
                params["track_index"], params["clip_index"], params["gain"],
            )
        if cmd_type == "set_clip_fades":
            return self._set_clip_fades(
                params["track_index"], params["clip_index"],
                params.get("fade_in"), params.get("fade_out"),
            )
        if cmd_type == "get_clip_props":
            return self._get_clip_props(params["track_index"], params["clip_index"])
        if cmd_type == "inspect_clip_envelopes":
            return self._inspect_clip_envelopes(params["track_index"], params["clip_index"])
        if cmd_type == "re_enable_automation":
            try:
                self._song.re_enable_automation()
                return {"re_enabled": True}
            except Exception as e:
                return {"re_enabled": False, "err": str(e)}
        if cmd_type == "get_device_property":
            return self._get_device_property(
                params["track_index"], params["device_index"], params["attr"],
            )
        if cmd_type == "get_sample_info":
            return self._get_sample_info(
                params["track_index"], params["device_index"],
            )
        if cmd_type == "set_sample_property":
            return self._set_sample_property(
                params["track_index"], params["device_index"],
                params["attr"], params["value"],
            )
        if cmd_type == "set_sample_slices":
            return self._set_sample_slices(
                params["track_index"], params["device_index"],
                params.get("times"), params.get("clear", True),
            )
        if cmd_type == "create_scene":
            return self._create_scene(params.get("index", -1))
        if cmd_type == "delete_scene":
            return self._delete_scene(params["scene_index"])
        if cmd_type == "get_scene_count":
            return {"count": len(list(self._song.scenes))}
        if cmd_type == "get_drum_pad_chain_info":
            return self._get_drum_pad_chain_info(
                params["track_index"], params["device_index"], params["note"],
            )
        if cmd_type == "set_drum_pad_chain_audio_output":
            return self._set_drum_pad_chain_audio_output(
                params["track_index"], params["device_index"], params["note"],
                params["target_name"],
            )
        if cmd_type == "set_drum_pad_chain_send":
            return self._set_drum_pad_chain_send(
                params["track_index"], params["device_index"], params["note"],
                params["send_index"], params["value"],
            )
        if cmd_type == "set_drum_pad_chain_volume":
            return self._set_drum_pad_chain_volume(
                params["track_index"], params["device_index"], params["note"], params["value"],
            )
        if cmd_type == "load_into_drum_pad_chain":
            return self._load_into_drum_pad_chain(
                params["track_index"], params["device_index"], params["note"],
                params.get("uri"), params.get("path"), params.get("item_name"),
            )
        if cmd_type == "set_drum_pad_chain_device_property":
            return self._set_drum_pad_chain_device_property(
                params["track_index"], params["device_index"], params["note"],
                params.get("chain_device_index", 0),
                params["property_name"], params["value"],
            )
        if cmd_type == "set_drum_pad_chain_device_param":
            return self._set_drum_pad_chain_device_param(
                params["track_index"], params["device_index"], params["note"],
                params.get("chain_device_index", 0),
                params.get("param_index"), params.get("param_name"),
                params["value"],
            )
        if cmd_type == "get_drum_pad_chain_device_info":
            return self._get_drum_pad_chain_device_info(
                params["track_index"], params["device_index"], params["note"],
                params.get("chain_device_index", 0),
            )
        if cmd_type == "load_sample_to_pad":
            return self._load_sample_to_pad(
                params["track_index"], params["device_index"], params["note"],
                params.get("path"), params.get("item_name"),
            )
        if cmd_type == "set_selected_clip_slot":
            return self._set_selected_clip_slot(params["track_index"], params["slot"])
        if cmd_type == "set_device_property":
            return self._set_device_property(
                params["track_index"], params["device_index"],
                params["attr"], params["value"],
            )
        if cmd_type == "load_audio_to_slot":
            return self._load_audio_to_slot(
                params["track_index"], params["slot"],
                params.get("path"), params.get("item_name"),
            )
        if cmd_type == "set_session_record":
            self._song.session_record = bool(params["on"])
            return {"session_record": self._song.session_record}
        if cmd_type == "get_song_time":
            return {
                "song_time": float(self._song.current_song_time),
                "is_playing": bool(self._song.is_playing),
                "is_arranging": bool(getattr(self._song, "is_counting_in", False)) or bool(self._song.is_playing),
            }
        if cmd_type == "set_song_time":
            self._song.current_song_time = float(params["beat"])
            return {"song_time": self._song.current_song_time}
        if cmd_type == "back_to_arrangement":
            self._song.back_to_arranger = False
            return {"back_to_arranger": False}
        if cmd_type == "set_record_mode":
            self._song.record_mode = bool(params["on"])
            return {"record_mode": self._song.record_mode}
        if cmd_type == "set_metronome":
            self._song.metronome = bool(params["on"])
            return {"metronome": self._song.metronome}
        if cmd_type == "set_overdub":
            self._song.overdub = bool(params["on"])
            return {"overdub": self._song.overdub}
        if cmd_type == "set_clip_mixer_envelope":
            return self._set_clip_mixer_envelope(
                params["clip_track"], params["clip_index"],
                params["target_track"], params["mixer_param"], params["breakpoints"],
            )
        if cmd_type == "get_track_clips":
            return self._get_track_clips(params["track_index"])
        if cmd_type == "set_track_color":
            track = self._track(params["track_index"])
            track.color_index = int(params["color_index"])
            return {"color_index": track.color_index}
        if cmd_type == "set_scene_color":
            scene = self._song.scenes[int(params["scene_index"])]
            scene.color_index = int(params["color_index"])
            return {"scene_index": int(params["scene_index"]),
                    "color_index": scene.color_index}
        if cmd_type == "set_scene_name":
            scene = self._song.scenes[int(params["scene_index"])]
            scene.name = str(params["name"])
            return {"scene_index": int(params["scene_index"]),
                    "name": scene.name}
        if cmd_type == "set_clip_color":
            track = self._track(params["track_index"])
            slot = track.clip_slots[int(params["clip_index"])]
            if not slot.has_clip:
                raise ValueError("No clip in slot")
            slot.clip.color_index = int(params["color_index"])
            return {"track_index": params["track_index"],
                    "clip_index": int(params["clip_index"]),
                    "color_index": slot.clip.color_index}
        if cmd_type == "move_track":
            self._song.move_track(params["track_index"], params["target_position"])
            return {"moved": True}
        if cmd_type == "get_track_input_options":
            return self._get_track_input_options(params["track_index"])
        if cmd_type == "set_track_input_routing":
            return self._set_track_input_routing(params["track_index"], params["target_name"])
        if cmd_type == "freeze_track":
            track = self._track(params["track_index"])
            track.freeze()
            return {"frozen": True}
        if cmd_type == "flatten_track":
            track = self._track(params["track_index"])
            track.flatten()
            return {"flattened": True}
        if cmd_type == "duplicate_track":
            self._song.duplicate_track(params["track_index"])
            return {"duplicated": True, "tracks": len(self._song.tracks)}
        if cmd_type == "get_clip_notes":
            return self._get_clip_notes(
                params["track_index"], params["clip_index"],
                params.get("from_pitch", 0), params.get("pitch_span", 128),
                params.get("from_time", 0.0), params.get("time_span"),
            )
        if cmd_type == "remove_clip_notes":
            return self._remove_clip_notes(
                params["track_index"], params["clip_index"],
                params.get("from_pitch", 0), params.get("pitch_span", 128),
                params.get("from_time", 0.0), params.get("time_span"),
            )
        if cmd_type == "set_clip_follow_action":
            return self._set_clip_follow_action(
                params["track_index"], params["clip_index"],
                params.get("action_a"), params.get("action_b"),
                params.get("chance_a"), params.get("chance_b"),
                params.get("time_beats"), params.get("enabled"),
            )
        if cmd_type == "get_clip_follow_action":
            return self._get_clip_follow_action(
                params["track_index"], params["clip_index"]
            )
        if cmd_type == "select_track":
            return self._select_track(params["track_index"])
        if cmd_type == "select_scene":
            return self._select_scene(params["scene_index"])
        if cmd_type == "show_view":
            return self._show_view(params["view"])
        if cmd_type == "capture_midi":
            try:
                self._song.capture_midi()
                return {"captured": True}
            except Exception as e:
                return {"captured": False, "err": str(e)}
        if cmd_type == "get_grooves":
            return self._get_grooves()
        if cmd_type == "set_clip_groove":
            return self._set_clip_groove(
                params["track_index"], params["clip_index"], params["groove_index"]
            )
        if cmd_type == "clear_clip_groove":
            return self._set_clip_groove(
                params["track_index"], params["clip_index"], -1
            )
        if cmd_type == "get_listener_snapshot":
            return self._get_listener_snapshot()
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
        info = {
            "index": track_index,
            "name": track.name,
            "is_midi_track": track.has_midi_input,
            "device_count": len(track.devices),
            "devices": devices,
        }
        # Mixer state - without this a caller cannot know the "on" value to
        # restore when gating a track's volume, and has to mix blind.
        mixer = getattr(track, "mixer_device", None)
        if mixer is not None:
            for key in ("volume", "panning"):
                try:
                    info[key] = float(getattr(mixer, key).value)
                except Exception:
                    pass
            try:
                info["sends"] = [float(s.value) for s in mixer.sends]
            except Exception:
                pass
        for key in ("mute", "solo", "arm"):
            try:
                info[key] = bool(getattr(track, key))
            except Exception:
                pass
        return info

    def _create_midi_track(self, index):
        self._song.create_midi_track(index)
        new_idx = len(self._song.tracks) - 1 if index == -1 else index
        return {"index": new_idx, "name": self._song.tracks[new_idx].name}

    def _set_track_name(self, track_index, name):
        t = self._track(track_index)
        t.name = name
        return {"name": t.name}

    def _create_clip(self, track_index, clip_index, length):
        track = self._track(track_index)
        if clip_index < 0 or clip_index >= len(track.clip_slots):
            raise IndexError("clip_index out of range")
        slot = track.clip_slots[clip_index]
        if slot.has_clip:
            slot.delete_clip()
        slot.create_clip(float(length))
        return {
            "track_index": track_index,
            "clip_index": clip_index,
            "name": slot.clip.name,
            "length": slot.clip.length,
        }

    def _add_notes_to_clip(self, track_index, clip_index, notes, replace):
        track = self._track(track_index)
        if clip_index < 0 or clip_index >= len(track.clip_slots):
            raise IndexError("clip_index out of range")
        slot = track.clip_slots[clip_index]
        if not slot.has_clip:
            raise ValueError("No clip in slot")
        clip = slot.clip

        # Detect whether any input note carries modern attrs (probability or
        # velocity_deviation). If so, route through Live 11+ add_new_notes
        # which accepts MidiNoteSpecification objects. Otherwise use the
        # legacy 5-tuple set_notes path.
        has_modern = any(
            ("probability" in n and float(n["probability"]) != 1.0)
            or ("velocity_deviation" in n and float(n["velocity_deviation"]) != 0.0)
            for n in notes
        )

        if has_modern:
            try:
                import Live as _Live
                Spec = _Live.Clip.MidiNoteSpecification
                specs = []
                for n in notes:
                    specs.append(Spec(
                        pitch=int(n.get("pitch", 60)),
                        start_time=float(n.get("start_time", 0.0)),
                        duration=float(n.get("duration", 0.25)),
                        velocity=float(n.get("velocity", 100)),
                        mute=bool(n.get("mute", False)),
                        probability=float(n.get("probability", 1.0)),
                        velocity_deviation=float(n.get("velocity_deviation", 0.0)),
                    ))
                if replace:
                    try:
                        clip.remove_notes_extended(0, 128, 0.0, clip.length)
                    except Exception:
                        pass
                clip.add_new_notes(tuple(specs))
                return {"note_count": len(specs), "replaced": replace, "modern": True}
            except Exception as exc:
                # Fall through to legacy path if modern API unavailable
                pass

        live_notes = []
        for n in notes:
            live_notes.append((
                int(n.get("pitch", 60)),
                float(n.get("start_time", 0.0)),
                float(n.get("duration", 0.25)),
                int(n.get("velocity", 100)),
                bool(n.get("mute", False)),
            ))
        if replace:
            try:
                clip.remove_notes_extended(0, 128, 0.0, clip.length)
            except Exception:
                # Older API path
                try:
                    clip.select_all_notes()
                    clip.replace_selected_notes(tuple(live_notes))
                    return {"note_count": len(live_notes), "replaced": True}
                except Exception:
                    pass
        clip.set_notes(tuple(live_notes))
        return {"note_count": len(live_notes), "replaced": replace}

    def _set_clip_name(self, track_index, clip_index, name):
        track = self._track(track_index)
        slot = track.clip_slots[clip_index]
        if not slot.has_clip:
            raise ValueError("No clip in slot")
        slot.clip.name = name
        return {"name": slot.clip.name}

    def _clear_clip(self, track_index, clip_index):
        track = self._track(track_index)
        slot = track.clip_slots[clip_index]
        if slot.has_clip:
            slot.delete_clip()
        return {"cleared": True}

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

    def _find_browser_item_by_uri(self, node, uri, depth=0, max_depth=12):
        if hasattr(node, "uri") and node.uri == uri:
            return node
        if depth >= max_depth:
            return None
        # If this looks like the Browser root, walk EVERY attribute (instruments,
        # sounds, drums, plugins, samples, user_library, etc.).
        if hasattr(node, "instruments") and not hasattr(node, "uri"):
            for attr in dir(node):
                if attr.startswith("_"):
                    continue
                try:
                    val = getattr(node, attr)
                except Exception:
                    continue
                if val is None or callable(val):
                    continue
                if hasattr(val, "uri") or hasattr(val, "children"):
                    hit = self._find_browser_item_by_uri(val, uri, depth + 1, max_depth)
                    if hit:
                        return hit
            return None
        # Recurse into children
        try:
            children = getattr(node, "children", None)
        except Exception:
            children = None
        if children:
            for c in children:
                hit = self._find_browser_item_by_uri(c, uri, depth + 1, max_depth)
                if hit:
                    return hit
        return None

    def _load_item_at_path(self, track_index, path, item_name=None, drum_pad_note=None, drum_device_index=None):
        """Walk path, optionally match item by name, then load_item to track.

        path: e.g. 'user_library/Samples/Splice'. If item_name is given, find
        the child of that name; else load the path's terminal node itself.
        """
        track = self._track(track_index)
        b = self._browser()
        parts = [p for p in path.split("/") if p]
        head = parts[0].lower()
        cur = None
        for attr in dir(b):
            if attr.startswith("_"):
                continue
            if attr.lower() == head:
                try:
                    cur = getattr(b, attr)
                except Exception:
                    cur = None
                break
        if cur is None:
            raise ValueError("unknown root: " + parts[0])
        for p in parts[1:]:
            children = self._browser_children(cur)
            nxt = None
            for c in children:
                if getattr(c, "name", "").lower() == p.lower():
                    nxt = c
                    break
            if nxt is None:
                raise ValueError("path part not found: " + p)
            cur = nxt
        if item_name:
            children = self._browser_children(cur)
            target = None
            for c in children:
                if getattr(c, "name", "").lower() == item_name.lower():
                    target = c
                    break
            if target is None:
                names = [getattr(c, "name", "?") for c in children][:20]
                raise ValueError("item '" + item_name + "' not in " + path + ". Sample: " + ", ".join(names))
            cur = target
        if not getattr(cur, "is_loadable", False):
            raise ValueError("item not loadable: " + getattr(cur, "name", "?"))
        self._song.view.selected_track = track
        # If drum-pad target requested, select the pad first so load goes there
        if drum_pad_note is not None:
            di = drum_device_index if drum_device_index is not None else 0
            if di >= len(track.devices):
                raise ValueError("drum_device_index out of range: " + str(di))
            rack = track.devices[di]
            if not hasattr(rack, "drum_pads"):
                raise ValueError("device " + rack.name + " is not a Drum Rack")
            pad_idx = int(drum_pad_note)
            if pad_idx < 0 or pad_idx > 127:
                raise ValueError("drum_pad_note out of MIDI range")
            # NOTE: do NOT call select_device(rack) — it resets selected_drum_pad.
            self._song.view.selected_track = track
            try:
                self._song.view.selected_drum_pad = rack.drum_pads[pad_idx]
            except Exception as e:
                raise ValueError("could not select drum pad " + str(pad_idx) + ": " + str(e))
        b.load_item(cur)
        return {
            "loaded": True,
            "track_index": track_index,
            "item_name": getattr(cur, "name", "?"),
            "track_name": track.name,
            "drum_pad_note": drum_pad_note,
        }

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
        # Live's API for reordering: Song.move_device(device, dest_track, insert_pos)
        device = track.devices[from_index]
        self._song.move_device(device, track, to_index)
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

    # ---- routing / sidechain ----------------------------------------

    def _device_routing_attrs(self, device):
        """Find which Live API attribute name a device uses for input routing.

        Live 11+ uses audio_input_routing_type; older uses input_routing_type.
        """
        if hasattr(device, "audio_input_routing_type"):
            return ("audio_input_routing_type", "available_audio_input_routing_types",
                    "audio_input_routing_channel", "available_audio_input_routing_channels")
        return ("input_routing_type", "available_input_routing_types",
                "input_routing_channel", "available_input_routing_channels")

    def _get_device_routing_options(self, track_index, device_index):
        device = self._device(track_index, device_index)
        type_attr, type_avail_attr, ch_attr, ch_avail_attr = self._device_routing_attrs(device)
        types = []
        try:
            for rt in getattr(device, type_avail_attr, []) or []:
                types.append(getattr(rt, "display_name", str(rt)))
        except Exception as e:
            self.log_message("routing types err: " + str(e))
        channels = []
        try:
            for rc in getattr(device, ch_avail_attr, []) or []:
                channels.append(getattr(rc, "display_name", str(rc)))
        except Exception as e:
            self.log_message("routing channels err: " + str(e))
        current_type = ""
        try:
            current_type = getattr(getattr(device, type_attr), "display_name", "")
        except Exception:
            pass
        return {
            "track_index": track_index,
            "device_index": device_index,
            "device_name": device.name,
            "available_types": types,
            "available_channels": channels,
            "current_type": current_type,
        }

    def _set_device_sidechain_source(self, track_index, device_index, source_track_index):
        device = self._device(track_index, device_index)
        source_track = self._track(source_track_index)
        type_attr, type_avail_attr, ch_attr, ch_avail_attr = self._device_routing_attrs(device)
        candidates = list(getattr(device, type_avail_attr, []) or [])
        # Match against source track name; fall back to substring match
        target = None
        src_name = source_track.name
        for rt in candidates:
            if getattr(rt, "display_name", "") == src_name:
                target = rt
                break
        if target is None:
            for rt in candidates:
                dn = getattr(rt, "display_name", "")
                if src_name in dn or dn in src_name:
                    target = rt
                    break
        if target is None:
            names = [getattr(rt, "display_name", "?") for rt in candidates]
            raise ValueError(
                "No routing entry matches source '" + src_name + "'. Available: " + ", ".join(names)
            )
        setattr(device, type_attr, target)
        # Also try to enable S/C On if it's a Compressor-style param
        try:
            for p in device.parameters:
                if p.name == "S/C On":
                    p.value = 1.0
                    break
        except Exception:
            pass
        return {
            "track_index": track_index,
            "device_index": device_index,
            "source_track_index": source_track_index,
            "source_name": getattr(target, "display_name", src_name),
        }

    def _set_device_sidechain_channel(self, track_index, device_index, channel):
        """Set the sidechain CHANNEL (Pre FX / Post FX / Post Mixer / etc.).

        Live's LOM exposes `audio_input_routing_channel` separately from
        `audio_input_routing_type` (the source track). The CHANNEL selector
        controls where in the source track's signal path the sidechain
        taps in — Pre FX gets the raw instrument output before any device
        chain, Post FX gets the signal after all devices, Post Mixer
        includes the track fader/pan.

        Pre FX is the right pick for most sidechain pumping because the
        kick's transient envelope is preserved — Post FX of a heavily-
        processed kick (Drum Buss + Saturator + compressor) becomes a
        near-constant signal that pins the comp to the floor.
        """
        device = self._device(track_index, device_index)
        type_attr, type_avail_attr, ch_attr, ch_avail_attr = self._device_routing_attrs(device)
        if not ch_attr:
            raise ValueError("Device has no routing-channel attribute")
        candidates = list(getattr(device, ch_avail_attr, []) or [])
        target = None
        for ch in candidates:
            if getattr(ch, "display_name", "") == channel:
                target = ch
                break
        if target is None:
            # substring fallback (case-insensitive)
            for ch in candidates:
                dn = getattr(ch, "display_name", "")
                if channel.lower() in dn.lower() or dn.lower() in channel.lower():
                    target = ch
                    break
        if target is None:
            names = [getattr(ch, "display_name", "?") for ch in candidates]
            raise ValueError(
                "No routing channel matches '" + str(channel) + "'. "
                "Available: " + ", ".join(names)
            )
        setattr(device, ch_attr, target)
        return {
            "track_index": track_index,
            "device_index": device_index,
            "channel": getattr(target, "display_name", str(channel)),
        }

    # ---- track output routing ---------------------------------------

    def _track_output_attrs(self, track):
        if hasattr(track, "output_routing_type"):
            return ("output_routing_type", "available_output_routing_types",
                    "output_routing_channel", "available_output_routing_channels")
        # very old versions
        return ("current_output_routing", "available_output_routings", None, None)

    def _get_track_output_options(self, track_index):
        track = self._track(track_index)
        type_attr, type_avail_attr, ch_attr, ch_avail_attr = self._track_output_attrs(track)
        types = []
        try:
            for rt in getattr(track, type_avail_attr, []) or []:
                types.append(getattr(rt, "display_name", str(rt)))
        except Exception as e:
            self.log_message("output types err: " + str(e))
        current = ""
        try:
            current = getattr(getattr(track, type_attr), "display_name", "")
        except Exception:
            pass
        return {
            "track_index": track_index,
            "available_types": types,
            "current_type": current,
        }

    def _set_track_output_routing(self, track_index, target_name):
        track = self._track(track_index)
        type_attr, type_avail_attr, ch_attr, ch_avail_attr = self._track_output_attrs(track)
        candidates = list(getattr(track, type_avail_attr, []) or [])
        target = None
        for rt in candidates:
            dn = getattr(rt, "display_name", "")
            if dn == target_name:
                target = rt
                break
        if target is None:
            for rt in candidates:
                dn = getattr(rt, "display_name", "")
                if target_name in dn or dn in target_name:
                    target = rt
                    break
        if target is None:
            names = [getattr(rt, "display_name", "?") for rt in candidates]
            raise ValueError(
                "No output routing matches '" + target_name + "'. Available: " + ", ".join(names)
            )
        setattr(track, type_attr, target)
        return {
            "track_index": track_index,
            "target": getattr(target, "display_name", target_name),
        }

    def _create_audio_track(self, index):
        self._song.create_audio_track(index)
        new_idx = len(self._song.tracks) - 1 if index == -1 else index
        return {"index": new_idx, "name": self._song.tracks[new_idx].name}

    def _resolve_target_param(self, target_track, target_device, target_param):
        device = self._device(target_track, target_device)
        if isinstance(target_param, int):
            return device.parameters[target_param]
        for p in device.parameters:
            if p.name == target_param:
                return p
        for p in device.parameters:
            if p.name.lower() == target_param.lower():
                return p
        raise ValueError("Unknown param '" + target_param + "' on " + device.name)

    def _set_clip_envelope(self, clip_track, clip_index, target_track, target_device, target_param, breakpoints):
        """Write a clip automation envelope.

        breakpoints: list of [time_in_beats, value] pairs.
        Will REPLACE any existing envelope for this parameter on the clip.
        """
        track = self._track(clip_track)
        if clip_index < 0 or clip_index >= len(track.clip_slots):
            raise IndexError("clip_index out of range")
        slot = track.clip_slots[clip_index]
        if not slot.has_clip:
            raise ValueError("No clip in slot")
        clip = slot.clip
        param = self._resolve_target_param(target_track, target_device, target_param)
        # remove any existing envelope first
        try:
            clip.clear_envelope(param)
        except Exception:
            pass
        env = clip.create_automation_envelope(param)
        # Sort breakpoints by time
        bps = sorted([(float(bp[0]), float(bp[1])) for bp in breakpoints], key=lambda x: x[0])
        # Live 12 only exposes insert_step(time, length, value) — flat
        # segments. Use a length that spans until the NEXT breakpoint so
        # consecutive segments tile the timeline. Callers pass densely-
        # spaced breakpoints to approximate a smooth ramp via this
        # staircase. Last breakpoint gets a default 1-beat length.
        n_written = 0
        last_err = None
        for i, (t, v) in enumerate(bps):
            if i + 1 < len(bps):
                length = max(0.001, bps[i + 1][0] - t)
            else:
                length = 1.0   # last step — default 1-beat sustain
            wrote = False
            for fn_name in ("add_breakpoint", "insert_step"):
                fn = getattr(env, fn_name, None)
                if fn is None: continue
                try:
                    if fn_name == "insert_step":
                        fn(t, length, v)
                    else:
                        fn(t, v)
                    n_written += 1
                    wrote = True
                    break
                except Exception as e:
                    last_err = (fn_name, str(e))
            if not wrote and last_err:
                self.log_message("envelope write failed at t=" + str(t)
                                  + " via " + last_err[0] + ": " + last_err[1])
        return {
            "clip_track": clip_track,
            "clip_index": clip_index,
            "target": param.name,
            "breakpoints_written": n_written,
            "fn_attempted": "add_breakpoint preferred",
        }

    def _clear_clip_envelope(self, clip_track, clip_index, target_track, target_device, target_param):
        track = self._track(clip_track)
        slot = track.clip_slots[clip_index]
        if not slot.has_clip:
            raise ValueError("No clip in slot")
        clip = slot.clip
        param = self._resolve_target_param(target_track, target_device, target_param)
        try:
            clip.clear_envelope(param)
        except Exception as e:
            self.log_message("clear envelope failed: " + str(e))
        return {"cleared": True, "target": param.name}

    def _get_track_meter(self, track_index):
        track = self._track(track_index)
        return {
            "track_index": track_index,
            "name": track.name,
            "left":  float(getattr(track, "output_meter_left",  0.0) or 0.0),
            "right": float(getattr(track, "output_meter_right", 0.0) or 0.0),
            "level": float(getattr(track, "output_meter_level", 0.0) or 0.0),
        }

    def _get_all_meters(self):
        out = []
        for i, t in enumerate(self._song.tracks):
            row = {"track_index": i, "name": t.name,
                   "left": 0.0, "right": 0.0, "level": 0.0}
            # A MIDI track with no instrument RAISES on these rather than
            # returning None, so getattr's default is not enough - one bad
            # track must not take down the whole call.
            for key, attr in (("left", "output_meter_left"),
                              ("right", "output_meter_right"),
                              ("level", "output_meter_level")):
                try:
                    row[key] = float(getattr(t, attr, 0.0) or 0.0)
                except Exception:
                    row["no_audio_output"] = True
            out.append(row)
        # also master
        try:
            m = self._song.master_track
            out.append({
                "track_index": -1,
                "name": "Master",
                "left":  float(getattr(m, "output_meter_left",  0.0) or 0.0),
                "right": float(getattr(m, "output_meter_right", 0.0) or 0.0),
                "level": float(getattr(m, "output_meter_level", 0.0) or 0.0),
            })
        except Exception:
            pass
        return {"meters": out}

    def _set_launch_quantization(self, bars):
        """Set Live's global clip-launch quantization.

        bars accepts: 0 (None), 0.0625 (1/16), 0.125 (1/8), 0.25 (1/4), 0.5 (1/2),
        1, 2, 4, 8, 16 (bars). Picks the closest available enum value Live offers.
        """
        # Live's Quantization enum values typically:
        # 0 q_no_q, 1 q_8_bars, 2 q_4_bars, 3 q_2_bars, 4 q_bar, 5 q_half,
        # 7 q_quarter, 9 q_eight, 11 q_sixteenth, 13 q_thirtytwoth.
        # Live 12 may add 16-bar (or it may not — fall back to 8 bars).
        try:
            import Live
            Q = Live.Song.Quantization
            # Build mapping defensively — Live versions vary on what's exposed
            mapping = {}
            for bars_val, attr in [
                (0, "q_no_q"),
                (0.0625, "q_sixteenth"),
                (0.125, "q_eight"),
                (0.25, "q_quarter"),
                (0.5, "q_half"),
                (1, "q_bar"),
                (2, "q_2_bars"),
                (4, "q_4_bars"),
                (8, "q_8_bars"),
            ]:
                if hasattr(Q, attr):
                    mapping[bars_val] = getattr(Q, attr)
            # 16 bars requested? Use 16-bars if exposed, else 8 bars.
            if bars == 16:
                if hasattr(Q, "q_16_bars"):
                    target = Q.q_16_bars
                    chosen = 16
                else:
                    target = Q.q_8_bars
                    chosen = 8
            else:
                target = mapping.get(bars, Q.q_bar)
                chosen = bars
            self._song.clip_trigger_quantization = target
            return {"requested_bars": bars, "applied_bars": chosen}
        except Exception as e:
            self.log_message("set_launch_quantization err: " + str(e))
            raise

    def _set_clip_loop(self, track_index, clip_index, loop):
        track = self._track(track_index)
        if clip_index < 0 or clip_index >= len(track.clip_slots):
            raise IndexError("clip_index out of range")
        slot = track.clip_slots[clip_index]
        if not slot.has_clip:
            raise ValueError("No clip in slot")
        slot.clip.looping = bool(loop)
        return {"track_index": track_index, "clip_index": clip_index, "looping": slot.clip.looping}

    def _set_clip_loop_region(self, track_index, clip_index, loop_start, loop_end):
        track = self._track(track_index)
        slot = track.clip_slots[clip_index]
        if not slot.has_clip:
            raise ValueError("No clip in slot")
        clip = slot.clip
        clip.looping = True
        clip.loop_start = float(loop_start)
        clip.loop_end = float(loop_end)
        return {
            "track_index": track_index, "clip_index": clip_index,
            "loop_start": clip.loop_start, "loop_end": clip.loop_end,
        }

    def _delete_track(self, track_index):
        if track_index < 0 or track_index >= len(self._song.tracks):
            raise IndexError("track_index out of range")
        # song.delete_track expects an index
        self._song.delete_track(track_index)
        return {"deleted_track_index": track_index, "tracks_remaining": len(self._song.tracks)}

    # ---- arrangement loop ------------------------------------------

    def _get_arrangement_loop(self):
        return {
            "start": float(self._song.loop_start),
            "length": float(self._song.loop_length),
            "on": bool(self._song.loop),
        }

    def _set_arrangement_loop(self, start=None, length=None, on=None):
        if start is not None:
            self._song.loop_start = float(start)
        if length is not None:
            self._song.loop_length = float(length)
        if on is not None:
            self._song.loop = bool(on)
        return {
            "start": float(self._song.loop_start),
            "length": float(self._song.loop_length),
            "on": bool(self._song.loop),
        }

    # ---- drum rack pads --------------------------------------------

    def _get_drum_rack(self, track_index, device_index):
        track = self._track(track_index)
        if device_index < 0 or device_index >= len(track.devices):
            raise IndexError("device_index out of range")
        rack = track.devices[device_index]
        if not hasattr(rack, "drum_pads"):
            raise ValueError("device " + rack.name + " is not a Drum Rack")
        return rack

    def _get_drum_pads(self, track_index, device_index):
        rack = self._get_drum_rack(track_index, device_index)
        out = []
        for note in range(36, 100):  # standard drum-rack span
            try:
                pad = rack.drum_pads[note]
            except Exception:
                continue
            chains = []
            try:
                for c in pad.chains:
                    chains.append({"name": getattr(c, "name", "?"), "mute": bool(getattr(c, "mute", False))})
            except Exception:
                pass
            if not chains and bool(getattr(pad, "mute", False)) is False and not getattr(pad, "name", ""):
                continue  # skip empty pads
            out.append({
                "note": note,
                "name": getattr(pad, "name", ""),
                "mute": bool(getattr(pad, "mute", False)),
                "solo": bool(getattr(pad, "solo", False)),
                "chain_count": len(chains),
                "chains": chains,
            })
        return {"track_index": track_index, "device_index": device_index, "pads": out}

    def _set_drum_pad_mute(self, track_index, device_index, note, mute):
        rack = self._get_drum_rack(track_index, device_index)
        pad = rack.drum_pads[int(note)]
        pad.mute = bool(mute)
        return {"note": int(note), "mute": pad.mute}

    def _set_drum_pad_volume(self, track_index, device_index, note, value):
        rack = self._get_drum_rack(track_index, device_index)
        pad = rack.drum_pads[int(note)]
        # Pad volume is on the first chain's mixer_device.volume
        try:
            chain = pad.chains[0]
            chain.mixer_device.volume.value = float(value)
            return {"note": int(note), "volume": chain.mixer_device.volume.value}
        except Exception as e:
            raise ValueError("could not set pad volume: " + str(e))

    # ---- master track devices ---------------------------------------

    def _load_master_device(self, uri=None, path=None, item_name=None):
        master = self._song.master_track
        b = self._browser()
        if uri:
            item = self._find_browser_item_by_uri(b, uri)
            if not item:
                raise ValueError("Browser item not found: " + uri)
        elif path:
            parts = [p for p in path.split("/") if p]
            head = parts[0].lower()
            cur = None
            for attr in dir(b):
                if attr.startswith("_"): continue
                if attr.lower() == head:
                    try: cur = getattr(b, attr)
                    except Exception: cur = None
                    break
            if cur is None:
                raise ValueError("unknown root: " + parts[0])
            for p in parts[1:]:
                children = self._browser_children(cur)
                nxt = None
                for c in children:
                    if getattr(c, "name", "").lower() == p.lower():
                        nxt = c; break
                if nxt is None:
                    raise ValueError("path part not found: " + p)
                cur = nxt
            if item_name:
                children = self._browser_children(cur)
                target = None
                for c in children:
                    if getattr(c, "name", "").lower() == item_name.lower():
                        target = c; break
                if target is None:
                    raise ValueError("item '" + item_name + "' not in " + path)
                cur = target
            item = cur
        else:
            raise ValueError("must supply uri or path")
        self._song.view.selected_track = master
        b.load_item(item)
        return {"loaded": True, "item_name": getattr(item, "name", "?")}

    def _get_master_device_info(self, device_index):
        master = self._song.master_track
        if device_index < 0 or device_index >= len(master.devices):
            raise IndexError("device_index out of range on master")
        device = master.devices[device_index]
        params = []
        for i, p in enumerate(device.parameters):
            params.append({
                "index": i, "name": p.name, "value": p.value,
                "min": p.min, "max": p.max, "is_quantized": p.is_quantized,
            })
        return {
            "device_index": device_index, "name": device.name, "class_name": device.class_name,
            "parameter_count": len(params), "parameters": params,
        }

    def _set_master_device_param(self, device_index, param_index, param_name, value):
        master = self._song.master_track
        device = master.devices[device_index]
        param, idx = self._resolve_param(device, param_index, param_name)
        v = float(value)
        if v < param.min: v = param.min
        elif v > param.max: v = param.max
        param.value = v
        return {"device_index": device_index, "param_index": idx, "param_name": param.name, "value": param.value}

    def _get_master_device_param(self, device_index, param_index, param_name):
        master = self._song.master_track
        device = master.devices[device_index]
        param, idx = self._resolve_param(device, param_index, param_name)
        return {"device_index": device_index, "param_index": idx, "param_name": param.name,
                "value": param.value, "min": param.min, "max": param.max}

    def _bulk_load_drum_pads(self, track_index, device_index, browser_path, items):
        """Load multiple browser items into successive drum-rack pads in one call.

        items: list of {"name": "filename.wav", "note": 36}.
        Each item is selected on its target pad, then loaded.
        Doing this within one RPC keeps the UI-thread sequence intact.
        """
        track = self._track(track_index)
        if device_index >= len(track.devices):
            raise ValueError("device_index out of range")
        rack = track.devices[device_index]
        if not hasattr(rack, "drum_pads"):
            raise ValueError("device " + rack.name + " is not a Drum Rack")
        b = self._browser()

        # Walk to browser folder
        parts = [p for p in browser_path.split("/") if p]
        head = parts[0].lower()
        cur = None
        for attr in dir(b):
            if attr.startswith("_"):
                continue
            if attr.lower() == head:
                try:
                    cur = getattr(b, attr)
                except Exception:
                    cur = None
                break
        if cur is None:
            raise ValueError("unknown root: " + parts[0])
        for p in parts[1:]:
            children = self._browser_children(cur)
            nxt = None
            for c in children:
                if getattr(c, "name", "").lower() == p.lower():
                    nxt = c
                    break
            if nxt is None:
                raise ValueError("path part not found: " + p)
            cur = nxt
        children = self._browser_children(cur)
        by_name = {getattr(c, "name", "").lower(): c for c in children}

        self._song.view.selected_track = track
        loaded = []
        failed = []
        for entry in items:
            name = entry.get("name", "")
            note = int(entry.get("note", -1))
            item = by_name.get(name.lower())
            if item is None or not getattr(item, "is_loadable", False):
                failed.append({"name": name, "reason": "not found or not loadable"})
                continue
            try:
                self._song.view.selected_drum_pad = rack.drum_pads[note]
                b.load_item(item)
                loaded.append({"name": name, "note": note})
            except Exception as e:
                failed.append({"name": name, "note": note, "reason": str(e)})
        return {"loaded": loaded, "failed": failed}

    def _duplicate_clip(self, track_index, src_slot, dst_slot):
        track = self._track(track_index)
        if src_slot < 0 or src_slot >= len(track.clip_slots):
            raise IndexError("src_slot out of range")
        if dst_slot < 0 or dst_slot >= len(track.clip_slots):
            raise IndexError("dst_slot out of range")
        src = track.clip_slots[src_slot]
        if not src.has_clip:
            raise ValueError("src slot has no clip")
        dst = track.clip_slots[dst_slot]
        if dst.has_clip:
            dst.delete_clip()
        src.duplicate_clip_to(dst)
        return {"track_index": track_index, "src_slot": src_slot, "dst_slot": dst_slot}

    def _delete_master_device(self, device_index):
        master = self._song.master_track
        if device_index < 0 or device_index >= len(master.devices):
            raise IndexError("device_index out of range on master")
        master.delete_device(device_index)
        return {"deleted": True, "device_index": device_index}

    def _set_clip_reverse(self, track_index, clip_index, reverse):
        """Reverse an audio clip's playback. Tries multiple Live API surfaces."""
        track = self._track(track_index)
        slot = track.clip_slots[clip_index]
        if not slot.has_clip:
            raise ValueError("No clip in slot")
        clip = slot.clip
        # Approach 1: clip.reverse_audio_data() — Live 11+
        try:
            if reverse:
                clip.reverse_audio_data()
                return {"reversed": True, "method": "reverse_audio_data"}
        except Exception:
            pass
        # Approach 2: setattr 'reverse' (some versions expose as bool)
        try:
            clip.reverse = bool(reverse)
            return {"reversed": clip.reverse, "method": "reverse_attr"}
        except Exception:
            pass
        # Approach 3: warping with negative speed (last resort — flips warp markers)
        raise NotImplementedError("clip reverse not exposed in this Live version")

    def _set_clip_pitch(self, track_index, clip_index, coarse=None, fine=None):
        track = self._track(track_index)
        slot = track.clip_slots[clip_index]
        if not slot.has_clip:
            raise ValueError("No clip in slot")
        clip = slot.clip
        if coarse is not None:
            clip.pitch_coarse = int(coarse)
        if fine is not None:
            clip.pitch_fine = int(fine)
        return {"pitch_coarse": clip.pitch_coarse, "pitch_fine": clip.pitch_fine}

    def _set_clip_mixer_envelope(self, clip_track, clip_index, target_track, mixer_param, breakpoints):
        """Envelope a track-mixer parameter (volume / panning / sends[N]) across a clip.

        mixer_param: 'volume', 'panning', 'send_0', 'send_1', etc.
        """
        track = self._track(clip_track)
        slot = track.clip_slots[clip_index]
        if not slot.has_clip:
            raise ValueError("No clip in slot")
        clip = slot.clip
        target = self._track(target_track)
        mixer = target.mixer_device
        if mixer_param == "volume":
            param = mixer.volume
        elif mixer_param == "panning":
            param = mixer.panning
        elif mixer_param.startswith("send_"):
            idx = int(mixer_param.split("_")[1])
            sends = list(mixer.sends)
            if idx < 0 or idx >= len(sends):
                raise IndexError("send index out of range")
            param = sends[idx]
        else:
            raise ValueError("unknown mixer_param: " + mixer_param)
        try:
            clip.clear_envelope(param)
        except Exception:
            pass
        env = clip.create_automation_envelope(param)
        bps = sorted([(float(b[0]), float(b[1])) for b in breakpoints], key=lambda x: x[0])
        for i, (t, v) in enumerate(bps):
            length = max(0.001, bps[i+1][0] - t) if i + 1 < len(bps) else 0.5
            try: env.insert_step(t, length, v)
            except Exception: pass
        return {
            "clip_track": clip_track, "clip_index": clip_index,
            "target_track": target_track, "param": mixer_param,
            "breakpoints_written": len(bps),
        }

    def _get_track_clips(self, track_index):
        track = self._track(track_index)
        clips = []
        for i, slot in enumerate(track.clip_slots):
            if slot.has_clip:
                clip = slot.clip
                clips.append({
                    "slot": i, "name": clip.name, "length": float(clip.length),
                    "is_audio": bool(clip.is_audio_clip), "looping": bool(clip.looping),
                })
        return {"track_index": track_index, "name": track.name, "clips": clips,
                "slot_count": len(list(track.clip_slots))}

    def _get_track_input_options(self, track_index):
        track = self._track(track_index)
        types = []
        try:
            for rt in (track.available_input_routing_types or []):
                types.append(getattr(rt, "display_name", str(rt)))
        except Exception: pass
        current = ""
        try: current = getattr(track.input_routing_type, "display_name", "")
        except Exception: pass
        return {"track_index": track_index, "available_types": types, "current_type": current}

    def _set_track_input_routing(self, track_index, target_name):
        track = self._track(track_index)
        candidates = list(track.available_input_routing_types or [])
        target = None
        for rt in candidates:
            dn = getattr(rt, "display_name", "")
            if dn == target_name or target_name in dn:
                target = rt; break
        if target is None:
            names = [getattr(rt, "display_name", "?") for rt in candidates]
            raise ValueError("no input matches '" + target_name + "'. Available: " + ", ".join(names))
        track.input_routing_type = target
        return {"track_index": track_index, "target": getattr(target, "display_name", target_name)}

    def _set_selected_clip_slot(self, track_index, slot):
        track = self._track(track_index)
        if slot < 0 or slot >= len(track.clip_slots):
            raise IndexError("slot out of range")
        self._song.view.selected_track = track
        self._song.view.highlighted_clip_slot = track.clip_slots[slot]
        return {"track_index": track_index, "slot": slot}

    @staticmethod
    def _resolve_attr_path(obj, attr):
        """Walk a dotted attribute path, returning (owner, final_name).

        Lets callers reach nested LOM objects that are not devices in their
        own right — most usefully `sample.slicing_style` and friends on a
        Simpler, which are otherwise unaddressable.
        """
        parts = [p for p in str(attr).split(".") if p]
        if not parts:
            raise ValueError("empty attr path")
        owner = obj
        for p in parts[:-1]:
            if not hasattr(owner, p):
                avail = [a for a in dir(owner) if not a.startswith("_")][:30]
                raise ValueError(
                    "attr '" + p + "' not on " + type(owner).__name__
                    + ". Available: " + ", ".join(avail)
                )
            owner = getattr(owner, p)
            if owner is None:
                raise ValueError("attr path '" + attr + "' hit None at '" + p + "'")
        return owner, parts[-1]

    def _set_device_property(self, track_index, device_index, attr, value):
        device = self._device(track_index, device_index)
        device, attr = self._resolve_attr_path(device, attr)
        if not hasattr(device, attr):
            avail = [a for a in dir(device) if not a.startswith("_")][:30]
            raise ValueError("attr '" + attr + "' not on " + type(device).__name__ + ". Sample: " + ", ".join(avail))
        try:
            # Coerce types where possible — properties can be int or float
            current = getattr(device, attr)
            if isinstance(current, bool):
                setattr(device, attr, bool(value))
            elif isinstance(current, int):
                setattr(device, attr, int(value))
            elif isinstance(current, float):
                setattr(device, attr, float(value))
            else:
                setattr(device, attr, value)
            return {"attr": attr, "value": getattr(device, attr)}
        except Exception as e:
            raise ValueError("could not set '" + attr + "': " + str(e))

    def _load_audio_to_slot(self, track_index, slot, path=None, item_name=None):
        """Load an audio file into a specific clip slot on an audio track.

        Sets selected_track + highlighted_clip_slot, then app.browser.load_item.
        Live should create an audio clip in that slot.
        """
        track = self._track(track_index)
        if slot < 0 or slot >= len(track.clip_slots):
            raise IndexError("slot out of range")
        b = self._browser()
        # Resolve item via path
        parts = [p for p in (path or "").split("/") if p]
        if not parts:
            raise ValueError("path required")
        head = parts[0].lower()
        cur = None
        for attr in dir(b):
            if attr.startswith("_"): continue
            if attr.lower() == head:
                try: cur = getattr(b, attr)
                except Exception: cur = None
                break
        if cur is None:
            raise ValueError("unknown root: " + parts[0])
        for p in parts[1:]:
            children = self._browser_children(cur)
            nxt = None
            for c in children:
                if getattr(c, "name", "").lower() == p.lower():
                    nxt = c; break
            if nxt is None:
                raise ValueError("path part not found: " + p)
            cur = nxt
        if item_name:
            children = self._browser_children(cur)
            target = None
            for c in children:
                if getattr(c, "name", "").lower() == item_name.lower():
                    target = c; break
            if target is None:
                raise ValueError("item not in path: " + item_name)
            cur = target
        if not getattr(cur, "is_loadable", False):
            raise ValueError("item not loadable")
        # Select target track + slot
        self._song.view.selected_track = track
        self._song.view.highlighted_clip_slot = track.clip_slots[slot]
        b.load_item(cur)
        landed = track.clip_slots[slot].has_clip
        return {
            "loaded": True, "track_index": track_index, "slot": slot,
            "item_name": getattr(cur, "name", "?"), "landed_in_slot": bool(landed),
        }

    def _drum_pad_chain(self, track_index, device_index, note):
        rack = self._get_drum_rack(track_index, device_index)
        pad = rack.drum_pads[int(note)]
        if not pad.chains:
            raise ValueError("pad note " + str(note) + " has no chain")
        return pad, pad.chains[0]

    def _drum_pad_chain_device(self, track_index, device_index, note, chain_device_index):
        _, chain = self._drum_pad_chain(track_index, device_index, note)
        devs = list(chain.devices)
        idx = int(chain_device_index)
        if idx < 0 or idx >= len(devs):
            raise IndexError("chain_device_index out of range (have " + str(len(devs)) + ")")
        return devs[idx]

    def _set_drum_pad_chain_device_property(self, track_index, device_index, note,
                                              chain_device_index, property_name, value):
        dev = self._drum_pad_chain_device(track_index, device_index, note, chain_device_index)
        # Coerce primitives. playback_mode is int; loop flags are bool.
        try:
            v = value
            if isinstance(value, bool):
                v = bool(value)
            elif isinstance(value, (int, float)):
                # try int first
                try:
                    v = int(value)
                except (TypeError, ValueError):
                    v = float(value)
            setattr(dev, property_name, v)
        except Exception as e:
            raise RuntimeError("setattr " + str(property_name) + " failed: " + str(e))
        return {
            "track_index": track_index, "device_index": device_index,
            "note": int(note), "chain_device_index": int(chain_device_index),
            "property_name": property_name,
            "value": getattr(dev, property_name, None),
        }

    def _set_drum_pad_chain_device_param(self, track_index, device_index, note,
                                           chain_device_index, param_index, param_name, value):
        dev = self._drum_pad_chain_device(track_index, device_index, note, chain_device_index)
        param, idx = self._resolve_param(dev, param_index, param_name)
        v = float(value)
        if v < param.min:
            v = param.min
        elif v > param.max:
            v = param.max
        param.value = v
        return {
            "track_index": track_index, "device_index": device_index,
            "note": int(note), "chain_device_index": int(chain_device_index),
            "param_index": idx, "param_name": param.name, "value": param.value,
        }

    def _get_drum_pad_chain_device_info(self, track_index, device_index, note, chain_device_index):
        dev = self._drum_pad_chain_device(track_index, device_index, note, chain_device_index)
        params = []
        for i, p in enumerate(dev.parameters):
            params.append({"index": i, "name": p.name, "value": p.value,
                           "min": p.min, "max": p.max})
        # Pull common known properties (best-effort, ignore missing)
        props = {}
        for pname in ("playback_mode", "playback_loop", "loop_on", "trigger_mode"):
            if hasattr(dev, pname):
                try:
                    props[pname] = getattr(dev, pname)
                except Exception:
                    pass
        return {
            "track_index": track_index, "device_index": device_index,
            "note": int(note), "chain_device_index": int(chain_device_index),
            "name": getattr(dev, "name", ""),
            "class_name": getattr(dev, "class_name", ""),
            "param_count": len(params),
            "parameters": params,
            "properties": props,
        }

    def _get_drum_pad_chain_info(self, track_index, device_index, note):
        pad, chain = self._drum_pad_chain(track_index, device_index, note)
        mixer = chain.mixer_device
        out = {
            "note": int(note),
            "pad_name": getattr(pad, "name", ""),
            "chain_name": getattr(chain, "name", ""),
            "volume": float(getattr(mixer.volume, "value", 0)),
            "panning": float(getattr(mixer.panning, "value", 0)),
            "mute": bool(getattr(chain, "mute", False)),
            "solo": bool(getattr(chain, "solo", False)),
            "device_count": len(list(chain.devices)),
            "devices": [{"name": d.name, "class_name": d.class_name} for d in chain.devices],
            "send_count": len(list(mixer.sends)),
            "sends": [{"index": i, "value": float(s.value)} for i, s in enumerate(mixer.sends)],
        }
        # Audio output routing options
        try:
            out["audio_output_types"] = [getattr(rt, "display_name", str(rt))
                                          for rt in chain.audio_output_routing_types]
            out["current_audio_output"] = getattr(chain.audio_output_routing_type, "display_name", "")
        except Exception:
            pass
        return out

    def _set_drum_pad_chain_audio_output(self, track_index, device_index, note, target_name):
        pad, chain = self._drum_pad_chain(track_index, device_index, note)
        try:
            candidates = list(chain.audio_output_routing_types)
        except Exception:
            raise ValueError("chain doesn't expose audio_output_routing_types")
        target = None
        for rt in candidates:
            dn = getattr(rt, "display_name", "")
            if dn == target_name or target_name in dn:
                target = rt; break
        if target is None:
            names = [getattr(rt, "display_name", "?") for rt in candidates]
            raise ValueError("no output matches '" + target_name + "'. Available: " + ", ".join(names))
        chain.audio_output_routing_type = target
        return {"note": int(note), "target": getattr(target, "display_name", target_name)}

    def _set_drum_pad_chain_send(self, track_index, device_index, note, send_index, value):
        pad, chain = self._drum_pad_chain(track_index, device_index, note)
        sends = list(chain.mixer_device.sends)
        if send_index < 0 or send_index >= len(sends):
            raise IndexError("send_index out of range")
        sends[send_index].value = float(value)
        return {"note": int(note), "send_index": send_index, "value": sends[send_index].value}

    def _set_drum_pad_chain_volume(self, track_index, device_index, note, value):
        pad, chain = self._drum_pad_chain(track_index, device_index, note)
        chain.mixer_device.volume.value = float(value)
        return {"note": int(note), "volume": chain.mixer_device.volume.value}

    def _load_into_drum_pad_chain(self, track_index, device_index, note, uri=None, path=None, item_name=None):
        """Try to load a device INTO a specific drum-pad chain by setting selected_chain
        and selected_drum_pad before browser.load_item. Live's selection model is fragile
        for this; if it fails, fall back to loading on the main track and tell the caller.
        """
        pad, chain = self._drum_pad_chain(track_index, device_index, note)
        track = self._track(track_index)
        b = self._browser()

        # Resolve item
        if uri:
            item = self._find_browser_item_by_uri(b, uri)
            if not item:
                raise ValueError("item not found: " + uri)
        elif path:
            parts = [p for p in path.split("/") if p]
            head = parts[0].lower()
            cur = None
            for attr in dir(b):
                if attr.startswith("_"): continue
                if attr.lower() == head:
                    try: cur = getattr(b, attr)
                    except Exception: cur = None
                    break
            if cur is None:
                raise ValueError("unknown root: " + parts[0])
            for p in parts[1:]:
                children = self._browser_children(cur)
                nxt = None
                for c in children:
                    if getattr(c, "name", "").lower() == p.lower():
                        nxt = c; break
                if nxt is None:
                    raise ValueError("path part not found: " + p)
                cur = nxt
            if item_name:
                children = self._browser_children(cur)
                target = None
                for c in children:
                    if getattr(c, "name", "").lower() == item_name.lower():
                        target = c; break
                if target is None:
                    raise ValueError("item '" + item_name + "' not in path")
                cur = target
            item = cur
        else:
            raise ValueError("must supply uri or path")

        # Try multiple selection paths to direct the load
        self._song.view.selected_track = track
        try:
            self._song.view.selected_drum_pad = pad
        except Exception:
            pass
        try:
            self._song.view.selected_chain = chain
        except Exception:
            pass
        # If chain has at least one device, focus it so further loads append
        try:
            if list(chain.devices):
                self._song.view.select_device(chain.devices[-1])
        except Exception:
            pass

        before = list(chain.devices)
        b.load_item(item)
        after = list(chain.devices)

        landed_in_chain = len(after) > len(before)
        return {
            "loaded": True,
            "item_name": getattr(item, "name", "?"),
            "landed_in_chain": landed_in_chain,
            "chain_devices_after": [d.name for d in after],
            "warning": None if landed_in_chain else "Live API likely loaded onto track main chain instead — use send/output routing alternative",
        }

    def _load_sample_to_pad(self, track_index, device_index, note, path=None, item_name=None):
        """Per-pad sample load via Browser.hotswap_target — Live 12 path
        that respects pad targeting where selected_drum_pad does not.
        """
        track = self._track(track_index)
        if device_index >= len(track.devices):
            raise ValueError("device_index out of range")
        rack = track.devices[device_index]
        if not hasattr(rack, "drum_pads"):
            raise ValueError("device " + rack.name + " is not a Drum Rack")
        pad = rack.drum_pads[int(note)]
        b = self._browser()

        if not path:
            raise ValueError("path required")
        parts = [p for p in path.split("/") if p]
        head = parts[0].lower()
        cur = None
        for attr in dir(b):
            if attr.startswith("_"): continue
            if attr.lower() == head:
                try: cur = getattr(b, attr)
                except Exception: cur = None
                break
        if cur is None:
            raise ValueError("unknown root: " + parts[0])
        for p in parts[1:]:
            children = self._browser_children(cur)
            nxt = None
            for c in children:
                if getattr(c, "name", "").lower() == p.lower():
                    nxt = c; break
            if nxt is None:
                raise ValueError("path part not found: " + p)
            cur = nxt
        if item_name:
            children = self._browser_children(cur)
            target = None
            for c in children:
                if getattr(c, "name", "").lower() == item_name.lower():
                    target = c; break
            if target is None:
                raise ValueError("item '" + item_name + "' not in path")
            cur = target
        if not getattr(cur, "is_loadable", False):
            raise ValueError("item not loadable: " + getattr(cur, "name", "?"))

        before_chains = len(list(pad.chains))
        # Set hotswap target to the pad, then load — Live's documented per-pad swap path
        try:
            b.hotswap_target = pad
        except Exception as e:
            raise ValueError("could not set hotswap_target: " + str(e))
        try:
            b.load_item(cur)
        finally:
            try: b.hotswap_target = None
            except Exception: pass
        after_chains = list(pad.chains)
        return {
            "loaded": True,
            "note": int(note),
            "item_name": getattr(cur, "name", "?"),
            "chain_count_before": before_chains,
            "chain_count_after": len(after_chains),
            "chain_names": [getattr(c, "name", "?") for c in after_chains],
        }

    def _create_scene(self, index):
        self._song.create_scene(index)
        return {"scene_count": len(list(self._song.scenes))}

    def _delete_scene(self, scene_index):
        self._song.delete_scene(scene_index)
        return {"scene_count": len(list(self._song.scenes))}

    # ---- sample / slicing (Simpler) ---------------------------------

    def _sample_or_raise(self, track_index, device_index):
        device = self._device(track_index, device_index)
        sample = getattr(device, "sample", None)
        if sample is None:
            raise ValueError(
                "device '" + device.name + "' (" + device.class_name
                + ") has no .sample - need a Simpler with a file loaded"
            )
        return device, sample

    def _get_sample_info(self, track_index, device_index):
        """Everything readable about a Simpler's sample, including slices.

        Slice positions come back in whatever unit Live reports them in;
        `length` and `sample_rate` are returned alongside so the caller can
        convert between sample time, seconds and beats without guessing.
        """
        device, sample = self._sample_or_raise(track_index, device_index)
        out = {
            "device_name": device.name,
            "device_class": device.class_name,
            "playback_mode": int(getattr(device, "playback_mode", -1)),
        }
        for attr in ("length", "sample_rate", "start_marker", "end_marker",
                     "warping", "warp_mode", "gain", "beats_per_minute",
                     "slicing_style", "slicing_beat_division",
                     "file_path", "name"):
            try:
                v = getattr(sample, attr)
                if not isinstance(v, (int, float, bool, str, type(None))):
                    v = str(v)
                out[attr] = v
            except Exception:
                pass
        try:
            out["slices"] = [float(s) for s in sample.slices]
            out["slice_count"] = len(out["slices"])
        except Exception as e:
            out["slices_error"] = str(e)
        try:
            out["available_attrs"] = [a for a in dir(sample) if not a.startswith("_")]
        except Exception:
            pass
        return out

    def _set_sample_property(self, track_index, device_index, attr, value):
        _device, sample = self._sample_or_raise(track_index, device_index)
        owner, name = self._resolve_attr_path(sample, attr)
        if not hasattr(owner, name):
            avail = [a for a in dir(owner) if not a.startswith("_")][:40]
            raise ValueError(
                "attr '" + name + "' not on sample. Available: " + ", ".join(avail)
            )
        current = getattr(owner, name)
        try:
            if isinstance(current, bool):
                setattr(owner, name, bool(value))
            elif isinstance(current, int):
                setattr(owner, name, int(value))
            elif isinstance(current, float):
                setattr(owner, name, float(value))
            else:
                setattr(owner, name, value)
        except Exception as e:
            raise ValueError("could not set sample '" + attr + "': " + str(e))
        return {"attr": attr, "value": getattr(owner, name)}

    def _set_sample_slices(self, track_index, device_index, times, clear=True):
        """Replace the slice points with an explicit list.

        With slicing_style set to manual this is what makes slice N mean a
        known position rather than "the Nth transient Live happened to find".
        """
        _device, sample = self._sample_or_raise(track_index, device_index)
        removed = 0
        if clear:
            try:
                sample.clear_slices()
            except Exception:
                for s in list(getattr(sample, "slices", [])):
                    try:
                        sample.remove_slice(s)
                        removed += 1
                    except Exception:
                        pass
        inserted, failed = [], []
        for t in (times or []):
            try:
                sample.insert_slice(float(t))
                inserted.append(float(t))
            except Exception as e:
                failed.append({"time": float(t), "error": str(e)})
        try:
            now = [float(s) for s in sample.slices]
        except Exception:
            now = None
        return {
            "cleared": bool(clear), "removed_individually": removed,
            "inserted": inserted, "failed": failed, "slices": now,
            "slice_count": len(now) if now is not None else None,
        }

    def _get_device_property(self, track_index, device_index, attr):
        """Read an arbitrary device attribute by name (e.g. 'gain_reduction',
        'output_meter_left', 'name', 'class_name'). Useful for compressor GR,
        EQ analyser values, etc. Returns the value as float / int / string."""
        device = self._device(track_index, device_index)
        device, attr = self._resolve_attr_path(device, attr)
        if not hasattr(device, attr):
            avail = [a for a in dir(device) if not a.startswith("_")][:30]
            raise ValueError("attr '" + attr + "' not on " + type(device).__name__ + ". Sample: " + ", ".join(avail))
        try:
            val = getattr(device, attr)
        except Exception as e:
            raise ValueError("could not read '" + attr + "': " + str(e))
        # Convert to JSON-friendly
        if isinstance(val, (int, float, bool, str, type(None))):
            return {"attr": attr, "value": val}
        try:
            return {"attr": attr, "value": float(val)}
        except Exception:
            return {"attr": attr, "value": str(val)}

    def _set_clip_gain(self, track_index, clip_index, gain):
        track = self._track(track_index)
        slot = track.clip_slots[clip_index]
        if not slot.has_clip:
            raise ValueError("No clip in slot")
        clip = slot.clip
        clip.gain = float(gain)
        return {"gain": clip.gain}

    def _get_clip_props(self, track_index, clip_index):
        """Read every diagnostic clip property we can reach for debugging
        clip-launch timing / start-offset / loop / warp issues."""
        track = self._track(track_index)
        slot = track.clip_slots[clip_index]
        if not slot.has_clip:
            return {"has_clip": False}
        c = slot.clip
        out = {"has_clip": True, "name": c.name}
        for attr in ("length", "loop_start", "loop_end", "start_marker",
                     "end_marker", "looping", "warping", "warp_mode",
                     "is_audio_clip", "is_midi_clip", "is_playing",
                     "fades_enabled", "fade_in_time", "fade_out_time",
                     "launch_mode", "launch_quantization",
                     "legato", "ram_mode", "gain", "pitch_coarse",
                     "pitch_fine", "signature_numerator",
                     "signature_denominator", "color_index"):
            try:
                v = getattr(c, attr)
                if not isinstance(v, (int, float, bool, str)):
                    v = str(v)
                out[attr] = v
            except Exception:
                pass
        return out

    def _inspect_clip_envelopes(self, track_index, clip_index):
        """Return clip + envelope object diagnostics."""
        track = self._track(track_index)
        slot = track.clip_slots[clip_index]
        if not slot.has_clip:
            return {"has_clip": False}
        clip = slot.clip
        out = {
            "has_clip": True,
            "name": clip.name,
            "is_audio_clip": getattr(clip, "is_audio_clip", None),
            "has_envelopes": bool(getattr(clip, "has_envelopes", False)),
        }
        envs_attr = getattr(clip, "automation_envelopes", None)
        if envs_attr is not None:
            try:
                envs = list(envs_attr)
                out["automation_envelopes_count"] = len(envs)
                env_summaries = []
                for e in envs:
                    summary = {
                        "param_attr_present": hasattr(e, "parameter"),
                        "param": None,
                        "events_count": None,
                        "values_at_times": {},
                    }
                    if hasattr(e, "parameter"):
                        try:
                            p = e.parameter
                            summary["param"] = p.name if p is not None else None
                        except Exception as ex:
                            summary["param_err"] = str(ex)
                    # try events_in_range to enumerate stored events
                    try:
                        events = list(e.events_in_range(0.0, 64.0))
                        summary["events_count"] = len(events)
                        if events:
                            summary["events_sample"] = [
                                {"time": getattr(ev, "time", None),
                                 "value": getattr(ev, "value", None)}
                                for ev in events[:5]
                            ]
                    except Exception as ex:
                        summary["events_err"] = str(ex)
                    # value_at_time at a few sample beats
                    try:
                        for beat in (0.0, 4.0, 8.0, 12.0, 16.0):
                            summary["values_at_times"][beat] = e.value_at_time(beat)
                    except Exception as ex:
                        summary["value_at_time_err"] = str(ex)
                    env_summaries.append(summary)
                out["envelopes"] = env_summaries
            except Exception as ex:
                out["envelopes_iter_err"] = str(ex)
        return out

    def _set_clip_fades(self, track_index, clip_index, fade_in=None, fade_out=None):
        """Audio-clip fade in/out times in SECONDS. clip.fades_enabled
        must be on for them to take effect. MIDI clips don't support this."""
        track = self._track(track_index)
        slot = track.clip_slots[clip_index]
        if not slot.has_clip:
            raise ValueError("No clip in slot")
        clip = slot.clip
        out = {}
        try:
            if hasattr(clip, "fades_enabled"):
                clip.fades_enabled = True
            if fade_in is not None:
                clip.fade_in_time = float(fade_in)
                out["fade_in"] = clip.fade_in_time
            if fade_out is not None:
                clip.fade_out_time = float(fade_out)
                out["fade_out"] = clip.fade_out_time
        except Exception as e:
            raise RuntimeError("set_clip_fades failed (audio clip required?): " + str(e))
        return out

    def _set_clip_warp(self, track_index, clip_index, warping=None, warp_mode=None):
        """warping: bool. warp_mode: int (0=Beats, 1=Tones, 2=Texture, 3=Re-Pitch, 4=Complex, 5=REX, 6=Complex Pro)."""
        track = self._track(track_index)
        slot = track.clip_slots[clip_index]
        if not slot.has_clip:
            raise ValueError("No clip in slot")
        clip = slot.clip
        if warping is not None:
            clip.warping = bool(warping)
        if warp_mode is not None:
            clip.warp_mode = int(warp_mode)
        return {
            "track_index": track_index, "clip_index": clip_index,
            "warping": clip.warping, "warp_mode": int(clip.warp_mode),
        }

    def _set_track_monitoring(self, track_index, state):
        """state: 0 = In (always), 1 = Auto, 2 = Off."""
        track = self._track(track_index)
        track.current_monitoring_state = int(state)
        return {"track_index": track_index, "monitoring_state": track.current_monitoring_state}

    # ---- transport --------------------------------------------------

    def _fire_scene(self, scene_index):
        scenes = list(self._song.scenes)
        if scene_index < 0 or scene_index >= len(scenes):
            raise IndexError("scene_index out of range")
        scenes[scene_index].fire()
        return {"scene_index": scene_index, "fired": True}

    def _set_scene_tempo(self, scene_index, tempo):
        """Bake a per-scene tempo. Live snaps the project tempo when the
        scene fires. Set tempo to 0 (or negative) to unbind."""
        scenes = list(self._song.scenes)
        if scene_index < 0 or scene_index >= len(scenes):
            raise IndexError("scene_index out of range")
        scene = scenes[scene_index]
        try:
            scene.tempo = float(tempo)
        except Exception as e:
            raise RuntimeError("Scene.tempo not assignable: " + str(e))
        return {"scene_index": scene_index, "tempo": float(scene.tempo)}

    def _get_scene_tempo(self, scene_index):
        scenes = list(self._song.scenes)
        if scene_index < 0 or scene_index >= len(scenes):
            raise IndexError("scene_index out of range")
        return {"scene_index": scene_index, "tempo": float(scenes[scene_index].tempo)}

    def _stop_all_clips(self):
        try:
            self._song.stop_all_clips()
        except Exception:
            for t in self._song.tracks:
                try:
                    t.stop_all_clips()
                except Exception:
                    pass
        return {"stopped": True}

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

    @staticmethod
    def _browser_children(node):
        """Children of a browser node.

        Most roots are a BrowserItem exposing `.children`, but a few - most
        importantly `user_folders`, the Places sidebar - are returned by the
        LOM as a plain list of items. Treating those as childless is why a
        user-added Place looked empty.
        """
        if isinstance(node, (list, tuple)):
            return list(node)
        return list(getattr(node, "children", []) or [])

    def _list_browser_roots(self):
        b = self._browser()
        out = []
        for attr in dir(b):
            if attr.startswith("_"):
                continue
            try:
                val = getattr(b, attr)
            except Exception:
                continue
            if val is None:
                continue
            entry = {"attr": attr}
            if hasattr(val, "name"):
                try:
                    entry["name"] = val.name
                except Exception:
                    pass
            if isinstance(val, (list, tuple)):
                entry["child_count"] = len(val)
                entry["is_list_root"] = True
                if not entry.get("name"):
                    entry["name"] = attr
            elif hasattr(val, "children"):
                try:
                    entry["child_count"] = len(list(val.children))
                except Exception:
                    pass
            out.append(entry)
        return {"roots": out}

    def _get_browser_items_at_path(self, path):
        b = self._browser()
        parts = [p for p in path.split("/") if p]
        if not parts:
            raise ValueError("empty path")
        head = parts[0].lower()
        # Try direct attribute lookup on browser (handles plugins, places, user_library, etc.)
        cur = None
        # First attempt: case-insensitive dir() match
        for attr in dir(b):
            if attr.startswith("_"):
                continue
            if attr.lower() == head:
                try:
                    cur = getattr(b, attr)
                except Exception:
                    cur = None
                break
        if cur is None:
            # Fallback: try canonical roots explicitly
            roots = {
                "instruments": getattr(b, "instruments", None),
                "sounds": getattr(b, "sounds", None),
                "drums": getattr(b, "drums", None),
                "audio_effects": getattr(b, "audio_effects", None),
                "midi_effects": getattr(b, "midi_effects", None),
            }
            cur = roots.get(head)
        if cur is None:
            raise ValueError("unknown root category: " + parts[0])
        for p in parts[1:]:
            children = self._browser_children(cur)
            nxt = None
            for c in children:
                if getattr(c, "name", "").lower() == p.lower():
                    nxt = c
                    break
            if nxt is None:
                raise ValueError("path part not found: " + p)
            cur = nxt
        items = []
        for c in self._browser_children(cur):
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

    # ------------------------------------------------------------------
    # MIDI note manipulation, follow actions, view, grooves, capture,
    # listener-snapshot helpers
    # ------------------------------------------------------------------

    def _clip_or_raise(self, track_index, clip_index):
        track = self._track(track_index)
        if clip_index < 0 or clip_index >= len(track.clip_slots):
            raise IndexError("clip_index out of range")
        slot = track.clip_slots[clip_index]
        if not slot.has_clip:
            raise ValueError("No clip in slot")
        return slot.clip

    def _get_clip_notes(self, track_index, clip_index, from_pitch, pitch_span, from_time, time_span):
        clip = self._clip_or_raise(track_index, clip_index)
        if time_span is None:
            time_span = float(clip.length)
        notes_out = []
        # Prefer Live 11+ extended API (returns objects with note_id +
        # probability + velocity_deviation); fall back to legacy tuples.
        try:
            ext = clip.get_notes_extended(int(from_pitch), int(pitch_span),
                                          float(from_time), float(time_span))
            for n in ext:
                notes_out.append({
                    "note_id": getattr(n, "note_id", None),
                    "pitch": int(n.pitch),
                    "start_time": float(n.start_time),
                    "duration": float(n.duration),
                    "velocity": float(n.velocity),
                    "mute": bool(n.mute),
                    "probability": float(getattr(n, "probability", 1.0)),
                    "velocity_deviation": float(getattr(n, "velocity_deviation", 0.0)),
                })
        except AttributeError:
            tuples = clip.get_notes(float(from_time), int(from_pitch),
                                    float(time_span), int(pitch_span))
            for t in tuples:
                pitch, start, dur, vel, mute = t
                notes_out.append({
                    "note_id": None, "pitch": int(pitch),
                    "start_time": float(start), "duration": float(dur),
                    "velocity": float(vel), "mute": bool(mute),
                    "probability": 1.0, "velocity_deviation": 0.0,
                })
        return {"count": len(notes_out), "notes": notes_out}

    def _remove_clip_notes(self, track_index, clip_index, from_pitch, pitch_span, from_time, time_span):
        clip = self._clip_or_raise(track_index, clip_index)
        if time_span is None:
            time_span = float(clip.length)
        try:
            clip.remove_notes_extended(int(from_pitch), int(pitch_span),
                                       float(from_time), float(time_span))
        except AttributeError:
            clip.remove_notes(float(from_time), int(from_pitch),
                              float(time_span), int(pitch_span))
        return {"removed": True}

    # Follow-action enum: 0=none, 1=stop, 2=play_again, 3=previous, 4=next,
    # 5=first, 6=last, 7=any, 8=other, 9=jump (Live 11). Live 12 expands
    # this; we accept any int and let Live validate.
    def _set_clip_follow_action(self, track_index, clip_index, action_a, action_b,
                                chance_a, chance_b, time_beats, enabled):
        clip = self._clip_or_raise(track_index, clip_index)
        applied = {}
        if action_a is not None:
            clip.follow_action_a = int(action_a); applied["action_a"] = int(action_a)
        if action_b is not None:
            clip.follow_action_b = int(action_b); applied["action_b"] = int(action_b)
        if chance_a is not None:
            clip.follow_action_chance_a = int(chance_a); applied["chance_a"] = int(chance_a)
        if chance_b is not None:
            clip.follow_action_chance_b = int(chance_b); applied["chance_b"] = int(chance_b)
        if time_beats is not None:
            clip.follow_action_time = float(time_beats); applied["time_beats"] = float(time_beats)
        if enabled is not None and hasattr(clip, "follow_action_enabled"):
            clip.follow_action_enabled = bool(enabled); applied["enabled"] = bool(enabled)
        return {"applied": applied}

    def _get_clip_follow_action(self, track_index, clip_index):
        clip = self._clip_or_raise(track_index, clip_index)
        return {
            "action_a": int(getattr(clip, "follow_action_a", 0)),
            "action_b": int(getattr(clip, "follow_action_b", 0)),
            "chance_a": int(getattr(clip, "follow_action_chance_a", 1)),
            "chance_b": int(getattr(clip, "follow_action_chance_b", 0)),
            "time_beats": float(getattr(clip, "follow_action_time", 1.0)),
            "enabled": bool(getattr(clip, "follow_action_enabled", True)),
        }

    def _select_track(self, track_index):
        track = self._track(track_index)
        self._song.view.selected_track = track
        return {"selected": track.name, "track_index": track_index}

    def _select_scene(self, scene_index):
        scenes = list(self._song.scenes)
        if scene_index < 0 or scene_index >= len(scenes):
            raise IndexError("scene_index out of range")
        self._song.view.selected_scene = scenes[scene_index]
        return {"selected_scene": scene_index}

    def _show_view(self, view_name):
        # Valid: "Browser", "Detail", "Detail/Clip", "Detail/DeviceChain",
        # "Session", "Arranger".
        app = __import__("Live").Application.get_application()
        app.view.show_view(view_name)
        return {"shown": view_name}

    def _get_grooves(self):
        out = []
        pool = getattr(self._song, "groove_pool", None)
        if pool is None:
            # Pre-Live-11 fallback (deprecated `song.grooves`)
            grooves = list(getattr(self._song, "grooves", []) or [])
        else:
            grooves = list(getattr(pool, "grooves", []) or [])
        for i, g in enumerate(grooves):
            out.append({"index": i, "name": getattr(g, "name", "?")})
        return {"count": len(out), "grooves": out}

    def _set_clip_groove(self, track_index, clip_index, groove_index):
        clip = self._clip_or_raise(track_index, clip_index)
        if groove_index is None or groove_index < 0:
            clip.groove = None
            return {"groove": None}
        pool = getattr(self._song, "groove_pool", None)
        grooves = list(getattr(pool, "grooves", []) if pool is not None
                       else getattr(self._song, "grooves", []) or [])
        if groove_index >= len(grooves):
            raise IndexError("groove_index out of range")
        clip.groove = grooves[groove_index]
        return {"groove": getattr(grooves[groove_index], "name", "?"),
                "groove_index": groove_index}

    # Polling-based shim until protocol grows a server->client push channel.
    # Same data the Live LOM listeners would push, batched into one read.
    def _get_listener_snapshot(self):
        playing_clips = []
        for ti, t in enumerate(self._song.tracks):
            ps = getattr(t, "playing_slot_index", -1)
            fs = getattr(t, "fired_slot_index", -1)
            playing_clips.append({
                "track_index": ti,
                "playing_slot": int(ps) if ps is not None else -1,
                "fired_slot": int(fs) if fs is not None else -1,
            })
        return {
            "is_playing": bool(self._song.is_playing),
            "current_song_time": float(self._song.current_song_time),
            "tempo": float(self._song.tempo),
            "signature_numerator": int(self._song.signature_numerator),
            "signature_denominator": int(self._song.signature_denominator),
            "metronome": bool(self._song.metronome),
            "session_record": bool(self._song.session_record),
            "record_mode": bool(self._song.record_mode),
            "back_to_arranger": bool(getattr(self._song, "back_to_arranger", False)),
            "playing_clips": playing_clips,
        }
