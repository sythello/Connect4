from __future__ import annotations

# import asyncio
from dataclasses import dataclass
from typing import List, Optional, Tuple


EMPTY = 0
P1 = 1
P2 = 2


@dataclass(frozen=True)
class Connect4Config:
    rows: int = 6
    cols: int = 7

    def __post_init__(self) -> None:
        if self.rows <= 0 or self.cols <= 0:
            raise ValueError("Connect4 board dimensions must be positive.")

@dataclass
class MoveResult:
    placed: bool
    row: Optional[int] = None
    col: Optional[int] = None
    winner: int = 0   # 0=none, 1/2=winner
    is_draw: bool = False


class Connect4Game:
    """Headless Connect4 engine (UI-agnostic).

    Parameters
    ----------
    config:
        Optional :class:`Connect4Config` to control board dimensions. If omitted,
        the default 6x7 board is used.
    """

    def __init__(self, config: Optional[Connect4Config] = None) -> None:
        self.config = config or Connect4Config()
        self.board = [[EMPTY for _ in range(self.cols)] for _ in range(self.rows)]
        self.current_player = P1
        self.last_move: Optional[Tuple[int, int]] = None
        self.winner = 0
        self.is_draw = False

    def reset(self, first_player: int = P1) -> None:
        self.board = [[EMPTY for _ in range(self.cols)] for _ in range(self.rows)]
        self.current_player = first_player
        self.last_move = None
        self.winner = 0
        self.is_draw = False

    def valid_moves(self) -> List[int]:
        return [c for c in range(self.cols) if self.board[0][c] == EMPTY]

    def drop_piece(self, col: int) -> MoveResult:
        if self.winner != 0 or self.is_draw:
            return MoveResult(placed=False)

        if col < 0 or col >= self.cols:
            return MoveResult(placed=False)

        if self.board[0][col] != EMPTY:
            return MoveResult(placed=False)

        r = self.rows - 1
        while r >= 0 and self.board[r][col] != EMPTY:
            r -= 1
        if r < 0:
            return MoveResult(placed=False)

        self.board[r][col] = self.current_player
        self.last_move = (r, col)

        if self._check_win_from(r, col, self.current_player):
            self.winner = self.current_player
        elif len(self.valid_moves()) == 0:
            self.is_draw = True

        result = MoveResult(
            placed=True, row=r, col=col, winner=self.winner, is_draw=self.is_draw
        )

        if self.winner == 0 and not self.is_draw:
            self.current_player = P2 if self.current_player == P1 else P1

        return result

    def _check_win_from(self, r: int, c: int, player: int) -> bool:
        for dr, dc in [(0, 1), (1, 0), (1, 1), (-1, 1)]:
            count = (
                self._count_dir(r, c, dr, dc, player)
                + self._count_dir(r, c, -dr, -dc, player)
                - 1
            )
            if count >= 4:
                return True
        return False

    def _count_dir(self, r: int, c: int, dr: int, dc: int, player: int) -> int:
        rr, cc = r, c
        count = 0
        while 0 <= rr < self.rows and 0 <= cc < self.cols and self.board[rr][cc] == player:
            count += 1
            rr += dr
            cc += dc
        return count

    @property
    def rows(self) -> int:
        return self.config.rows

    @property
    def cols(self) -> int:
        return self.config.cols
