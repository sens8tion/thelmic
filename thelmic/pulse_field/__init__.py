"""Pulse Field — Python upstream of the field-native generation architecture.

This package turns landscape position + motion into the 8-dimension field
vector consumed by the Max for Live Pulse Field devices, and ships it over OSC.

It is a SEPARATE, parallel track to thelmic's planner-first engine: it does not
touch PhrasePlan, the voices, or the bank generator. See the branch spec and
thelmic/devices/README.md.

Public surface:
    FieldVector          — the 8-dim state (dataclass)
    FieldDriver          — stateful landscape -> field mapper
    field_from_sample    — pure mapping function
    nearest_territory    — Oak/Chaos/Nott match for a field vector
    OSCSender            — dependency-free UDP OSC sender
    DIMENSION_NAMES      — canonical dimension order (matches field-osc-config.js)
"""

from thelmic.pulse_field.field_vector import (
    DIMENSION_NAMES,
    FieldDriver,
    FieldVector,
    TERRITORY_PROFILES,
    field_from_sample,
    nearest_territory,
)
from thelmic.pulse_field.osc import OSCSender, encode_message

__all__ = [
    "DIMENSION_NAMES",
    "FieldDriver",
    "FieldVector",
    "TERRITORY_PROFILES",
    "field_from_sample",
    "nearest_territory",
    "OSCSender",
    "encode_message",
]
