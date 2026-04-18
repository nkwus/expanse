from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto


class SimEvent(Enum):
    CONTACT_ACQUIRED = auto()
    CONTACT_LOST = auto()
    TORPEDO_LAUNCHED = auto()
    TORPEDO_INBOUND = auto()
    TORPEDO_DETONATED = auto()
    SHIP_DESTROYED = auto()
    SCENARIO_END = auto()


@dataclass
class Event:
    time: float
    kind: SimEvent
    message: str
    payload: dict = field(default_factory=dict)
