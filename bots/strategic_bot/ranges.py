from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Set, Tuple

HandCombo = Tuple[str, str]

RANKS_DESC = "AKQJT98765432"
RANKS_ASC = RANKS_DESC[::-1]
RANK_INDEX_ASC = {rank: idx for idx, rank in enumerate(RANKS_ASC)}
SUITS = "cdhs"


def canonical_combo(card_a: str, card_b: str) -> HandCombo:
    return tuple(sorted((card_a, card_b)))


def _pair_combos(rank: str) -> List[HandCombo]:
    combos: List[HandCombo] = []
    for i, suit_a in enumerate(SUITS):
        for suit_b in SUITS[i + 1 :]:
            combos.append(canonical_combo(f"{rank}{suit_a}", f"{rank}{suit_b}"))
    return combos


def _suited_combos(rank_high: str, rank_low: str) -> List[HandCombo]:
    combos: List[HandCombo] = []
    for suit in SUITS:
        combos.append(canonical_combo(f"{rank_high}{suit}", f"{rank_low}{suit}"))
    return combos


def _offsuit_combos(rank_high: str, rank_low: str) -> List[HandCombo]:
    combos: List[HandCombo] = []
    for suit_a in SUITS:
        for suit_b in SUITS:
            if suit_a == suit_b:
                continue
            combos.append(canonical_combo(f"{rank_high}{suit_a}", f"{rank_low}{suit_b}"))
    return combos


def _expand_token(token: str) -> List[HandCombo]:
    plus = token.endswith("+")
    if plus:
        token = token[:-1]
    combos: List[HandCombo] = []
    if len(token) == 2 and token[0] == token[1]:
        rank = token[0]
        if plus:
            start_idx = RANK_INDEX_ASC[rank]
            ranks = RANKS_ASC[start_idx:]
            for candidate in ranks:
                combos.extend(_pair_combos(candidate))
        else:
            combos.extend(_pair_combos(rank))
    elif len(token) == 3:
        high, low, suit_flag = token[0], token[1], token[2]
        low_idx = RANK_INDEX_ASC[low]
        high_idx = RANK_INDEX_ASC[high]
        if high_idx <= low_idx:
            rank_pairs = [(high, low)]
        else:
            rank_pairs = (
                [(high, low)]
                if not plus
                else [
                    (high, RANKS_ASC[idx])
                    for idx in range(low_idx, high_idx)
                ]
            )
        for rank_high, rank_low in rank_pairs:
            if suit_flag == "s":
                combos.extend(_suited_combos(rank_high, rank_low))
            elif suit_flag == "o":
                combos.extend(_offsuit_combos(rank_high, rank_low))
    return combos


@dataclass(frozen=True)
class HandRange:
    name: str
    tokens: Sequence[str]

    def combos(self) -> List[HandCombo]:
        seen: Set[HandCombo] = set()
        for token in self.tokens:
            for combo in _expand_token(token):
                seen.add(combo)
        return list(seen)

    def contains(self, hole_cards: Sequence[str]) -> bool:
        if len(hole_cards) != 2:
            return False
        return canonical_combo(hole_cards[0], hole_cards[1]) in self.combos()


def combine_ranges(*ranges: HandRange) -> List[HandCombo]:
    seen: Set[HandCombo] = set()
    for hand_range in ranges:
        seen.update(hand_range.combos())
    return list(seen)


def _range(tokens: Sequence[str], name: str) -> HandRange:
    return HandRange(name=name, tokens=tokens)


