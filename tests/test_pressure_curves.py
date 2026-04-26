"""Tests for pressure curve evaluation and engine."""

import math
import pytest
from thelmic.pressure_curves import evaluate, PressureCurve, CurveEngine, _shape_t


# ── Shape evaluation ────────────────────────────────────────────────────────

class TestShapes:
    def test_linear_midpoint(self):
        assert _shape_t("linear", 0.5) == pytest.approx(0.5)

    def test_linear_endpoints(self):
        assert _shape_t("linear", 0.0) == pytest.approx(0.0)
        assert _shape_t("linear", 1.0) == pytest.approx(1.0)

    def test_accelerating_slow_start(self):
        # At t=0.5, accelerating should be below 0.5 (concave)
        assert _shape_t("accelerating", 0.5) < 0.5

    def test_decelerating_fast_start(self):
        # At t=0.5, decelerating should be above 0.5 (convex)
        assert _shape_t("decelerating", 0.5) > 0.5

    def test_sinusoidal_midpoint_is_peak(self):
        assert _shape_t("sinusoidal", 0.5) == pytest.approx(1.0, abs=1e-6)

    def test_sinusoidal_endpoints_zero(self):
        assert _shape_t("sinusoidal", 0.0) == pytest.approx(0.0, abs=1e-6)
        assert _shape_t("sinusoidal", 1.0) == pytest.approx(0.0, abs=1e-6)

    def test_step_holds_until_end(self):
        assert _shape_t("step", 0.0) == 0.0
        assert _shape_t("step", 0.5) == 0.0
        assert _shape_t("step", 0.99) == 0.0
        assert _shape_t("step", 1.0) == 1.0

    def test_clamps_input(self):
        assert _shape_t("linear", -0.5) == pytest.approx(0.0)
        assert _shape_t("linear", 1.5)  == pytest.approx(1.0)


# ── Curve evaluation ─────────────────────────────────────────────────────────

class TestEvaluate:
    def _curve(self, shape="linear", bars=8, fv=0.0, tv=1.0):
        return PressureCurve(id=1, shape=shape, bars=bars,
                             from_value=fv, to_value=tv, target="ghost_inject")

    def test_start_at_from_value(self):
        c = self._curve(fv=0.2, tv=0.8)
        assert evaluate(c, 0.0) == pytest.approx(0.2)

    def test_end_at_to_value(self):
        c = self._curve(fv=0.2, tv=0.8)
        assert evaluate(c, 1.0) == pytest.approx(0.8)

    def test_midpoint_linear(self):
        c = self._curve(fv=0.0, tv=1.0)
        assert evaluate(c, 0.5) == pytest.approx(0.5)

    def test_descending_curve(self):
        c = self._curve(fv=1.0, tv=0.0)
        assert evaluate(c, 0.5) == pytest.approx(0.5)
        assert evaluate(c, 1.0) == pytest.approx(0.0)


# ── CurveEngine ──────────────────────────────────────────────────────────────

class TestCurveEngine:
    def test_add_and_start(self):
        eng = CurveEngine()
        cid = eng.add("linear", 8, 0.0, 1.0, "ghost_inject")
        assert eng.current_value("ghost_inject") is None
        eng.start(cid)
        assert eng.current_value("ghost_inject") == pytest.approx(0.0)

    def test_advance_updates_value(self):
        eng = CurveEngine()
        cid = eng.add("linear", 8, 0.0, 1.0, "ghost_inject")
        eng.start(cid)
        eng.advance(bars=4)
        assert eng.current_value("ghost_inject") == pytest.approx(0.5)

    def test_curve_completes_and_stops(self):
        eng = CurveEngine()
        cid = eng.add("linear", 4, 0.0, 1.0, "ghost_inject")
        eng.start(cid)
        eng.advance(bars=4)
        assert eng.current_value("ghost_inject") is None

    def test_loop_restarts(self):
        eng = CurveEngine()
        cid = eng.add("linear", 4, 0.0, 1.0, "ghost_inject", loop=True)
        eng.start(cid)
        eng.advance(bars=4)
        # Should have restarted
        assert eng.current_value("ghost_inject") == pytest.approx(0.0, abs=0.1)

    def test_chain(self):
        eng = CurveEngine()
        cid2 = eng.add("linear", 4, 0.5, 1.0, "cc:0:74")
        cid1 = eng.add("linear", 4, 0.0, 0.5, "cc:0:74", next_id=cid2)
        eng.start(cid1)
        eng.advance(bars=4)   # first curve completes → second starts
        # Second curve just started → value = from_value of second = 0.5
        assert eng.current_value("cc:0:74") == pytest.approx(0.5, abs=0.05)

    def test_deformer_target_allows_only_one_curve(self):
        eng = CurveEngine()
        first = eng.add("linear", 8, 0.0, 1.0, "ghost_inject")
        second = eng.add("step", 2, 1.0, 0.0, "ghost_inject")
        state = eng.state_dict()
        curves_for_target = [c for c in state["curves"] if c["target"] == "ghost_inject"]
        assert second == first
        assert len(curves_for_target) == 1

    def test_cc_target_allows_multiple_curves(self):
        eng = CurveEngine()
        first = eng.add("linear", 8, 0.0, 1.0, "cc:0:74")
        second = eng.add("step", 2, 1.0, 0.0, "cc:0:74")
        assert second != first

    def test_overrides_returns_active(self):
        eng = CurveEngine()
        cid = eng.add("linear", 8, 0.3, 0.7, "ghost_inject")
        eng.start(cid)
        overrides = eng.overrides()
        assert "ghost_inject" in overrides
        assert 0.3 <= overrides["ghost_inject"] <= 0.7

    def test_projected_overrides_look_ahead_without_advancing(self):
        eng = CurveEngine()
        cid = eng.add("linear", 8, 0.0, 1.0, "ghost_inject")
        eng.start(cid)
        assert eng.overrides()["ghost_inject"] == pytest.approx(0.0)
        assert eng.projected_overrides(4)["ghost_inject"] == pytest.approx(0.5)
        assert eng.overrides()["ghost_inject"] == pytest.approx(0.0)

    def test_remove_stops_curve(self):
        eng = CurveEngine()
        cid = eng.add("linear", 8, 0.0, 1.0, "ghost_inject")
        eng.start(cid)
        eng.remove(cid)
        assert eng.current_value("ghost_inject") is None

    def test_cc_output_on_advance(self):
        eng = CurveEngine()
        cid = eng.add("linear", 4, 0.0, 1.0, "cc:0:74")
        eng.start(cid)
        outputs = eng.advance(bars=2)
        assert len(outputs) == 1
        target, cc_num, val = outputs[0]
        assert cc_num == 74
        assert val == pytest.approx(0.5)
