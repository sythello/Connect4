from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


MODE_SETUP = "setup"
MODE_PLAYING = "playing"


@dataclass(frozen=True)
class PlayerSelections:
    p1_option_id: str
    p2_option_id: str

    def __post_init__(self) -> None:
        p1_option_id = self.p1_option_id.strip()
        p2_option_id = self.p2_option_id.strip()

        if not p1_option_id or not p2_option_id:
            raise ValueError("Player option ids must be non-empty.")

        object.__setattr__(self, "p1_option_id", p1_option_id)
        object.__setattr__(self, "p2_option_id", p2_option_id)


class Connect4UISessionState:
    def __init__(self, default_p1_option_id: str, default_p2_option_id: str) -> None:
        default_selection = PlayerSelections(default_p1_option_id, default_p2_option_id)
        self.mode = MODE_SETUP
        self.setup_selection = default_selection
        self.last_started_selection: Optional[PlayerSelections] = None

    def update_setup_selection(self, p1_option_id: str, p2_option_id: str) -> PlayerSelections:
        self.setup_selection = PlayerSelections(p1_option_id, p2_option_id)
        return self.setup_selection

    def start(self, p1_option_id: str, p2_option_id: str) -> PlayerSelections:
        selection = self.update_setup_selection(p1_option_id, p2_option_id)
        self.last_started_selection = selection
        self.mode = MODE_PLAYING
        return selection

    def restart(self) -> PlayerSelections:
        if self.last_started_selection is None:
            raise RuntimeError("Cannot restart before a game has been started.")

        self.mode = MODE_PLAYING
        return self.last_started_selection

    def back(self) -> PlayerSelections:
        if self.last_started_selection is not None:
            self.setup_selection = self.last_started_selection

        self.mode = MODE_SETUP
        return self.setup_selection
