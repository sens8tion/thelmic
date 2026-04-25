from dataclasses import dataclass


@dataclass
class Controls:
    groove_lock: float = 0.8      # how tightly rhythm aligns to grid
    chaos_limit: float = 1.0      # ceiling on instability dimension
    density_ceiling: float = 1.0
    variation_rate: float = 0.5   # how fast patterns change within a bank
    kick_dominance: float = 0.7   # kick vs other elements
