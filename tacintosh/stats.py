"""Persistent game results."""

import json
from datetime import UTC, datetime
from pathlib import Path

LOG_PATH = Path.home() / "Library" / "Application Support" / "tacintosh" / "games.jsonl"
RESULTS = ("you", "model", "draw")


def load_stats(path: Path | None = None) -> dict[str, int]:
    stats = {result: 0 for result in RESULTS}
    path = LOG_PATH if path is None else path

    try:
        with path.open(encoding="utf-8", errors="replace") as log:
            for line in log:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if not isinstance(entry, dict):
                    continue

                result = entry.get("result")
                if isinstance(result, str) and result in stats:
                    stats[result] += 1
    except OSError:
        pass

    return stats


def record_game(
    mode: str,
    result: str,
    path: Path | None = None,
) -> bool:
    if result not in RESULTS:
        raise ValueError(f"Unknown result: {result}")

    path = LOG_PATH if path is None else path
    entry = {
        "played_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "mode": mode,
        "result": result,
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as log:
            json.dump(entry, log, separators=(",", ":"))
            log.write("\n")
    except OSError:
        return False
    return True
