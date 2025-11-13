from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from .types import HandHistory, Street


class HandLogger:
    def __init__(self, directory: str = "logs/hands") -> None:
        self.directory = directory
        os.makedirs(self.directory, exist_ok=True)

    def log_hand(self, history: HandHistory) -> None:
        path = os.path.join(self.directory, f"{history.hand_id}.jsonl")
        payload: dict[str, Any] = {
            "hand_id": history.hand_id,
            "button": history.button,
            "start_stacks": history.start_stacks,
            "board_by_street": history.board_by_street,
            "payouts": history.payouts,
            "eliminations": history.eliminations,
            "showdowns": history.showdowns,
            "actions": {
                street.value: [
                    {
                        "seat": record.seat,
                        "action": record.action,
                        "amount": record.amount,
                        "timestamp": record.timestamp,
                    }
                    for record in history.actions.get(street, [])
                ]
                for street in Street
            },
            "timestamp": datetime.utcnow().isoformat(),
        }
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload))
            handle.write("\n")

