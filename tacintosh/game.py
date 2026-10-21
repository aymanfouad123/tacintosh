"""Modes and rules. The language model never decides legality or the winner."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Mode:
    label: str
    description: str
    size: int = 3
    vanishing: bool = False


MODES = {
    "classic": Mode("Classic 3×3", "Standard tic-tac-toe. Three in a row wins."),
    "4x4": Mode("Big 4×4", "Sixteen squares. Four in a row wins.", size=4),
    "vanishing": Mode(
        "Vanishing 3×3",
        "Only your three newest marks stay. A fourth erases the oldest.",
        vanishing=True,
    ),
}

FIRST_LABELS = {"random": "Random", "you": "You", "model": "Model"}


def other(mark: str) -> str:
    return "O" if mark == "X" else "X"


def winning_lines(size: int) -> list[tuple[int, ...]]:
    rows = [tuple(range(row * size, row * size + size)) for row in range(size)]
    columns = [tuple(range(column, size * size, size)) for column in range(size)]
    diagonals = [
        tuple(i * size + i for i in range(size)),
        tuple(i * size + size - i - 1 for i in range(size)),
    ]
    return rows + columns + diagonals


@dataclass
class Game:
    """Board plus every square each player has played, oldest first. X moves first."""

    mode: Mode
    board: list[str] = field(init=False)
    history: dict[str, list[int]] = field(init=False)

    def __post_init__(self) -> None:
        self.board = ["."] * (self.size * self.size)
        self.history = {"X": [], "O": []}

    @property
    def size(self) -> int:
        return self.mode.size

    @property
    def turn(self) -> str:
        return "X" if len(self.history["X"]) == len(self.history["O"]) else "O"

    def legal_moves(self) -> list[int]:
        return [i for i, mark in enumerate(self.board) if mark == "."]

    def winning_line(self) -> tuple[int, ...]:
        for line in winning_lines(self.size):
            mark = self.board[line[0]]
            if mark != "." and all(self.board[i] == mark for i in line):
                return line
        return ()

    def result(self) -> str | None:
        """'X' or 'O' for a win, 'draw' for a full board, None while playing."""
        line = self.winning_line()
        if line:
            return self.board[line[0]]
        return None if "." in self.board else "draw"

    def marks(self, mark: str) -> list[int]:
        """Squares this player holds, oldest first."""
        return self.history[mark][-3:] if self.mode.vanishing else self.history[mark]

    def next_to_vanish(self, mark: str) -> int | None:
        """The square this player loses on their next move in vanishing mode."""
        marks = self.marks(mark)
        return marks[0] if self.mode.vanishing and len(marks) == 3 else None

    def play(self, square: int, mark: str) -> None:
        if self.result() or mark != self.turn or square not in self.legal_moves():
            raise ValueError("Illegal move")
        vanishing = self.next_to_vanish(mark)
        if vanishing is not None:
            self.board[vanishing] = "."
        self.board[square] = mark
        self.history[mark].append(square)
