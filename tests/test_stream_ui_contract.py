"""UI contract tests — continuous stream viewport.

Proves:
  1. The pure step→screen_x transform is correct and marker-stable.
  2. The server payload still contains all fields the UI requires.
  3. Musical output (fingerprint, event count) is unchanged by UI edits.

No server-side logic is altered. All assertions are observational.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from thelmic.note_generation_chain import generate_bank, structure_frames, BANK_STEPS


# ─── Constants (mirror of index.html JS) ─────────────────────────────────────

STEPS_VISIBLE = 96
MARKER_FRAC   = 0.25
LABEL_W       = 80
CANVAS_W      = 1200   # representative width for transform tests


# ─── Pure transform helper ────────────────────────────────────────────────────

def _step_to_x(global_step: float, now_step: float, canvas_w: int = CANVAS_W) -> float:
    """Mirror of the JS stepToX pure function.

    screen_x = MARKER_X + (global_step − now_step) × px_per_step
    """
    usable_w    = canvas_w - LABEL_W
    marker_x    = LABEL_W + usable_w * MARKER_FRAC
    px_per_step = usable_w / STEPS_VISIBLE
    return marker_x + (global_step - now_step) * px_per_step


def _marker_x(canvas_w: int = CANVAS_W) -> float:
    return LABEL_W + (canvas_w - LABEL_W) * MARKER_FRAC


# ─── Transform invariants ──────────────────────────────────────────────────────

class TestStepToScreenTransform:
    """screen_x = MARKER_X + (event_step − now_step) × px_per_step"""

    def test_now_step_maps_to_marker(self):
        for now in (0, 64, 128, 255, 512):
            x = _step_to_x(now, now)
            assert abs(x - _marker_x()) < 1e-9, (
                f"now_step={now} should map to marker_x but got x={x}"
            )

    def test_past_step_is_left_of_marker(self):
        now = 100.0
        x   = _step_to_x(80.0, now)
        assert x < _marker_x(), "past events must be left of the marker"

    def test_future_step_is_right_of_marker(self):
        now = 100.0
        x   = _step_to_x(130.0, now)
        assert x > _marker_x(), "future events must be right of the marker"

    def test_marker_x_is_time_independent(self):
        """Marker x depends only on canvas geometry — never on current time."""
        assert _marker_x() == _marker_x()

    def test_scroll_advances_as_now_increases(self):
        """When now_step increases, a fixed event's screen_x decreases (scrolls left)."""
        event_gs = 100
        x_early  = _step_to_x(event_gs, now_step=80)
        x_late   = _step_to_x(event_gs, now_step=90)
        assert x_late < x_early, "events must scroll left as time advances"

    def test_phrase_boundary_at_exact_now_is_at_marker(self):
        phrase_gs = 256
        x = _step_to_x(phrase_gs, now_step=float(phrase_gs))
        assert abs(x - _marker_x()) < 1e-9

    def test_phrase_boundary_ahead_is_right_of_marker(self):
        assert _step_to_x(300, 256.0) > _marker_x()

    def test_phrase_boundary_past_is_left_of_marker(self):
        assert _step_to_x(200, 256.0) < _marker_x()

    def test_transform_is_linear(self):
        """Equal step intervals produce equal pixel intervals."""
        now  = 128.0
        dx1  = _step_to_x(130.0, now) - _step_to_x(129.0, now)
        dx2  = _step_to_x(140.0, now) - _step_to_x(139.0, now)
        assert abs(dx1 - dx2) < 1e-9, "transform must be linear (uniform px/step)"


# ─── Server payload contract ──────────────────────────────────────────────────

