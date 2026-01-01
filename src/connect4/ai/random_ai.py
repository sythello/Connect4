from __future__ import annotations

# import asyncio
import random
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple
import time

import numpy as np

from connect4.core import Connect4Game
from connect4.ai import Connect4AIPlayer


class RandomAI(Connect4AIPlayer):
    """Example AI: chooses uniformly at random among valid moves."""

    name = "RandomAI"

    def choose_move(self, board, player_id, valid_moves, last_move) -> int:
        return random.choice(list(valid_moves))