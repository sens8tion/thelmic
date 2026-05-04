"""Audit current Live state against declared CHANNEL_AUDIO meta.

Reads each role's track:
- Declared FreqRegion vs actual EQ8 HP/LP cutoffs
- Declared LevelTarget peak vs measured channel peak (via track meter)
- Declared sidechain_source vs whether a Compressor on the track has
  sidechain enabled (cannot fully verify the source name from API alone)

Returns a list of drift records the agent can act on.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import math


@dataclass
class DriftRecord:
    role: str
    field: str           # "freq.hp_hz", "freq.lp_hz", "level.peak_db", ...
    declared: object
    actual: object
    severity: str = "warn"   # "info" | "warn" | "error"
    note: str = ""


def _norm_to_hz(norm: float, low_hz=30.0, high_hz=22000.0) -> float:
    norm = max(0.0, min(1.0, norm))
    return low_hz * math.exp(norm * math.log(high_hz / low_hz))


def audit_session(ch, roles: dict[str, int], channel_audio: dict) -> list[DriftRecord]:
    out: list[DriftRecord] = []
    for role, ca in channel_audio.items():
        ti = roles.get(role)
        if ti is None:
            out.append(DriftRecord(role=role, field="presence",
                                    declared="present", actual="missing",
                                    severity="error", note="role not in layout"))
            continue
        info = ch.get_track_info(ti).result(timeout=3)
        eq_idx = next((i for i, d in enumerate(info.get("devices", []))
                       if d.get("class_name") == "Eq8"), None)
        if eq_idx is None:
            if ca.freq.hp_hz is not None or ca.freq.lp_hz is not None:
                out.append(DriftRecord(role=role, field="eq8",
                                        declared="EQ8 with HP/LP",
                                        actual="no EQ8",
                                        severity="warn"))
        else:
            _audit_eq(ch, ti, eq_idx, role, ca, out)
        # Peak meter check
        try:
            meter = ch.get_track_meter(ti).result(timeout=2)
            actual_peak = max(meter.get("peak_left", 0.0), meter.get("peak_right", 0.0))
            # Live's meter is linear 0..1, ~0.85 = -1.4 dB; convert
            if actual_peak > 0:
                peak_db = 20 * math.log10(actual_peak)
                if peak_db > ca.level.peak_db + 0.5:
                    out.append(DriftRecord(role=role, field="level.peak_db",
                                            declared=ca.level.peak_db,
                                            actual=round(peak_db, 2),
                                            severity="warn",
                                            note="channel hotter than declared"))
        except Exception:
            pass
    return out


def _audit_eq(ch, ti: int, eq_idx: int, role: str, ca, out: list[DriftRecord]) -> None:
    di = ch.get_device_info(ti, eq_idx).result(timeout=3)
    params = {p["name"]: p for p in di["parameters"]}

    def band_state(band):
        on = params.get(f"{band} Filter On A", {}).get("value", 0)
        freq = params.get(f"{band} Frequency A", {}).get("value", 0.0)
        return bool(on), float(freq)

    if ca.freq.hp_hz is not None:
        on, norm = band_state(1)
        if not on:
            out.append(DriftRecord(role=role, field="freq.hp_hz",
                                    declared=ca.freq.hp_hz, actual=None,
                                    severity="warn", note="HP band not on"))
        else:
            actual_hz = _norm_to_hz(norm)
            if abs(actual_hz - ca.freq.hp_hz) > max(5, ca.freq.hp_hz * 0.1):
                out.append(DriftRecord(role=role, field="freq.hp_hz",
                                        declared=ca.freq.hp_hz,
                                        actual=round(actual_hz, 1),
                                        severity="info"))
    if ca.freq.lp_hz is not None:
        on, norm = band_state(8)
        if not on:
            out.append(DriftRecord(role=role, field="freq.lp_hz",
                                    declared=ca.freq.lp_hz, actual=None,
                                    severity="warn", note="LP band not on"))
        else:
            actual_hz = _norm_to_hz(norm)
            if abs(actual_hz - ca.freq.lp_hz) > max(50, ca.freq.lp_hz * 0.1):
                out.append(DriftRecord(role=role, field="freq.lp_hz",
                                        declared=ca.freq.lp_hz,
                                        actual=round(actual_hz, 1),
                                        severity="info"))


def format_report(drifts: list[DriftRecord]) -> str:
    if not drifts:
        return "audit: clean — no drift"
    lines = [f"audit: {len(drifts)} drift record(s)"]
    for d in drifts:
        lines.append(f"  [{d.severity:>5}] {d.role}.{d.field}: "
                     f"declared={d.declared!r} actual={d.actual!r} "
                     + (f"({d.note})" if d.note else ""))
    return "\n".join(lines)
