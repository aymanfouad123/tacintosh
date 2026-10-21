"""Persistent game results."""

import json
from datetime import UTC, datetime
from pathlib import Path

LOG_PATH = Path.home() / "Library" / "Application Support" / "tacintosh" / "games.jsonl"
RESULTS = ("you", "model", "draw")


def load_stats() -> dict[str, int]:
    stats = {result: 0 for result in RESULTS}
    try:
        lines = LOG_PATH.read_text().splitlines()
    except OSError:
        return stats

    for line in lines:
        try:
            result = json.loads(line)["result"]
        except (json.JSONDecodeError, KeyError, TypeError):
            continue
        if result in stats:
            stats[result] += 1
    return stats


def record_game(mode: str, result: str) -> bool:
    entry = {
        "played_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "mode": mode,
        "result": result,
    }
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a") as log:
            json.dump(entry, log, separators=(",", ":"))
            log.write("\n")
    except OSError:
        return False
    return True
