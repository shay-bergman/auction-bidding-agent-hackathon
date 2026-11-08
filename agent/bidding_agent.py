"""The ``BiddingAgent`` class the auction engine instantiates and drives."""

from __future__ import annotations

import os
import sys
from typing import Dict, List

# The engine loads this file standalone by path (not as part of a package), so
# ensure the repository root is importable before resolving the sibling modules
# that make up the agent package.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from agent.estimation import MarketModel
from agent.opponents import OpponentBook
from agent.policy import BidPolicy

TOTAL_ROUNDS = 15


class BiddingAgent:
    """Adaptive shading bidder for sequential second-price auctions.

    The agent maximizes total utility (value of items won minus prices paid)
    across a fixed sequence of single-item auctions under a shared budget. It
    holds the game state and delegates estimation to a :class:`MarketModel`,
    opponent tracking to an :class:`OpponentBook`, and the bid decision to a
    :class:`BidPolicy`.

    The engine calls :meth:`bidding_function` once per item and
    :meth:`update_after_each_round` once the round's public outcome is known.
    Agent state is serialized between rounds by the engine, so all cross-round
    state lives in picklable, non-underscore attributes.

    Attributes:
        team_id: This agent's identifier.
        valuation_vector: Mapping of item id to private value.
        budget: Remaining budget.
        opponent_teams: Identifiers of the opponents in the game.
        initial_budget: Budget at the start of the game.
        utility: Running utility accumulated from won items.
        items_won: Items this agent has won.
        rounds_completed: Number of rounds played so far.
        market: Market model tracking prices and value lookups.
        opponents: Per-opponent budget and aggression models.
        policy: The bid-decision policy.
    """

    def __init__(
        self,
        team_id: str,
        valuation_vector: Dict[str, float],
        budget: float,
        opponent_teams: List[str],
    ) -> None:
        """Initialize the agent at the start of a game.

        Args:
            team_id: This agent's unique identifier.
            valuation_vector: Mapping of item id to this agent's private value.
            budget: Initial budget for the whole game.
            opponent_teams: Identifiers of the opponents in the game.
        """
        self.team_id = team_id
        self.valuation_vector = valuation_vector
        self.budget = float(budget)
        self.opponent_teams = list(opponent_teams)

        self.initial_budget = float(budget)
        self.utility = 0.0
        self.items_won: List[str] = []

        self.total_rounds = TOTAL_ROUNDS
        self.rounds_completed = 0

        self.market = MarketModel(valuation_vector)
        self.opponents = OpponentBook(self.opponent_teams, self.initial_budget)
        self.policy = BidPolicy()

    def bidding_function(self, item_id: str) -> float:
        """Return this agent's bid for the current item.

        Args:
            item_id: Item being auctioned.

        Returns:
            A bid in ``[0, budget]``, never exceeding the item's value.
        """
        value = float(self.valuation_vector.get(item_id, 0.0))
        return self.policy.decide_bid(
            item_id=item_id,
            value=value,
            budget=self.budget,
            initial_budget=self.initial_budget,
            rounds_completed=self.rounds_completed,
            total_rounds=self.total_rounds,
            market=self.market,
            opponents=self.opponents,
        )

    def update_after_each_round(
        self, item_id: str, winning_team: str, price_paid: float
    ) -> bool:
        """Record the public outcome of a completed round and update all models.

        Only the winning team and the price paid are public; opponents' bids are
        never revealed.

        Args:
            item_id: Item that was auctioned.
            winning_team: Identifier of the round winner (empty if no winner).
            price_paid: Price the winner paid.

        Returns:
            True once the update is applied.
        """
        price = float(price_paid)

        if winning_team == self.team_id:
            self.budget -= price
            self.items_won.append(item_id)
            self.utility += float(self.valuation_vector.get(item_id, 0.0)) - price

        my_value = float(self.valuation_vector.get(item_id, 0.0))
        self.market.observe(price, my_value)
        if winning_team and winning_team != self.team_id:
            self.opponents.observe_win(
                winning_team, price, self.market.global_median_prior()
            )

        self.rounds_completed += 1
        return True
