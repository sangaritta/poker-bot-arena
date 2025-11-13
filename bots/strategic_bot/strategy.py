from __future__ import annotations

import random
from typing import Dict, Optional

from .analysis import (
    classify_board,
    detect_draws,
    evaluate_hand,
    estimate_equity_vs_range,
    implied_odds,
    pot_odds,
)
from .decisions import DecisionResult
from .context import DecisionContext
from .mcts import MonteCarloActionSearch
from .opponent_model import OpponentModel
from .ranges import (
    canonical_combo,
    get_opening_range,
    get_push_range,
    get_three_bet_range,
)
from .state import GameStateTracker, TableConfig
from .types import PlayerSnapshot, Position, Street
from .utils import preflop_strength


class DecisionBuilder:
    def __init__(self, tracker: GameStateTracker, opponent_model: OpponentModel) -> None:
        self.tracker = tracker
        self.opponent_model = opponent_model

    def build(self, payload: Dict[str, object]) -> DecisionContext:
        self.tracker.sync_from_act_payload(payload)
        you = payload.get("you", {})
        seat = payload.get("seat")
        if seat is None:
            raise ValueError("Seat missing from payload")
        street = Street(payload.get("phase", "PRE_FLOP"))
        hole_cards = list(you.get("hole", []))
        community = list(payload.get("community", []))
        position = self.tracker.position_of(seat, street)
        hero_role = self.tracker.role_of(seat)
        call_amount = payload.get("call_amount") or 0
        min_raise_to = payload.get("min_raise_to")
        max_raise_to = payload.get("max_raise_to")
        min_raise_increment = payload.get("min_raise_increment", 0)
        pot_value = payload.get("pot", self.tracker.pot)
        hero_stack = you.get("stack", 0)
        hero_committed = you.get("committed", 0)

        players = list(self.tracker.players.values())
        opponents = [player for player in players if player.seat != seat]
        opponent_profiles = {
            opp.seat: self.opponent_model.describe(opp.seat) for opp in opponents
        }
        effective_stack = hero_stack + hero_committed
        for opp in opponents:
            effective_stack = min(effective_stack, opp.stack + opp.committed)
        bb_value = max(getattr(self.tracker.table, "bb", 1), 1)
        effective_bb = effective_stack / bb_value

        board_texture = classify_board(community)
        draws = detect_draws(hole_cards, community)
        hand_strength = evaluate_hand(hole_cards, community)

        opponent_range = []
        if opponents:
            villain = opponents[0]
            role = self.tracker.role_of(villain.seat)
            opponent_range = [
                combo
                for combo in self.opponent_model.estimate_preflop_range(
                    villain.seat,
                    role=role,
                    action=villain.last_action or "CALL",
                )
                if combo[0] not in hole_cards + community
                and combo[1] not in hole_cards + community
            ]
        equity_vs_range = estimate_equity_vs_range(
            hole_cards,
            community,
            opponent_range,
        )

        return DecisionContext(
            hand_id=payload["hand_id"],
            seat=seat,
            street=street,
            hole_cards=hole_cards,
            community=community,
            pot=pot_value,
            call_amount=call_amount,
            min_raise_to=min_raise_to,
            max_raise_to=max_raise_to,
            min_raise_increment=min_raise_increment,
            legal_actions=list(payload.get("legal", [])),
            time_ms=you.get("time_ms", 0),
            position=position,
            table=self.tracker.table,
            opponents=opponents,
            players=players,
            action_history=self.tracker.action_history(),
            board_texture=board_texture,
            draws=draws,
            hand_strength=hand_strength,
            pot_odds=pot_odds(call_amount, pot_value),
            implied_odds=implied_odds(call_amount, pot_value, effective_stack),
            opponent_profiles=opponent_profiles,
            effective_stack=effective_stack,
            effective_bb=effective_bb,
            opponent_range=opponent_range,
            equity_vs_range=equity_vs_range,
            hero_stack=hero_stack,
            hero_committed=hero_committed,
            hero_role=hero_role,
        )


