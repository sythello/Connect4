from __future__ import annotations

from typing import Dict, Optional
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from connect4.ai import Connect4AIPlayer
from connect4.core import Connect4Config, Connect4Game, EMPTY, MoveResult, P1, P2
from connect4.ui.player_options import PlayerOption, load_player_options
from connect4.ui.session_state import (
    MODE_PLAYING,
    MODE_SETUP,
    Connect4UISessionState,
    PlayerSelections,
)


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
    - Supported player options are loaded from `ai_options.json`.
    """

    def __init__(self, config: Optional[Connect4Config] = None) -> None:
        self.game = Connect4Game(config=config)

        self.player_options = load_player_options()
        self.player_option_by_id: Dict[str, PlayerOption] = {
            option.id: option for option in self.player_options
        }
        self.player_option_by_label: Dict[str, PlayerOption] = {
            option.label: option for option in self.player_options
        }

        default_option_id = self.player_options[0].id
        self.session = Connect4UISessionState(
            default_p1_option_id=default_option_id,
            default_p2_option_id=default_option_id,
        )

        # Player controllers: None means human; otherwise an AI instance.
        self.p1_ai: Optional[Connect4AIPlayer] = None
        self.p2_ai: Optional[Connect4AIPlayer] = None

        # Token to invalidate scheduled AI moves when a new game starts or exits.
        self._turn_token = 0
        self._ai_job_id: Optional[str] = None
        self._ai_delay_ms = 200

        # Shared board sizing keeps the move buttons aligned with the board columns.
        self.cell_size = 70
        self.cell_padding = 8
        self.board_width = self.game.cols * self.cell_size
        self.board_height = self.game.rows * self.cell_size
        self.board_bg = "#1d4ed8"
        self.board_grid = "#93c5fd"

        # ---- UI widgets ----
        self.root = tk.Tk()
        self.root.title("Connect4 (Tkinter)")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self.container = ttk.Frame(self.root, padding=16)
        self.container.grid(row=0, column=0, sticky="nsew")
        self.container.columnconfigure(0, weight=1)
        self.container.rowconfigure(0, weight=1)

        default_label = self.player_option_by_id[default_option_id].label
        self.setup_p1_var = tk.StringVar(value=default_label)
        self.setup_p2_var = tk.StringVar(value=default_label)
        self.status_var = tk.StringVar(value="Choose players and start a game.")
        self.matchup_var = tk.StringVar(value="")

        self._build_setup_view()
        self._build_playing_view()

        self._set_setup_widgets(self.session.setup_selection)
        self._draw_board()
        self._show_mode(self.session.mode)
        self._sync_controls()

    # ---------- public ----------
    def run(self) -> None:
        self.root.mainloop()

    # ---------- UI construction ----------
    def _build_setup_view(self) -> None:
        self.view_setup = ttk.Frame(self.container, padding=(0, 12, 0, 0))
        self.view_setup.columnconfigure(0, weight=1)

        header = ttk.Frame(self.view_setup)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        ttk.Label(
            header,
            text="Game Setup",
            font=("Arial", 16, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="Choose how Player 1 and Player 2 will play, then start the match.",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        config_row = ttk.Frame(self.view_setup)
        config_row.grid(row=1, column=0, sticky="ew", pady=(18, 0))
        config_row.columnconfigure(0, weight=1)
        config_row.columnconfigure(1, weight=1)

        p1_panel = ttk.LabelFrame(config_row, text="Player 1", padding=14)
        p1_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        p1_panel.columnconfigure(0, weight=1)
        ttk.Label(
            p1_panel,
            text="Select Player Type!",
        ).grid(row=0, column=0, sticky="w")
        self.dd_p1 = ttk.Combobox(
            p1_panel,
            textvariable=self.setup_p1_var,
            values=self._option_labels(),
            state="readonly",
            width=28,
        )
        self.dd_p1.grid(row=1, column=0, sticky="ew", pady=(10, 0))

        p2_panel = ttk.LabelFrame(config_row, text="Player 2", padding=14)
        p2_panel.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        p2_panel.columnconfigure(0, weight=1)
        ttk.Label(
            p2_panel,
            text="Select Player Type!",
        ).grid(row=0, column=0, sticky="w")
        self.dd_p2 = ttk.Combobox(
            p2_panel,
            textvariable=self.setup_p2_var,
            values=self._option_labels(),
            state="readonly",
            width=28,
        )
        self.dd_p2.grid(row=1, column=0, sticky="ew", pady=(10, 0))

        footer = ttk.Frame(self.view_setup)
        footer.grid(row=2, column=0, sticky="ew", pady=(18, 0))
        footer.columnconfigure(0, weight=1)

        ttk.Label(
            footer,
            text="Configured AI options are loaded from connect4.ui/ai_options.json.",
        ).grid(row=0, column=0, sticky="w")
        self.btn_start = ttk.Button(footer, text="Start", command=self._on_start_game)
        self.btn_start.grid(row=0, column=1, sticky="e")

    def _build_playing_view(self) -> None:
        self.view_playing = ttk.Frame(self.container, padding=(0, 6, 0, 0))
        self.view_playing.columnconfigure(0, weight=1)
        self.view_playing.rowconfigure(1, weight=1)

        header = ttk.Frame(self.view_playing)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        header_text = ttk.Frame(header)
        header_text.grid(row=0, column=0, sticky="w")
        ttk.Label(
            header_text,
            textvariable=self.status_var,
            font=("Arial", 13, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            header_text,
            textvariable=self.matchup_var,
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        action_bar = ttk.Frame(header)
        action_bar.grid(row=0, column=1, sticky="e")
        self.btn_restart = ttk.Button(
            action_bar,
            text="Restart",
            command=self._on_restart_game,
        )
        self.btn_restart.grid(row=0, column=0, padx=(0, 8))
        self.btn_back = ttk.Button(
            action_bar,
            text="Back",
            command=self._on_back_to_setup,
        )
        self.btn_back.grid(row=0, column=1)

        content = ttk.Frame(self.view_playing)
        content.grid(row=1, column=0, sticky="nsew", pady=(16, 0))
        content.columnconfigure(0, weight=0)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)

        board_panel = ttk.Frame(content)
        board_panel.grid(row=0, column=0, sticky="n")
        board_panel.columnconfigure(0, weight=1)

        self.col_buttons = []
        self.btn_frame = ttk.Frame(board_panel, width=self.board_width, height=36)
        self.btn_frame.grid(row=0, column=0, sticky="ew")
        self.btn_frame.grid_propagate(False)
        self.btn_frame.rowconfigure(0, weight=1)
        for column_index in range(self.game.cols):
            self.btn_frame.columnconfigure(column_index, weight=1, uniform="board-col")
            button = ttk.Button(
                self.btn_frame,
                text=f"▼ {column_index + 1}",
                command=lambda cc=column_index: self._on_human_move(cc),
            )
            button.grid(row=0, column=column_index, padx=0, pady=2, sticky="nsew")
            self.col_buttons.append(button)

        self.canvas = tk.Canvas(
            board_panel,
            width=self.board_width,
            height=self.board_height,
            bg=self.board_bg,
            bd=0,
            highlightthickness=0,
        )
        self.canvas.grid(row=1, column=0, sticky="w", pady=(10, 0))

        log_panel = ttk.LabelFrame(content, text="Log", padding=10)
        log_panel.grid(row=0, column=1, sticky="nsew", padx=(18, 0))
        log_panel.columnconfigure(0, weight=1)
        log_panel.rowconfigure(0, weight=1)

        self.log = ScrolledText(
            log_panel,
            width=42,
            height=22,
            state="disabled",
            font=("Consolas", 10),
            wrap="word",
        )
        self.log.grid(row=0, column=0, sticky="nsew")

    # ---------- logging ----------
    def _clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", tk.END)
        self.log.configure(state="disabled")

    def _log(self, msg: str) -> None:
        self.log.configure(state="normal")
        self.log.insert(tk.END, msg + "\n")
        self.log.see(tk.END)
        self.log.configure(state="disabled")

    # ---------- state helpers ----------
    def _option_labels(self) -> list[str]:
        return [option.label for option in self.player_options]

    def _selection_from_widgets(self) -> PlayerSelections:
        return PlayerSelections(
            self._option_from_label(self.setup_p1_var.get()).id,
            self._option_from_label(self.setup_p2_var.get()).id,
        )

    def _set_setup_widgets(self, selection: PlayerSelections) -> None:
        self.setup_p1_var.set(self.player_option_by_id[selection.p1_option_id].label)
        self.setup_p2_var.set(self.player_option_by_id[selection.p2_option_id].label)

    def _option_from_label(self, label: str) -> PlayerOption:
        try:
            return self.player_option_by_label[label]
        except KeyError as exc:
            raise ValueError(f"Unknown player option label: {label}") from exc

    def _option_from_id(self, option_id: str) -> PlayerOption:
        try:
            return self.player_option_by_id[option_id]
        except KeyError as exc:
            raise ValueError(f"Unknown player option id: {option_id}") from exc

    def _is_ai_player(self, player_id: int) -> bool:
        return (player_id == P1 and self.p1_ai is not None) or (
            player_id == P2 and self.p2_ai is not None
        )

    def _current_ai(self) -> Optional[Connect4AIPlayer]:
        return self.p1_ai if self.game.current_player == P1 else self.p2_ai

    def _matchup_text(self, selection: PlayerSelections) -> str:
        p1_label = self._option_from_id(selection.p1_option_id).label
        p2_label = self._option_from_id(selection.p2_option_id).label
        return f"Player 1: {p1_label} vs Player 2: {p2_label}"

    def _status_text(self) -> str:
        if self.game.winner == P1:
            return "Result: Player 1 wins."
        if self.game.winner == P2:
            return "Result: Player 2 wins."
        if self.game.is_draw:
            return "Result: Draw game."
        player_id = self.game.current_player
        player_kind = "AI" if self._is_ai_player(player_id) else "Human"
        return f"Turn: Player {player_id} ({player_kind})"

    def _sync_controls(self) -> None:
        ended = (self.game.winner != 0) or self.game.is_draw
        human_turn = not self._is_ai_player(self.game.current_player)
        valid_moves = set(self.game.valid_moves())
        is_playing = self.session.mode == MODE_PLAYING

        for column_index, button in enumerate(self.col_buttons):
            is_enabled = is_playing and (not ended) and human_turn and (column_index in valid_moves)
            button.state(["!disabled"] if is_enabled else ["disabled"])

        self.status_var.set(self._status_text())

        if is_playing:
            self._schedule_ai_if_needed()
        else:
            self._cancel_ai_job()

    def _show_mode(self, mode: str) -> None:
        if mode == MODE_SETUP:
            self.view_playing.grid_remove()
            self.view_setup.grid(row=0, column=0, sticky="nsew")
            return

        self.view_setup.grid_remove()
        self.view_playing.grid(row=0, column=0, sticky="nsew")

    # ---------- rendering ----------
    def _draw_board(self) -> None:
        self.canvas.delete("all")
        for row_index in range(self.game.rows):
            for column_index in range(self.game.cols):
                cell_x0 = column_index * self.cell_size
                cell_y0 = row_index * self.cell_size
                cell_x1 = (column_index + 1) * self.cell_size
                cell_y1 = (row_index + 1) * self.cell_size

                self.canvas.create_rectangle(
                    cell_x0,
                    cell_y0,
                    cell_x1,
                    cell_y1,
                    fill=self.board_bg,
                    outline=self.board_grid,
                    width=1,
                )

                x0 = cell_x0 + self.cell_padding
                y0 = cell_y0 + self.cell_padding
                x1 = cell_x1 - self.cell_padding
                y1 = cell_y1 - self.cell_padding

                value = self.game.board[row_index][column_index]
                if value == EMPTY:
                    fill = "white"
                    outline = "#dbeafe"
                elif value == P1:
                    fill = "#e63946"
                    outline = "#8b1d2c"
                else:
                    fill = "#ffd166"
                    outline = "#b37a00"

                self.canvas.create_oval(x0, y0, x1, y1, fill=fill, outline=outline, width=2)

        if self.game.last_move is not None:
            last_row, last_col = self.game.last_move
            x0 = last_col * self.cell_size + self.cell_padding / 2
            y0 = last_row * self.cell_size + self.cell_padding / 2
            x1 = (last_col + 1) * self.cell_size - self.cell_padding / 2
            y1 = (last_row + 1) * self.cell_size - self.cell_padding / 2
            self.canvas.create_oval(x0, y0, x1, y1, outline="#1d4ed8", width=3)

    # ---------- game lifecycle ----------
    def _create_player(self, option_id: str) -> Optional[Connect4AIPlayer]:
        return self._option_from_id(option_id).create_player()

    def _cancel_ai_job(self) -> None:
        if self._ai_job_id is not None:
            try:
                self.root.after_cancel(self._ai_job_id)
            except Exception:
                pass
            self._ai_job_id = None

    def _reset_game_with_selection(self, selection: PlayerSelections) -> None:
        self._cancel_ai_job()
        self._turn_token += 1

        self.p1_ai = self._create_player(selection.p1_option_id)
        self.p2_ai = self._create_player(selection.p2_option_id)

        self.game.reset(first_player=P1)

        if self.p1_ai is not None:
            self.p1_ai.on_new_game(P1)
        if self.p2_ai is not None:
            self.p2_ai.on_new_game(P2)

        self.matchup_var.set(self._matchup_text(selection))
        self._clear_log()
        self._log(f"=== New game started. {self._matchup_text(selection)}. First: Player {P1}. ===")
        self._draw_board()
        self._sync_controls()

    def _on_start_game(self) -> None:
        selection = self._selection_from_widgets()
        started_selection = self.session.start(
            selection.p1_option_id,
            selection.p2_option_id,
        )
        self._set_setup_widgets(started_selection)
        self._show_mode(MODE_PLAYING)
        self._reset_game_with_selection(started_selection)

    def _on_restart_game(self) -> None:
        selection = self.session.restart()
        self._show_mode(MODE_PLAYING)
        self._reset_game_with_selection(selection)

    def _on_back_to_setup(self) -> None:
        self._cancel_ai_job()
        self._turn_token += 1
        self.p1_ai = None
        self.p2_ai = None

        selection = self.session.back()
        self._set_setup_widgets(selection)
        self.status_var.set("Choose players and start a game.")
        self.matchup_var.set("")
        self._show_mode(MODE_SETUP)

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

    def _log_result(self, res: MoveResult) -> None:
        if res.winner == P1:
            self._log("=== Result: Player 1 wins. ===")
        elif res.winner == P2:
            self._log("=== Result: Player 2 wins. ===")
        elif res.is_draw:
            self._log("=== Result: Draw game. ===")

    def _complete_turn(self, actor_name: str, res: MoveResult) -> None:
        mover_id = self.game.board[res.row][res.col]
        self._log(f"{actor_name} (Player {mover_id}) played column {res.col + 1}")
        self._after_move_hooks(res)
        self._log_result(res)
        self._draw_board()
        self._sync_controls()

    def _on_human_move(self, col: int) -> None:
        if self.session.mode != MODE_PLAYING:
            return
        if self.game.winner != 0 or self.game.is_draw:
            return
        if self._is_ai_player(self.game.current_player):
            return

        res = self.game.drop_piece(col)
        if not res.placed:
            self._log(f"Illegal move: column {col + 1}")
            return

        self._complete_turn("Human", res)

    def _schedule_ai_if_needed(self) -> None:
        self._cancel_ai_job()
        if (
            self.session.mode == MODE_PLAYING
            and self.game.winner == 0
            and not self.game.is_draw
            and self._is_ai_player(self.game.current_player)
        ):
            token = self._turn_token
            self._ai_job_id = self.root.after(
                self._ai_delay_ms,
                lambda: self._do_ai_turn(token),
            )

    def _do_ai_turn(self, token: int) -> None:
        if token != self._turn_token or self.session.mode != MODE_PLAYING:
            return

        if self.game.winner != 0 or self.game.is_draw:
            return

        ai = self._current_ai()
        if ai is None:
            return

        valid_moves = self.game.valid_moves()
        if not valid_moves:
            return

        board_copy = tuple(tuple(row) for row in self.game.board)

        try:
            col = ai.choose_move(
                board=board_copy,
                player_id=self.game.current_player,
                valid_moves=tuple(valid_moves),
                last_move=self.game.last_move,
            )
        except Exception as exc:
            self._log(f"[AI ERROR] {ai.name} crashed: {exc}")
            return

        if col not in valid_moves:
            self._log(f"[AI ERROR] {ai.name} returned invalid move: {col}")
            return

        res = self.game.drop_piece(col)
        if not res.placed:
            self._log(f"[AI ERROR] {ai.name} attempted illegal move: {col}")
            return

        self._complete_turn(ai.name, res)


def main() -> None:
    app = Connect4TkApp()
    app.run()


if __name__ == "__main__":
    main()
