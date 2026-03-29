from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Iterable, Optional, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from connect4.evaluation import (  # noqa: E402
    EvaluationConfig,
    build_calibration_field,
    build_default_registry,
    load_ladder,
    run_round_robin,
    save_ladder,
    sync_snapshot_entries,
)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "list":
        _print_registry()
        return 0

    registry = build_default_registry()
    config = EvaluationConfig(
        games_per_pair=args.games_per_pair,
        initial_rating=args.initial_rating,
        k_factor=args.k_factor,
        alternate_first_player=not args.no_alternate_first_player,
        seed=args.seed,
        provisional_games=args.provisional_games,
        ratings_path=args.ratings_path,
    )

    ladder = load_ladder(
        config.ratings_path,
        initial_rating=config.initial_rating,
        k_factor=config.k_factor,
        provisional_games=config.provisional_games,
        anchor_ids=config.anchor_ids,
    )
    sync_snapshot_entries(ladder, registry.list_entrants(), create_missing=False)

    try:
        if args.command == "calibration":
            entrants = build_calibration_field(
                registry=registry,
                ladder=ladder,
                new_entrant_ids=args.entrant_ids,
                anchor_ids=config.anchor_ids,
            )
        elif args.command == "full":
            entrants = registry.resolve_many(args.entrant_ids)
            if not args.no_save:
                _validate_full_tournament_can_save(
                    entrant_ids=[entrant.id for entrant in entrants],
                    rated_ids=set(ladder.entries.keys()),
                    anchor_ids=config.anchor_ids,
                )
        else:
            parser.error(f"Unknown command: {args.command}")
            return 2
    except (KeyError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")

    result = run_round_robin(entrants=entrants, config=config, ladder=ladder)

    print(f"Field: {', '.join(entrant.id for entrant in entrants)}")
    print(f"Games played: {len(result.matches)}")
    print()
    _print_standings(result.snapshot.standings(), provisional_games=config.provisional_games)

    if args.no_save:
        print()
        print("Ladder file not updated (`--no-save` was used).")
        return 0

    save_ladder(result.snapshot, config.ratings_path)
    print()
    print(f"Saved ladder to {Path(config.ratings_path).resolve()}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate Connect4 AI entrants and update the ELO ladder.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="Show the built-in entrant registry.")

    for name, help_text in (
        ("calibration", "Calibrate new entrants against anchors and the active rated pool."),
        ("full", "Run a tournament among a chosen set of already-rated entrants."),
    ):
        subparser = subparsers.add_parser(name, help=help_text)
        subparser.add_argument("entrant_ids", nargs="+", help="Entrant IDs from the registry.")
        subparser.add_argument("--games-per-pair", type=int, default=10, help="Games per unordered entrant pair.")
        subparser.add_argument("--initial-rating", type=float, default=1500.0, help="Starting rating for new entrants.")
        subparser.add_argument("--k-factor", type=float, default=32.0, help="ELO K-factor.")
        subparser.add_argument("--provisional-games", type=int, default=12, help="Games required before a rating is no longer provisional.")
        subparser.add_argument("--ratings-path", default="artifacts/elo_ratings.json", help="JSON file used to load and save the ladder.")
        subparser.add_argument("--seed", type=int, default=None, help="Optional base seed for deterministic tournaments.")
        subparser.add_argument("--no-save", action="store_true", help="Run the tournament without writing the ladder file.")
        subparser.add_argument(
            "--no-alternate-first-player",
            action="store_true",
            help="Disable mirrored first-player alternation within each pair.",
        )

    return parser


def _validate_full_tournament_can_save(
    entrant_ids: Sequence[str],
    rated_ids: Iterable[str],
    anchor_ids: Sequence[str],
) -> None:
    rated_id_set = set(rated_ids)
    new_ids = [entrant_id for entrant_id in entrant_ids if entrant_id not in rated_id_set]
    if not new_ids:
        return

    if not rated_id_set and set(anchor_ids).issubset(set(entrant_ids)):
        return

    raise ValueError(
        "Full mode can only save already-rated entrants. "
        "Use calibration mode to add new entrants to the canonical ladder."
    )


def _print_registry() -> None:
    registry = build_default_registry()
    print("Registered entrants:")
    for entrant in registry.list_entrants():
        anchor_flag = "anchor" if entrant.is_anchor else "non-anchor"
        active_flag = "active" if entrant.active else "inactive"
        print(
            f"- {entrant.id}: {entrant.resolved_display_name} "
            f"[family={entrant.family}, version={entrant.version}, {anchor_flag}, {active_flag}]"
        )


def _print_standings(entries, provisional_games: int) -> None:
    print(
        f"{'Rank':<4} {'Entrant':<18} {'ELO':>8} {'G':>4} {'W':>4} {'L':>4} "
        f"{'D':>4} {'FFL':>4} {'Prov':>5}"
    )
    for index, entry in enumerate(entries, start=1):
        provisional_flag = "yes" if entry.is_provisional(provisional_games) else "no"
        print(
            f"{index:<4} {entry.entrant_id:<18} {entry.rating:>8.1f} {entry.games:>4} "
            f"{entry.wins:>4} {entry.losses:>4} {entry.draws:>4} {entry.forfeit_losses:>4} "
            f"{provisional_flag:>5}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
