from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from .analysis import BoardTexture, DrawFeatures, HandStrength
from .state import TableConfig
from .types import ActionRecord, PlayerSnapshot, Position, Street


@dataclass
class DecisionContext:
    hand_id: str
    seat: int
    street: Street
    hole_cards: List[str]
    community: List[str]
    pot: int
    call_amount: int
    min_raise_to: Optional[int]
    max_raise_to: Optional[int]
    min_raise_increment: int
    legal_actions: List[str]
    time_ms: int
    position: Position
    table: TableConfig
    opponents: List[PlayerSnapshot]
    players: List[PlayerSnapshot]
    action_history: Dict[Street, List[ActionRecord]]
    board_texture: BoardTexture
    draws: DrawFeatures
    hand_strength: HandStrength
    pot_odds: float
    implied_odds: float
    opponent_profiles: Dict[int, Dict[str, float | str]]
    effective_stack: int
    effective_bb: float
    opponent_range: List[tuple[str, str]]
    equity_vs_range: float
    hero_stack: int
    hero_committed: int
    hero_role: str

