from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional

import websockets

from .decisions import DecisionResult
from .logging_utils import HandLogger
from .opponent_model import OpponentModel
from .state import GameStateTracker
from .strategy import DecisionBuilder, DecisionEngine, sanitize_result
from .types import Street

LOGGER = logging.getLogger("strategic_bot")


class StrategicBot:
    def __init__(self, team_name: str, bot_label: Optional[str] = None) -> None:
        self.team_name = team_name
        self.bot_label = bot_label
        self.display_name = f"{team_name} ({bot_label})" if bot_label else team_name
        self.tracker = GameStateTracker()
        self.opponent_model = OpponentModel()
        self.builder = DecisionBuilder(self.tracker, self.opponent_model)
        self.engine = DecisionEngine(self.opponent_model)
        self.hand_logger = HandLogger()

    async def connect_and_play(self, url: str) -> None:
        async with websockets.connect(url) as ws:
            hello = {"type": "hello", "v": 1, "team": self.team_name}
            if self.bot_label:
                hello["bot"] = self.bot_label
            await ws.send(json.dumps(hello))
            LOGGER.info("[connect] %s as %s", url, self.display_name)
            await self._play(ws)

    async def _play(self, websocket: websockets.WebSocketClientProtocol) -> None:
        async for raw in websocket:
            message = json.loads(raw)
            msg_type = message.get("type")

            if msg_type == "welcome":
                await self._handle_welcome(message)
                continue
            if msg_type == "lobby":
                self._handle_lobby(message)
                continue
            if msg_type == "start_hand":
                self._handle_start_hand(message)
                continue
            if msg_type == "event":
                self._handle_event(message)
                continue
            if msg_type == "act":
                await self._handle_act(message, websocket)
                continue
            if msg_type == "end_hand":
                self._handle_end_hand(message)
                continue
            if msg_type == "match_end":
                LOGGER.info("[match] winner=%s", message.get("winner"))
                break
            if msg_type == "ab_status":
                LOGGER.info("[practice] waiting for partner | bot=%s state=%s", message.get("bot"), message.get("state"))
            elif msg_type == "error":
                LOGGER.warning("[error] %s", message)

    async def _handle_welcome(self, message: Dict[str, Any]) -> None:
        LOGGER.info("[welcome] seat=%s config=%s", message.get("seat"), message.get("config"))
        seat = message.get("seat")
        if seat is not None:
            self.tracker.set_seat(seat)
        config = message.get("config", {})
        self.tracker.update_table_config(config)
        self.tracker.register_seat(seat, self.display_name)

    def _handle_lobby(self, message: Dict[str, Any]) -> None:
        for entry in message.get("players", []):
            self.tracker.register_seat(entry.get("seat"), entry.get("team"))

    def _handle_start_hand(self, message: Dict[str, Any]) -> None:
        self.tracker.start_hand(message)
        LOGGER.info(
            "[hand %s] start | button=%s",
            message.get("hand_id"),
            self.tracker.seat_label(message.get("button")),
        )

    def _handle_event(self, message: Dict[str, Any]) -> None:
        self.tracker.handle_event(message)
        event = message.get("ev")
        seat = message.get("seat")
        if seat is None or seat == self.tracker.seat:
            return
        if event in {"BET", "RAISE", "CALL"}:
            aggressive = event in {"BET", "RAISE"}
            if self.tracker.street == Street.PRE_FLOP:
                self.opponent_model.observe_preflop(
                    seat,
                    action=event,
                    voluntarily_in_pot=True,
                    raised=aggressive,
                )
            else:
                self.opponent_model.observe_postflop_action(seat, aggressive)
        if event == "SHOWDOWN":
            self.opponent_model.observe_showdown(seat, won=False)
        if event == "POT_AWARD":
            self.opponent_model.observe_showdown(seat, won=True)

    async def _handle_act(
        self,
        message: Dict[str, Any],
        websocket: websockets.WebSocketClientProtocol,
    ) -> None:
        try:
            context = self.builder.build(message)
            decision = self.engine.decide(context)
            decision = sanitize_result(context, decision)
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.exception("Failed to choose action: %s", exc)
            decision = self._fallback(message)
        payload = {
            "type": "action",
            "v": 1,
            "hand_id": message.get("hand_id"),
            "action": decision.action,
        }
        if decision.amount is not None:
            payload["amount"] = int(decision.amount)
        LOGGER.debug("[action] %s", payload)
        await websocket.send(json.dumps(payload))

    def _fallback(self, message: Dict[str, Any]) -> DecisionResult:
        legal = message.get("legal", [])
        if "CHECK" in legal:
            return DecisionResult("CHECK", None)
        if "CALL" in legal:
            return DecisionResult("CALL", None)
        if legal:
            return DecisionResult(legal[0], message.get("min_raise_to"))
        return DecisionResult("FOLD", None)

    def _handle_end_hand(self, message: Dict[str, Any]) -> None:
        if self.tracker.hand:
            history = self.tracker.finalize_hand()
            self.hand_logger.log_hand(history)
        LOGGER.info("[hand %s] end | stacks=%s", message.get("hand_id"), message.get("stacks"))

