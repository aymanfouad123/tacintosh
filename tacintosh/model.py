"""One short, fresh Apple SDK request per move or end-of-game quip."""

import asyncio
import json
from dataclasses import dataclass

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
        payload["rule"] = (
            "Each player keeps only their three newest marks. "
            "Place on an empty square, then remove your oldest mark if you have four. "
            "Check for a win after removal."
        )
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
                "description": "Playful remark consistent with your chosen move, at most eight words",
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
            "description": "Playful remark consistent with the supplied result, at most twelve words",
        },
    },
    "required": ["reaction"],
    "x-order": ["reaction"],
    "additionalProperties": False,
}


def _normalize(text: str, words: int) -> str:
    return " ".join(text.split()[:words])[:120]


class AppleOpponent:
    def __init__(self) -> None:
        self.model = None

    def ensure_ready(self) -> None:
        # Defer native loading so startup failures can be shown in the menu.
        if self.model is None:
            import apple_fm_sdk as fm

            self.model = fm.SystemLanguageModel()

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
        self,
        instructions: str,
        payload: dict[str, object],
        schema: dict[str, object],
        timeout: float,
    ) -> dict:
        self.ensure_ready()
        import apple_fm_sdk as fm

        session = fm.LanguageModelSession(model=self.model, instructions=instructions)
        prompt = json.dumps(payload, separators=(",", ":"))
        content = await asyncio.wait_for(
            session.respond(
                prompt,
                json_schema=schema,
                options=fm.GenerationOptions(sampling=fm.SamplingMode.greedy()),
            ),
            timeout=timeout,
        )
        reply = content.value()
        if not isinstance(reply, dict):
            raise ValueError("Expected a structured model response.")
        return reply

    async def choose(self, game: Game, mark: str) -> Move:
        empty = game.legal_moves()
        if game.result() or not empty or mark != game.turn:
            raise ValueError("The model cannot move in this position.")

        reply = await self._respond(
            f"Play {game.size}x{game.size} tic-tac-toe as {mark}. "
            "Your objective is to win. "
            "Empty cells show their square numbers. Choose a square. "
            "Give a short, playful remark about your chosen move. "
            "Keep it consistent with the board. "
            "Avoid claims about winning, blocking, or your opponent's intentions.",
            board_payload(game, mark),
            move_schema(empty),
            timeout=45,
        )
        chosen = reply.get("square")
        if not isinstance(chosen, str) or chosen not in {
            str(i + 1) for i in empty
        }:
            raise ValueError("The model returned an illegal move.")

        reaction = reply.get("reaction")
        if not isinstance(reaction, str):
            raise ValueError("The model returned an invalid reaction.")

        return Move(
            square=int(chosen) - 1,
            reaction=_normalize(reaction, words=8),
        )

    async def react(self, game: Game, mark: str, result: str) -> str:
        reply = await self._respond(
            "You just finished a playful tic-tac-toe game. "
            "Give one short, playful remark consistent with the supplied result.",
            {"you": mark, "result": result, "board": board_payload(game, mark)},
            REACTION_SCHEMA,
            timeout=30,
        )
        reaction = reply.get("reaction")
        if not isinstance(reaction, str):
            raise ValueError("The model returned an invalid reaction.")

        return _normalize(reaction, words=12)
