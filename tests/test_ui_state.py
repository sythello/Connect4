from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from connect4.ai import MinimaxAI
from connect4.ui.player_options import load_player_options
from connect4.ui.session_state import (
    MODE_PLAYING,
    MODE_SETUP,
    Connect4UISessionState,
    PlayerSelections,
)


class PlayerOptionsTests(unittest.TestCase):
    def test_load_default_player_options_contains_seeded_ids(self) -> None:
        options = load_player_options()

        self.assertEqual(
            [option.id for option in options],
            ["human", "random-v1", "minimax-d2-v1", "minimax-d4-v1"],
        )
        self.assertTrue(options[0].is_human)

    def test_load_player_options_rejects_unknown_factory(self) -> None:
        config_path = self._write_config(
            [
                {"id": "human", "label": "Human", "kind": "human"},
                {
                    "id": "broken",
                    "label": "BrokenAI",
                    "kind": "ai",
                    "factory": "MissingAI",
                    "params": {},
                },
            ]
        )

        with self.assertRaisesRegex(ValueError, "Unknown AI factory"):
            load_player_options(config_path)

    def test_load_player_options_wires_minimax_params(self) -> None:
        config_path = self._write_config(
            [
                {"id": "human", "label": "Human", "kind": "human"},
                {
                    "id": "minimax-d5-v1",
                    "label": "MinimaxAI depth 5 v1",
                    "kind": "ai",
                    "factory": "MinimaxAI",
                    "params": {"max_depth": 5},
                },
            ]
        )

        options = load_player_options(config_path)
        player = options[1].create_player()

        self.assertIsInstance(player, MinimaxAI)
        self.assertEqual(player.max_depth, 5)

    def _write_config(self, payload) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        config_path = Path(temp_dir.name) / "ai_options.json"
        config_path.write_text(json.dumps(payload), encoding="utf-8")
        return config_path


class UISessionStateTests(unittest.TestCase):
    def test_start_tracks_last_started_selection_and_mode(self) -> None:
        session = Connect4UISessionState("human", "human")

        selection = session.start("random-v1", "minimax-d4-v1")

        self.assertEqual(session.mode, MODE_PLAYING)
        self.assertEqual(selection, PlayerSelections("random-v1", "minimax-d4-v1"))
        self.assertEqual(session.setup_selection, selection)
        self.assertEqual(session.last_started_selection, selection)

    def test_restart_uses_last_started_selection(self) -> None:
        session = Connect4UISessionState("human", "human")
        session.start("human", "minimax-d2-v1")
        session.update_setup_selection("random-v1", "random-v1")

        selection = session.restart()

        self.assertEqual(session.mode, MODE_PLAYING)
        self.assertEqual(selection, PlayerSelections("human", "minimax-d2-v1"))
        self.assertEqual(session.last_started_selection, selection)

    def test_back_restores_last_started_selection_to_setup(self) -> None:
        session = Connect4UISessionState("human", "human")
        session.start("human", "minimax-d4-v1")
        session.update_setup_selection("random-v1", "random-v1")

        selection = session.back()

        self.assertEqual(session.mode, MODE_SETUP)
        self.assertEqual(selection, PlayerSelections("human", "minimax-d4-v1"))
        self.assertEqual(session.setup_selection, selection)

    def test_restart_before_start_raises(self) -> None:
        session = Connect4UISessionState("human", "human")

        with self.assertRaisesRegex(RuntimeError, "Cannot restart before a game has been started"):
            session.restart()


if __name__ == "__main__":
    unittest.main()
