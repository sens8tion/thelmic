"""Hat voice — archetype-driven subdivision, sparsity-gated.

Fires hat steps from the active archetype's hat pattern.
Hat steps are high-probability (not anchors) — sparsity may thin them.
On-beat steps (0, 4, 8, 12) are stronger and more sparsity-resistant.
"""

from __future__ import annotations

from typing import Optional

from typing import TYPE_CHECKING
from thelmic.archetypes import PATTERNS
from thelmic.bank_generator import CLOSED_HAT_NOTE, OPEN_HAT_NOTE
from thelmic.dimensions import Dimensions, PhraseContext
from thelmic.stream_engine import Intent, StructureFrame
from thelmic.voices import make_intent
if TYPE_CHECKING:
    from thelmic.anticipation_engine import AnticipationState

# Open hat steps are now per-archetype (pattern.open_hat_steps).
# The fixed {6, 14} is gone — each archetype has its own OH placement.


class HatIntentStream:
    def intents_for_frame(
        self,
        frame: StructureFrame,
        context: Optional[PhraseContext] = None,
        dims: Optional[Dimensions] = None,
        ant: Optional["AnticipationState"] = None,
    ) -> tuple[Intent, ...]:
        intents: list[Intent] = []
        intents.extend(self._subdivision(frame, context, dims, ant))
        intents.extend(self._grid_reminder(frame))
        return tuple(intents)

    def _subdivision(
        self,
        frame: StructureFrame,
        context: Optional[PhraseContext],
        dims: Optional[Dimensions],
        ant: Optional["AnticipationState"] = None,
    ) -> tuple[Intent, ...]:
        # No structural is_drop_prep override here.
        # Hat behavior is controlled by the anticipation engine (ant) which
        # correctly fires only when the trajectory's ptd < 2 (drop approaching).
        # Structural sub-phrase markers do NOT change hat — only trajectory does.

        pattern          = PATTERNS[context.active_archetype] if context else None
        closed_hat_steps = pattern.closed_hat_steps if pattern else frozenset({0, 2, 4, 6, 8, 10, 12, 14})
        open_hat_steps   = pattern.open_hat_steps   if pattern else frozenset({6, 14})
        hat_steps        = closed_hat_steps | open_hat_steps
        sparsity  = dims.sparsity  if dims else 0.0
        stability = dims.stability if dims else 0.5
        emphasis  = dims.emphasis  if dims else 0.0

        # Anticipation engine overrides (pre-drop withholding/compression)
        if ant is not None:
            if not ant.hat_allowed:
                return ()
            # Compression/dissolution: only fire on allowed interval/steps
            if frame.step_in_bar % ant.hat_interval != 0:
                return ()

        if frame.step_in_bar not in hat_steps:
            return ()

        # ── Sparsity thresholds — genre-correct ─────────────────────────────
        # Hard dance: 16th hats throughout the groove. Thinning only happens
        # at extreme Chaos (very high sparsity). Rules from musical_rules.md:
        #   stability_bias < 0.25 → deep Chaos: kick+hat+bass only (hat survives!)
        #   stability_bias 0.25–0.45 → hook/call withheld; hat still 16ths
        # So hat should persist at ALL positions except deepest Chaos.
        #
        # Correct thresholds (much higher than before):
        #   off-beat 16ths: removed only at sparsity > 0.82 (deep Chaos floor)
        #   8th-note positions (mod2): removed at sparsity > 0.90
        #   on-beat (mod4): removed at sparsity > 0.96 (essentially never)
        on_beat    = frame.step_in_bar % 4 == 0
        on_8th     = frame.step_in_bar % 2 == 0
        if on_beat:
            if sparsity > 0.96:
                return ()
        elif on_8th:
            if sparsity > 0.90:
                return ()
        else:
            if sparsity > 0.82:
                return ()

        # ── Pressure-driven rare drop gate ──────────────────────────────────
        # Adds musical variation: occasional off-beat drops, rate grows with tension.
        # On-beat steps are never dropped — they anchor the grid.
        pressure = dims.pressure if dims else 0.0
        if not on_beat:
            # Drop probability: 2% at groove → 15% at max pressure
            drop_prob_255 = int((0.02 + pressure * 0.13) * 255)
            arch_val  = sum(ord(c) for c in (context.active_archetype.value if context else ""))
            step_hash = ((arch_val * 31 + frame.musical_step * 7) * 2654435761) & 0xFF
            if step_hash < drop_prob_255:
                return ()

        # Determine open vs closed from per-archetype pattern
        is_open  = frame.step_in_bar in open_hat_steps
        note     = OPEN_HAT_NOTE if is_open else CLOSED_HAT_NOTE
        layer    = "open_hat" if is_open else "hat"
        duration = 0.12 if is_open else 0.035   # OH sustains ~3x longer than CH
        velocity = self._velocity(stability, emphasis, note)
        return (make_intent(frame, layer, "subdivision", velocity, duration,
                            "archetype_hat", note, 5),)

    def _velocity(
        self, stability: float, emphasis: float, note: int,
    ) -> int:
        """Flat consistent velocity — sidechain/ducking handled in DAW.

        Open hat slightly brighter. Stability widens the range slightly
        (hot/unstable = more expressive; cold/stable = more uniform).

        References: hardstyle pumping, French house sidechain, industrial techno.
        """
        heat_proxy = 1.0 - stability

        # Flat consistent velocity — DAW handles sidechain/ducking.
        # Open hat slightly brighter.
        if note == OPEN_HAT_NOTE:
            base = int(72 + heat_proxy * 18)   # 72–90
        else:
            base = int(70 + heat_proxy * 15)   # 70–85

        # Emphasis post-drop boost
        boosted = int(base * (1.0 + emphasis * 0.25))

        return max(8, min(118, boosted))

    def _grid_reminder(self, frame: StructureFrame) -> tuple[Intent, ...]:
        # Grid reminder suppressed — was firing every phrase regardless of drop proximity.
        # Anticipation engine handles this when an actual drop is approaching.
        return ()
