from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .context import DecisionContext
from .decisions import DecisionResult


@dataclass
class ActionNode:
    action: str
    amount: Optional[int]
    value_sum: float = 0.0
    visits: int = 0

    @property
    def mean_value(self) -> float:
        if self.visits == 0:
            return 0.0
        return self.value_sum / self.visits


class MonteCarloActionSearch:
    def __init__(self, max_iterations: int = 800, exploration: float = 1.2) -> None:
        self.max_iterations = max_iterations
        self.exploration = exploration

    def refine(self, ctx: DecisionContext, seed: DecisionResult) -> DecisionResult:
        candidates = self._candidate_actions(ctx, seed)
        if len(candidates) <= 1:
            return seed
        nodes = [ActionNode(action=action, amount=amount) for action, amount in candidates]
        start = time.monotonic()
        time_budget = max(0.15, (ctx.time_ms - 200) / 1000.0)
        iteration = 0
        while (
            iteration < self.max_iterations
            and time.monotonic() - start < time_budget
        ):
            node = self._select(nodes)
            reward = self._simulate(ctx, node.action, node.amount)
            node.visits += 1
            node.value_sum += reward
            iteration += 1
        best = max(nodes, key=lambda n: n.mean_value)
        return DecisionResult(best.action, best.amount)

    def _select(self, nodes: List[ActionNode]) -> ActionNode:
        total_visits = sum(node.visits for node in nodes) + 1
        best_score = float("-inf")
        best_node = nodes[0]
        for node in nodes:
            if node.visits == 0:
                return node
            exploit = node.mean_value
            explore = math.sqrt(math.log(total_visits) / node.visits)
            score = exploit + self.exploration * explore
            if score > best_score:
                best_score = score
                best_node = node
        return best_node

    def _candidate_actions(
        self,
        ctx: DecisionContext,
        seed: DecisionResult,
    ) -> List[Tuple[str, Optional[int]]]:
        options = set()
        options.add((seed.action, seed.amount))
        if "FOLD" in ctx.legal_actions:
            options.add(("FOLD", None))
        if "CALL" in ctx.legal_actions:
            options.add(("CALL", None))
        if "CHECK" in ctx.legal_actions:
            options.add(("CHECK", None))
        if "RAISE_TO" in ctx.legal_actions:
            min_total = ctx.min_raise_to
            pot_size = ctx.pot + ctx.call_amount + ctx.table.bb
            raise_targets = {
                min_total,
                min(ctx.max_raise_to or pot_size, pot_size),
                ctx.max_raise_to,
            }
            for amount in raise_targets:
                if amount:
                    options.add(("RAISE_TO", int(amount)))
        return list(options)

    def _simulate(
        self,
        ctx: DecisionContext,
        action: str,
        amount: Optional[int],
    ) -> float:
        equity = ctx.equity_vs_range
        if action == "FOLD":
            return -ctx.call_amount
        if action in {"CHECK", "CALL"} and ctx.call_amount == 0:
            return equity * ctx.pot
        if action == "CALL":
            final_pot = ctx.pot + ctx.call_amount
            return equity * final_pot - (1 - equity) * ctx.call_amount
        if action == "CHECK":
            return equity * ctx.pot * 0.8
        if action == "RAISE_TO":
            target = amount or ctx.min_raise_to or ctx.call_amount
            hero_invest = max(target - ctx.hero_committed, 0)
            opponent_commit = 0
            if ctx.opponents:
                villain = ctx.opponents[0]
                opponent_commit = max(target - villain.committed, 0)
                opponent_commit = min(opponent_commit, villain.stack + villain.committed)
            fold_prob = self._fold_probability(ctx)
            pot_if_fold = ctx.pot
            pot_if_called = ctx.pot + hero_invest + opponent_commit
            showdown_ev = equity * pot_if_called - (1 - equity) * hero_invest
            return fold_prob * pot_if_fold + (1 - fold_prob) * showdown_ev
        return 0.0

    def _fold_probability(self, ctx: DecisionContext) -> float:
        if not ctx.opponents:
            return 0.3
        profile = ctx.opponent_profiles.get(ctx.opponents[0].seat, {})
        vpip = profile.get("vpip", 0.3) if isinstance(profile, dict) else 0.3
        agg = profile.get("agg", 1.0) if isinstance(profile, dict) else 1.0
        texture_bonus = 0.1 if ctx.board_texture.label == "Dry" else -0.05
        fold_prob = max(0.05, min(0.9, (0.6 - vpip) + (0.4 / (agg + 0.5)) + texture_bonus))
        return fold_prob

