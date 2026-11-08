#!/usr/bin/env python3
"""Entry point: simulate the bidding agent against the baseline strategies."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

from engine.agent_manager import AgentManager
from engine.auction_engine import AuctionEngine
from engine.config import BID_TIMEOUT_SECONDS
from engine.game_manager import GameManager
from engine.utils import format_utility
from engine.valuation_generator import ValuationGenerator

ROOT = Path(__file__).resolve().parent
AGENT_PATH = ROOT / "agent" / "bidding_agent.py"
BASELINES_DIR = ROOT / "baselines"
AGENT_LABEL = "my_agent"


def discover_baselines(directory: Path) -> List[Dict[str, str]]:
    """Find the baseline opponents in a directory.

    Args:
        directory: Directory containing baseline agent modules.

    Returns:
        A list of ``{"team_id", "agent_file"}`` dicts, one per baseline.
    """
    opponents: List[Dict[str, str]] = []
    for agent_file in sorted(directory.glob("*.py")):
        if agent_file.name == "__init__.py":
            continue
        opponents.append({"team_id": agent_file.stem, "agent_file": str(agent_file)})
    return opponents


def new_stats() -> Dict[str, object]:
    """Create a zeroed statistics record for one competitor.

    Returns:
        A dict with the accumulators used by :func:`run` and :func:`print_summary`.
    """
    return {
        "total_utility": 0.0,
        "games_won": 0,
        "total_items": 0,
        "total_spent": 0.0,
        "utilities": [],
        "ranks": [],
    }


def play_game(
    agent_path: str,
    opponents: List[Dict[str, str]],
    game_num: int,
    timeout: float,
    valuation_generator: ValuationGenerator,
):
    """Play a single game of the agent against the given opponents.

    Args:
        agent_path: Path to the agent module under test.
        opponents: Opponent descriptors from :func:`discover_baselines`.
        game_num: 1-based game number, used for logging.
        timeout: Per-bid timeout in seconds.
        valuation_generator: Shared generator; its state advances each game so
            successive games use different valuations.

    Returns:
        The engine's ``GameResult``, or ``None`` if the game raised.
    """
    team_agents = {AGENT_LABEL: agent_path}
    for opp in opponents:
        team_agents[opp["team_id"]] = opp["agent_file"]

    game_manager = GameManager(
        stage=1,
        arena_id="local",
        game_number=game_num,
        valuation_generator=valuation_generator,
        auction_engine=AuctionEngine(),
        agent_manager=AgentManager(timeout_seconds=timeout),
    )
    try:
        return game_manager.run_game(team_agents)
    except Exception as exc:  # defensive: one bad game should not abort the run
        logging.error("Error in game %d: %s", game_num, exc, exc_info=True)
        return None


def run(
    agent_path: str,
    opponents: List[Dict[str, str]],
    num_games: int,
    timeout: float,
    seed: Optional[int],
) -> Dict[str, Dict[str, object]]:
    """Play many games and accumulate statistics for every competitor.

    Args:
        agent_path: Path to the agent module under test.
        opponents: Opponent descriptors from :func:`discover_baselines`.
        num_games: Number of games to play.
        timeout: Per-bid timeout in seconds.
        seed: Optional random seed for reproducible valuations.

    Returns:
        A mapping of competitor id to its accumulated statistics record.
    """
    generator = ValuationGenerator(random_seed=seed)

    print("=" * 72)
    print("AUCTION BIDDING SIMULATION")
    print("=" * 72)
    print(f"Agent      : {agent_path}")
    print(f"Opponents  : {', '.join(o['team_id'] for o in opponents)}")
    print(f"Games      : {num_games}")
    print(f"Random seed: {seed if seed is not None else 'random'}")
    print("=" * 72)

    stats: Dict[str, Dict[str, object]] = {AGENT_LABEL: new_stats()}
    for opp in opponents:
        stats[opp["team_id"]] = new_stats()

    for game_num in range(1, num_games + 1):
        result = play_game(agent_path, opponents, game_num, timeout, generator)
        if result is None:
            continue

        ranking = sorted(
            result.team_results.items(), key=lambda kv: kv[1].utility, reverse=True
        )

        for team_id, team_result in result.team_results.items():
            if team_id in stats:
                stats[team_id]["total_utility"] += team_result.utility
                stats[team_id]["total_items"] += len(team_result.items_won)
                stats[team_id]["total_spent"] += team_result.budget_spent
                stats[team_id]["utilities"].append(team_result.utility)

        winner_id = ranking[0][0]
        if winner_id in stats:
            stats[winner_id]["games_won"] += 1

        for rank, (team_id, _) in enumerate(ranking, 1):
            if team_id == AGENT_LABEL:
                stats[AGENT_LABEL]["ranks"].append(rank)
                mine = result.team_results[AGENT_LABEL]
                print(
                    f"Game {game_num:>3}: rank {rank}/{len(ranking)}  "
                    f"utility {mine.utility:7.2f}  "
                    f"items {len(mine.items_won):>2}  "
                    f"spent {mine.budget_spent:6.2f}  "
                    f"(winner: {winner_id})"
                )
                break

    return stats


def print_summary(stats: Dict[str, Dict[str, object]], num_games: int) -> None:
    """Print the agent's performance and a leaderboard across all games.

    Args:
        stats: Accumulated statistics from :func:`run`.
        num_games: Number of games played.
    """
    mine = stats[AGENT_LABEL]
    ranks = mine["ranks"]
    avg_rank = sum(ranks) / len(ranks) if ranks else 0.0

    print("\n" + "=" * 72)
    print(f"SUMMARY OVER {num_games} GAMES")
    print("=" * 72)
    print("\nMy agent:")
    print(
        f"  Win rate      : {100 * mine['games_won'] / num_games:5.1f}% "
        f"({mine['games_won']}/{num_games})"
    )
    print(f"  Average rank  : {avg_rank:.2f}")
    print(f"  Avg utility   : {format_utility(mine['total_utility'] / num_games)}")
    print(f"  Avg items won : {mine['total_items'] / num_games:.1f}")
    print(f"  Avg spent     : {mine['total_spent'] / num_games:.2f}")
    if mine["utilities"]:
        print(
            f"  Utility range : [{format_utility(min(mine['utilities']))}, "
            f"{format_utility(max(mine['utilities']))}]"
        )

    print("\nLeaderboard (by average utility):")
    print(f"  {'competitor':<22}{'avg utility':>13}{'wins':>8}{'win rate':>11}")
    print("  " + "-" * 52)
    board = [
        (
            team_id,
            s["total_utility"] / num_games,
            s["games_won"],
            100 * s["games_won"] / num_games,
        )
        for team_id, s in stats.items()
    ]
    board.sort(key=lambda x: x[1], reverse=True)
    for team_id, avg_util, wins, win_rate in board:
        marker = " *" if team_id == AGENT_LABEL else "  "
        print(
            f"{marker}{team_id:<22}{format_utility(avg_util):>13}"
            f"{wins:>8}{win_rate:>10.1f}%"
        )
    print("=" * 72 + "\n")


def main() -> None:
    """Parse arguments, run the simulation, and print the summary."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--agent",
        default=str(AGENT_PATH),
        help="Path to the agent under test (default: agent/bidding_agent.py)",
    )
    parser.add_argument(
        "--opponent",
        help="Play against a single opponent file instead of all baselines",
    )
    parser.add_argument(
        "--num-games",
        type=int,
        default=20,
        help="Number of games to play (default: 20)",
    )
    parser.add_argument("--seed", type=int, help="Random seed for reproducibility")
    parser.add_argument(
        "--timeout",
        type=float,
        default=BID_TIMEOUT_SECONDS,
        help=f"Per-bid timeout in seconds (default: {BID_TIMEOUT_SECONDS})",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    agent_path = Path(args.agent)
    if not agent_path.exists():
        sys.exit(f"Agent file not found: {agent_path}")

    if args.opponent:
        opp_path = Path(args.opponent)
        if not opp_path.exists():
            sys.exit(f"Opponent file not found: {opp_path}")
        opponents = [{"team_id": opp_path.stem, "agent_file": str(opp_path)}]
    else:
        opponents = discover_baselines(BASELINES_DIR)

    if not opponents:
        sys.exit("No opponents found.")

    stats = run(str(agent_path), opponents, args.num_games, args.timeout, args.seed)
    print_summary(stats, args.num_games)


if __name__ == "__main__":
    main()
