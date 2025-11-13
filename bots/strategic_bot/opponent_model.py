from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from .ranges import HandCombo, OPENING_RANGES
from .utils import select_top_fraction


@dataclass
class OpponentStats:
    seat: int
    hands_seen: int = 0
    voluntarily_played: int = 0
    preflop_raises: int = 0
    bets_or_raises: int = 0
    calls: int = 0
    showdowns: int = 0
    showdowns_won: int = 0
    fold_to_cbet: int = 0
    cbet_opportunities: int = 0
    range_cache: List[HandCombo] = field(default_factory=list)

    @property
    def vpip(self) -> float:
        if self.hands_seen == 0:
            return 0.0
        return self.voluntarily_played / self.hands_seen

    @property
    def pfr(self) -> float:
        if self.hands_seen == 0:
            return 0.0
        return self.preflop_raises / self.hands_seen

    @property
    def aggression_factor(self) -> float:
        if self.calls == 0:
            return float(self.bets_or_raises)
        return self.bets_or_raises / max(1, self.calls)

    @property
    def classification(self) -> str:
        if self.vpip < 0.15:
            return "NIT"
        if self.vpip < 0.27:
            return "TAG"
        if self.vpip < 0.4:
            return "LAG"
        return "Maniac"


class OpponentModel:
    def __init__(self) -> None:
        self._stats: Dict[int, OpponentStats] = {}

    def get(self, seat: int) -> OpponentStats:
        return self._stats.setdefault(seat, OpponentStats(seat=seat))

    def observe_preflop(
        self,
        seat: int,
        action: str,
        voluntarily_in_pot: bool,
        raised: bool,
    ) -> None:
        stats = self.get(seat)
        stats.hands_seen += 1
        if voluntarily_in_pot:
            stats.voluntarily_played += 1
        if raised:
            stats.preflop_raises += 1

    def observe_postflop_action(self, seat: int, aggressive: bool) -> None:
        stats = self.get(seat)
        if aggressive:
            stats.bets_or_raises += 1
        else:
            stats.calls += 1

    def observe_cbet_opportunity(self, seat: int, folded: bool) -> None:
        stats = self.get(seat)
        stats.cbet_opportunities += 1
        if folded:
            stats.fold_to_cbet += 1

    def observe_showdown(self, seat: int, won: bool) -> None:
        stats = self.get(seat)
        stats.showdowns += 1
        if won:
            stats.showdowns_won += 1

    # ------------------------------------------------------------------
    # Range estimation helpers
    # ------------------------------------------------------------------
    def estimate_preflop_range(
        self,
        seat: int,
        role: str,
        action: str,
    ) -> List[HandCombo]:
        base = OPENING_RANGES["HU_SB_OPEN"]
        if role == "BB":
            base = OPENING_RANGES["HU_BB_DEFEND_CALL"]
            if action in {"RAISE", "3BET"}:
                base = OPENING_RANGES["HU_BB_3BET"]
        elif role == "SB" and action in {"RAISE", "3BET"}:
            base = OPENING_RANGES["HU_SB_3BET"]

        combos = base.combos()
        profile = self.get(seat)

        # More sophisticated range estimation based on opponent tendencies
        if profile.classification == "NIT":
            combos = select_top_fraction(combos, 0.25)  # Even tighter vs nits
        elif profile.classification == "TAG":
            combos = select_top_fraction(combos, 0.4)   # Tighter vs TAGs
        elif profile.classification == "LAG":
            combos = select_top_fraction(combos, 0.8)   # Wider vs LAGs
        else:  # Maniac
            # Use VPIP to estimate range more precisely
            vpip_adjustment = min(1.0, max(0.3, profile.vpip * 1.2))
            combos = select_top_fraction(combos, vpip_adjustment)
        profile.range_cache = combos
        return combos

    def equity_weight(self, seat: int) -> float:
        profile = self.get(seat)
        if profile.classification == "NIT":
            return 0.85
        if profile.classification == "TAG":
            return 0.7
        if profile.classification == "LAG":
            return 0.5
        return 0.3

    def describe(self, seat: int) -> Dict[str, float | str]:
        stats = self.get(seat)
        return {
            "seat": seat,
            "vpip": round(stats.vpip, 2),
            "pfr": round(stats.pfr, 2),
            "agg": round(stats.aggression_factor, 2),
            "classification": stats.classification,
        }

