from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from itertools import combinations
from pathlib import Path
import random
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

import numpy as np

from connect4.core import Connect4Game, P1, P2

from .registry import AIEntrant, AIEntrantRegistry, DEFAULT_ANCHOR_IDS

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class EvaluationConfig:
    games_per_pair: int = 10
    initial_rating: float = 1500.0
    k_factor: float = 32.0
    alternate_first_player: bool = True
    seed: Optional[int] = None
    provisional_games: int = 12
    ratings_path: str = "artifacts/elo_ratings.json"
    anchor_ids: Tuple[str, ...] = DEFAULT_ANCHOR_IDS

    def __post_init__(self) -> None:
        if self.games_per_pair <= 0:
            raise ValueError("games_per_pair must be positive.")
        if self.alternate_first_player and self.games_per_pair % 2 != 0:
            raise ValueError("games_per_pair must be even when alternating the first player.")
        if self.initial_rating <= 0:
            raise ValueError("initial_rating must be positive.")
        if self.k_factor <= 0:
            raise ValueError("k_factor must be positive.")
        if self.provisional_games < 0:
            raise ValueError("provisional_games must be non-negative.")
        if not self.anchor_ids:
            raise ValueError("At least one anchor entrant is required.")


@dataclass
class LadderEntry:
    entrant_id: str
    display_name: str
    family: str
    version: str
    rating: float
    games: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    forfeit_losses: int = 0
    last_played_at: Optional[str] = None
    is_anchor: bool = False
    active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_entrant(cls, entrant: AIEntrant, initial_rating: float) -> "LadderEntry":
        return cls(
            entrant_id=entrant.id,
            display_name=entrant.resolved_display_name,
            family=entrant.family,
            version=entrant.version,
            rating=float(initial_rating),
            is_anchor=entrant.is_anchor,
            active=entrant.active,
            metadata=dict(entrant.metadata),
        )

    @classmethod
    def from_dict(cls, entrant_id: str, payload: Dict[str, Any]) -> "LadderEntry":
        return cls(
            entrant_id=entrant_id,
            display_name=str(payload.get("display_name", entrant_id)),
            family=str(payload.get("family", "")),
            version=str(payload.get("version", "")),
            rating=float(payload.get("rating", 1500.0)),
            games=int(payload.get("games", 0)),
            wins=int(payload.get("wins", 0)),
            losses=int(payload.get("losses", 0)),
            draws=int(payload.get("draws", 0)),
            forfeit_losses=int(payload.get("forfeit_losses", 0)),
            last_played_at=payload.get("last_played_at"),
            is_anchor=bool(payload.get("is_anchor", False)),
            active=bool(payload.get("active", True)),
            metadata=dict(payload.get("metadata", {})),
        )

    def clone(self) -> "LadderEntry":
        return LadderEntry(
            entrant_id=self.entrant_id,
            display_name=self.display_name,
            family=self.family,
            version=self.version,
            rating=self.rating,
            games=self.games,
            wins=self.wins,
            losses=self.losses,
            draws=self.draws,
            forfeit_losses=self.forfeit_losses,
            last_played_at=self.last_played_at,
            is_anchor=self.is_anchor,
            active=self.active,
            metadata=dict(self.metadata),
        )

    def is_provisional(self, provisional_games: int) -> bool:
        return self.games < provisional_games

    def to_dict(self) -> Dict[str, Any]:
        return {
            "display_name": self.display_name,
            "family": self.family,
            "version": self.version,
            "rating": self.rating,
            "games": self.games,
            "wins": self.wins,
            "losses": self.losses,
            "draws": self.draws,
            "forfeit_losses": self.forfeit_losses,
            "last_played_at": self.last_played_at,
            "is_anchor": self.is_anchor,
            "active": self.active,
            "metadata": dict(self.metadata),
        }