OPENING_RANGES: Dict[str, HandRange] = {
    "HU_BTN_100BB": _range(
        [
            "22+",
            "A2s+",
            "K4s+",
            "Q6s+",
            "J7s+",
            "T7s+",
            "97s+",
            "87s",
            "76s",
            "65s",
            "A2o+",
            "K8o+",
            "Q9o+",
            "J9o+",
            "T9o",
        ],
        "HU Button 100bb",
    ),
    "HU_SB_20BB": _range(
        [
            "22+",
            "A2s+",
            "K6s+",
            "Q8s+",
            "J8s+",
            "T8s+",
            "98s",
            "A9o+",
            "KTo+",
            "QJo",
        ],
        "HU Button 20bb",
    ),
    "HU_BB_DEFEND": _range(
        [
            "22+",
            "A2s+",
            "K2s+",
            "Q5s+",
            "J7s+",
            "T7s+",
            "97s+",
            "87s",
            "76s",
            "A5o+",
            "K9o+",
            "Q9o+",
            "J9o+",
            "T9o",
            "98o",
        ],
        "HU Big Blind Defend",
    ),
    # Legacy keys for opponent modeling
    "HU_SB_OPEN": _range(
        [
            "22+",
            "A2s+",
            "K6s+",
            "Q8s+",
            "J8s+",
            "T8s+",
            "98s",
            "A9o+",
            "KTo+",
            "QJo",
        ],
        "HU SB Open",
    ),
    "HU_BB_DEFEND_CALL": _range(
        [
            "22+",
            "A2s+",
            "K2s+",
            "Q5s+",
            "J7s+",
            "T7s+",
            "97s+",
            "87s",
            "76s",
            "A5o+",
            "K9o+",
            "Q9o+",
            "J9o+",
            "T9o",
            "98o",
        ],
        "HU BB Defend Call",
    ),
    "HU_BB_3BET": _range(
        [
            "TT+",
            "AQ+",
            "A5s+",
            "KTs+",
            "QTs+",
            "JTs",
        ],
        "HU BB 3bet",
    ),
    "HU_SB_3BET": _range(
        [
            "TT+",
            "AQ+",
            "A8s+",
            "KTs+",
            "QTs+",
            "JTs",
        ],
        "HU SB 3bet",
    ),
}

THREE_BET_RANGES: Dict[str, HandRange] = {
    "HU_BTN_VS_BB": _range(
        [
            "TT+",
            "A8s+",
            "KTs+",
            "QTs+",
            "JTs",
            "AQo+",
        ],
        "HU Button vs BB 3bet",
    ),
    "HU_BB_VS_BTN": _range(
        [
            "99+",
            "A5s+",
            "KTs+",
            "QTs+",
            "JTs",
            "AQo+",
        ],
        "HU BB vs BTN 3bet",
    ),
}

PUSH_FOLD_RANGES: Dict[str, List[Tuple[int, HandRange]]] = {
    "BTN": [
        (
            6,
            _range(
                [
                    "22+",
                    "A2s+",
                    "K2s+",
                    "Q4s+",
                    "J5s+",
                    "T6s+",
                    "96s+",
                    "86s+",
                    "A2o+",
                    "K5o+",
                    "Q8o+",
                    "J8o+",
                    "T8o+",
                    "98o",
                ],
                "BTN shove <=6bb",
            ),
        ),
        (
            10,
            _range(
                [
                    "22+",
                    "A2s+",
                    "K6s+",
                    "Q8s+",
                    "J8s+",
                    "T8s+",
                    "A8o+",
                    "KTo+",
                    "QJo",
                ],
                "BTN shove <=10bb",
            ),
        ),
    ],
    "BB": [
        (
            6,
            _range(
                [
                    "22+",
                    "A2s+",
                    "K4s+",
                    "Q6s+",
                    "J7s+",
                    "T7s+",
                    "97s+",
                    "87s",
                    "A5o+",
                    "K9o+",
                    "Q9o+",
                    "J9o+",
                ],
                "BB shove <=6bb",
            ),
        ),
        (
            10,
            _range(
                [
                    "33+",
                    "A2s+",
                    "K7s+",
                    "Q9s+",
                    "J9s+",
                    "T9s",
                    "A9o+",
                    "KJo+",
                ],
                "BB shove <=10bb",
            ),
        ),
    ],
}


def get_opening_range(position: str, stack_bb: float) -> List[HandCombo]:
    if position in {"SB", "BTN"}:
        if stack_bb <= 20:
            return OPENING_RANGES["HU_SB_20BB"].combos()
        return OPENING_RANGES["HU_BTN_100BB"].combos()
    return OPENING_RANGES["HU_BB_DEFEND"].combos()


def get_three_bet_range(position: str) -> List[HandCombo]:
    if position == "BTN":
        return THREE_BET_RANGES["HU_BTN_VS_BB"].combos()
    return THREE_BET_RANGES["HU_BB_VS_BTN"].combos()


def get_push_range(position: str, stack_bb: float) -> List[HandCombo]:
    ladder = PUSH_FOLD_RANGES.get(position)
    if not ladder:
        return []
    for threshold, hand_range in ladder:
        if stack_bb <= threshold:
            return hand_range.combos()
    return ladder[-1][1].combos()


PRE_FLOP_RANGES = OPENING_RANGES
