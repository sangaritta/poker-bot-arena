from __future__ import annotations
import random
from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

from core.cards import Card, parse_label
from core.evaluator import RANK_VALUE, evaluate_best

HandCombo = Tuple[str, str]

HAND_CATEGORY = {
    8: "Straight Flush",
    7: "Four of a Kind",
    6: "Full House",
    5: "Flush",
    4: "Straight",
    3: "Three of a Kind",
    2: "Two Pair",
    1: "Pair",
    0: "High Card",
}


@dataclass
class HandStrength:
    category: str
    rank: int
    score_vector: List[int]

    @property
    def normalized(self) -> float:
        return (self.rank + sum(self.score_vector) / 100.0) / 10.0


@dataclass
class DrawFeatures:
    flush_draw: bool
    straight_draw: bool
    backdoor_flush: bool
    backdoor_straight: bool
    combo_draw: bool
    outs: int


@dataclass
class BoardTexture:
    label: str
    paired: bool
    monotone: bool
    straight_possible: bool
    high_card: str


def parse_cards(labels: Sequence[str]) -> List[Card]:
    return [parse_label(label) for label in labels]


def evaluate_hand(hole: Sequence[str], community: Sequence[str]) -> HandStrength:
    cards = parse_cards([*hole, *community])
    if len(cards) < 5:
        ranks = sorted((RANK_VALUE[card.rank] for card in cards), reverse=True)
        padded = ranks + [0] * (5 - len(ranks))
        return HandStrength(category="Partial", rank=0, score_vector=padded)
    rank, vector = evaluate_best(cards)
    category = HAND_CATEGORY.get(rank, "Unknown")
    return HandStrength(category=category, rank=rank, score_vector=vector)


def detect_draws(hole: Sequence[str], community: Sequence[str]) -> DrawFeatures:
    cards = [*hole, *community]
    suits = [card[1] for card in cards if len(card) == 2]
    ranks = [card[0] for card in cards if len(card) == 2]
    suit_counts = {suit: suits.count(suit) for suit in "cdhs"}
    flush_draw = any(count >= 4 for count in suit_counts.values())
    backdoor_flush = any(count == 3 for count in suit_counts.values())

    rank_values = _rank_values(cards)
    straight_draw, backdoor_straight = _detect_straight_draw(rank_values)

    outs = 0
    if flush_draw:
        outs += 9
    elif backdoor_flush:
        outs += 4
    if straight_draw:
        outs += 8
    elif backdoor_straight:
        outs += 4

    combo_draw = flush_draw and straight_draw

    return DrawFeatures(
        flush_draw=flush_draw,
        straight_draw=straight_draw,
        backdoor_flush=backdoor_flush,
        backdoor_straight=backdoor_straight,
        combo_draw=combo_draw,
        outs=outs,
    )


def classify_board(community: Sequence[str]) -> BoardTexture:
    if not community:
        return BoardTexture("Empty", False, False, False, "NA")
    suits = [card[1] for card in community if len(card) == 2]
    ranks = [card[0] for card in community if len(card) == 2]
    monotone = len(set(suits)) == 1
    paired = len(ranks) != len(set(ranks))
    straight_possible = _straight_possible(community)
    high_card = max(ranks, key=_rank_index)
    label = "Wet" if straight_possible or monotone or paired else "Dry"
    return BoardTexture(
        label=label,
        paired=paired,
        monotone=monotone,
        straight_possible=straight_possible,
        high_card=high_card,
    )


def pot_odds(call_amount: int, pot: int) -> float:
    if call_amount <= 0:
        return 0.0
    return call_amount / max(pot + call_amount, 1)


def implied_odds(call_amount: int, pot: int, effective_stack: int) -> float:
    future = pot + min(call_amount * 4, effective_stack)
    if call_amount <= 0:
        return 0.0
    return call_amount / future


def estimate_equity_vs_range(
    hole: Sequence[str],
    community: Sequence[str],
    opponent_range: Sequence[HandCombo],
    trials: int = 400,
) -> float:
    deck = _remaining_deck([*hole, *community])
    hero_cards = parse_cards(hole)
    board_cards = parse_cards(community)

    wins = 0
    ties = 0
    total = 0
    rng = random.Random()

    for _ in range(trials):
        if opponent_range:
            opp_combo = rng.choice(opponent_range)
            opp_cards = parse_cards(opp_combo)
            used_labels = set(opp_combo)
        else:
            opp_cards = rng.sample(deck, 2)
            used_labels = {card.label for card in opp_cards}
        drawn_board = list(board_cards)
        cards_needed = 5 - len(drawn_board)
        trial_deck = [card for card in deck if card.label not in used_labels]
        rng.shuffle(trial_deck)
        while len(drawn_board) < 5:
            drawn_board.append(trial_deck.pop())

        hero_rank = evaluate_best(hero_cards + drawn_board)
        opp_rank = evaluate_best(opp_cards + drawn_board)
        total += 1
        if hero_rank > opp_rank:
            wins += 1
        elif hero_rank == opp_rank:
            ties += 1

    if total == 0:
        return 0.0
    return (wins + ties * 0.5) / total


def _rank_values(cards: Sequence[str]) -> List[int]:
    mapping = {r: idx for idx, r in enumerate("23456789TJQKA", start=2)}
    values = []
    for label in cards:
        if len(label) != 2:
            continue
        values.append(mapping[label[0]])
    return sorted(set(values))


def _detect_straight_draw(values: Sequence[int]) -> Tuple[bool, bool]:
    if not values:
        return False, False
    ordered = sorted(values)
    straight_draw = False
    backdoor = False
    for idx in range(len(ordered) - 3):
        window = ordered[idx : idx + 4]
        if window == list(range(window[0], window[0] + 4)):
            straight_draw = True
            break
    if not straight_draw:
        for idx in range(len(ordered) - 2):
            window = ordered[idx : idx + 3]
            if window == list(range(window[0], window[0] + 3)):
                backdoor = True
                break
    return straight_draw, backdoor


def _straight_possible(community: Sequence[str]) -> bool:
    values = _rank_values(community)
    for idx in range(len(values) - 4):
        window = values[idx : idx + 5]
        if window == list(range(window[0], window[0] + 5)):
            return True
    # Wheel straight
    wheel = {14, 5, 4, 3, 2}
    return wheel.issubset(values)


def _rank_index(rank: str) -> int:
    order = "23456789TJQKA"
    return order.index(rank)


def _remaining_deck(excluded: Sequence[str]) -> List[Card]:
    excluded_set = set(excluded)
    deck = []
    for rank in "AKQJT98765432":
        for suit in "cdhs":
            label = f"{rank}{suit}"
            if label not in excluded_set:
                deck.append(parse_label(label))
    return deck