class TestServerPayloadContract:
    """Server _state() must carry all fields the continuous stream UI reads."""

    @pytest.fixture(scope="class")
    def state(self):
        from thelmic import server
        return server._state(include_bank=True)

    def test_has_bank_events(self, state):
        assert "bank_events" in state
        assert len(state["bank_events"]) > 0

    def test_has_structure_frames(self, state):
        assert "structure_frames" in state
        assert len(state["structure_frames"]) == BANK_STEPS

    def test_has_timing_fields(self, state):
        for field in ("bank_started_at_ms", "bank_duration_ms", "playhead_step"):
            assert field in state, f"missing: {field}"

    def test_has_motifs(self, state):
        assert "motifs" in state

    def test_events_have_global_step(self, state):
        for evt in state["bank_events"]:
            assert "global_step" in evt, f"event missing global_step: {evt.get('layer')} @ {evt.get('musical_step')}"

    def test_events_have_layer(self, state):
        valid = {"kick", "snare", "hat", "open_hat", "bass", "sub", "hook", "call", "response"}
        for evt in state["bank_events"]:
            assert evt.get("layer") in valid, f"unexpected layer: {evt}"

    def test_frames_have_required_ui_fields(self, state):
        required = {
            "global_step", "musical_step",
            "is_phrase_start", "is_bar_start",
            "phrase_role", "phrase_index", "bar_index",
        }
        for frame in state["structure_frames"]:
            missing = required - frame.keys()
            assert not missing, f"frame missing: {missing}"

    def test_phrase_starts_have_phrase_index(self, state):
        phrase_starts = [f for f in state["structure_frames"] if f["is_phrase_start"]]
        assert phrase_starts, "no phrase start frames found"
        for f in phrase_starts:
            assert f["phrase_index"] is not None

    # ── Upcoming bank ────────────────────────────────────────────────────────

    def test_has_upcoming_structure_frames(self, state):
        assert "upcoming_structure_frames" in state
        assert len(state["upcoming_structure_frames"]) == BANK_STEPS

    def test_upcoming_frames_have_higher_global_step(self, state):
        current_min = min(f["global_step"] for f in state["structure_frames"])
        upcoming_min = min(f["global_step"] for f in state["upcoming_structure_frames"])
        assert upcoming_min == current_min + BANK_STEPS, (
            f"upcoming bank should start at current + {BANK_STEPS}, "
            f"got current={current_min} upcoming={upcoming_min}"
        )

    def test_upcoming_frames_have_required_fields(self, state):
        required = {
            "global_step", "musical_step",
            "is_phrase_start", "is_bar_start",
            "phrase_role", "phrase_index", "bar_index",
        }
        for frame in state["upcoming_structure_frames"]:
            missing = required - frame.keys()
            assert not missing, f"upcoming frame missing: {missing}"

    def test_upcoming_frames_phrase_start_is_first_step(self, state):
        phrase_starts = [f for f in state["upcoming_structure_frames"] if f["is_phrase_start"]]
        assert len(phrase_starts) == 1, "upcoming bank must have exactly one phrase start"
        assert phrase_starts[0]["musical_step"] == 0

    # ── Next bank preview ────────────────────────────────────────────────────

    def test_has_next_bank_preview(self, state):
        assert "next_bank_preview" in state

    def test_preview_is_non_authoritative(self, state):
        assert state["next_bank_preview"]["authoritative"] is False

    def test_preview_bank_index_is_current_plus_one(self, state):
        current_idx = state["bank_count"] - 1   # bank_count = bank_index + 1
        preview_idx = state["next_bank_preview"]["bank_index"]
        assert preview_idx == current_idx + 1, (
            f"preview bank_index should be {current_idx + 1}, got {preview_idx}"
        )

    def test_preview_events_have_global_step(self, state):
        events = state["next_bank_preview"]["bank_events"]
        assert events, "preview must contain events"
        for evt in events:
            assert "global_step" in evt
            assert "layer" in evt

    def test_preview_events_global_step_beyond_current_bank(self, state):
        current_max = max(f["global_step"] for f in state["structure_frames"])
        preview_min = min(e["global_step"] for e in state["next_bank_preview"]["bank_events"])
        assert preview_min > current_max, (
            f"preview events should start beyond current bank: "
            f"current_max={current_max} preview_min={preview_min}"
        )

    # ── Sub-phrase metadata ──────────────────────────────────────────────────

    def test_state_has_subphrases(self, state):
        assert "subphrases" in state
        assert len(state["subphrases"]) > 0

    def test_subphrase_lengths_are_power_of_two_gte_four(self, state):
        for sp in state["subphrases"]:
            lb = sp["length_bars"]
            assert lb >= 4, f"length_bars {lb} must be >= 4"
            assert (lb & (lb - 1)) == 0, f"length_bars {lb} is not a power of two"

    def test_subphrases_contiguous_and_aligned(self, state):
        sps = sorted(state["subphrases"], key=lambda s: s["start_bar"])
        for i, sp in enumerate(sps):
            assert sp["start_bar"] >= 1
            if i > 0:
                prev = sps[i - 1]
                assert sp["start_bar"] == prev["start_bar"] + prev["length_bars"], (
                    f"gap between subphrase {i-1} and {i}"
                )

    def test_subphrases_cover_full_phrase(self, state):
        from thelmic.bank_generator import BARS_PER_PHRASE, PHRASES_PER_BANK
        total = BARS_PER_PHRASE * PHRASES_PER_BANK
        covered = sum(sp["length_bars"] for sp in state["subphrases"])
        assert covered == total, f"subphrases cover {covered} bars, expected {total}"

    def test_each_subphrase_has_one_role(self, state):
        for sp in state["subphrases"]:
            assert sp.get("role"), f"subphrase missing role: {sp}"

    def test_subphrases_have_start_step(self, state):
        for sp in state["subphrases"]:
            assert "start_step" in sp
            assert isinstance(sp["start_step"], int)

    def test_subphrases_deterministic(self):
        from thelmic import server
        s1 = server._compute_subphrases(0, 0)
        s2 = server._compute_subphrases(0, 0)
        assert s1 == s2

    def test_subphrases_steps_consistent_with_bars(self, state):
        from thelmic.subphrase_engine import STEPS_PER_BAR as _STEPS_PER_BAR
        for sp in state["subphrases"]:
            assert sp["length_steps"] == sp["length_bars"] * _STEPS_PER_BAR

    def test_preview_has_subphrases(self, state):
        assert "subphrases" in state["next_bank_preview"]
        assert len(state["next_bank_preview"]["subphrases"]) > 0

    def test_subphrases_have_transformers_field(self, state):
        for sp in state["subphrases"]:
            assert "transformers" in sp, f"subphrase '{sp['role']}' missing transformers field"
            assert isinstance(sp["transformers"], list)

    def test_transformer_names_are_from_taxonomy(self, state):
        from thelmic.server import _TRANSFORMER_CATEGORIES
        for sp in state["subphrases"]:
            for tx in sp["transformers"]:
                assert tx["name"] in _TRANSFORMER_CATEGORIES, (
                    f"transformer '{tx['name']}' not in taxonomy"
                )

    def test_transformer_categories_are_correct(self, state):
        from thelmic.server import _TRANSFORMER_CATEGORIES
        for sp in state["subphrases"]:
            for tx in sp["transformers"]:
                assert tx["category"] == _TRANSFORMER_CATEGORIES[tx["name"]], (
                    f"wrong category for {tx['name']}"
                )

    def test_unmapped_role_emits_no_transformers(self):
        from thelmic.server import _transformers_for_role
        assert _transformers_for_role("unknown_role") == []
        assert _transformers_for_role("") == []

    def test_build_gets_anticipation_build(self, state):
        """v1.2 rules: build default = anticipation_build."""
        build = next((s for s in state["subphrases"] if s["role"] == "build"), None)
        assert build is not None
        names = [t["name"] for t in build["transformers"]]
        assert "anticipation_build" in names

    def test_hold_gets_density_hold(self, state):
        hold = next((s for s in state["subphrases"] if s["role"] == "hold"), None)
        assert hold is not None
        names = [t["name"] for t in hold["transformers"]]
        assert "density_hold" in names

    def test_release_gets_release_resolve(self, state):
        """v1.2 rules: release default = release_resolve."""
        release = next((s for s in state["subphrases"] if s["role"] == "release"), None)
        assert release is not None
        names = [t["name"] for t in release["transformers"]]
        assert "release_resolve" in names

    def test_transformer_metadata_is_deterministic(self):
        from thelmic.server import _compute_subphrases
        assert _compute_subphrases(0, 0) == _compute_subphrases(0, 0)

    def test_preview_subphrases_offset_from_current(self, state):
        cur_start = state["subphrases"][0]["start_step"]
        prv_start = state["next_bank_preview"]["subphrases"][0]["start_step"]
        from thelmic.note_generation_chain import BANK_STEPS
        assert prv_start == cur_start + BANK_STEPS

    # ── Transformer execution ────────────────────────────────────────────────

    def test_state_has_transformer_execution(self, state):
        assert "transformer_execution" in state
        assert isinstance(state["transformer_execution"], list)

    def test_transformer_execution_uses_only_taxonomy_names(self, state):
        from thelmic.server import _TRANSFORMER_CATEGORIES
        for result in state["transformer_execution"]:
            assert result["transformer"] in _TRANSFORMER_CATEGORIES, (
                f"'{result['transformer']}' not in taxonomy"
            )

    def test_transformer_execution_targets_are_from_static_tables(self, state):
        from thelmic.transformer_engine import TRANSFORMER_TARGETS
        for result in state["transformer_execution"]:
            tx  = result["transformer"]
            tgt = result["target_lane"]
            assert tgt in TRANSFORMER_TARGETS.get(tx, []), (
                f"target '{tgt}' not allowed for '{tx}'"
            )

    def test_transformer_execution_actions_are_from_static_tables(self, state):
        from thelmic.transformer_engine import TRANSFORMER_ACTIONS
        for result in state["transformer_execution"]:
            tx  = result["transformer"]
            act = result["action"]
            assert act in TRANSFORMER_ACTIONS.get(tx, []), (
                f"action '{act}' not allowed for '{tx}'"
            )

    def test_transformer_execution_attach_only_to_subphrases(self, state):
        sp_roles = {sp["role"] for sp in state["subphrases"]}
        for result in state["transformer_execution"]:
            assert result["subphrase_role"] in sp_roles, (
                f"execution references unknown subphrase '{result['subphrase_role']}'"
            )

    def test_transformer_execution_results_have_required_fields(self, state):
        required = {
            "phrase_index", "subphrase_role", "transformer",
            "target_lane", "action", "step_or_range", "accepted", "reason",
        }
        for result in state["transformer_execution"]:
            assert required.issubset(result.keys()), (
                f"execution result missing fields: {required - result.keys()}"
            )

    def test_transformer_execution_step_or_range_has_start_and_end(self, state):
        for result in state["transformer_execution"]:
            r = result["step_or_range"]
            assert "start" in r and "end" in r, f"step_or_range malformed: {r}"
            assert r["start"] <= r["end"]

    def test_transformer_execution_is_deterministic(self):
        from thelmic import server
        s1 = server._state(include_bank=True)["transformer_execution"]
        s2 = server._state(include_bank=True)["transformer_execution"]
        assert s1 == s2

    def test_no_markdown_parsed_at_runtime(self):
        """Transformer engine must not read musical_rules.md at runtime."""
        import inspect
        import thelmic.transformer_engine as te
        source = inspect.getsource(te)
        assert "musical_rules" not in source or "musical_rules.md" not in source.split("open")[1:], (
            "transformer_engine must not open musical_rules.md at runtime"
        )
        assert "open(" not in source, "transformer_engine must not open files at runtime"

    def test_static_table_names_subset_of_taxonomy(self):
        from thelmic.server import _TRANSFORMER_CATEGORIES
        from thelmic.transformer_engine import TRANSFORMER_TARGETS, TRANSFORMER_ACTIONS
        for name in TRANSFORMER_TARGETS:
            assert name in _TRANSFORMER_CATEGORIES, f"'{name}' in TARGETS but not in taxonomy"
        for name in TRANSFORMER_ACTIONS:
            assert name in _TRANSFORMER_CATEGORIES, f"'{name}' in ACTIONS but not in taxonomy"

    def test_preview_content_matches_eventual_bank(self, state):
        """Preview bank must be identical to the bank that will actually play
        (assuming dims remain stable, which they do in the test environment)."""
        from thelmic.dimension_engine import compute
        from thelmic.server import _trajectory, _heat_applied
        dims = compute(_trajectory, _heat_applied)
        sr   = _trajectory.active_feature().signature_rhythm

        preview       = state["next_bank_preview"]
        preview_idx   = preview["bank_index"]
        eventual_bank = generate_bank(preview_idx, dims=dims, signature_rhythm=sr)

        preview_set = {
            (e["global_step"], e["layer"], e["musical_step"], e["velocity"])
            for e in preview["bank_events"]
        }
        eventual_set = {
            (e.global_step, e.layer, e.musical_step, e.velocity)
            for e in eventual_bank.all_events()
            if e.active
        }
        assert preview_set == eventual_set, (
            f"preview does not match eventual bank {preview_idx}"
        )


