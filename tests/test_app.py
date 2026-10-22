"""Exercise model workers without loading Apple's native model."""

import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch

from textual.worker import WorkerState
from textual.widgets import Static

from tacintosh.app import GameScreen, MenuScreen, Tacintosh
from tacintosh.game import MODES
from tacintosh.model import Move


class ModelWorkerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.started = asyncio.Event()
        self.cancelled = asyncio.Event()
        self.opponent = Mock()
        self.opponent.choose = AsyncMock(side_effect=self.pending_move)
        self.opponent.react = AsyncMock(return_value="Good game.")
        self.model_patch = patch("tacintosh.app.AppleOpponent", return_value=self.opponent)
        self.model_patch.start()
        self.addCleanup(self.model_patch.stop)
        self.stats_patch = patch(
            "tacintosh.app.load_stats", return_value={"you": 0, "model": 0, "draw": 0}
        )
        self.stats_patch.start()
        self.addCleanup(self.stats_patch.stop)
        self.app = Tacintosh()

    async def pending_move(self, game, mark):
        self.started.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            self.cancelled.set()
            # Like the SDK, yield while cleaning up the native request.
            await asyncio.sleep(0.01)
            raise

    async def open_game(self, first="model"):
        screen = GameScreen(MODES["vanishing"], first)
        await self.app.push_screen(screen)
        if first == "model":
            await asyncio.wait_for(self.started.wait(), timeout=2)
        return screen

    async def test_quit_during_model_request(self):
        async with self.app.run_test() as pilot:
            screen = await self.open_game()
            worker = next(iter(screen.workers))
            await pilot.press("q")
        self.assertTrue(self.cancelled.is_set())
        self.assertEqual(worker.state, WorkerState.CANCELLED)

    async def test_remove_screen_during_model_request(self):
        async with self.app.run_test() as pilot:
            screen = await self.open_game()
            worker = next(iter(screen.workers))
            await self.app.pop_screen()
            await pilot.pause()
            self.assertEqual(worker.state, WorkerState.CANCELLED)
            self.assertTrue(self.cancelled.is_set())
            self.assertIsInstance(self.app.screen, MenuScreen)

    async def test_menu_during_model_request(self):
        async with self.app.run_test() as pilot:
            screen = await self.open_game()
            worker = next(iter(screen.workers))
            await pilot.press("m")
            await pilot.pause()
            self.assertEqual(worker.state, WorkerState.CANCELLED)
            self.assertIsInstance(self.app.screen, MenuScreen)

    async def test_restart_does_not_clear_new_worker_busy_state(self):
        async with self.app.run_test() as pilot:
            screen = await self.open_game()
            old_worker = next(iter(screen.workers))
            await pilot.press("n")
            await pilot.pause()
            self.assertEqual(old_worker.state, WorkerState.CANCELLED)
            self.assertEqual(screen.round_id, 2)
            self.assertTrue(screen.busy)
            self.assertEqual(screen.game.board, ["."] * 9)
            self.assertEqual(self.opponent.choose.await_count, 2)

    async def test_error_allows_retry_and_successful_move(self):
        self.opponent.choose.side_effect = TimeoutError("Model took too long")
        async with self.app.run_test() as pilot:
            screen = await self.open_game(first="you")
            screen.play(0)
            await pilot.pause()
            self.assertFalse(screen.busy)
            self.assertIn("Press r to retry", str(screen.query_one("#status", Static).content))
            self.assertIn("Model took too long", str(screen.query_one("#reaction", Static).content))
            self.opponent.choose.side_effect = None
            self.opponent.choose.return_value = Move(4, "My move.")
            await pilot.press("r")
            await pilot.pause()
            self.assertFalse(screen.busy)
            self.assertEqual(screen.game.board[4], screen.ai)
            self.assertEqual(screen.game.turn, screen.human)


if __name__ == "__main__":
    unittest.main()
