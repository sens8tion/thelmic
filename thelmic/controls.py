from dataclasses import dataclass


@dataclass
class Controls:
    chaos_limit: float = 1.0      # ceiling on instability dimension
    density_ceiling: float = 1.0
