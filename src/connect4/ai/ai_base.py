from __future__ import annotations

# import asyncio
import random
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple
import time

import numpy as np

from connect4.core import Connect4Game

class Connect4AIPlayer:
    """Base class for Connect4 AI players.

    Subclass this class and override :meth:`choose_move` to implement your AI.

    The UI/game engine calls :meth:`choose_move` whenever it is the AI's turn.

    Contract
    --------
    - `choose_move(...)` MUST return a column index in ``[0, COLS-1]``.
    - The returned column MUST be a valid move (i.e., the column is not full).
    - The AI should treat the `board` as read-only.

    Board representation
    --------------------
    The board is a 2D array-like object (ROWS x COLS) where:
    - 0 = empty
    - 1 = player 1 piece
    - 2 = player 2 piece

    Player identity
    ---------------
    - `player_id` passed to `choose_move` is 1 or 2, matching the board encoding.

    Performance notes
    -----------------
    If your AI does heavier computation (minimax/MCTS/RL inference), consider:
    - caching,
    - limiting depth/rollouts,
    - adding time budgets,
    so the notebook UI remains responsive.
    """

    name: str = "Connect4AIPlayer"

    def choose_move(
        self,
        board: Sequence[Sequence[int]],
        player_id: int,
        valid_moves: Sequence[int],
        last_move: Optional[Tuple[int, int]],
    ) -> int:
        """Choose the next move (column index) for the AI.

        Parameters
        ----------
        board:
            Current board state (ROWS x COLS) with values in {0,1,2}.
        player_id:
            The player ID for this AI on this turn: 1 or 2.
        valid_moves:
            Sequence of currently valid columns (not full).
        last_move:
            Last move played as (row, col), or None if no moves yet.

        Returns
        -------
        int
            Column index in [0, COLS-1] to drop a piece.

        Raises
        ------
        NotImplementedError
            If the subclass does not override this method.
        """
        raise NotImplementedError("Subclass must implement choose_move().")

    def on_new_game(self, player_id: int) -> None:
        """Hook called when a new game starts.

        Override to reset internal AI state (e.g., search tree, RNG seed, etc.).

        Parameters
        ----------
        player_id:
            The player ID (1 or 2) that this AI controls in the new game.
        """
        return

    def on_opponent_move(self, move: Tuple[int, int]) -> None:
        """Hook called after the opponent makes a move.

        Override to update internal state incrementally.

        Parameters
        ----------
        move:
            Opponent's move as (row, col).
        """
        return

    def on_ai_move(self, move: Tuple[int, int]) -> None:
        """Hook called after THIS AI makes a move.

        Override to update internal state incrementally.

        Parameters
        ----------
        move:
            This AI's move as (row, col).
        """
        return