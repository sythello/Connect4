from __future__ import annotations

from dataclasses import dataclass, field
from importlib import resources
import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple, Union

from connect4.ai import Connect4AIPlayer, MinimaxAI, RandomAI


DEFAULT_AI_OPTIONS_FILE = "ai_options.json"

AI_FACTORY_WHITELIST = {
    "RandomAI": RandomAI,
    "MinimaxAI": MinimaxAI,
}

PathLike = Union[str, Path]


@dataclass(frozen=True)
class PlayerOption:
    id: str
    label: str
    kind: str
    factory: Optional[str] = None
    params: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        option_id = self.id.strip()
        label = self.label.strip()
        kind = self.kind.strip()
        factory = self.factory.strip() if isinstance(self.factory, str) else self.factory
        params = dict(self.params)

        if not option_id:
            raise ValueError("Player option id must be non-empty.")
        if not label:
            raise ValueError("Player option label must be non-empty.")
        if kind not in {"human", "ai"}:
            raise ValueError(f"Unknown player option kind: {kind}")

        if kind == "human":
            if factory is not None:
                raise ValueError("Human player options must not define a factory.")
            if params:
                raise ValueError("Human player options must not define params.")
        elif factory not in AI_FACTORY_WHITELIST:
            raise ValueError(f"Unknown AI factory: {factory}")

        object.__setattr__(self, "id", option_id)
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "factory", factory)
        object.__setattr__(self, "params", params)

    @property
    def is_human(self) -> bool:
        return self.kind == "human"

    def create_player(self) -> Optional[Connect4AIPlayer]:
        if self.is_human:
            return None

        factory = AI_FACTORY_WHITELIST[self.factory]
        return factory(**dict(self.params))


def load_player_options(path: Optional[PathLike] = None) -> Tuple[PlayerOption, ...]:
    payload = _load_options_payload(path)

    if not isinstance(payload, list) or not payload:
        raise ValueError("AI options config must be a non-empty JSON array.")

    options = []
    seen_ids = set()
    seen_labels = set()

    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"Player option at index {index} must be an object.")

        option = PlayerOption(
            id=str(item.get("id", "")),
            label=str(item.get("label", "")),
            kind=str(item.get("kind", "")),
            factory=item.get("factory"),
            params=item.get("params", {}),
        )

        if option.id in seen_ids:
            raise ValueError(f"Duplicate player option id: {option.id}")
        if option.label in seen_labels:
            raise ValueError(f"Duplicate player option label: {option.label}")

        seen_ids.add(option.id)
        seen_labels.add(option.label)
        options.append(option)

    return tuple(options)


def _load_options_payload(path: Optional[PathLike]) -> Any:
    if path is None:
        resource = resources.files("connect4.ui").joinpath(DEFAULT_AI_OPTIONS_FILE)
        with resource.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)
