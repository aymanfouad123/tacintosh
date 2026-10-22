"""One short, fresh Apple SDK request per move or end-of-game quip."""

import asyncio
from dataclasses import dataclass

from .game import Game, other, winning_lines


@dataclass(frozen=True)
class Move:
    square: int
    reaction: str


def board_prompt(game: Game, mark: str) -> str:
    """Show numbered cells in their board positions, followed by legal choices."""
    size = game.size
    lines = [
        f"Game: {game.mode.label}",
        f"You play {mark}. Your opponent plays {other(mark)}.",
        f"It is {game.turn}'s turn.",
        "Rules:",
        "- X moves first. Players alternate placing one mark in an empty cell.",
        "- You cannot replace an occupied cell.",
        f"- The first player with {size} of their own marks filling one entire row, "
        "one entire column, or either corner-to-corner diagonal wins.",
        "- Marks from different rows, columns, or diagonals do not combine into a win.",
    ]
    if game.mode.vanishing:
        lines.extend([
            "- Each player keeps at most three marks. After placing a fourth mark, "
            "remove that player's oldest mark BEFORE checking for a win.",
            "- The cell must be empty before placing; you cannot choose the occupied "
            "cell that will disappear on this turn.",
        ])
        for player in ("X", "O"):
            squares = ", ".join(str(i + 1) for i in game.marks(player)) or "none"
            lines.append(f"{player}'s marks, oldest to newest: {squares}.")
    else:
        lines.append("- If the board fills without a winner, the game is a draw.")

    example_before = " | ".join([mark] * (size - 1) + ["."])
    example_after = " | ".join([mark] * size)
    lines.extend([
        "",
        "Rule examples (illustrations only; these are NOT the current board):",
        f"- A row containing {example_before} is not yet a win: . is empty.",
        f"- Placing {mark} in that empty cell makes {example_after}. "
        f"That is {size} of your marks in one row, so you win if no mark is removed.",
        f"- A row containing {other(mark)} | "
        + " | ".join([mark] * (size - 1))
        + " is not a win for either player: every cell must have the SAME mark.",
        "- A square number is just an address. Only X or O counts toward a win.",
    ])
    if game.mode.vanishing:
        lines.append(
            "- Removal example: your marks are on squares 1, 2, 5, oldest first. "
            "Placing on empty square 3 removes square 1. You now occupy 2, 5, 3. "
            "You do NOT win the top row, because square 1 is empty again."
        )

    lines.extend([
        "",
        f"CURRENT BOARD ({size} rows by {size} columns):",
        "Each cell is square:contents. X and O are occupied; . means empty.",
        "Square numbers run left to right, then top to bottom.",
    ])
    for row in range(size):
        start = row * size
        lines.append(" | ".join(
            f"{i + 1:>2}:{game.board[i]}" for i in range(start, start + size)
        ))
    lines.extend(["", "Winning groups of square numbers (the same for both players):"])
    for group in winning_lines(size):
        lines.append(", ".join(str(i + 1) for i in group))
    legal = ", ".join(str(i + 1) for i in game.legal_moves()) or "none"
    lines.extend(["", f"Legal squares: {legal}."])
    return "\n".join(lines)


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
        prompt: str,
        schema: dict[str, object],
        timeout: float,
    ) -> dict:
        self.ensure_ready()
        import apple_fm_sdk as fm

        session = fm.LanguageModelSession(model=self.model, instructions=instructions)
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
            "You are playing tic-tac-toe. Your objective is to win; "
            "if you cannot win, try to draw. "
            "Read the rules, your mark, and the current board carefully. "
            "First look for a legal move that wins this turn. "
            "If there is no winning move, try to prevent your opponent winning next turn. "
            "Otherwise choose a move that helps complete a winning group. "
            "In vanishing mode, account for the oldest mark being removed. "
            "Choose the best move yourself from the legal squares. "
            "Return its square number as a string in the square field. "
            "After choosing, add a friendly remark of at most eight words "
            "in the reaction field. Focus on the move first.",
            board_prompt(game, mark),
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
            f"Your result: {result}. This game is over.\n\n{board_prompt(game, mark)}",
            REACTION_SCHEMA,
            timeout=30,
        )
        reaction = reply.get("reaction")
        if not isinstance(reaction, str):
            raise ValueError("The model returned an invalid reaction.")

        return _normalize(reaction, words=12)
