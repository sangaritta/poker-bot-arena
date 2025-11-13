from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class Street(str, Enum):
    PRE_FLOP = "PRE_FLOP"
    FLOP = "FLOP"
    TURN = "TURN"
    RIVER = "RIVER"
    SHOWDOWN = "SHOWDOWN"

    @property
    def order(self) -> int:
        return {
            Street.PRE_FLOP: 0,
            Street.FLOP: 1,
            Street.TURN: 2,
            Street.RIVER: 3,
            Street.SHOWDOWN: 4,
        }[self]


class Position(str, Enum):
    IN_POSITION = "IN_POSITION"
    OUT_OF_POSITION = "OUT_OF_POSITION"
    BLINDS = "BLINDS"


@dataclass
class PlayerSnapshot:
    seat: int
    name: Optional[str]
    stack: int
    committed: int = 0
    has_folded: bool = False
    is_all_in: bool = False
    last_action: Optional[str] = None
    aggression_factor: float = 0.0
    vpip: float = 0.0
    pfr: float = 0.0
    seen_hands: int = 0
    voluntarily_played: int = 0
    preflop_raises: int = 0
    bets_or_raises: int = 0
    calls: int = 0


@dataclass
class ActionRecord:
    hand_id: str
    seat: int
    action: str
    amount: Optional[int]
    street: Street
    pot_before: int
    stack_before: int
    timestamp: float
    resulting_stack: int


@dataclass
class HandHistory:
    hand_id: str
    button: Optional[int]
    start_stacks: List[Dict[str, int]]
    board_by_street: Dict[Street, List[str]] = field(default_factory=dict)
    actions: Dict[Street, List[ActionRecord]] = field(
        default_factory=lambda: {
            Street.PRE_FLOP: [],
            Street.FLOP: [],
            Street.TURN: [],
            Street.RIVER: [],
        }
    )
    showdowns: List[Dict[str, object]] = field(default_factory=list)
    payouts: List[Dict[str, object]] = field(default_factory=list)
    eliminations: List[int] = field(default_factory=list)

