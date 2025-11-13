from __future__ import annotations

from typing import Iterable, List, Sequence, Tuple

HandCombo = Tuple[str, str]

RANK_ORDER = "23456789TJQKA"
RANK_VALUE = {rank: idx + 2 for idx, rank in enumerate(RANK_ORDER)}


def canonical(cards: Sequence[str]) -> HandCombo:
    return tuple(sorted(cards))


def preflop_strength(cards: Sequence[str]) -> float:
    if len(cards) != 2:
        return 0.0
    a, b = cards
    rank_a, suit_a = a[0], a[1]
    rank_b, suit_b = b[0], b[1]
    high = max(RANK_VALUE[rank_a], RANK_VALUE[rank_b])
    low = min(RANK_VALUE[rank_a], RANK_VALUE[rank_b])
    suited = suit_a == suit_b
    pair = rank_a == rank_b
    gap = abs(RANK_VALUE[rank_a] - RANK_VALUE[rank_b]) - 1
    strength = high / 14.0 * 0.6 + low / 14.0 * 0.3
    if pair:
        strength += 0.2
    if suited:
        strength += 0.05
    strength -= gap * 0.02
    return max(0.0, min(1.0, strength))


def select_top_fraction(combos: Sequence[HandCombo], fraction: float) -> List[HandCombo]:
    sorted_combos = sorted(
        combos,
        key=lambda combo: preflop_strength(combo),
        reverse=True,
    )
    count = max(1, int(len(sorted_combos) * fraction))
    return sorted_combos[:count]

