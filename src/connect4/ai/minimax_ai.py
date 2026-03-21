from __future__ import annotations

from math import inf
from typing import Iterable, Optional, Sequence, Tuple

from connect4.core import EMPTY

from .ai_base import Connect4AIPlayer

Board = Tuple[Tuple[int, ...], ...]
Move = Tuple[int, int]


class MinimaxAI(Connect4AIPlayer):
    """Depth-limited minimax AI with alpha-beta pruning.

    The implementation is intentionally written in a very explicit style:
    - each recursive search step works on an immutable board snapshot,
    - terminal checks are isolated,
    - the evaluation function is split into small helpers,
    so the control flow is easier to read and reason about.

    Parameters
    ----------
    max_depth:
        Maximum ply depth for the minimax search. A value around 4-5 keeps the
        UI responsive while still producing clearly stronger play than random.
    """

    name = "MinimaxAI"

    # Large terminal values dominate heuristic scores, so an actual forced win
    # always beats "good-looking" non-terminal positions.
    _WIN_SCORE = 1_000_000

    def __init__(self, max_depth: int = 4) -> None:
        if max_depth <= 0:
            raise ValueError("max_depth must be positive.")
        self.max_depth = max_depth

    def choose_move(
        self,
        board: Sequence[Sequence[int]],
        player_id: int,
        valid_moves: Sequence[int],
        last_move: Optional[Tuple[int, int]],
    ) -> int:
        if not valid_moves:
            raise ValueError("MinimaxAI received no valid moves.")

        board_state = self._normalize_board(board)
        ordered_moves = self._ordered_moves(valid_moves, cols=len(board_state[0]))

        best_move = ordered_moves[0]
        best_score = -inf
        alpha = -inf
        beta = inf

        for col in ordered_moves:
            next_board, row = self._drop_piece(board_state, col, player_id)
            score = self._minimax(
                board=next_board,
                depth=self.max_depth - 1,
                alpha=alpha,
                beta=beta,
                current_player=self._other_player(player_id),
                maximizing_player=player_id,
                last_move=(row, col),
            )

            if score > best_score:
                best_score = score
                best_move = col

            alpha = max(alpha, best_score)

        return best_move

    def _minimax(
        self,
        board: Board,
        depth: int,
        alpha: float,
        beta: float,
        current_player: int,
        maximizing_player: int,
        last_move: Optional[Move],
    ) -> int:
        winner = self._winner_from_last_move(board, last_move)
        if winner == maximizing_player:
            # Prefer faster wins: a win found with more search depth remaining
            # means it happens sooner in the game tree.
            return self._WIN_SCORE + depth
        if winner == self._other_player(maximizing_player):
            # Prefer lines that postpone an unavoidable loss as long as possible.
            return -self._WIN_SCORE - depth

        valid_moves = self._valid_moves(board)
        if not valid_moves:
            return 0

        if depth == 0:
            return self._evaluate_board(board, maximizing_player)

        ordered_moves = self._ordered_moves(valid_moves, cols=len(board[0]))

        if current_player == maximizing_player:
            value = -inf
            for col in ordered_moves:
                next_board, row = self._drop_piece(board, col, current_player)
                value = max(
                    value,
                    self._minimax(
                        board=next_board,
                        depth=depth - 1,
                        alpha=alpha,
                        beta=beta,
                        current_player=self._other_player(current_player),
                        maximizing_player=maximizing_player,
                        last_move=(row, col),
                    ),
                )
                alpha = max(alpha, value)
                if alpha >= beta:
                    break
            return int(value)

        value = inf
        for col in ordered_moves:
            next_board, row = self._drop_piece(board, col, current_player)
            value = min(
                value,
                self._minimax(
                    board=next_board,
                    depth=depth - 1,
                    alpha=alpha,
                    beta=beta,
                    current_player=self._other_player(current_player),
                    maximizing_player=maximizing_player,
                    last_move=(row, col),
                ),
            )
            beta = min(beta, value)
            if alpha >= beta:
                break
        return int(value)

    def _evaluate_board(self, board: Board, player_id: int) -> int:
        """Score a non-terminal board from `player_id`'s perspective.

        The heuristic is based on all contiguous windows of length 4, because
        every Connect4 win is made from one of those windows.
        """

        opponent_id = self._other_player(player_id)
        rows = len(board)
        cols = len(board[0])
        score = 0

        # Center control is valuable because the middle columns participate in
        # more potential four-in-a-row patterns than the outer columns.
        center_col = cols // 2
        center_count = sum(1 for row in range(rows) if board[row][center_col] == player_id)
        score += center_count * 6

        for row in range(rows):
            for col in range(cols - 3):
                window = [board[row][col + offset] for offset in range(4)]
                score += self._score_window(window, player_id, opponent_id)

        for row in range(rows - 3):
            for col in range(cols):
                window = [board[row + offset][col] for offset in range(4)]
                score += self._score_window(window, player_id, opponent_id)

        for row in range(rows - 3):
            for col in range(cols - 3):
                window = [board[row + offset][col + offset] for offset in range(4)]
                score += self._score_window(window, player_id, opponent_id)

        for row in range(3, rows):
            for col in range(cols - 3):
                window = [board[row - offset][col + offset] for offset in range(4)]
                score += self._score_window(window, player_id, opponent_id)

        return score

    def _score_window(self, window: Sequence[int], player_id: int, opponent_id: int) -> int:
        """Assign a value to a single 4-cell window.

        The weights bias the search toward:
        - finishing our own 3-in-a-row threats,
        - blocking the opponent's immediate threats,
        - slowly accumulating value from flexible 2-in-a-row shapes.
        """

        player_count = window.count(player_id)
        opponent_count = window.count(opponent_id)
        empty_count = window.count(EMPTY)

        if player_count > 0 and opponent_count > 0:
            return 0

        if player_count == 4:
            return 10_000
        if player_count == 3 and empty_count == 1:
            return 100
        if player_count == 2 and empty_count == 2:
            return 10
        if player_count == 1 and empty_count == 3:
            return 1

        if opponent_count == 4:
            return -10_000
        if opponent_count == 3 and empty_count == 1:
            return -120
        if opponent_count == 2 and empty_count == 2:
            return -12
        if opponent_count == 1 and empty_count == 3:
            return -1

        return 0

    def _winner_from_last_move(self, board: Board, last_move: Optional[Move]) -> int:
        """Check whether the most recent move ended the game.

        Only the latest move can create a new four-in-a-row, so checking from
        that coordinate is much cheaper than scanning the whole board.
        """

        if last_move is None:
            return 0

        row, col = last_move
        player = board[row][col]
        if player == EMPTY:
            return 0

        for row_delta, col_delta in ((0, 1), (1, 0), (1, 1), (-1, 1)):
            count = (
                self._count_direction(board, row, col, row_delta, col_delta, player)
                + self._count_direction(board, row, col, -row_delta, -col_delta, player)
                - 1
            )
            if count >= 4:
                return player

        return 0

    def _count_direction(
        self,
        board: Board,
        row: int,
        col: int,
        row_delta: int,
        col_delta: int,
        player: int,
    ) -> int:
        rows = len(board)
        cols = len(board[0])
        count = 0
        current_row = row
        current_col = col

        while (
            0 <= current_row < rows
            and 0 <= current_col < cols
            and board[current_row][current_col] == player
        ):
            count += 1
            current_row += row_delta
            current_col += col_delta

        return count

    def _drop_piece(self, board: Board, col: int, player_id: int) -> Tuple[Board, int]:
        mutable_board = [list(row) for row in board]

        for row in range(len(mutable_board) - 1, -1, -1):
            if mutable_board[row][col] == EMPTY:
                mutable_board[row][col] = player_id
                return tuple(tuple(board_row) for board_row in mutable_board), row

        raise ValueError(f"Column {col} is full.")

    def _valid_moves(self, board: Board) -> Tuple[int, ...]:
        return tuple(col for col, cell in enumerate(board[0]) if cell == EMPTY)

    def _ordered_moves(self, valid_moves: Iterable[int], cols: int) -> Tuple[int, ...]:
        center = cols // 2

        # Searching center-first is useful for two reasons:
        # 1. center moves are often genuinely stronger in Connect4,
        # 2. good moves searched early make alpha-beta pruning cut off more work.
        return tuple(sorted(valid_moves, key=lambda col: (abs(center - col), col)))

    def _normalize_board(self, board: Sequence[Sequence[int]]) -> Board:
        return tuple(tuple(int(cell) for cell in row) for row in board)

    def _other_player(self, player_id: int) -> int:
        return 1 if player_id == 2 else 2