@dataclass
class LadderSnapshot:
    schema_version: int = SCHEMA_VERSION
    updated_at: Optional[str] = None
    initial_rating: float = 1500.0
    k_factor: float = 32.0
    provisional_games: int = 12
    anchor_ids: Tuple[str, ...] = DEFAULT_ANCHOR_IDS
    entries: Dict[str, LadderEntry] = field(default_factory=dict)

    def clone(self) -> "LadderSnapshot":
        return LadderSnapshot(
            schema_version=self.schema_version,
            updated_at=self.updated_at,
            initial_rating=self.initial_rating,
            k_factor=self.k_factor,
            provisional_games=self.provisional_games,
            anchor_ids=tuple(self.anchor_ids),
            entries={entrant_id: entry.clone() for entrant_id, entry in self.entries.items()},
        )

    def ensure_entry(self, entrant: AIEntrant) -> LadderEntry:
        entry = self.entries.get(entrant.id)
        if entry is None:
            entry = LadderEntry.from_entrant(entrant, initial_rating=self.initial_rating)
            self.entries[entrant.id] = entry
            return entry

        entry.display_name = entrant.resolved_display_name
        entry.family = entrant.family
        entry.version = entrant.version
        entry.is_anchor = entrant.is_anchor
        entry.active = entrant.active
        entry.metadata = dict(entrant.metadata)
        return entry

    def standings(self) -> List[LadderEntry]:
        return sorted(
            self.entries.values(),
            key=lambda entry: (-entry.rating, -entry.games, entry.entrant_id),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "updated_at": self.updated_at,
            "initial_rating": self.initial_rating,
            "k_factor": self.k_factor,
            "provisional_games": self.provisional_games,
            "anchor_ids": list(self.anchor_ids),
            "entries": {
                entrant_id: entry.to_dict()
                for entrant_id, entry in sorted(self.entries.items(), key=lambda item: item[0])
            },
        }


@dataclass(frozen=True)
class MatchRecord:
    player_one_entrant_id: str
    player_two_entrant_id: str
    winner_id: Optional[str]
    is_draw: bool
    termination: str
    move_count: int
    seed: Optional[int]
    finished_at: str
    forfeit_loser_id: Optional[str] = None
    error_message: Optional[str] = None


@dataclass(frozen=True)
class EvaluationRun:
    snapshot: LadderSnapshot
    matches: Tuple[MatchRecord, ...]


def load_ladder(
    path: Union[str, Path],
    *,
    initial_rating: float = 1500.0,
    k_factor: float = 32.0,
    provisional_games: int = 12,
    anchor_ids: Sequence[str] = DEFAULT_ANCHOR_IDS,
) -> LadderSnapshot:
    resolved_path = Path(path)
    if not resolved_path.exists():
        return LadderSnapshot(
            initial_rating=float(initial_rating),
            k_factor=float(k_factor),
            provisional_games=int(provisional_games),
            anchor_ids=tuple(anchor_ids),
        )

    with resolved_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    schema_version = int(payload.get("schema_version", SCHEMA_VERSION))
    if schema_version != SCHEMA_VERSION:
        raise ValueError(f"Unsupported ladder schema version: {schema_version}")

    entries_payload = payload.get("entries", {})
    entries = {
        entrant_id: LadderEntry.from_dict(entrant_id, entry_payload)
        for entrant_id, entry_payload in entries_payload.items()
    }

    return LadderSnapshot(
        schema_version=schema_version,
        updated_at=payload.get("updated_at"),
        initial_rating=float(payload.get("initial_rating", initial_rating)),
        k_factor=float(payload.get("k_factor", k_factor)),
        provisional_games=int(payload.get("provisional_games", provisional_games)),
        anchor_ids=tuple(payload.get("anchor_ids", list(anchor_ids))),
        entries=entries,
    )


