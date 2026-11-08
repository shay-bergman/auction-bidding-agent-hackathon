"""Opponent modeling for the bidding agent."""

from __future__ import annotations

from typing import Dict, List

from agent.mathutils import clamp

# Aggression update parameters (see OpponentModel.observe_win for use).
START_AGGRESSION = 0.45  # moderate prior before anything is observed
EXPENSIVE_STEP = 0.06  # aggression gained after an expensive win
CHEAP_STEP = 0.08  # aggression lost after a cheap win
EXPENSIVE_FLOOR = 10.0  # absolute price above which a win looks aggressive
EXPENSIVE_RATIO = 1.35  # ... or this multiple of the market median
CHEAP_FLOOR = 4.5  # absolute price below which a win looks passive
CHEAP_RATIO = 0.75  # ... or this fraction of the market median

# Solvency gate: an opponent is a credible threat for an item only if its
# estimated budget exceeds this fraction of the (capped) item value. A broke
# opponent cannot drive up a price, so it should not raise the competition
# estimate.
SOLVENCY_FRACTION = 0.4
SOLVENCY_VALUE_CAP = 15.0
DEFAULT_PRESSURE = 0.2  # assumed aggression when no opponent is solvent


class OpponentModel:
    """Tracked state for a single opponent.

    Only public round outcomes are observable, so the budget estimate is based
    on the prices this opponent is seen to pay and the aggression level is
    inferred from how expensive its wins are relative to the market.

    Attributes:
        name: Opponent identifier.
        estimated_budget: Remaining budget inferred from observed payments.
        aggression_level: Inferred aggression in ``[0, 1]``.
        wins: Number of rounds this opponent has won.
        total_spent: Total observed spend.
        win_prices: Prices paid on winning rounds.
    """

    def __init__(self, name: str, initial_budget: float) -> None:
        """Initialize the model with a full budget and a neutral aggression prior.

        Args:
            name: Opponent identifier.
            initial_budget: Budget every competitor starts the game with.
        """
        self.name = name
        self.estimated_budget = float(initial_budget)
        self.aggression_level = START_AGGRESSION
        self.wins = 0
        self.total_spent = 0.0
        self.win_prices: List[float] = []

    def observe_win(self, price: float, market_median: float) -> None:
        """Update the model after this opponent wins a round.

        Args:
            price: Price the opponent paid.
            market_median: Current median clearing price, used as a moving
                threshold for what counts as an expensive or cheap win.
        """
        self.wins += 1
        self.total_spent += price
        self.win_prices.append(price)
        self.estimated_budget = max(0.0, self.estimated_budget - price)

        if price > max(EXPENSIVE_FLOOR, EXPENSIVE_RATIO * market_median):
            self.aggression_level = min(1.0, self.aggression_level + EXPENSIVE_STEP)
        elif 0.0 < price < max(CHEAP_FLOOR, CHEAP_RATIO * market_median):
            self.aggression_level = max(0.0, self.aggression_level - CHEAP_STEP)

    def can_contest(self, value: float) -> bool:
        """Report whether the opponent could still afford to fight for an item.

        Args:
            value: This agent's value for the item in question.

        Returns:
            True if the opponent's estimated budget clears the solvency gate.
        """
        threshold = SOLVENCY_FRACTION * min(value, SOLVENCY_VALUE_CAP)
        return self.estimated_budget > threshold


class OpponentBook:
    """Collection of opponent models with aggregate queries."""

    def __init__(self, opponent_names: List[str], initial_budget: float) -> None:
        """Create one model per opponent.

        Args:
            opponent_names: Identifiers of the opponents in the game.
            initial_budget: Budget every competitor starts with.
        """
        self.models: Dict[str, OpponentModel] = {
            name: OpponentModel(name, initial_budget) for name in opponent_names
        }

    def observe_win(self, winner: str, price: float, market_median: float) -> None:
        """Update the winning opponent's model, if that opponent is tracked.

        Args:
            winner: Identifier of the round winner (may be this agent or empty).
            price: Price the winner paid.
            market_median: Current median clearing price.
        """
        model = self.models.get(winner)
        if model is not None:
            model.observe_win(price, market_median)

    def contesting_aggression(self, value: float) -> float:
        """Average aggression of opponents still able to contest an item.

        Args:
            value: This agent's value for the item in question.

        Returns:
            Mean aggression of solvent opponents, or ``DEFAULT_PRESSURE`` when
            none is solvent.
        """
        active = [
            m.aggression_level for m in self.models.values() if m.can_contest(value)
        ]
        if not active:
            return DEFAULT_PRESSURE
        return clamp(sum(active) / len(active), 0.0, 1.0)