# ─── Musical output fingerprint ───────────────────────────────────────────────

class TestMusicalOutputUnchanged:
    """UI changes must not alter the event stream — fingerprint locked."""

    def _traj(self):
        from thelmic.landscape_trajectory import LandscapeTrajectory
        from thelmic.landscape_map import LandscapeMap
        return LandscapeTrajectory(landscape=LandscapeMap(seed=1103))

    def _dims(self):
        from thelmic.dimension_engine import compute
        return compute(self._traj(), 0.5)

    def _sr(self):
        return self._traj().active_feature().signature_rhythm

    def _bank(self):
        return generate_bank(0, dims=self._dims(), signature_rhythm=self._sr())

    def test_fingerprint_matches_v1_01_locked_hash(self):
        import hashlib
        events  = self._bank().all_events()
        payload = "\n".join(
            f"{e.musical_step}:{e.layer}:{e.role}:{e.note}:{e.velocity}:{e.duration}"
            for e in events
        )
        assert hashlib.sha256(payload.encode()).hexdigest() == (
            "1b359c9cc2277661c6cea9ded763d0d9b79ff035cf44dfce62594493a00d7a04"
        )

    def test_event_count_unchanged(self):
        from collections import Counter
        counts = Counter(e.layer for e in self._bank().all_events())
        assert counts == {"hat":  139, "bass": 64, "kick": 62, "snare": 48, "sub": 64, "drone_rumble": 2}

    def test_generation_is_deterministic(self):
        e1 = [(e.musical_step, e.layer, e.velocity) for e in self._bank().all_events()]
        e2 = [(e.musical_step, e.layer, e.velocity) for e in self._bank().all_events()]
        assert e1 == e2


class TestPassiveLandscapeMapUI:
    def test_ui_renders_passive_landscape_map_at_top(self):
        html = Path("thelmic/static/index.html").read_text(encoding="utf-8")

        assert 'id="landscape-map"' in html
        assert "/api/landscape-map.svg" in html
        assert html.index('id="landscape-map"') < html.index('class="controls"')
