#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import logging

from bots.strategic_bot import StrategicBot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Advanced strategic poker bot")
    parser.add_argument("--team", required=True, help="Registered team name")
    parser.add_argument("--url", default="ws://127.0.0.1:9876/ws", help="WebSocket URL")
    parser.add_argument("--bot", choices=["A", "B"], help="Optional practice slot label")
    parser.add_argument("--log-level", default="INFO", help="Logging level (INFO, DEBUG, ...)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(message)s")
    bot = StrategicBot(team_name=args.team, bot_label=args.bot)
    asyncio.run(bot.connect_and_play(args.url))


if __name__ == "__main__":
    main()