class DecisionEngine:
    def __init__(self, opponent_model: OpponentModel) -> None:
        self.opponent_model = opponent_model
        self.rng = random.Random()

    def decide(self, ctx: DecisionContext) -> DecisionResult:
        if ctx.street == Street.PRE_FLOP:
            result = self._preflop(ctx)
        else:
            result = self._postflop(ctx)

        result = sanitize_result(ctx, result)
        if self._should_search(ctx, result):
            search = MonteCarloActionSearch()
            result = sanitize_result(ctx, search.refine(ctx, result))
        return sanitize_result(ctx, result)

    # ------------------------------------------------------------------
    # Preflop heuristics
    # ------------------------------------------------------------------
    def _preflop(self, ctx: DecisionContext) -> DecisionResult:
        hero_combo = (
            canonical_combo(ctx.hole_cards[0], ctx.hole_cards[1])
            if len(ctx.hole_cards) == 2
            else None
        )
        profile = self._villain_profile(ctx)
        eff_bb = ctx.effective_bb
        if eff_bb <= 12:
            return self._short_stack_plan(ctx, hero_combo, eff_bb, profile)
        if ctx.call_amount == 0:
            return self._open_uncontested(ctx, hero_combo, eff_bb, profile)
        return self._vs_raise(ctx, hero_combo, profile)

    def _short_stack_plan(
        self,
        ctx: DecisionContext,
        hero_combo: Optional[tuple[str, str]],
        eff_bb: float,
        profile: Dict[str, float | str],
    ) -> DecisionResult:
        position_key = "BTN" if ctx.hero_role in {"SB", "BTN"} else "BB"
        shove_range = get_push_range(position_key, eff_bb)
        strength = preflop_strength(ctx.hole_cards)
        if hero_combo in shove_range and "RAISE_TO" in ctx.legal_actions:
            amount = ctx.max_raise_to or ctx.hero_stack + ctx.hero_committed
            return DecisionResult("RAISE_TO", amount)
        if ctx.call_amount > 0:
            if strength >= 0.62 or (ctx.equity_vs_range > 0.55):
                if "CALL" in ctx.legal_actions and ctx.call_amount <= ctx.hero_stack:
                    return DecisionResult("CALL", None)
            return DecisionResult("FOLD", None)
        if "CHECK" in ctx.legal_actions:
            return DecisionResult("CHECK", None)
        return DecisionResult("FOLD", None)

    def _open_uncontested(
        self,
        ctx: DecisionContext,
        hero_combo: Optional[tuple[str, str]],
        eff_bb: float,
        profile: Dict[str, float | str],
    ) -> DecisionResult:
        position_key = "BTN" if ctx.hero_role in {"SB", "BTN"} else "BB"
        opening_range = get_opening_range(position_key, eff_bb)
        should_open = hero_combo in opening_range
        classification = profile.get("classification", "TAG")
        if not should_open and classification in {"Maniac", "LAG"}:
            should_open = self.rng.random() < 0.15  # mix in steals
        if should_open and "RAISE_TO" in ctx.legal_actions:
            base = 2.5 if eff_bb > 25 else 2.2
            target = ctx.min_raise_to or int(ctx.table.bb * base)
            if ctx.max_raise_to is not None:
                target = min(target, ctx.max_raise_to)
            return DecisionResult("RAISE_TO", target)
        if "CHECK" in ctx.legal_actions:
            return DecisionResult("CHECK", None)
        return DecisionResult("CALL", None)

    def _vs_raise(
        self,
        ctx: DecisionContext,
        hero_combo: Optional[tuple[str, str]],
        profile: Dict[str, float | str],
    ) -> DecisionResult:
        if hero_combo is None:
            return DecisionResult("FOLD", None)
        position_key = "BTN" if ctx.hero_role in {"SB", "BTN"} else "BB"
        three_bet_range = get_three_bet_range(position_key)
        defend_range = get_opening_range(position_key, ctx.effective_bb) + three_bet_range
        aggression = profile.get("agg", 1.0) or 1.0
        strength = preflop_strength(ctx.hole_cards)

        if hero_combo in three_bet_range and "RAISE_TO" in ctx.legal_actions:
            size = min(
                ctx.max_raise_to or ctx.call_amount + ctx.table.bb * (3 if ctx.effective_bb > 40 else 2.2),
                ctx.call_amount + ctx.table.bb * (3.5 if ctx.effective_bb > 60 else 2.5),
            )
            return DecisionResult("RAISE_TO", size)

        call_threshold = 0.48 if aggression > 1.2 else 0.52
        if "CALL" in ctx.legal_actions and (
            hero_combo in defend_range or strength >= call_threshold
        ):
            return DecisionResult("CALL", None)

        if (
            "RAISE_TO" in ctx.legal_actions
            and ctx.call_amount / max(ctx.effective_stack, 1) > 0.45
            and strength >= 0.7
        ):
            return DecisionResult("RAISE_TO", ctx.max_raise_to or ctx.hero_stack + ctx.hero_committed)

        if "FOLD" in ctx.legal_actions:
            return DecisionResult("FOLD", None)
        return DecisionResult("CHECK", None)

    # ------------------------------------------------------------------
    # Postflop heuristics
    # ------------------------------------------------------------------
    def _postflop(self, ctx: DecisionContext) -> DecisionResult:
        value = ctx.hand_strength.normalized
        draws = ctx.draws
        profile = self._villain_profile(ctx)
        aggression = profile.get("agg", 1.0) or 1.0
        draw_equity = min(draws.outs / 18, 1.0)
        board_pressure = 0.12 if ctx.board_texture.label == "Wet" else -0.05
        bet_size = self._bet_size(ctx, value, draws)

        if ctx.call_amount == 0:
            if value >= 0.78 and "BET" in ctx.legal_actions:
                return DecisionResult("BET", bet_size)
            if draw_equity >= 0.5 and "BET" in ctx.legal_actions:
                return DecisionResult("BET", max(bet_size, ctx.min_raise_to or bet_size))
            if value >= 0.65 and self.rng.random() < 0.4 and "BET" in ctx.legal_actions:
                return DecisionResult("BET", bet_size)
            if "CHECK" in ctx.legal_actions:
                return DecisionResult("CHECK", None)
            return DecisionResult("CALL", None)

        if "RAISE_TO" in ctx.legal_actions and value >= 0.9:
            return DecisionResult("RAISE_TO", bet_size)

        call_threshold = 0.44 + board_pressure - (0.05 if aggression > 1.2 else 0)
        call_threshold = max(0.32, call_threshold)
        if value >= call_threshold or draw_equity >= 0.55 or ctx.equity_vs_range >= 0.55:
            if "CALL" in ctx.legal_actions:
                return DecisionResult("CALL", None)

        if self._should_check_raise(ctx, aggression, value, draw_equity):
            return DecisionResult("RAISE_TO", bet_size)

        if self._bluff_spot(ctx, aggression):
            if "RAISE_TO" in ctx.legal_actions:
                return DecisionResult("RAISE_TO", bet_size)

        if "FOLD" in ctx.legal_actions:
            return DecisionResult("FOLD", None)
        return DecisionResult("CALL", None)

    def _bet_size(self, ctx: DecisionContext, value: float, draws) -> int:
        pot = ctx.pot
        effective_stack = ctx.effective_stack
        stack_to_pot_ratio = effective_stack / max(pot, 1)

        # Advanced sizing based on game theory and stack depth
        if ctx.street == Street.FLOP:
            if value >= 0.9:  # Nuts/near nuts
                multiplier = min(1.2, stack_to_pot_ratio * 0.8)  # Polarize with overbets when deep
            elif value >= 0.8:  # Strong value
                multiplier = 0.75
            else:
                multiplier = 0.5
        elif ctx.street == Street.TURN:
            if value >= 0.92:  # Very strong
                multiplier = min(1.0, stack_to_pot_ratio * 0.6)
            elif value >= 0.85:
                multiplier = 0.8
            else:
                multiplier = 0.55
        else:  # River
            if value >= 0.95:
                multiplier = min(0.9, stack_to_pot_ratio * 0.5)
            elif value >= 0.88:
                multiplier = 0.75
            else:
                multiplier = 0.6

        # Adjust for draws and board texture
        if draws.flush_draw or draws.straight_draw:
            draw_equity = min(draws.outs / 18, 1.0)
            multiplier = max(multiplier, 0.5 + draw_equity * 0.3)

        if ctx.board_texture.label == "Wet":
            multiplier += 0.15  # Bet bigger on coordinated boards
        elif ctx.board_texture.label == "Dry":
            multiplier -= 0.1   # Smaller bets on dry boards

        # Opponent-specific adjustments
        profile = self._villain_profile(ctx)
        aggression = profile.get("agg", 1.0) or 1.0
        if aggression > 1.3:  # Vs aggressive opponents
            multiplier *= 1.1  # Bet bigger to deny them initiative
        elif aggression < 0.8:  # Vs passive opponents
            multiplier *= 0.9  # Smaller bets to get value

        amount = int(pot * multiplier)
        min_total = ctx.min_raise_to or ((ctx.call_amount or 0) + max(ctx.min_raise_increment or ctx.table.bb, ctx.table.bb))
        amount = max(amount, min_total)
        if ctx.max_raise_to is not None:
            amount = min(amount, ctx.max_raise_to)

        return max(amount, (ctx.call_amount or 0) + max(ctx.min_raise_increment, ctx.table.bb))

    def _bluff_spot(self, ctx: DecisionContext, aggression: float) -> bool:
        """Advanced bluffing logic based on board texture, opponent tendencies, and game state"""
        random_factor = self.rng.random()

        # Board texture adjustments
        board_bonus = 0.0
        if ctx.board_texture.label == "Dry":
            board_bonus += 0.25  # Much more likely to bluff on dry boards
        elif ctx.board_texture.label == "Wet":
            board_bonus -= 0.1   # Less likely on wet boards

        # Opponent aggression adjustments
        opp_bonus = 0.0
        if aggression > 1.5:  # Vs very aggressive opponents
            opp_bonus += 0.2   # Bluff more to balance vs maniacs
        elif aggression < 0.7: # Vs passive opponents
            opp_bonus += 0.15  # Bluff more vs calling stations

        # Position and stack adjustments
        position_bonus = 0.1 if ctx.position.name in ["BTN", "CO"] else 0.0
        stack_pressure = 0.1 if ctx.effective_bb < 15 else 0.0

        # Street-specific adjustments
        street_bonus = 0.0
        if ctx.street == Street.FLOP:
            street_bonus = 0.05  # Slightly more bluffs on flop
        elif ctx.street == Street.TURN:
            street_bonus = 0.1   # More bluffs on turn
        elif ctx.street == Street.RIVER:
            street_bonus = 0.15  # Most bluffs on river

        total_bluff_freq = 0.12 + board_bonus + opp_bonus + position_bonus + stack_pressure + street_bonus
        total_bluff_freq = min(0.6, max(0.05, total_bluff_freq))  # Cap between 5% and 60%

        return random_factor < total_bluff_freq

    def _should_check_raise(
        self,
        ctx: DecisionContext,
        aggression: float,
        value: float,
        draw_equity: float,
    ) -> bool:
        if ctx.call_amount is None or "RAISE_TO" not in ctx.legal_actions:
            return False
        if value >= 0.75:
            return True
        if draw_equity >= 0.55 and aggression > 1.1:
            return True
        if ctx.pot / max(ctx.effective_stack, 1) > 0.45 and value >= 0.6:
            return True
        return False

    # ------------------------------------------------------------------
    # Monte Carlo search integration
    # ------------------------------------------------------------------
    def _should_search(self, ctx: DecisionContext, result: DecisionResult) -> bool:
        if ctx.time_ms < 300:
            return False
        if ctx.street in {Street.TURN, Street.RIVER} and ctx.pot > ctx.table.bb * 20:
            return True
        if result.action == "RAISE_TO" and (ctx.max_raise_to or 0) > ctx.table.bb * 20:
            return True
        return False

    def _villain_profile(self, ctx: DecisionContext) -> Dict[str, float | str]:
        if not ctx.opponents:
            return {"classification": "TAG", "agg": 1.0}
        seat = ctx.opponents[0].seat
        profile = ctx.opponent_profiles.get(seat, {})
        if isinstance(profile, dict):
            return profile
        return {"classification": "TAG", "agg": 1.0}


def sanitize_result(ctx: DecisionContext, result: DecisionResult) -> DecisionResult:
    if result.action not in ctx.legal_actions:
        if "CHECK" in ctx.legal_actions:
            return DecisionResult("CHECK", None)
        if "CALL" in ctx.legal_actions:
            return DecisionResult("CALL", None)
        return DecisionResult(ctx.legal_actions[0], None)
    if result.action == "RAISE_TO":
        amount = result.amount or ctx.min_raise_to or ctx.call_amount + ctx.min_raise_increment
        if amount < (ctx.min_raise_to or amount):
            amount = ctx.min_raise_to or amount
        if ctx.max_raise_to is not None and amount > ctx.max_raise_to:
            amount = ctx.max_raise_to
        return DecisionResult(result.action, amount)
    return result

