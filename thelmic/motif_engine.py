"""Thelmic v1.02 descriptive motif tracking.

The motif engine is rules-only in this phase. It observes final events and
reports motif structure; it does not generate, mutate, add, remove, or reorder
events.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Sequence

from thelmic.bank_generator import MIDIEvent
from thelmic.note_generation_chain import BANK_STEPS


VERSION = "v1.0"
RULE_SOURCE = "musical_rules.md"


class MotifType(str, Enum):
    PERCUSSIVE_PATTERN = "percussive pattern motif"
    HOOK = "hook motif"
    CALL_RESPONSE = "call/response motif"
    GRID_REMINDER = "drop-prep anchor-tightening motif"


class MutationClassification(str, Enum):
    LEGAL = "legal"
    STRUCTURAL = "structural"


@dataclass(frozen=True)
class Motif:
    id: str
    type: MotifType
    instrument: str
    phrase_start: int
    phrase_end: int
    event_references: tuple[str, ...]
    state: str = "observed"
    version: str = VERSION

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "instrument": self.instrument,
            "phrase_start": self.phrase_start,
            "phrase_end": self.phrase_end,
            "event_references": list(self.event_references),
            "state": self.state,
            "version": self.version,
            "rule_source": RULE_SOURCE,
        }


@dataclass(frozen=True)
class MotifMutationValidation:
    classification: MutationClassification
    added_count: int
    removed_count: int
    changed_count: int
    change_ratio: float
    reason: str

    @property
    def is_legal(self) -> bool:
        return self.classification == MutationClassification.LEGAL

    @property
    def is_structural(self) -> bool:
        return self.classification == MutationClassification.STRUCTURAL


def motifs_for_events(events: Sequence[MIDIEvent]) -> tuple[Motif, ...]:
    """Describe motifs present in final output.

    This is intentionally a projection over final events. It does not feed back
    into generation or resolution.
    """

    active = tuple(event for event in events if getattr(event, "active", True))
    motifs: list[Motif] = []
    for lane in sorted({event.layer for event in active}):
        lane_events = tuple(event for event in active if event.layer == lane)
        motif_type = (
            MotifType.GRID_REMINDER
            if lane == "hat" and any(event.role == "grid_reminder" for event in lane_events)
            else MotifType.PERCUSSIVE_PATTERN
        )
        motifs.append(
            Motif(
                id=f"v1.02:{lane}:phrase:0",
                type=motif_type,
                instrument=lane,
                phrase_start=0,
                phrase_end=BANK_STEPS,
                event_references=tuple(_event_ref(event) for event in lane_events),
            )
        )
    return tuple(motifs)


def empty_future_motifs() -> tuple[Motif, ...]:
    """Expose planned motif categories without creating behaviour."""

    return (
        Motif(
            id="v1.02:hook:future",
            type=MotifType.HOOK,
            instrument="hook",
            phrase_start=0,
            phrase_end=BANK_STEPS,
            event_references=(),
            state="declared_future",
        ),
        Motif(
            id="v1.02:call_response:future",
            type=MotifType.CALL_RESPONSE,
            instrument="call_response",
            phrase_start=0,
            phrase_end=BANK_STEPS,
            event_references=(),
            state="declared_future",
        ),
    )


def validate_motif_contract(motifs: Iterable[Motif]) -> None:
    for motif in motifs:
        if motif.version != VERSION:
            raise ValueError(f"motif version mismatch: {motif.id}")
        if motif.phrase_end - motif.phrase_start < BANK_STEPS:
            raise ValueError(f"motif does not persist for one phrase: {motif.id}")
        if motif.state not in {"observed", "declared_future"}:
            raise ValueError(f"unsupported motif state: {motif.id}")


def classify_motif_change(
    before: Motif,
    after_event_references: Sequence[str],
) -> MotifMutationValidation:
    """Classify a proposed motif reference change without applying it.

    The rules come from ``musical_rules.md``: add/remove one event or <=20%
    event replacement is legal mutation; anything larger is structural.
    """

    before_refs = tuple(before.event_references)
    after_refs = tuple(after_event_references)
    before_set = set(before_refs)
    after_set = set(after_refs)

    added_count = len(after_set - before_set)
    removed_count = len(before_set - after_set)
    same_length = len(before_refs) == len(after_refs)
    changed_count = (
        sum(1 for previous, current in zip(before_refs, after_refs) if previous != current)
        if same_length
        else 0
    )
    change_ratio = changed_count / max(1, len(before_refs))

    if same_length:
        if change_ratio > 0.20:
            return MotifMutationValidation(
                classification=MutationClassification.STRUCTURAL,
                added_count=added_count,
                removed_count=removed_count,
                changed_count=changed_count,
                change_ratio=change_ratio,
                reason="change_ratio_above_20_percent",
            )

        return MotifMutationValidation(
            classification=MutationClassification.LEGAL,
            added_count=added_count,
            removed_count=removed_count,
            changed_count=changed_count,
            change_ratio=change_ratio,
            reason="change_ratio_within_20_percent",
        )

    if added_count > 1 or removed_count > 1:
        return MotifMutationValidation(
            classification=MutationClassification.STRUCTURAL,
            added_count=added_count,
            removed_count=removed_count,
            changed_count=changed_count,
            change_ratio=change_ratio,
            reason="add_remove_more_than_one_event",
        )

    return MotifMutationValidation(
        classification=MutationClassification.LEGAL,
        added_count=added_count,
        removed_count=removed_count,
        changed_count=changed_count,
        change_ratio=change_ratio,
        reason="single_event_add_or_remove",
    )


def validate_motif_change_boundary(
    validation: MotifMutationValidation,
    *,
    is_drop: bool,
) -> None:
    """Reject structural motif changes outside the drop boundary."""

    if validation.is_structural and not is_drop:
        raise ValueError("structural motif change rejected outside drop boundary")


def _event_ref(event: MIDIEvent) -> str:
    return event.resolved_event_id or event.intent_id