def save_ladder(snapshot: LadderSnapshot, path: Union[str, Path]) -> None:
    resolved_path = Path(path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    with resolved_path.open("w", encoding="utf-8") as handle:
        json.dump(snapshot.to_dict(), handle, indent=2, sort_keys=True)
        handle.write("\n")


def sync_snapshot_entries(
    snapshot: LadderSnapshot,
    entrants: Iterable[AIEntrant],
    *,
    create_missing: bool = False,
) -> None:
    for entrant in entrants:
        if entrant.id in snapshot.entries or create_missing:
            snapshot.ensure_entry(entrant)


def build_calibration_field(
    registry: AIEntrantRegistry,
    ladder: LadderSnapshot,
    new_entrant_ids: Sequence[str],
    anchor_ids: Optional[Sequence[str]] = None,
) -> Tuple[AIEntrant, ...]:
    if not new_entrant_ids:
        raise ValueError("Calibration requires at least one entrant ID.")

    required_anchor_ids = tuple(anchor_ids or ladder.anchor_ids or DEFAULT_ANCHOR_IDS)
    registry.require_anchor_ids(required_anchor_ids)

    entrants: List[AIEntrant] = []
    seen_ids = set()

    def add_entrant(entrant: AIEntrant) -> None:
        if entrant.id in seen_ids:
            return
        seen_ids.add(entrant.id)
        entrants.append(entrant)

    for entrant in registry.resolve_many(new_entrant_ids):
        add_entrant(entrant)

    for entrant in registry.resolve_many(required_anchor_ids):
        add_entrant(entrant)

    for entrant in registry.list_entrants(active_only=True):
        if entrant.id in ladder.entries:
            add_entrant(entrant)

    return tuple(entrants)


def run_round_robin(
    entrants: Sequence[AIEntrant],
    config: EvaluationConfig,
    ladder: Optional[LadderSnapshot] = None,
) -> EvaluationRun:
    snapshot = (
        ladder.clone()
        if ladder is not None
        else load_ladder(
            config.ratings_path,
            initial_rating=config.initial_rating,
            k_factor=config.k_factor,
            provisional_games=config.provisional_games,
            anchor_ids=config.anchor_ids,
        )
    )

    snapshot.initial_rating = config.initial_rating
    snapshot.k_factor = config.k_factor
    snapshot.provisional_games = config.provisional_games
    snapshot.anchor_ids = tuple(config.anchor_ids)
    sync_snapshot_entries(snapshot, entrants, create_missing=True)

    matches: List[MatchRecord] = []
    entrant_pairs = tuple(combinations(tuple(entrants), 2))

    for pair_index, (entrant_one, entrant_two) in enumerate(entrant_pairs):
        scheduled_games = _scheduled_games(
            entrant_one=entrant_one,
            entrant_two=entrant_two,
            games_per_pair=config.games_per_pair,
            alternate_first_player=config.alternate_first_player,
        )

        for game_index, (player_one_entrant, player_two_entrant) in enumerate(scheduled_games):
            game_seed = _derive_seed(
                config.seed,
                "pair",
                str(pair_index),
                "game",
                str(game_index),
                player_one_entrant.id,
                player_two_entrant.id,
            )
            match = _play_single_game(player_one_entrant, player_two_entrant, seed=game_seed)
            _apply_match_result(
                snapshot=snapshot,
                player_one_entrant=player_one_entrant,
                player_two_entrant=player_two_entrant,
                match=match,
                k_factor=config.k_factor,
            )
            matches.append(match)

    snapshot.updated_at = _utcnow_iso()
    return EvaluationRun(snapshot=snapshot, matches=tuple(matches))


def evaluate_round_robin(
    entrants: Sequence[AIEntrant],
    config: EvaluationConfig,
    ladder: Optional[LadderSnapshot] = None,
) -> LadderSnapshot:
    return run_round_robin(entrants=entrants, config=config, ladder=ladder).snapshot


def _scheduled_games(
    entrant_one: AIEntrant,
    entrant_two: AIEntrant,
    games_per_pair: int,
    alternate_first_player: bool,
) -> Tuple[Tuple[AIEntrant, AIEntrant], ...]:
    scheduled_games: List[Tuple[AIEntrant, AIEntrant]] = []

    if alternate_first_player:
        for _ in range(games_per_pair // 2):
            scheduled_games.append((entrant_one, entrant_two))
            scheduled_games.append((entrant_two, entrant_one))
        return tuple(scheduled_games)

    for _ in range(games_per_pair):
        scheduled_games.append((entrant_one, entrant_two))

    return tuple(scheduled_games)


def _play_single_game(
    player_one_entrant: AIEntrant,
    player_two_entrant: AIEntrant,
    *,
    seed: Optional[int],
) -> MatchRecord:
    _seed_global_generators(seed)

    try:
        player_one = player_one_entrant.create_player(seed=_derive_seed(seed, player_one_entrant.id, "p1"))
    except Exception as exc:
        return _forfeit_match(
            player_one_entrant=player_one_entrant,
            player_two_entrant=player_two_entrant,
            winner_id=player_two_entrant.id,
            forfeit_loser_id=player_one_entrant.id,
            termination="exception",
            seed=seed,
            error_message=str(exc),
        )

    try:
        player_two = player_two_entrant.create_player(seed=_derive_seed(seed, player_two_entrant.id, "p2"))
    except Exception as exc:
        return _forfeit_match(
            player_one_entrant=player_one_entrant,
            player_two_entrant=player_two_entrant,
            winner_id=player_one_entrant.id,
            forfeit_loser_id=player_two_entrant.id,
            termination="exception",
            seed=seed,
            error_message=str(exc),
        )

    game = Connect4Game()
    game.reset(first_player=P1)
    try:
        player_one.on_new_game(P1)
    except Exception as exc:
        return _forfeit_match(
            player_one_entrant=player_one_entrant,
            player_two_entrant=player_two_entrant,
            winner_id=player_two_entrant.id,
            forfeit_loser_id=player_one_entrant.id,
            termination="exception",
            seed=seed,
            error_message=str(exc),
        )
    try:
        player_two.on_new_game(P2)
    except Exception as exc:
        return _forfeit_match(
            player_one_entrant=player_one_entrant,
            player_two_entrant=player_two_entrant,
            winner_id=player_one_entrant.id,
            forfeit_loser_id=player_two_entrant.id,
            termination="exception",
            seed=seed,
            error_message=str(exc),
        )

    winner_id: Optional[str] = None
    forfeit_loser_id: Optional[str] = None
    termination = "completed"
    error_message: Optional[str] = None
    move_count = 0

    while game.winner == 0 and not game.is_draw:
        current_player = game.current_player
        active_ai = player_one if current_player == P1 else player_two
        active_entrant = player_one_entrant if current_player == P1 else player_two_entrant
        opponent_entrant = player_two_entrant if current_player == P1 else player_one_entrant

        valid_moves = tuple(game.valid_moves())
        board_copy = tuple(tuple(row) for row in game.board)

        try:
            chosen_column = active_ai.choose_move(
                board=board_copy,
                player_id=current_player,
                valid_moves=valid_moves,
                last_move=game.last_move,
            )
        except Exception as exc:
            winner_id = opponent_entrant.id
            forfeit_loser_id = active_entrant.id
            termination = "exception"
            error_message = str(exc)
            break

        if chosen_column not in valid_moves:
            winner_id = opponent_entrant.id
            forfeit_loser_id = active_entrant.id
            termination = "invalid_move"
            error_message = f"Invalid move: {chosen_column}"
            break

        result = game.drop_piece(chosen_column)
        if not result.placed or result.row is None or result.col is None:
            winner_id = opponent_entrant.id
            forfeit_loser_id = active_entrant.id
            termination = "illegal_move"
            error_message = f"Illegal move rejected by engine: {chosen_column}"
            break

        move_count += 1
        move = (result.row, result.col)
        mover_player = game.board[result.row][result.col]

        if mover_player == P1:
            hook_failure = _apply_hook(player_one.on_ai_move, move, losing_entrant=player_one_entrant, winning_entrant=player_two_entrant)
            if hook_failure is not None:
                winner_id, forfeit_loser_id, termination, error_message = hook_failure
                break

            hook_failure = _apply_hook(player_two.on_opponent_move, move, losing_entrant=player_two_entrant, winning_entrant=player_one_entrant)
            if hook_failure is not None:
                winner_id, forfeit_loser_id, termination, error_message = hook_failure
                break
        else:
            hook_failure = _apply_hook(player_two.on_ai_move, move, losing_entrant=player_two_entrant, winning_entrant=player_one_entrant)
            if hook_failure is not None:
                winner_id, forfeit_loser_id, termination, error_message = hook_failure
                break

            hook_failure = _apply_hook(player_one.on_opponent_move, move, losing_entrant=player_one_entrant, winning_entrant=player_two_entrant)
            if hook_failure is not None:
                winner_id, forfeit_loser_id, termination, error_message = hook_failure
                break

    if termination == "completed":
        if game.winner == P1:
            winner_id = player_one_entrant.id
        elif game.winner == P2:
            winner_id = player_two_entrant.id

    return MatchRecord(
        player_one_entrant_id=player_one_entrant.id,
        player_two_entrant_id=player_two_entrant.id,
        winner_id=winner_id,
        is_draw=game.is_draw and winner_id is None,
        termination=termination,
        move_count=move_count,
        seed=seed,
        finished_at=_utcnow_iso(),
        forfeit_loser_id=forfeit_loser_id,
        error_message=error_message,
    )


def _apply_hook(
    hook,
    move: Tuple[int, int],
    *,
    losing_entrant: AIEntrant,
    winning_entrant: AIEntrant,
) -> Optional[Tuple[str, str, str, str]]:
    try:
        hook(move)
    except Exception as exc:
        return (winning_entrant.id, losing_entrant.id, "exception", str(exc))
    return None


def _forfeit_match(
    player_one_entrant: AIEntrant,
    player_two_entrant: AIEntrant,
    *,
    winner_id: str,
    forfeit_loser_id: str,
    termination: str,
    seed: Optional[int],
    error_message: Optional[str],
) -> MatchRecord:
    return MatchRecord(
        player_one_entrant_id=player_one_entrant.id,
        player_two_entrant_id=player_two_entrant.id,
        winner_id=winner_id,
        is_draw=False,
        termination=termination,
        move_count=0,
        seed=seed,
        finished_at=_utcnow_iso(),
        forfeit_loser_id=forfeit_loser_id,
        error_message=error_message,
    )


def _apply_match_result(
    snapshot: LadderSnapshot,
    player_one_entrant: AIEntrant,
    player_two_entrant: AIEntrant,
    match: MatchRecord,
    k_factor: float,
) -> None:
    player_one_entry = snapshot.entries[player_one_entrant.id]
    player_two_entry = snapshot.entries[player_two_entrant.id]

    player_one_entry.games += 1
    player_two_entry.games += 1
    player_one_entry.last_played_at = match.finished_at
    player_two_entry.last_played_at = match.finished_at

    if match.is_draw:
        player_one_entry.draws += 1
        player_two_entry.draws += 1
        player_one_score = 0.5
        player_two_score = 0.5
    else:
        player_one_won = match.winner_id == player_one_entrant.id
        if player_one_won:
            player_one_entry.wins += 1
            player_two_entry.losses += 1
            player_one_score = 1.0
            player_two_score = 0.0
        else:
            player_one_entry.losses += 1
            player_two_entry.wins += 1
            player_one_score = 0.0
            player_two_score = 1.0

    if match.forfeit_loser_id == player_one_entrant.id:
        player_one_entry.forfeit_losses += 1
    elif match.forfeit_loser_id == player_two_entrant.id:
        player_two_entry.forfeit_losses += 1

    _update_elo(player_one_entry, player_two_entry, player_one_score, player_two_score, k_factor)


def _update_elo(
    player_one_entry: LadderEntry,
    player_two_entry: LadderEntry,
    player_one_score: float,
    player_two_score: float,
    k_factor: float,
) -> None:
    expected_one = _expected_score(player_one_entry.rating, player_two_entry.rating)
    expected_two = _expected_score(player_two_entry.rating, player_one_entry.rating)

    player_one_entry.rating += k_factor * (player_one_score - expected_one)
    player_two_entry.rating += k_factor * (player_two_score - expected_two)


def _expected_score(player_rating: float, opponent_rating: float) -> float:
    return 1.0 / (1.0 + 10.0 ** ((opponent_rating - player_rating) / 400.0))


def _derive_seed(base_seed: Optional[int], *parts: str) -> Optional[int]:
    if base_seed is None:
        return None

    digest = hashlib.sha256()
    for part in (str(base_seed),) + tuple(parts):
        digest.update(part.encode("utf-8"))
        digest.update(b"\0")
    return int.from_bytes(digest.digest()[:4], "big")


def _seed_global_generators(seed: Optional[int]) -> None:
    if seed is None:
        return

    random.seed(seed)
    np.random.seed(seed)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
