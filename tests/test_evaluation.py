from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from connect4.ai.ai_base import Connect4AIPlayer
from connect4.evaluation import (
    AIEntrant,
    AIEntrantRegistry,
    EvaluationConfig,
    LadderSnapshot,
    build_calibration_field,
    build_default_registry,
    load_ladder,
    run_round_robin,
    save_ladder,
)


class PreferredColumnAI(Connect4AIPlayer):
    def __init__(self, preferred_columns):
        self.preferred_columns = tuple(preferred_columns)

    def choose_move(self, board, player_id, valid_moves, last_move) -> int:
        for column in self.preferred_columns:
            if column in valid_moves:
                return column
        return valid_moves[0]


class IllegalMoveAI(Connect4AIPlayer):
    def choose_move(self, board, player_id, valid_moves, last_move) -> int:
        return 999


class CrashAI(Connect4AIPlayer):
    def choose_move(self, board, player_id, valid_moves, last_move) -> int:
        raise RuntimeError("boom")


def make_preferred_entrant(
    entrant_id: str,
    preferred_columns,
    *,
    family: str = "ScriptedAI",
    version: str = "v1",
    is_anchor: bool = False,
    active: bool = True,
) -> AIEntrant:
    return AIEntrant(
        id=entrant_id,
        display_name=entrant_id,
        family=family,
        version=version,
        is_anchor=is_anchor,
        active=active,
        metadata={"preferred_columns": list(preferred_columns)},
        factory=lambda seed=None, columns=tuple(preferred_columns): PreferredColumnAI(columns),
    )


def make_illegal_entrant(entrant_id: str) -> AIEntrant:
    return AIEntrant(
        id=entrant_id,
        display_name=entrant_id,
        family="BrokenAI",
        version="v1",
        metadata={},
        factory=lambda seed=None: IllegalMoveAI(),
    )


def make_crash_entrant(entrant_id: str) -> AIEntrant:
    return AIEntrant(
        id=entrant_id,
        display_name=entrant_id,
        family="BrokenAI",
        version="v1",
        metadata={},
        factory=lambda seed=None: CrashAI(),
    )


class EvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.anchor_a = make_preferred_entrant("anchor-a", [0, 1, 2, 3], is_anchor=True)
        self.anchor_b = make_preferred_entrant("anchor-b", [1, 2, 3, 4], is_anchor=True)
        self.anchor_c = make_preferred_entrant("anchor-c", [3, 2, 4, 1], is_anchor=True)
        self.active_rated = make_preferred_entrant("active-rated", [6, 5, 4, 3], active=True)
        self.inactive_rated = make_preferred_entrant("inactive-rated", [2, 3, 4, 5], active=False)
        self.candidate = make_preferred_entrant("candidate", [0, 2, 4, 6])
        self.registry = AIEntrantRegistry(
            [
                self.anchor_a,
                self.anchor_b,
                self.anchor_c,
                self.active_rated,
                self.inactive_rated,
                self.candidate,
            ]
        )
        self.config = EvaluationConfig(
            games_per_pair=2,
            seed=123,
            provisional_games=3,
            anchor_ids=(self.anchor_a.id, self.anchor_b.id, self.anchor_c.id),
        )

    def test_registry_rejects_duplicate_ids(self) -> None:
        with self.assertRaises(ValueError):
            AIEntrantRegistry([self.anchor_a, self.anchor_a])

    def test_registry_requires_missing_and_real_anchor_ids(self) -> None:
        with self.assertRaises(ValueError):
            self.registry.require_anchor_ids(("missing-anchor",))

        with self.assertRaises(ValueError):
            self.registry.require_anchor_ids((self.active_rated.id,))

    def test_calibration_field_includes_anchors_and_active_rated_pool(self) -> None:
        ladder = LadderSnapshot(anchor_ids=self.config.anchor_ids)
        ladder.ensure_entry(self.active_rated)
        ladder.ensure_entry(self.inactive_rated)

        entrants = build_calibration_field(
            registry=self.registry,
            ladder=ladder,
            new_entrant_ids=(self.candidate.id,),
            anchor_ids=self.config.anchor_ids,
        )

        self.assertEqual(
            [entrant.id for entrant in entrants],
            [
                self.candidate.id,
                self.anchor_a.id,
                self.anchor_b.id,
                self.anchor_c.id,
                self.active_rated.id,
            ],
        )

    def test_cross_run_continuity_keeps_existing_ratings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ratings_path = Path(temp_dir) / "ladder.json"
            config = EvaluationConfig(
                games_per_pair=2,
                seed=11,
                provisional_games=3,
                ratings_path=str(ratings_path),
                anchor_ids=self.config.anchor_ids,
            )

            first_ladder = load_ladder(
                ratings_path,
                initial_rating=config.initial_rating,
                k_factor=config.k_factor,
                provisional_games=config.provisional_games,
                anchor_ids=config.anchor_ids,
            )
            initial_field = build_calibration_field(
                registry=self.registry,
                ladder=first_ladder,
                new_entrant_ids=(self.active_rated.id,),
                anchor_ids=config.anchor_ids,
            )
            first_run = run_round_robin(initial_field, config, ladder=first_ladder)
            save_ladder(first_run.snapshot, ratings_path)

            loaded = load_ladder(
                ratings_path,
                initial_rating=config.initial_rating,
                k_factor=config.k_factor,
                provisional_games=config.provisional_games,
                anchor_ids=config.anchor_ids,
            )
            self.assertAlmostEqual(
                loaded.entries[self.active_rated.id].rating,
                first_run.snapshot.entries[self.active_rated.id].rating,
            )

            second_field = build_calibration_field(
                registry=self.registry,
                ladder=loaded,
                new_entrant_ids=(self.candidate.id,),
                anchor_ids=config.anchor_ids,
            )
            second_run = run_round_robin(second_field, config, ladder=loaded)

            self.assertGreater(
                second_run.snapshot.entries[self.active_rated.id].games,
                loaded.entries[self.active_rated.id].games,
            )
            self.assertIn(self.candidate.id, second_run.snapshot.entries)

    def test_round_robin_is_deterministic_and_balanced(self) -> None:
        entrants = (self.anchor_a, self.anchor_b, self.anchor_c)
        run_one = run_round_robin(entrants, self.config, ladder=LadderSnapshot(anchor_ids=self.config.anchor_ids))
        run_two = run_round_robin(entrants, self.config, ladder=LadderSnapshot(anchor_ids=self.config.anchor_ids))

        matches_one = [
            (match.player_one_entrant_id, match.player_two_entrant_id, match.winner_id, match.termination)
            for match in run_one.matches
        ]
        matches_two = [
            (match.player_one_entrant_id, match.player_two_entrant_id, match.winner_id, match.termination)
            for match in run_two.matches
        ]
        self.assertEqual(matches_one, matches_two)

        first_player_counts = Counter(match.player_one_entrant_id for match in run_one.matches if self.anchor_a.id in (match.player_one_entrant_id, match.player_two_entrant_id))
        self.assertEqual(first_player_counts[self.anchor_a.id], 2)

    def test_new_entries_are_flagged_provisional_until_threshold(self) -> None:
        run = run_round_robin(
            (self.anchor_a, self.anchor_b),
            self.config,
            ladder=LadderSnapshot(anchor_ids=self.config.anchor_ids),
        )
        self.assertTrue(run.snapshot.entries[self.anchor_a.id].is_provisional(self.config.provisional_games))

        longer_config = EvaluationConfig(
            games_per_pair=4,
            seed=self.config.seed,
            provisional_games=3,
            anchor_ids=self.config.anchor_ids,
        )
        longer_run = run_round_robin(
            (self.anchor_a, self.anchor_b),
            longer_config,
            ladder=LadderSnapshot(anchor_ids=self.config.anchor_ids),
        )
        self.assertFalse(longer_run.snapshot.entries[self.anchor_a.id].is_provisional(longer_config.provisional_games))

    def test_invalid_and_crashing_ai_receive_forfeit_losses(self) -> None:
        stable = make_preferred_entrant("stable", [0, 1, 2, 3])
        illegal = make_illegal_entrant("illegal")
        crashing = make_crash_entrant("crashy")

        illegal_run = run_round_robin(
            (stable, illegal),
            self.config,
            ladder=LadderSnapshot(anchor_ids=self.config.anchor_ids),
        )
        illegal_matches = [match for match in illegal_run.matches if match.forfeit_loser_id == illegal.id]
        self.assertTrue(illegal_matches)
        self.assertEqual(illegal_run.snapshot.entries[illegal.id].forfeit_losses, len(illegal_matches))

        crash_run = run_round_robin(
            (stable, crashing),
            self.config,
            ladder=LadderSnapshot(anchor_ids=self.config.anchor_ids),
        )
        crash_matches = [match for match in crash_run.matches if match.forfeit_loser_id == crashing.id]
        self.assertTrue(crash_matches)
        self.assertEqual(crash_run.snapshot.entries[crashing.id].forfeit_losses, len(crash_matches))

    def test_driver_script_updates_ratings_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ratings_path = Path(temp_dir) / "elo.json"
            script_path = ROOT / "scripts" / "evaluate_ai_strength.py"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(script_path),
                    "calibration",
                    "random-v1",
                    "--games-per-pair",
                    "2",
                    "--seed",
                    "5",
                    "--ratings-path",
                    str(ratings_path),
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                check=True,
            )

            self.assertTrue(ratings_path.exists())
            self.assertIn("Saved ladder", completed.stdout)

            with ratings_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)

            self.assertIn("random-v1", payload["entries"])
            self.assertIn("minimax-d4-v1", payload["entries"])


class DefaultRegistryTests(unittest.TestCase):
    def test_default_registry_contains_anchor_ids(self) -> None:
        registry = build_default_registry()
        self.assertEqual(registry.anchor_ids(), ("random-v1", "minimax-d2-v1", "minimax-d4-v1"))


if __name__ == "__main__":
    unittest.main()
