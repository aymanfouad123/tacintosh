"""One short, fresh Apple SDK request per move or end-of-game quip."""
import asyncio
import json
from dataclasses import dataclass

import apple_fm_sdk as fm

from .game import Game, other


@dataclass(frozen=True)
class Move:
    square: int
    reaction: str


def board_payload(game: Game, mark: str) -> dict[str, object]:
    """Describe the board using one-based square numbers for the model."""
    size = game.size
    cells = [cell if cell != "." else str(i + 1) for i, cell in enumerate(game.board)]
    payload: dict[str, object] = {
        "you": mark,
        "opponent": other(mark),
        "size": size,
        "goal": f"{size} in a row (row, column, or diagonal)",
        "rows": [cells[row * size:(row + 1) * size] for row in range(size)],
        "empty": [i + 1 for i in game.legal_moves()],
    }
    if game.mode.vanishing:
        payload["rule"] = "each player keeps only their 3 newest marks"
        payload["marks_oldest_first"] = {
            player: [square + 1 for square in game.marks(player)] for player in ("X", "O")
        }
    return payload


def move_schema(empty: list[int]) -> dict[str, object]:
    """Constrain the model's square to the currently empty squares."""
    return {
        "title": "Move",
        "type": "object",
        "properties": {
            "square": {
                "type": "string",
                "description": "Choose a legal square",
                "enum": [str(i + 1) for i in empty],
            },
            "reaction": {
                "type": "string",
                "description": "Whimsical remark, at most eight words",
            },
        },
        "required": ["square", "reaction"],
        "x-order": ["square", "reaction"],
        "additionalProperties": False,
    }


REACTION_SCHEMA = {
    "title": "Reaction",
    "type": "object",
    "properties": {
        "reaction": {
            "type": "string",
            "description": "Whimsical remark, at most twelve words",
        },
    },
    "required": ["reaction"],
    "x-order": ["reaction"],
    "additionalProperties": False,
}


def _normalize(text: str, limit: int = 120) -> str:
    return " ".join(text.split())[:limit]


class AppleOpponent:
    def __init__(self) -> None:
        self.model = fm.SystemLanguageModel()

    def ensure_ready(self) -> None:
        available, reason = self.model.is_available()
        if not available:
            message = (
                reason.name.replace("_", " ").capitalize()
                if reason is not None else "Unknown reason"
            )
            raise RuntimeError(
                f"Apple model unavailable: {message}. Check Apple Intelligence in Settings."
            )

    async def _respond(
        self, instructions: str, payload: dict, request: str, schema: dict, timeout: float
    ) -> dict:
        session = fm.LanguageModelSession(model=self.model, instructions=instructions)
        prompt = json.dumps(payload, separators=(",", ":")) + "\n" + request
        content = await asyncio.wait_for(
            session.respond(
                prompt,
                json_schema=schema,
                options=fm.GenerationOptions(sampling=fm.SamplingMode.greedy()),
            ),
            timeout=timeout,
        )
        return content.value()

    async def choose(self, game: Game, mark: str) -> Move:
        empty = game.legal_moves()
        reply = await self._respond(
            f"Play {game.size}x{game.size} tic-tac-toe as {mark}. "
            "Empty cells show their square numbers. Choose a square and give a short reaction.",
            board_payload(game, mark),
            "Pick your move.",
            move_schema(empty),
            timeout=45,
        )
        square = int(reply["square"]) - 1
        if square not in empty:
            raise ValueError("The model returned an illegal move.")
        return Move(square, _normalize(reply["reaction"]))

    async def react(self, game: Game, mark: str, result: str) -> str:
        reply = await self._respond(
            "You just finished a playful tic-tac-toe game. "
            "Answer with one short whimsical line about the result.",
            {"you": mark, "result": result, "board": board_payload(game, mark)},
            "One short whimsical reaction.",
            REACTION_SCHEMA,
            timeout=30,
        )
        return _normalize(reply["reaction"])
