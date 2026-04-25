"""Transport — stub for Phase 2. Interface defined here; implementation in Phase 2."""

from __future__ import annotations

from thelmic.bank_generator import Bank


class Transport:
    """Queue / play / interrupt-replace. Implemented in Phase 2."""

    def queue_bank(self, bank: Bank) -> None:
        raise NotImplementedError("Transport implemented in Phase 2")

    def interrupt_and_replace(self, bank: Bank) -> None:
        raise NotImplementedError("Transport implemented in Phase 2")

    def on_bank_boundary(self) -> None:
        raise NotImplementedError("Transport implemented in Phase 2")

    def current_position(self) -> str:
        raise NotImplementedError("Transport implemented in Phase 2")
