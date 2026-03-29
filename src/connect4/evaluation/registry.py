from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from connect4.ai import Connect4AIPlayer, MinimaxAI, RandomAI

EntrantFactory = Callable[[Optional[int]], Connect4AIPlayer]

DEFAULT_ANCHOR_IDS = ("random-v1", "minimax-d2-v1", "minimax-d4-v1")


@dataclass(frozen=True)
class AIEntrant:
    """Immutable registry record for a single rated AI version."""

    id: str
    factory: EntrantFactory
    family: str
    version: str
    display_name: Optional[str] = None
    is_anchor: bool = False
    active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("Entrant ID must be non-empty.")
        if not self.family.strip():
            raise ValueError("Entrant family must be non-empty.")
        if not self.version.strip():
            raise ValueError("Entrant version must be non-empty.")

    @property
    def resolved_display_name(self) -> str:
        return self.display_name or self.id

    def create_player(self, seed: Optional[int] = None) -> Connect4AIPlayer:
        return self.factory(seed)


class AIEntrantRegistry:
    """Stable registry for all known evaluation entrants."""

    def __init__(self, entrants: Optional[Iterable[AIEntrant]] = None) -> None:
        self._entrants: Dict[str, AIEntrant] = {}
        self._order: List[str] = []

        for entrant in entrants or ():
            self.register(entrant)

    def register(self, entrant: AIEntrant) -> None:
        if entrant.id in self._entrants:
            raise ValueError(f"Duplicate entrant ID: {entrant.id}")

        self._entrants[entrant.id] = entrant
        self._order.append(entrant.id)

    def get(self, entrant_id: str) -> AIEntrant:
        try:
            return self._entrants[entrant_id]
        except KeyError as exc:
            raise KeyError(f"Unknown entrant ID: {entrant_id}") from exc

    def resolve_many(self, entrant_ids: Sequence[str]) -> Tuple[AIEntrant, ...]:
        return tuple(self.get(entrant_id) for entrant_id in entrant_ids)

    def list_entrants(self, active_only: bool = False) -> Tuple[AIEntrant, ...]:
        entrants = tuple(self._entrants[entrant_id] for entrant_id in self._order)
        if not active_only:
            return entrants
        return tuple(entrant for entrant in entrants if entrant.active)

    def anchor_ids(self) -> Tuple[str, ...]:
        return tuple(entrant.id for entrant in self.list_entrants() if entrant.is_anchor)

    def require_anchor_ids(self, anchor_ids: Sequence[str]) -> None:
        missing = [entrant_id for entrant_id in anchor_ids if entrant_id not in self._entrants]
        if missing:
            raise ValueError(f"Missing anchor entrants in registry: {', '.join(missing)}")

        invalid = [entrant_id for entrant_id in anchor_ids if not self._entrants[entrant_id].is_anchor]
        if invalid:
            raise ValueError(f"Entrants are not marked as anchors: {', '.join(invalid)}")


def make_random_entrant(
    entrant_id: str = "random-v1",
    *,
    version: str = "v1",
    is_anchor: bool = False,
    active: bool = True,
) -> AIEntrant:
    return AIEntrant(
        id=entrant_id,
        display_name="RandomAI",
        family="RandomAI",
        version=version,
        is_anchor=is_anchor,
        active=active,
        metadata={},
        factory=lambda seed=None: RandomAI(),
    )


def make_minimax_entrant(
    max_depth: int,
    entrant_id: Optional[str] = None,
    *,
    version: str = "v1",
    is_anchor: bool = False,
    active: bool = True,
) -> AIEntrant:
    resolved_id = entrant_id or f"minimax-d{max_depth}-{version}"
    return AIEntrant(
        id=resolved_id,
        display_name=f"MinimaxAI depth {max_depth}",
        family="MinimaxAI",
        version=version,
        is_anchor=is_anchor,
        active=active,
        metadata={"max_depth": max_depth},
        factory=lambda seed=None, depth=max_depth: MinimaxAI(max_depth=depth),
    )


def build_default_registry() -> AIEntrantRegistry:
    return AIEntrantRegistry(
        entrants=(
            make_random_entrant(is_anchor=True),
            make_minimax_entrant(2, entrant_id="minimax-d2-v1", is_anchor=True),
            make_minimax_entrant(4, entrant_id="minimax-d4-v1", is_anchor=True),
        )
    )
