#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_winner(log: str) -> Optional[str]:
    for line in reversed(log.splitlines()):
        if "[match]" in line and "winner=" in line:
            _, _, payload = line.partition("winner=")
            payload = payload.strip()
            try:
                info = ast.literal_eval(payload)
            except (ValueError, SyntaxError):
                continue
            if isinstance(info, dict):
                team = info.get("team")
                if isinstance(team, str):
                    return team
    return None


def run_iteration(
    iteration: int,
    args: argparse.Namespace,
    env: Dict[str, str],
) -> Tuple[Optional[str], Dict[str, str]]:
    commands = []
    for label in ("A", "B"):
        cmd = [
            args.python,
            args.bot_script,
            "--team",
            args.team,
            "--bot",
            label,
            "--url",
            args.url,
        ]
        commands.append((label, cmd))

    processes = []
    outputs: Dict[str, str] = {}
    try:
        for label, cmd in commands:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )
            processes.append((label, proc))
        winner: Optional[str] = None
        for label, proc in processes:
            stdout, _ = proc.communicate()
            outputs[label] = stdout
            candidate = parse_winner(stdout)
            if candidate:
                winner = candidate
            if proc.returncode != 0:
                raise RuntimeError(f"Bot {label} exited with {proc.returncode}")
        return winner, outputs
    finally:
        for _, proc in processes:
            if proc.poll() is None:
                proc.kill()


def summarize(team: str, winner: Optional[str]) -> str:
    if not winner:
        return "unknown"
    if winner.endswith("(HOUSE)") or winner.casefold() == "house":
        return "house"
    if winner.startswith(team):
        if "(A)" in winner:
            return "bot_a"
        if "(B)" in winner:
            return "bot_b"
        return "team"
    return "other"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run repeated A/B practice matches for benchmarking.")
    parser.add_argument("--team", required=True, help="Team name registered with the host.")
    parser.add_argument("--url", default="ws://127.0.0.1:9876/ws", help="Practice server URL.")
    parser.add_argument("--iterations", type=int, default=100, help="Number of sequential matches to run.")
    parser.add_argument("--bot-script", default=str(REPO_ROOT / "strategic_bot.py"), help="Bot entrypoint to execute.")
    parser.add_argument("--python", default=sys.executable, help="Python executable to launch bots.")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds to wait between iterations.")
    args = parser.parse_args()

    env = os.environ.copy()
    existing_path = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        f"{REPO_ROOT}{os.pathsep}{existing_path}" if existing_path else str(REPO_ROOT)
    )

    stats = {"bot_a": 0, "bot_b": 0, "team": 0, "house": 0, "other": 0, "unknown": 0}
    logs_dir = REPO_ROOT / "logs" / "ab_batch"
    logs_dir.mkdir(parents=True, exist_ok=True)

    for iteration in range(1, args.iterations + 1):
        start = time.perf_counter()
        try:
            winner, outputs = run_iteration(iteration, args, env)
        except Exception as exc:  # noqa: BLE001
            stats["unknown"] += 1
            print(f"[iter {iteration}] failed: {exc}")
            break

        bucket = summarize(args.team, winner)
        stats.setdefault(bucket, 0)
        stats[bucket] += 1
        duration = time.perf_counter() - start

        log_path = logs_dir / f"match_{iteration:03d}.log"
        with log_path.open("w", encoding="utf-8") as handle:
            for label, text in outputs.items():
                handle.write(f"===== BOT {label} =====\n{text}\n")

        print(
            f"[iter {iteration}] winner={winner or 'UNKNOWN'} bucket={bucket} duration={duration:.1f}s "
            f"({stats['bot_a']}A/{stats['bot_b']}B/{stats['house']}H/{stats['unknown']}?)"
        )
        if iteration < args.iterations and args.delay > 0:
            time.sleep(args.delay)

    print("\n=== Summary ===")
    total = sum(stats.values())
    for key, value in stats.items():
        if value == 0:
            continue
        pct = (value / total) * 100 if total else 0
        print(f"{key:>7}: {value} ({pct:.1f}%)")


if __name__ == "__main__":
    main()

