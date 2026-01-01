from typing import List, Optional

import matplotlib.pyplot as plt
import numpy as np

import ipywidgets as widgets
from IPython.display import display, clear_output

from connect4.core import Connect4Config, Connect4Game, EMPTY, MoveResult, P1, P2
from connect4.ai import Connect4AIPlayer, RandomAI

class Connect4WidgetApp:
    """Interactive Connect4 app for Jupyter/Colab using ipywidgets + matplotlib.

    Usage
    -----
    app = Connect4WidgetApp()
    app.display()

    Notes
    -----
    - Human moves: click a column button (1..7).
    - AI moves: performed automatically
    - Subclass `Connect4AIPlayer` and wire it into `_make_player` if desired.
    """

    def __init__(self, config: Optional[Connect4Config] = None) -> None:
        self.game = Connect4Game(config=config)

        # Player controllers: None means human; otherwise an AI instance
        self.p1_ai: Optional[Connect4AIPlayer] = None
        self.p2_ai: Optional[Connect4AIPlayer] = None

        # Token to invalidate scheduled AI moves when a new game starts
        self._turn_token = 0
        # self._ai_task: Optional[asyncio.Task] = None

        # ---- UI widgets ----
        self.status = widgets.HTML(value="<b>Welcome to Connect4</b>")

        self.dd_p1 = widgets.Dropdown(
            options=["Human", "AI: RandomAI"],
            value="Human",
            description="Player 1:"
        )
        self.dd_p2 = widgets.Dropdown(
            options=["Human", "AI: RandomAI"],
            value="Human",
            description="Player 2:"
        )
        # self.dd_first = widgets.Dropdown(
        #     options=["Player 1", "Player 2"],
        #     value="Player 1",
        #     description="First:"
        # )
        self.btn_start = widgets.Button(description="Start New Game", button_style="success")
        self.btn_start.on_click(self._on_start_new_game)

        # Column buttons
        self.col_buttons: List[widgets.Button] = []
        for c in range(self.game.cols):
            b = widgets.Button(description=f"▼ {c+1}", layout=widgets.Layout(width="55px"))
            b.on_click(lambda _, cc=c: self._on_human_move(cc))
            self.col_buttons.append(b)

        self.row_buttons = widgets.HBox(self.col_buttons)

        # Output areas
        self.out_board = widgets.Output()
        self.out_log = widgets.Output(layout=widgets.Layout(max_height="180px", overflow="auto"))

        self.panel_new_game = widgets.VBox(
            [
                widgets.HTML("<b>New Game</b>"),
                self.dd_p1,
                self.dd_p2,
                # self.dd_first,
                self.btn_start,
            ],
            layout=widgets.Layout(border="1px solid #ddd", padding="10px", width="320px"),
        )

        self.panel_game = widgets.VBox(
            [
                self.status,
                self.row_buttons,
                self.out_board,
                widgets.HTML("<b>Log</b>"),
                self.out_log,
            ]
        )

        self.root = widgets.HBox([self.panel_new_game, self.panel_game], gap="18px")

        self._draw_board()
        self._sync_controls()

    # ---------- public ----------
    def display(self) -> None:
        display(self.root)

    # ---------- logging ----------
    def _log(self, msg: str) -> None:
        with self.out_log:
            print(msg)

    # ---------- state helpers ----------
    def _is_ai_player(self, player_id: int) -> bool:
        return (player_id == P1 and self.p1_ai is not None) or (player_id == P2 and self.p2_ai is not None)

    def _current_ai(self) -> Optional[Connect4AIPlayer]:
        return self.p1_ai if self.game.current_player == P1 else self.p2_ai

    def _status_text(self) -> str:
        if self.game.winner == P1:
            return "<b>Player 1 wins! 🎉</b>"
        if self.game.winner == P2:
            return "<b>Player 2 wins! 🎉</b>"
        if self.game.is_draw:
            return "<b>Draw game.</b>"
        p = self.game.current_player
        kind = "AI" if self._is_ai_player(p) else "Human"
        return f"<b>Turn:</b> Player {p} ({kind})"

    def _sync_controls(self) -> None:
        ended = (self.game.winner != 0) or self.game.is_draw
        human_turn = not self._is_ai_player(self.game.current_player)
        valid = set(self.game.valid_moves())

        for c, b in enumerate(self.col_buttons):
            b.disabled = ended or (not human_turn) or (c not in valid)

        self.status.value = self._status_text()

        self._maybe_trigger_ai()    
        # if human turn, just does nothing and wait button click 

    # ---------- rendering ----------
    def _draw_board(self) -> None:
        board = np.array(self.game.board, dtype=int)

        with self.out_board:
            clear_output(wait=True)
            fig, ax = plt.subplots(figsize=(7, 6))
            ax.set_xlim(-0.5, self.game.cols - 0.5)
            ax.set_ylim(self.game.rows - 0.5, -0.5)
            ax.set_aspect("equal")
            ax.set_xticks(range(self.game.cols))
            ax.set_yticks(range(self.game.rows))
            ax.grid(True, linewidth=1)

            for r in range(self.game.rows):
                for c in range(self.game.cols):
                    v = board[r, c]
                    if v == EMPTY:
                        face, edge = "white", "gray"
                    elif v == P1:
                        face, edge = "red", "darkred"
                    else:
                        face, edge = "gold", "darkgoldenrod"

                    circle = plt.Circle((c, r), 0.40, facecolor=face, edgecolor=edge, linewidth=2)
                    ax.add_patch(circle)

            if self.game.last_move is not None:
                lr, lc = self.game.last_move
                ring = plt.Circle((lc, lr), 0.46, fill=False, edgecolor="dodgerblue", linewidth=3)
                ax.add_patch(ring)

            ax.set_xticklabels([str(i + 1) for i in range(self.game.cols)])
            ax.set_yticklabels([str(i + 1) for i in range(self.game.rows)])
            ax.set_title("Connect4 Board")
            plt.show()

    # ---------- new game ----------
    def _make_player(self, selection: str) -> Optional[Connect4AIPlayer]:
        if selection == "Human":
            return None
        if selection == "AI: RandomAI":
            return RandomAI()
        raise ValueError(f"Unknown player type: {selection}")

    def _on_start_new_game(self, _btn) -> None:
        # if self._ai_task is not None and not self._ai_task.done():
        #     self._ai_task.cancel()

        self.p1_ai = self._make_player(self.dd_p1.value)
        self.p2_ai = self._make_player(self.dd_p2.value)
        # first = P1 if self.dd_first.value == "Player 1" else P2

        self.game.reset(first_player=P1)
        self._turn_token += 1

        if self.p1_ai is not None:
            self.p1_ai.on_new_game(P1)
        if self.p2_ai is not None:
            self.p2_ai.on_new_game(P2)

        self._log(f"=== New game started. First: Player {P1} ===")
        self._draw_board()
        self._sync_controls()
        # self._maybe_trigger_ai()

    # ---------- moves ----------
    def _after_move_hooks(self, res: MoveResult) -> None:
        if not res.placed or res.row is None or res.col is None:
            return

        move = (res.row, res.col)
        mover = self.game.board[res.row][res.col]  # 1 or 2
        opponent = P2 if mover == P1 else P1

        if mover == P1 and self.p1_ai is not None:
            self.p1_ai.on_ai_move(move)
        if mover == P2 and self.p2_ai is not None:
            self.p2_ai.on_ai_move(move)

        if opponent == P1 and self.p1_ai is not None:
            self.p1_ai.on_opponent_move(move)
        if opponent == P2 and self.p2_ai is not None:
            self.p2_ai.on_opponent_move(move)

    def _on_human_move(self, col: int) -> None:
        if self.game.winner != 0 or self.game.is_draw:
            return
        if self._is_ai_player(self.game.current_player):
            return

        res = self.game.drop_piece(col)
        if not res.placed:
            self._log(f"Illegal move: column {col+1}")
            return

        curr_player_id = self.game.current_player
        self._log(f"Human (Player {curr_player_id}) played column {col+1}")
        self._after_move_hooks(res)
        self._draw_board()
        self._sync_controls()
        # self._maybe_trigger_ai()

    def _maybe_trigger_ai(self) -> None:
        """
        If it's an AI turn, make AI moves synchronously until
        a human turn or the game ends.
        """
        if (
            self.game.winner == 0
            and not self.game.is_draw
            and self._is_ai_player(self.game.current_player)
        ):
            self._do_ai_turn_sync()

    def _do_ai_turn_sync(self) -> None:
        # await asyncio.sleep(0.15)

        if self.game.winner != 0 or self.game.is_draw:
            return

        ai = self._current_ai()
        if ai is None:
            return

        valid = self.game.valid_moves()
        if not valid:
            return

        board_copy = tuple(tuple(row) for row in self.game.board)

        try:
            col = ai.choose_move(
                board=board_copy,
                player_id=self.game.current_player,
                valid_moves=tuple(valid),
                last_move=self.game.last_move,
            )
        except Exception as e:
            self._log(f"[AI ERROR] {ai.name} crashed: {e}")
            return

        if col not in valid:
            self._log(f"[AI ERROR] {ai.name} returned invalid move: {col}")
            return

        res = self.game.drop_piece(col)
        if not res.placed:
            self._log(f"[AI ERROR] {ai.name} attempted illegal move: {col}")
            return

        curr_player_id = self.game.current_player
        self._log(f"{ai.name} (Player {curr_player_id}) played column {col+1}")
        self._after_move_hooks(res)
        self._draw_board()
        self._sync_controls()
        # self._maybe_trigger_ai()
