from __future__ import annotations

from typing import Optional
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from connect4.ai import Connect4AIPlayer, RandomAI
from connect4.core import Connect4Config, Connect4Game, EMPTY, MoveResult, P1, P2


class Connect4TkApp:
    """Interactive Connect4 app for local desktops using Tkinter.

    Usage
    -----
    app = Connect4TkApp()
    app.run()

    Notes
    -----
    - Human moves: click a column button (1..7).
    - AI moves: performed automatically.
    - Subclass `Connect4AIPlayer` and wire it into `_make_player` if desired.
    """

    def __init__(self, config: Optional[Connect4Config] = None) -> None:
        self.game = Connect4Game(config=config)

        # Player controllers: None means human; otherwise an AI instance
        self.p1_ai: Optional[Connect4AIPlayer] = None
        self.p2_ai: Optional[Connect4AIPlayer] = None

        # Token to invalidate scheduled AI moves when a new game starts
        self._turn_token = 0
        self._ai_job_id: Optional[str] = None
        self._ai_delay_ms = 200

        # ---- UI widgets ----
        self.root = tk.Tk()
        self.root.title("Connect4 (Tkinter)")

        self.status_var = tk.StringVar()
        self.status_label = ttk.Label(self.root, textvariable=self.status_var, font=("Arial", 12, "bold"))

        # Control panel
        self.panel_controls = ttk.Frame(self.root, padding=10, relief=tk.RIDGE, borderwidth=2)
        self.panel_game = ttk.Frame(self.root, padding=10)

        ttk.Label(self.panel_controls, text="New Game", font=("Arial", 12, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))

        ttk.Label(self.panel_controls, text="Player 1:").grid(row=1, column=0, sticky="e", padx=(0, 6))
        ttk.Label(self.panel_controls, text="Player 2:").grid(row=2, column=0, sticky="e", padx=(0, 6))

        self.dd_p1_var = tk.StringVar(value="Human")
        self.dd_p2_var = tk.StringVar(value="Human")
        options = ["Human", "AI: RandomAI"]
        self.dd_p1 = ttk.OptionMenu(self.panel_controls, self.dd_p1_var, self.dd_p1_var.get(), *options)
        self.dd_p2 = ttk.OptionMenu(self.panel_controls, self.dd_p2_var, self.dd_p2_var.get(), *options)
        self.dd_p1.grid(row=1, column=1, sticky="w")
        self.dd_p2.grid(row=2, column=1, sticky="w")

        self.btn_start = ttk.Button(self.panel_controls, text="Start New Game", command=self._on_start_new_game)
        self.btn_start.grid(row=3, column=0, columnspan=2, pady=(10, 0), sticky="ew")

        # Column buttons
        self.col_buttons = []
        self.btn_frame = ttk.Frame(self.panel_game)
        for c in range(self.game.cols):
            btn = ttk.Button(self.btn_frame, text=f"▼ {c+1}", width=4, command=lambda cc=c: self._on_human_move(cc))
            btn.grid(row=0, column=c, padx=2, pady=2)
            self.col_buttons.append(btn)

        # Board canvas
        self.cell_size = 70
        self.cell_padding = 8
        canvas_width = self.game.cols * self.cell_size
        canvas_height = self.game.rows * self.cell_size
        self.canvas = tk.Canvas(self.panel_game, width=canvas_width, height=canvas_height, bg="white", highlightthickness=1, highlightbackground="#ccc")

        # Log area
        ttk.Label(self.panel_game, text="Log", font=("Arial", 11, "bold")).grid(row=3, column=0, sticky="w", pady=(10, 0))
        self.log = ScrolledText(self.panel_game, width=50, height=10, state="disabled", font=("Consolas", 10))

        # Layout
        self.status_label.grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 2))
        self.panel_controls.grid(row=1, column=0, sticky="nsw", padx=(10, 5), pady=(0, 10))
        self.panel_game.grid(row=1, column=1, sticky="nsew", padx=(5, 10), pady=(0, 10))
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(1, weight=1)
        self.btn_frame.grid(row=1, column=0, sticky="w")
        self.canvas.grid(row=2, column=0, sticky="w", pady=(10, 0))
        self.log.grid(row=4, column=0, sticky="nsew", pady=(4, 0))
        self.panel_game.rowconfigure(4, weight=1)
        self.panel_game.columnconfigure(0, weight=1)

        self._draw_board()
        self._sync_controls()

    # ---------- public ----------
    def run(self) -> None:
        self.root.mainloop()

    # ---------- logging ----------
    def _log(self, msg: str) -> None:
        self.log.configure(state="normal")
        self.log.insert(tk.END, msg + "\n")
        self.log.see(tk.END)
        self.log.configure(state="disabled")

    # ---------- state helpers ----------
    def _is_ai_player(self, player_id: int) -> bool:
        return (player_id == P1 and self.p1_ai is not None) or (player_id == P2 and self.p2_ai is not None)

    def _current_ai(self) -> Optional[Connect4AIPlayer]:
        return self.p1_ai if self.game.current_player == P1 else self.p2_ai

    def _status_text(self) -> str:
        if self.game.winner == P1:
            return "Player 1 wins! 🎉"
        if self.game.winner == P2:
            return "Player 2 wins! 🎉"
        if self.game.is_draw:
            return "Draw game."
        p = self.game.current_player
        kind = "AI" if self._is_ai_player(p) else "Human"
        return f"Turn: Player {p} ({kind})"

    def _sync_controls(self) -> None:
        ended = (self.game.winner != 0) or self.game.is_draw
        human_turn = not self._is_ai_player(self.game.current_player)
        valid = set(self.game.valid_moves())

        for c, b in enumerate(self.col_buttons):
            is_enabled = not ended and human_turn and (c in valid)
            b.state(["!disabled"] if is_enabled else ["disabled"])

        self.status_var.set(self._status_text())
        self._schedule_ai_if_needed()

    # ---------- rendering ----------
    def _draw_board(self) -> None:
        self.canvas.delete("all")
        for r in range(self.game.rows):
            for c in range(self.game.cols):
                x0 = c * self.cell_size + self.cell_padding
                y0 = r * self.cell_size + self.cell_padding
                x1 = (c + 1) * self.cell_size - self.cell_padding
                y1 = (r + 1) * self.cell_size - self.cell_padding

                v = self.game.board[r][c]
                if v == EMPTY:
                    fill = "white"
                    outline = "#999"
                elif v == P1:
                    fill = "#e63946"
                    outline = "#8b1d2c"
                else:
                    fill = "#ffd166"
                    outline = "#b37a00"

                self.canvas.create_oval(x0, y0, x1, y1, fill=fill, outline=outline, width=2)

        if self.game.last_move is not None:
            lr, lc = self.game.last_move
            x0 = lc * self.cell_size + self.cell_padding / 2
            y0 = lr * self.cell_size + self.cell_padding / 2
            x1 = (lc + 1) * self.cell_size - self.cell_padding / 2
            y1 = (lr + 1) * self.cell_size - self.cell_padding / 2
            self.canvas.create_oval(x0, y0, x1, y1, outline="#1d4ed8", width=3)

    # ---------- new game ----------
    def _make_player(self, selection: str) -> Optional[Connect4AIPlayer]:
        if selection == "Human":
            return None
        if selection == "AI: RandomAI":
            return RandomAI()
        raise ValueError(f"Unknown player type: {selection}")

    def _cancel_ai_job(self) -> None:
        if self._ai_job_id is not None:
            try:
                self.root.after_cancel(self._ai_job_id)
            except Exception:
                pass
            self._ai_job_id = None

    def _on_start_new_game(self) -> None:
        self._cancel_ai_job()
        self.p1_ai = self._make_player(self.dd_p1_var.get())
        self.p2_ai = self._make_player(self.dd_p2_var.get())

        self.game.reset(first_player=P1)
        self._turn_token += 1

        if self.p1_ai is not None:
            self.p1_ai.on_new_game(P1)
        if self.p2_ai is not None:
            self.p2_ai.on_new_game(P2)

        self._log(f"=== New game started. First: Player {P1} ===")
        self._draw_board()
        self._sync_controls()

    # ---------- moves ----------
    def _after_move_hooks(self, res: MoveResult) -> None:
        if not res.placed or res.row is None or res.col is None:
            return

        move = (res.row, res.col)
        mover = self.game.board[res.row][res.col]
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

    def _schedule_ai_if_needed(self) -> None:
        self._cancel_ai_job()
        if (
            self.game.winner == 0
            and not self.game.is_draw
            and self._is_ai_player(self.game.current_player)
        ):
            token = self._turn_token
            self._ai_job_id = self.root.after(self._ai_delay_ms, lambda: self._do_ai_turn(token))

    def _do_ai_turn(self, token: int) -> None:
        if token != self._turn_token:
            return

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


def main() -> None:
    app = Connect4TkApp()
    app.run()


if __name__ == "__main__":
    main()
