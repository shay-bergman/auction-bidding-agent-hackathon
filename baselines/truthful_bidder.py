"""
Example Agent 1: Truthful Bidder
Bids exactly the valuation (optimal in standard Vickrey auctions without budget constraints)
"""

from typing import Dict, List


class BiddingAgent:
    """Truthful bidding strategy - always bid your true valuation"""
    
    def __init__(self, team_id: str, valuation_vector: Dict[str, float], 
                 budget: float, opponent_teams: List[str]):
        self.team_id = team_id
        self.valuation_vector = valuation_vector
        self.budget = budget
        self.initial_budget = budget
        self.opponent_teams = opponent_teams
        self.utility = 0
        self.items_won = []
    
    def _update_available_budget(self, item_id: str, winning_team: str, price_paid: float):
        if winning_team == self.team_id:
            self.budget -= price_paid
            self.items_won.append(item_id)
    
    def update_after_each_round(self, item_id: str, winning_team: str, price_paid: float):
        self._update_available_budget(item_id, winning_team, price_paid)
        if winning_team == self.team_id:
            self.utility += (self.valuation_vector[item_id] - price_paid)
        return True
    
    def bidding_function(self, item_id: str) -> float:
        """
        Truthful bidding: bid exactly your valuation.
        Cap at budget to ensure feasibility.
        """
        valuation = self.valuation_vector.get(item_id, 0)
        bid = min(valuation, self.budget)
        return bid
