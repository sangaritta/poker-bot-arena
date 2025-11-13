from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from .types import ActionRecord, HandHistory, PlayerSnapshot, Position, Street


@dataclass
class TableConfig:
    seats: int = 2
    sb: int = 100
    bb: int = 200
    ante: int = 0


class GameStateTracker:
    """Tracks per-hand information so decisions have full history access."""

    def __init__(self) -> None:
        self.table = TableConfig()
        self.seat: Optional[int] = None
        self.seat_map: Dict[int, Optional[str]] = {}
        self.players: Dict[int, PlayerSnapshot] = {}
        self.hand: Optional[HandHistory] = None
        self.current_hand_id: Optional[str] = None
        self.board: List[str] = []
        self.street: Street = Street.PRE_FLOP
        self.pot: int = 0

    # ------------------------------------------------------------------
    # Seat / lobby management
    # ------------------------------------------------------------------
    def set_seat(self, seat: int) -> None:
        self.seat = seat

    def update_table_config(self, config: Dict[str, int]) -> None:
        self.table = TableConfig(
            seats=config.get("seats", self.table.seats),
            sb=config.get("sb", self.table.sb),
            bb=config.get("bb", self.table.bb),
            ante=config.get("ante", 0),
        )

    def register_seat(self, seat: Optional[int], team: Optional[str]) -> None:
        if seat is None:
            return
        self.seat_map[seat] = team

    # ------------------------------------------------------------------
    # Hand lifecycle
    # ------------------------------------------------------------------
    def start_hand(self, payload: Dict[str, object]) -> None:
        self.current_hand_id = str(payload.get("hand_id"))
        self.street = Street.PRE_FLOP
        self.board = []
        self.pot = 0
        start_stacks = payload.get("stacks") or []
        self.players = {
            entry["seat"]: PlayerSnapshot(
                seat=entry["seat"],
                name=self.seat_map.get(entry["seat"]),
                stack=entry.get("stack", 0),
            )
            for entry in start_stacks
            if isinstance(entry, dict) and entry.get("seat") is not None
        }
        self.hand = HandHistory(
            hand_id=self.current_hand_id or "unknown",
            button=payload.get("button", -1),
            start_stacks=start_stacks,
        )

    def record_board(self, street: Street, cards: List[str]) -> None:
        self.board = cards
        if self.hand:
            self.hand.board_by_street[street] = list(cards)

    def update_street(self, street: Street) -> None:
        if street.order >= self.street.order:
            self.street = street

    def finalize_hand(self) -> HandHistory:
        history = self.hand
        self.hand = None
        return history  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Event ingestion
    # ------------------------------------------------------------------
    def handle_event(self, message: Dict[str, object]) -> None:
        event_type = message.get("ev")
        if event_type == "POST_BLINDS":
            self._record_blind(message)
        elif event_type in {"BET", "CALL", "CHECK", "FOLD", "RAISE"}:
            self._record_action_event(message, override_action=event_type)
        elif event_type == "FLOP":
            cards = list(message.get("cards", []))
            self.update_street(Street.FLOP)
            self.record_board(Street.FLOP, cards)
        elif event_type == "TURN":
            card = message.get("card")
            if card:
                self.board.append(card)
            self.update_street(Street.TURN)
            self.record_board(Street.TURN, self.board)
        elif event_type == "RIVER":
            card = message.get("card")
            if card:
                self.board.append(card)
            self.update_street(Street.RIVER)
            self.record_board(Street.RIVER, self.board)
        elif event_type == "SHOWDOWN":
            if self.hand:
                self.hand.showdowns.append(
                    {
                        "seat": message.get("seat"),
                        "hand": list(message.get("hand", [])),
                        "rank": message.get("rank"),
                    }
                )
            self.update_street(Street.SHOWDOWN)
        elif event_type == "POT_AWARD":
            if self.hand:
                self.hand.payouts.append(
                    {
                        "seat": message.get("seat"),
                        "amount": message.get("amount"),
                    }
                )
        elif event_type == "ELIMINATED":
            seat = message.get("seat")
            if seat is not None and self.hand:
                self.hand.eliminations.append(seat)

    def _record_blind(self, message: Dict[str, object]) -> None:
        sb = message.get("sb", 0)
        bb = message.get("bb", 0)
        sb_seat = message.get("sb_seat")
        bb_seat = message.get("bb_seat")
        if isinstance(sb_seat, int):
            self._append_action(
                seat=sb_seat,
                action="POST_SB",
                amount=sb,
                street=Street.PRE_FLOP,
            )
        if isinstance(bb_seat, int):
            self._append_action(
                seat=bb_seat,
                action="POST_BB",
                amount=bb,
                street=Street.PRE_FLOP,
            )
        self.pot += int(sb or 0) + int(bb or 0) + self.table.ante * self.table.seats

    def _record_action_event(
        self,
        message: Dict[str, object],
        override_action: Optional[str] = None,
    ) -> None:
        seat = message.get("seat")
        if seat is None:
            return
        action = override_action or message.get("ev")
        amount = message.get("amount")
        self._append_action(
            seat=int(seat),
            action=str(action),
            amount=amount if amount is not None else None,
            street=self.street,
        )
        if isinstance(amount, int):
            self.pot += amount
        player = self.players.get(int(seat))
        if player:
            player.last_action = str(action)
            if action in {"BET", "RAISE", "POST_BB", "POST_SB"}:
                player.bets_or_raises += 1
            elif action in {"CALL"}:
                player.calls += 1
            if action not in {"FOLD"}:
                player.voluntarily_played += 1

    def _append_action(
        self,
        seat: int,
        action: str,
        amount: Optional[int],
        street: Street,
    ) -> None:
        if not self.hand:
            return
        player = self.players.get(seat)
        stack_before = player.stack if player else 0
        record = ActionRecord(
            hand_id=self.current_hand_id or "unknown",
            seat=seat,
            action=action,
            amount=amount,
            street=street,
            pot_before=self.pot,
            stack_before=stack_before,
            timestamp=time.time(),
            resulting_stack=stack_before - int(amount or 0),
        )
        self.hand.actions.setdefault(street, []).append(record)

    # ------------------------------------------------------------------
    # Player snapshot updates
    # ------------------------------------------------------------------
    def sync_from_act_payload(self, payload: Dict[str, object]) -> None:
        """Ensure local player snapshots mirror the act payload values."""
        for entry in payload.get("players", []):
            seat = entry.get("seat")
            if seat is None:
                continue
            snapshot = self.players.setdefault(
                seat,
                PlayerSnapshot(seat=seat, name=self.seat_map.get(seat), stack=0),
            )
            snapshot.stack = entry.get("stack", snapshot.stack)
            snapshot.committed = entry.get("committed", snapshot.committed)
            snapshot.has_folded = entry.get("has_folded", snapshot.has_folded)
            snapshot.is_all_in = entry.get("is_all_in", snapshot.is_all_in)
            snapshot.name = entry.get("team") or snapshot.name
            snapshot.seen_hands += 1
            self.seat_map.setdefault(seat, snapshot.name)

    # ------------------------------------------------------------------
    # Derived helpers
    # ------------------------------------------------------------------
    def seat_label(self, seat: Optional[int]) -> str:
        if seat is None:
            return "Seat ?"
        if seat == self.seat:
            return self.seat_map.get(seat) or "Hero"
        return self.seat_map.get(seat) or f"Seat {seat}"

    def action_history(self) -> Dict[Street, List[ActionRecord]]:
        if not self.hand:
            return {}
        return self.hand.actions

    def position_of(self, seat: int, phase: Street) -> Position:
        if self.table.seats <= 2:
            if phase == Street.PRE_FLOP:
                return Position.BLINDS if seat == self.table_button() else Position.IN_POSITION
            return Position.IN_POSITION if seat != self.table_button() else Position.OUT_OF_POSITION
        if self.table_button() is None:
            return Position.OUT_OF_POSITION
        relative = (seat - self.table_button()) % self.table.seats
        if relative == 0:
            return Position.IN_POSITION
        if relative == 1:
            return Position.BLINDS
        return Position.OUT_OF_POSITION

    def table_button(self) -> Optional[int]:
        return self.hand.button if self.hand else None

    def role_of(self, seat: int) -> str:
        if self.table.seats == 2:
            if seat == self.table_button():
                return "SB"
            return "BB"
        if seat == self.table_button():
            return "BTN"
        relative = (seat - (self.table_button() or 0)) % self.table.seats
        if relative == 1:
            return "SB"
        if relative == 2:
            return "BB"
        return f"SEAT_{seat}"

