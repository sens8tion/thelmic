"""Formal phrase boundary model.

Phase 1 contract:
- define stable phrase and sub-phrase boundaries
- expose deterministic cursor/indexing logic
- do not drive existing generators yet
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Optional


ALLOWED_SUB_PHRASE_BARS = (4, 8, 16)
DEFAULT_SUB_PHRASE_BARS = 8


class PhraseRole(str, Enum):
    INTRO = "intro"
    GROOVE = "groove"
    HOOK = "hook"
    CALL = "call"
    RESPONSE = "response"
    BUILD = "build"
    PRE_DROP = "pre_drop"
    DROP = "drop"
    RECOVERY = "recovery"
    TRANSITION = "transition"


class PhraseMode(str, Enum):
    HOOK_MODE = "HOOK_MODE"
    CALL_RESPONSE_MODE = "CALL_RESPONSE_MODE"


class SubPhraseRole(str, Enum):
    SETUP = "setup"
    STATEMENT = "statement"
    ANSWER = "answer"
    WITHHOLDING = "withholding"
    TRANSFORMATION = "transformation"
    RELEASE = "release"
    RESET = "reset"


@dataclass(frozen=True)
class TransformerSpec:
    target: str
    source_signature: str = ""
    destination_bias: str = ""
    progress: float = 0.0

    @property
    def creates_events(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "target": self.target,
            "source_signature": self.source_signature,
            "destination_bias": self.destination_bias,
            "progress": round(max(0.0, min(1.0, self.progress)), 3),
            "creates_events": self.creates_events,
        }


@dataclass(frozen=True)
class ActiveConstraints:
    allow_hook: bool = False
    allow_call: bool = False
    allow_response: bool = False
    allow_bass: bool = True
    allow_stab: bool = True
    silence_protected: bool = False
    pre_drop_gap: bool = False
    drop_arrival: bool = False

    def to_dict(self) -> dict:
        return {
            "allow_hook": self.allow_hook,
            "allow_call": self.allow_call,
            "allow_response": self.allow_response,
            "allow_bass": self.allow_bass,
            "allow_stab": self.allow_stab,
            "silence_protected": self.silence_protected,
            "pre_drop_gap": self.pre_drop_gap,
            "drop_arrival": self.drop_arrival,
        }


@dataclass(frozen=True)
class SubPhrase:
    index: int
    start_bar: int
    length_bars: int
    role: SubPhraseRole
    constraints: ActiveConstraints
    transformer: Optional[TransformerSpec] = None

    @property
    def end_bar(self) -> int:
        return self.start_bar + self.length_bars - 1

    def contains_bar(self, bar: int) -> bool:
        return self.start_bar <= bar <= self.end_bar

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "start_bar": self.start_bar,
            "end_bar": self.end_bar,
            "length_bars": self.length_bars,
            "role": self.role.value,
            "constraints": self.constraints.to_dict(),
            "transformer": self.transformer.to_dict() if self.transformer else None,
        }


@dataclass(frozen=True)
class Phrase:
    index: int
    start_bar: int
    length_bars: int
    role: PhraseRole
    mode: PhraseMode
    constraints: ActiveConstraints
    sub_phrases: tuple[SubPhrase, ...] = field(default_factory=tuple)

    @property
    def end_bar(self) -> int:
        return self.start_bar + self.length_bars - 1

    def contains_bar(self, bar: int) -> bool:
        return self.start_bar <= bar <= self.end_bar

    def sub_phrase_at_bar(self, bar: int) -> SubPhrase:
        for sub_phrase in self.sub_phrases:
            if sub_phrase.contains_bar(bar):
                return sub_phrase
        raise ValueError(f"bar {bar} is outside phrase {self.index}")

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "start_bar": self.start_bar,
            "end_bar": self.end_bar,
            "length_bars": self.length_bars,
            "role": self.role.value,
            "mode": self.mode.value,
            "constraints": self.constraints.to_dict(),
            "sub_phrases": [sub_phrase.to_dict() for sub_phrase in self.sub_phrases],
        }


@dataclass(frozen=True)
class PhraseCursor:
    bar: int
    phrase_index: int
    phrase_start_bar: int
    phrase_end_bar: int
    phrase_bar: int
    phrase_progress: float
    phrase_role: PhraseRole
    phrase_mode: PhraseMode
    sub_phrase_index: int
    sub_phrase_start_bar: int
    sub_phrase_end_bar: int
    sub_phrase_bar: int
    sub_phrase_progress: float
    sub_phrase_role: SubPhraseRole
    constraints: ActiveConstraints
    transformer: Optional[TransformerSpec] = None

    def to_dict(self) -> dict:
        return {
            "bar": self.bar,
            "phrase_index": self.phrase_index,
            "phrase_start_bar": self.phrase_start_bar,
            "phrase_end_bar": self.phrase_end_bar,
            "phrase_bar": self.phrase_bar,
            "phrase_progress": round(self.phrase_progress, 3),
            "phrase_role": self.phrase_role.value,
            "phrase_mode": self.phrase_mode.value,
            "sub_phrase_index": self.sub_phrase_index,
            "sub_phrase_start_bar": self.sub_phrase_start_bar,
            "sub_phrase_end_bar": self.sub_phrase_end_bar,
            "sub_phrase_bar": self.sub_phrase_bar,
            "sub_phrase_progress": round(self.sub_phrase_progress, 3),
            "sub_phrase_role": self.sub_phrase_role.value,
            "constraints": self.constraints.to_dict(),
            "transformer": self.transformer.to_dict() if self.transformer else None,
        }


@dataclass(frozen=True)
class PhraseModel:
    phrases: tuple[Phrase, ...]

    def phrase_at_bar(self, bar: int) -> Phrase:
        for phrase in self.phrases:
            if phrase.contains_bar(bar):
                return phrase
        raise ValueError(f"bar {bar} is outside the phrase model")

    def cursor_at_bar(self, bar: int) -> PhraseCursor:
        phrase = self.phrase_at_bar(bar)
        sub_phrase = phrase.sub_phrase_at_bar(bar)
        phrase_bar = bar - phrase.start_bar + 1
        sub_phrase_bar = bar - sub_phrase.start_bar + 1
        return PhraseCursor(
            bar=bar,
            phrase_index=phrase.index,
            phrase_start_bar=phrase.start_bar,
            phrase_end_bar=phrase.end_bar,
            phrase_bar=phrase_bar,
            phrase_progress=_progress(phrase_bar, phrase.length_bars),
            phrase_role=phrase.role,
            phrase_mode=phrase.mode,
            sub_phrase_index=sub_phrase.index,
            sub_phrase_start_bar=sub_phrase.start_bar,
            sub_phrase_end_bar=sub_phrase.end_bar,
            sub_phrase_bar=sub_phrase_bar,
            sub_phrase_progress=_progress(sub_phrase_bar, sub_phrase.length_bars),
            sub_phrase_role=sub_phrase.role,
            constraints=sub_phrase.constraints,
            transformer=sub_phrase.transformer,
        )

    def to_dict(self) -> dict:
        return {"phrases": [phrase.to_dict() for phrase in self.phrases]}


def build_phrase_model(
    drop_bars: Iterable[int],
    total_bars: int,
    *,
    phrase_roles: Optional[Iterable[PhraseRole]] = None,
    phrase_modes: Optional[Iterable[PhraseMode]] = None,
    sub_phrase_bars: int = DEFAULT_SUB_PHRASE_BARS,
) -> PhraseModel:
    """Build a deterministic phrase model from committed drop bars.

    A drop bar is the first bar of a phrase. Each phrase ends immediately
    before the next drop, or at total_bars for the final phrase.
    """
    starts = _normalise_drop_bars(drop_bars, total_bars)
    roles = tuple(phrase_roles or _default_phrase_roles(len(starts)))
    modes = tuple(phrase_modes or _default_phrase_modes(len(starts)))
    if len(roles) != len(starts):
        raise ValueError("phrase_roles must match the number of phrases")
    if len(modes) != len(starts):
        raise ValueError("phrase_modes must match the number of phrases")
    if sub_phrase_bars not in ALLOWED_SUB_PHRASE_BARS:
        raise ValueError("sub_phrase_bars must be 4, 8, or 16")

    phrases: list[Phrase] = []
    for index, start in enumerate(starts):
        next_start = starts[index + 1] if index + 1 < len(starts) else total_bars + 1
        length = next_start - start
        if length <= 0:
            raise ValueError("drop bars must create positive phrase lengths")
        if length % min(ALLOWED_SUB_PHRASE_BARS) != 0:
            raise ValueError("phrase lengths must align to 4-bar boundaries")
        role = roles[index]
        mode = modes[index]
        phrase_constraints = _constraints_for(role, mode, SubPhraseRole.SETUP)
        phrases.append(
            Phrase(
                index=index,
                start_bar=start,
                length_bars=length,
                role=role,
                mode=mode,
                constraints=phrase_constraints,
                sub_phrases=_build_sub_phrases(start, length, role, mode, sub_phrase_bars),
            )
        )
    return PhraseModel(tuple(phrases))


def _normalise_drop_bars(drop_bars: Iterable[int], total_bars: int) -> tuple[int, ...]:
    if total_bars < 1:
        raise ValueError("total_bars must be positive")
    starts = tuple(sorted(set(int(bar) for bar in drop_bars)))
    if not starts:
        raise ValueError("at least one drop bar is required")
    if starts[0] < 1 or starts[-1] > total_bars:
        raise ValueError("drop bars must be inside the model range")
    return starts


def _default_phrase_roles(count: int) -> tuple[PhraseRole, ...]:
    template = (
        PhraseRole.GROOVE,
        PhraseRole.HOOK,
        PhraseRole.CALL,
        PhraseRole.RESPONSE,
        PhraseRole.BUILD,
        PhraseRole.PRE_DROP,
        PhraseRole.DROP,
        PhraseRole.RECOVERY,
        PhraseRole.TRANSITION,
    )
    return tuple(template[index % len(template)] for index in range(count))


def _default_phrase_modes(count: int) -> tuple[PhraseMode, ...]:
    return tuple(
        PhraseMode.HOOK_MODE if index % 2 == 0 else PhraseMode.CALL_RESPONSE_MODE
        for index in range(count)
    )


def _build_sub_phrases(
    phrase_start: int,
    phrase_length: int,
    phrase_role: PhraseRole,
    mode: PhraseMode,
    preferred_bars: int,
) -> tuple[SubPhrase, ...]:
    lengths = _split_sub_phrase_lengths(phrase_length, preferred_bars)
    sub_phrases: list[SubPhrase] = []
    current_bar = phrase_start
    for index, length in enumerate(lengths):
        role = _sub_phrase_role(index, len(lengths), phrase_role, mode)
        transformer = (
            TransformerSpec(target="phrase_signature", progress=0.0)
            if role == SubPhraseRole.TRANSFORMATION
            else None
        )
        sub_phrases.append(
            SubPhrase(
                index=index,
                start_bar=current_bar,
                length_bars=length,
                role=role,
                constraints=_constraints_for(phrase_role, mode, role),
                transformer=transformer,
            )
        )
        current_bar += length
    return tuple(sub_phrases)


def _split_sub_phrase_lengths(phrase_length: int, preferred_bars: int) -> tuple[int, ...]:
    if phrase_length % 4 != 0:
        raise ValueError("phrase length must align to 4-bar boundaries")
    lengths: list[int] = []
    remaining = phrase_length
    while remaining > 0:
        if remaining < preferred_bars:
            length = remaining
        elif remaining - preferred_bars in (0, 4, 8, 12) or remaining >= preferred_bars * 2:
            length = preferred_bars
        else:
            length = 4
        lengths.append(length)
        remaining -= length
    return tuple(lengths)


def _sub_phrase_role(
    index: int,
    count: int,
    phrase_role: PhraseRole,
    mode: PhraseMode,
) -> SubPhraseRole:
    if phrase_role == PhraseRole.PRE_DROP:
        return SubPhraseRole.WITHHOLDING if index == count - 1 else SubPhraseRole.TRANSFORMATION
    if phrase_role == PhraseRole.DROP:
        return SubPhraseRole.RESET if index == 0 else SubPhraseRole.RELEASE
    if index == 0:
        return SubPhraseRole.SETUP
    if index == count - 1:
        return SubPhraseRole.RELEASE
    if mode == PhraseMode.CALL_RESPONSE_MODE:
        return SubPhraseRole.ANSWER if index % 2 == 0 else SubPhraseRole.STATEMENT
    return SubPhraseRole.TRANSFORMATION


def _constraints_for(
    phrase_role: PhraseRole,
    mode: PhraseMode,
    sub_phrase_role: SubPhraseRole,
) -> ActiveConstraints:
    silence = phrase_role == PhraseRole.PRE_DROP or sub_phrase_role == SubPhraseRole.WITHHOLDING
    return ActiveConstraints(
        allow_hook=mode == PhraseMode.HOOK_MODE and not silence,
        allow_call=(
            mode == PhraseMode.CALL_RESPONSE_MODE
            and sub_phrase_role in {SubPhraseRole.STATEMENT, SubPhraseRole.TRANSFORMATION}
            and not silence
        ),
        allow_response=(
            mode == PhraseMode.CALL_RESPONSE_MODE
            and sub_phrase_role in {SubPhraseRole.ANSWER, SubPhraseRole.RELEASE}
            and not silence
        ),
        allow_bass=phrase_role != PhraseRole.PRE_DROP,
        allow_stab=not silence,
        silence_protected=silence,
        pre_drop_gap=phrase_role == PhraseRole.PRE_DROP,
        drop_arrival=phrase_role == PhraseRole.DROP or sub_phrase_role == SubPhraseRole.RESET,
    )


def _progress(position: int, length: int) -> float:
    if length <= 1:
        return 1.0
    return max(0.0, min(1.0, (position - 1) / (length - 1)))
