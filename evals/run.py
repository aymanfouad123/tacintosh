"""Compare assistance levels on fixed tactical positions using the local model.

Run: .venv/bin/python -B evals/run.py [--dry-run]
Results are checkpointed after each request; rerunning resumes the same run.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import platform
import random
import sys
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tacintosh.game import Game, MODES  # noqa: E402
from tacintosh.model import AppleOpponent, board_prompt, move_schema  # noqa: E402

OUTPUT = ROOT / "evals" / "results.json"
REPORT = ROOT / "evals" / "REPORT.md"
VARIANTS = ("rules_only", "examples_and_groups", "current", "rules_broad_schema")
BASE_INSTRUCTIONS = (
    "You are playing tic-tac-toe. Your objective is to win; if you cannot win, try to draw. "
    "Read the rules, your mark, and the current board carefully. "
    "Choose the best move yourself from the legal squares. "
    "Return its square number as a string in the square field. "
    "After choosing, add a friendly remark of at most eight words "
    "in the reaction field. Focus on the move first."
)


def winner(board: list[str], size: int) -> str | None:
    """Independent evaluator; no tactical labels are sent to the model."""
    rows = [board[i:i + size] for i in range(0, len(board), size)]
    columns = [board[c::size] for c in range(size)]
    diagonals = [[board[i * size + i] for i in range(size)],
                 [board[i * size + size - 1 - i] for i in range(size)]]
    return next((line[0] for line in rows + columns + diagonals
                 if line[0] != "." and len(set(line)) == 1), None)


def after(game: Game, square: int, mark: str) -> Game:
    result = deepcopy(game)
    assert result.board[square] == "."
    result.board[square] = mark
    result.history[mark].append(square)
    if result.mode.vanishing and len(result.history[mark]) > 3:
        result.board[result.history[mark].pop(0)] = "."
    result.turn = "O" if mark == "X" else "X"
    return result


def wins(game: Game, mark: str) -> list[int]:
    return [i for i, cell in enumerate(game.board) if cell == "."
            and winner(after(game, i, mark).board, game.size) == mark]


def target(game: Game) -> tuple[str, list[int]]:
    winning = wins(game, game.turn)
    if winning:
        return "immediate_win", winning
    opponent = "O" if game.turn == "X" else "X"
    assert wins(game, opponent), "Fixture must contain an immediate threat"
    safe = [i for i in game.legal_moves() if not wins(after(game, i, game.turn), opponent)]
    assert safe, "Fixture must have a defensive move"
    return "prevent_immediate_loss", safe


def fixtures() -> list[tuple[str, Game]]:
    specs = [
        ("classic_win_x", "classic", [0, 3, 1, 4]),
        ("classic_block_o", "classic", [0, 4, 1]),
        ("classic_win_o", "classic", [0, 3, 1, 4, 8]),
        ("4x4_win_x", "4x4", [0, 4, 1, 5, 2, 9]),
        ("4x4_block_o", "4x4", [0, 4, 1, 5, 2]),
        ("4x4_win_o", "4x4", [0, 4, 1, 5, 10, 6, 15]),
        ("vanishing_win_x", "vanishing", [0, 3, 1, 4]),
        ("vanishing_remove_then_block_x", "vanishing", [0, 3, 1, 6, 4, 7]),
        ("vanishing_block_o", "vanishing", [0, 3, 1, 6, 4, 7, 8]),
    ]
    # Rotation checks whether fixed square numbers or the top-row example dominate.
    for name, mode, moves in list(specs):
        if name in ("classic_win_x", "4x4_win_x", "vanishing_remove_then_block_x"):
            size = MODES[mode].size
            rotated = [(i % size) * size + size - 1 - i // size for i in moves]
            specs.append((name + "_rotated", mode, rotated))
    cases = []
    for name, key, moves in specs:
        game = Game(MODES[key])
        for square in moves:
            assert not game.result()
            mark = game.turn
            independent = after(game, square, mark)
            game.play(square, mark)
            assert game.board == independent.board and game.history == independent.history
            assert game.result() == winner(game.board, game.size)
        assert not game.result()
        target(game)
        cases.append((name, game))
    return cases


class CaptureOpponent(AppleOpponent):
    async def _respond(self, instructions, prompt, schema, timeout):
        self.instructions = instructions
        return {"square": schema["properties"]["square"]["enum"][0], "reaction": ""}


def input_for(game: Game, variant: str, current_instructions: str) -> dict:
    prompt = board_prompt(game, game.turn)
    if variant in ("rules_only", "rules_broad_schema"):
        before, rest = prompt.split("\n\nRule examples", 1)
        _, board = rest.split("\n\nCURRENT BOARD", 1)
        board, groups = board.split("\n\nWinning groups", 1)
        _, legal = groups.split("\n\nLegal squares:", 1)
        prompt = before + "\n\nCURRENT BOARD" + board + "\n\nLegal squares:" + legal
    schema = move_schema(game.legal_moves())
    if variant == "rules_broad_schema":
        schema["properties"]["square"]["enum"] = [str(i + 1) for i in range(len(game.board))]
    return {
        "instructions": current_instructions if variant == "current" else BASE_INSTRUCTIONS,
        "prompt": prompt,
        "schema": schema,
    }


def save(data: dict) -> None:
    OUTPUT.write_text(json.dumps(data, indent=2) + "\n")
    labels = {
        "rules_only": "Rules only",
        "examples_and_groups": "Examples and winning groups",
        "current": "App prompt with strategy guidance",
        "rules_broad_schema": "Rules only, broader response schema",
    }
    lines = ["# Tactical evaluation results", "",
             "This report is generated from [results.json](results.json). The "
             "[experiment notes](README.md) explain what prompted the tests, the separate "
             "gameplay win rate, the harness audit, and the limits of these findings.", "",
             f"Requests recorded: **{len(data['results'])}/{len(data['cases']) * len(VARIANTS)}**. "
             f"Run started: {data['started_utc']}.", "",
             f"Environment: macOS {data['macos']}, apple-fm-sdk {data['sdk_version']}, "
             f"Python {data['python']}; {data['sampling']} sampling. "
             "The underlying Apple model build was not pinned.", "",
             "## Overall results", "",
             "Tactical success means taking an available immediate win, or preventing "
             "an immediate opponent win when no winning move is available. "
             "These are move-level scores, not full-game win rates.", "",
             "| Prompt | Tactical successes | Legal responses | Errors | Random expectation |",
             "| --- | --- | --- | --- | --- |"]
    for variant in VARIANTS:
        rows = [r for r in data["results"] if r["variant"] == variant]
        if not rows:
            continue
        successes = sum(r["success"] for r in rows)
        legal = sum(r["legal"] for r in rows)
        errors = sum("error" in r for r in rows)
        baseline = sum(r["random_baseline"] for r in rows) / len(rows)
        lines.append(f"| {labels[variant]} | {successes}/{len(rows)} ({successes / len(rows):.1%}) | {legal}/{len(rows)} | {errors} | {baseline:.1%} |")
    lines.extend(["", "Random expectation is calculated for uniform selection from legal "
                  "squares, except for the broader-schema variant, where it uses every "
                  "board square. These baselines have different action spaces. A legal-only "
                  "schema enforces legality, so a perfect legal-response score under that "
                  "constraint does not establish the model's understanding of legality."])
    lines.extend(["", "## By task", "",
                  "| Prompt | Immediate wins | Prevent immediate loss |",
                  "| --- | --- | --- |"])
    for variant in VARIANTS:
        scores = []
        for task in ("immediate_win", "prevent_immediate_loss"):
            rows = [r for r in data["results"] if r["variant"] == variant and r["task"] == task]
            scores.append(f"{sum(r['success'] for r in rows)}/{len(rows)}")
        lines.append(f"| {labels[variant]} | " + " | ".join(scores) + " |")
    lines.extend(["", "## By mode", "",
                  "| Prompt | Classic 3x3 | Big 4x4 | Vanishing 3x3 |",
                  "| --- | --- | --- | --- |"])
    for variant in VARIANTS:
        scores = []
        for mode in ("classic", "4x4", "vanishing"):
            rows = [r for r in data["results"] if r["variant"] == variant and r["case"].startswith(mode)]
            scores.append(f"{sum(r['success'] for r in rows)}/{len(rows)}")
        lines.append(f"| {labels[variant]} | " + " | ".join(scores) + " |")
    lines.extend(["", "## Per-position results", "",
                  "| Case | Task | Acceptable squares | rules_only | examples_and_groups | current | rules_broad_schema |",
                  "| --- | --- | --- | --- | --- | --- | --- |"])
    for case in data["cases"]:
        cells = []
        for variant in VARIANTS:
            row = next((r for r in data["results"] if r["case"] == case["name"] and r["variant"] == variant), None)
            cells.append("pending" if row is None else "error" if "error" in row else
                         f"{row['square']} ({'pass' if row['success'] else 'fail'})")
        lines.append(f"| {case['name']} | {case['task']} | {case['acceptable_squares']} | " + " | ".join(cells) + " |")
    lines.extend(["", "## Method", "",
        "The suite contains 12 fixed positions: four per mode, including three "
        "rotated counterparts of other cases. Each variant gets one greedy request "
        "per position in a fresh session. The response format includes both the "
        "move and commentary. All requests use a 45-second timeout, with no retries "
        "or replacement moves. Variant order rotates across positions.", "",
        "| Raw variant ID | Assistance supplied |",
        "| --- | --- |",
        "| `rules_only` | Rules, numbered grid, vanishing move history, legal-square list and legal-only enum. |",
        "| `examples_and_groups` | Rules-only input plus generic worked examples and all winning groups. |",
        "| `current` | The app prompt captured for this run: examples, groups and win/block priorities. |",
        "| `rules_broad_schema` | Rules-only input with all board squares allowed by the schema; the legal-square list remains visible. |", "",
        "A separate evaluator computes acceptable squares solely for scoring. It "
        "simulates mark removal before checking vanishing-mode wins. Correct-move "
        "labels and board-specific tactical scores are never sent to the model. "
        "Errors, timeouts and malformed responses count as unsuccessful requests "
        "and are also reported separately.", "",
        "## Interpretation limits", "",
        "These are diagnostic positions, including cases used in earlier prompt "
        "development, not a held-out benchmark. Rotated cases are related, and there "
        "is only one request per position and variant. The results measure immediate "
        "tactics, not long-term optimal play, game win rates, or general model capability.", "",
        "Examples and winning groups were tested together, so their individual "
        "effects cannot be separated. All variants use the numbered grid and a "
        "legal-square list; this run does not compare the original JSON format "
        "or measure completely unassisted action selection. Small differences "
        "between totals should not be treated as established effects.", "",
        "The raw results preserve inputs, schemas, responses, errors, latency, "
        "environment metadata and the model.py source hash. See the experiment "
        "notes for the independent scorer cross-check and suggested next tests.", ""])
    REPORT.write_text("\n".join(lines))


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    cases = fixtures()
    capture = CaptureOpponent()
    await capture.choose(cases[0][1], cases[0][1].turn)
    case_data = []
    jobs = []
    random.Random(42).shuffle(cases)
    for index, (name, game) in enumerate(cases):
        task, acceptable = target(game)
        case_data.append({"name": name, "mode": game.mode.label, "task": task,
                          "board": game.board, "history": game.history, "turn": game.turn,
                          "acceptable_squares": [i + 1 for i in acceptable]})
        order = VARIANTS[index % len(VARIANTS):] + VARIANTS[:index % len(VARIANTS)]
        for variant in order:
            inputs = input_for(game, variant, capture.instructions)
            if variant in ("rules_only", "rules_broad_schema"):
                assert "Rule examples" not in inputs["prompt"] and "Winning groups" not in inputs["prompt"]
                assert "First look for" not in inputs["instructions"]
            jobs.append((name, game, variant, task, acceptable, inputs))
    fingerprint = hashlib.sha256(json.dumps([(n, v, inp) for n, _, v, _, _, inp in jobs], sort_keys=True).encode()).hexdigest()
    if args.dry_run:
        print(json.dumps({"requests": len(jobs), "cases": case_data, "fingerprint": fingerprint}, indent=2))
        return
    if OUTPUT.exists():
        data = json.loads(OUTPUT.read_text())
        assert data["fingerprint"] == fingerprint, "Inputs changed; preserve or relocate prior results before a new run"
    else:
        data = {"started_utc": datetime.now(timezone.utc).isoformat(), "fingerprint": fingerprint,
                "model_py_sha256": hashlib.sha256((ROOT / "tacintosh/model.py").read_bytes()).hexdigest(),
                "sdk_version": importlib.metadata.version("apple-fm-sdk"), "macos": platform.mac_ver()[0],
                "python": platform.python_version(), "sampling": "greedy", "cases": case_data, "results": []}
    completed = {(r["case"], r["variant"]) for r in data["results"]}
    opponent = AppleOpponent()
    for name, game, variant, task, acceptable, inputs in jobs:
        if (name, variant) in completed:
            continue
        denominator = len(game.board) if variant == "rules_broad_schema" else len(game.legal_moves())
        row = {"case": name, "variant": variant, "task": task, "inputs": inputs,
               "acceptable_squares": [i + 1 for i in acceptable], "random_baseline": len(acceptable) / denominator,
               "legal": False, "success": False}
        started = time.monotonic()
        try:
            reply = await opponent._respond(inputs["instructions"], inputs["prompt"], inputs["schema"], timeout=45)
            row["response"] = reply
            square = reply.get("square")
            valid = isinstance(square, str) and square in {str(i + 1) for i in range(len(game.board))}
            if not valid or not isinstance(reply.get("reaction"), str):
                raise ValueError("Malformed structured response")
            row["square"] = int(square)
            row["legal"] = int(square) - 1 in game.legal_moves()
            row["success"] = int(square) - 1 in acceptable
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
        row["seconds"] = round(time.monotonic() - started, 3)
        data["results"].append(row)
        save(data)
        print(f"{len(data['results'])}/{len(jobs)} {variant} {name}: "
              f"{'ERROR' if 'error' in row else 'PASS' if row['success'] else 'MISS'} "
              f"square={row.get('square')} expected={row['acceptable_squares']} ({row['seconds']}s)", flush=True)
    save(data)
    print(f"Report: {REPORT}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
