"""
Example Agent 4: Random Bidder (Baseline)
Bids random amounts - useful for testing and as a baseline
"""

from typing import Dict, List
import random


class BiddingAgent:
    """Random bidding strategy - for testing purposes"""
    
    def __init__(self, team_id: str, valuation_vector: Dict[str, float], 
                 budget: float, opponent_teams: List[str]):
        self.team_id = team_id
        self.valuation_vector = valuation_vector
        self.budget = budget
        self.initial_budget = budget
        self.opponent_teams = opponent_teams
        self.utility = 0
        self.items_won = []
        
        random.seed()
    
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
        Random bidding: bid a random fraction of valuation.
        Still respects budget constraints.
        """
        valuation = self.valuation_vector.get(item_id, 0)
        
        # Bid between 0% and 100% of valuation randomly
        fraction = random.uniform(0, 1)
        bid = valuation * fraction
        
        # Don't exceed budget
        bid = min(bid, self.budget)
        
        return bid
