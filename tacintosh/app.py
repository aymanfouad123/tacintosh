"""Textual interface: start menu + game board."""

from __future__ import annotations

from random import choice
from typing import ClassVar, cast

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Center, Container, Vertical
from textual.screen import Screen
from textual.widgets import Footer, LoadingIndicator, Static

from .game import FIRST_LABELS, MODES, Game, Mode, other
from .model import AppleOpponent
from .stats import load_stats, record_game

MODE_KEYS = list(MODES)
FIRST_KEYS = list(FIRST_LABELS)


def _options(labels: list[str], selected: int, sep: str = "\n") -> str:
    return sep.join(
        f"[bold #b8f2cf]› {label}[/]" if i == selected else f"  {label}"
        for i, label in enumerate(labels)
    )


class Cell(Static):
    def __init__(self, index: int) -> None:
        self.index = index
        super().__init__(id=f"cell-{index}", classes="cell")

    def on_click(self) -> None:
        cast(GameScreen, self.screen).play(self.index)


class MenuScreen(Screen[None]):
    app: Tacintosh

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("up", "move_mode(-1)", show=False),
        Binding("down", "move_mode(1)", show=False),
        Binding("left", "move_first(-1)", show=False),
        Binding("right,tab", "move_first(1)", show=False),
        Binding("enter,space", "start", "Play"),
        Binding("q", "app.quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.mode_index = 0
        self.first_index = 0

    def compose(self) -> ComposeResult:
        error = self.app.model_error
        with Container(id="menu"):
            yield Static("tacintosh", id="menu-brand")
            yield Static("tic-tac-toe · Apple Foundation Models", id="menu-sub")
            yield Static(f"Model unavailable  {error}" if error else "", id="menu-status", markup=False)
            yield Static("MODE", classes="eyebrow")
            yield Static(id="mode-list")
            yield Static("FIRST MOVE", classes="eyebrow")
            yield Static(id="first-list")
            yield Static(id="mode-blurb")
            yield Static(self.app.stats_text, id="stats")
            yield Static("PLAY  ·  press Enter", id="play-hint")
            yield Static("↑↓ mode   ←→ first   q quit", id="menu-hint")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_menu()

    def refresh_menu(self) -> None:
        mode = MODES[MODE_KEYS[self.mode_index]]
        self.query_one("#mode-list", Static).update(
            _options([MODES[key].label for key in MODE_KEYS], self.mode_index)
        )
        self.query_one("#first-list", Static).update(
            _options(list(FIRST_LABELS.values()), self.first_index, sep="  ")
        )
        self.query_one("#mode-blurb", Static).update(mode.description)

    def action_move_mode(self, delta: int) -> None:
        self.mode_index = (self.mode_index + delta) % len(MODE_KEYS)
        self.refresh_menu()

    def action_move_first(self, delta: int) -> None:
        self.first_index = (self.first_index + delta) % len(FIRST_KEYS)
        self.refresh_menu()

    def action_start(self) -> None:
        # Availability can change after the model download finishes.
        try:
            self.app.opponent.ensure_ready()
        except Exception as exc:
            self.query_one("#menu-status", Static).update(
                f"Model unavailable: {exc}"
            )
            return

        self.app.model_error = None
        self.query_one("#menu-status", Static).update("")

        mode = MODES[MODE_KEYS[self.mode_index]]
        self.app.push_screen(GameScreen(mode, FIRST_KEYS[self.first_index]))


class GameScreen(Screen[None]):
    app: Tacintosh

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("up", "navigate(-1, 0)", show=False),
        Binding("down", "navigate(1, 0)", show=False),
        Binding("left", "navigate(0, -1)", show=False),
        Binding("right", "navigate(0, 1)", show=False),
        Binding("enter,space", "play_selected", "Place"),
        Binding("n", "new_game", "New"),
        Binding("m", "menu", "Menu"),
        Binding("r", "retry", "Retry", show=False),
        Binding("q", "app.quit", "Quit"),
    ]

    def __init__(self, mode: Mode, first: str) -> None:
        super().__init__()
        self.mode = mode
        self.first = first
        self.game = Game(mode)
        self.human = "X"
        self.selected = 0
        self.busy = False
        self.result_logged = False
        self.round_id = 0

    @property
    def ai(self) -> str:
        return other(self.human)

    def compose(self) -> ComposeResult:
        with Vertical(id="shell"):
            yield Static(f"tacintosh · {self.mode.label}", id="brand")
            yield Static(id="status")
            yield Static(self.app.stats_text, id="stats")
            with Center(id="board-wrap"), Container(id="board"):
                for index in range(len(self.game.board)):
                    yield Cell(index)
            keys = "1–9 / a–g" if self.mode.size == 4 else "1–9"
            yield Static(f"arrows select · enter / {keys} place", id="hint")
            yield Static(id="reaction", markup=False)
            yield LoadingIndicator(id="thinking")
        yield Footer()

    def on_mount(self) -> None:
        self.add_class(f"size-{self.mode.size}")
        self.start_round()

    def start_round(self) -> None:
        self.round_id += 1
        self.workers.cancel_node(self)
        self.busy = False
        self.result_logged = False
        self.game = Game(self.mode)
        self.selected = len(self.game.board) // 2
        first = choice(("you", "model")) if self.first == "random" else self.first
        self.human = "X" if first == "you" else "O"
        self.say("You go first." if first == "you" else "Model goes first.")
        if self.game.turn == self.ai:
            self.start_model_turn()
        else:
            self.refresh_board()

    def say(self, text: str) -> None:
        self.query_one("#reaction", Static).update(text)

    def refresh_board(self) -> None:
        game = self.game
        result = game.result()
        line = game.winning_line()
        for i, mark in enumerate(game.board):
            cell = self.query_one(f"#cell-{i}", Cell)
            cell.set_class(i == self.selected and not self.busy and not result, "selected")
            cell.set_class(i in line, "winning")
            cell.set_class(mark == self.human, "human")
            cell.set_class(mark == self.ai, "model")
            cell.set_class(mark != "." and i == game.next_to_vanish(mark), "oldest")
            cell.update(mark if mark != "." else str(i + 1))

        if result == "draw":
            status = "Draw."
        elif result:
            status = "You win." if result == self.human else "Model wins."
        elif self.busy:
            status = (
                "Model goes first · thinking…"
                if "X" not in game.board
                else "Model thinking…"
            )
        elif game.turn == self.ai:
            status = "Model paused. Press r to retry."
        elif "X" not in game.board:
            status = "You go first · your move."
        else:
            status = "Your move."
        self.query_one("#status", Static).update(status)
        self.query_one("#thinking").display = self.busy

    def play(self, square: int) -> None:
        game = self.game
        if self.busy or game.turn != self.human or game.result():
            return
        if square not in game.legal_moves():
            return
        self.selected = square
        game.play(square, self.human)
        self.start_model_turn()

    def start_model_turn(self) -> None:
        self.busy = True
        self.refresh_board()
        self.run_worker(self.model_turn(self.round_id), exclusive=True)

    async def model_turn(self, round_id: int) -> None:
        if round_id != self.round_id:
            return
        opponent = self.app.opponent
        game = self.game
        try:
            if not game.result():
                move = await opponent.choose(game, self.ai)
                if round_id != self.round_id:
                    return

                game.play(move.square, self.ai)
                self.selected = move.square
                self.say(f"“{move.reaction}”")
                self.refresh_board()
            result = game.result()
            if result:
                if not self.result_logged:
                    winner = (
                        "draw"
                        if result == "draw"
                        else "you"
                        if result == self.human
                        else "model"
                    )
                    self.app.record_result(self.mode.label, winner)
                    self.result_logged = True
                outcome = "draw" if result == "draw" else "win" if result == self.ai else "loss"
                try:
                    reaction = await opponent.react(game, self.ai, outcome)
                except Exception:
                    # The result is recorded; the final quip is optional.
                    reaction = "Good game."

                if round_id != self.round_id:
                    return
                self.say(f"“{reaction}”")
        except Exception as exc:
            if round_id == self.round_id:
                self.say(f"Model error: {str(exc) or type(exc).__name__}")
        finally:
            # A cancelled native request must never update a newer round.
            if round_id == self.round_id:
                self.busy = False
                self.refresh_board()

    def action_navigate(self, rows: int, columns: int) -> None:
        size = self.mode.size
        row, column = divmod(self.selected, size)
        self.selected = (row + rows) % size * size + (column + columns) % size
        self.refresh_board()

    def action_play_selected(self) -> None:
        self.play(self.selected)

    def action_new_game(self) -> None:
        self.start_round()

    def action_menu(self) -> None:
        self.round_id += 1
        self.workers.cancel_node(self)
        self.app.pop_screen()

    def action_retry(self) -> None:
        if not self.busy and not self.game.result() and self.game.turn == self.ai:
            self.start_model_turn()

    def on_key(self, event: events.Key) -> None:
        key = (event.character or "").lower()
        if key and key in "123456789":
            self.play(int(key) - 1)
            event.stop()
        elif self.mode.size == 4 and key and key in "abcdefg":
            self.play(9 + ord(key) - ord("a"))
            event.stop()


class Tacintosh(App):
    CSS_PATH = "style.tcss"
    TITLE = "tacintosh"
    ENABLE_COMMAND_PALETTE = False

    def __init__(self) -> None:
        super().__init__()
        self.opponent = AppleOpponent()
        self.model_error: str | None = None
        self.stats = load_stats()

    @property
    def stats_text(self) -> str:
        return (
            f"record  you {self.stats['you']} · "
            f"model {self.stats['model']} · draws {self.stats['draw']}"
        )

    def record_result(self, mode: str, result: str) -> None:
        saved = record_game(mode, result)
        self.stats[result] += 1
        for screen in self.screen_stack:
            for widget in screen.query("#stats"):
                cast(Static, widget).update(self.stats_text)

        if not saved:
            self.notify(
                "Result counted for this session, but couldn't be saved",
                severity="warning",
            )

    def on_mount(self) -> None:
        try:
            self.opponent.ensure_ready()
        except Exception as exc:
            self.model_error = str(exc)

        self.push_screen(MenuScreen())
