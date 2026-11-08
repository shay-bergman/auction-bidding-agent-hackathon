"""
Example Agent 3: Strategic Bidder with Opponent Modeling
Attempts to learn opponent behavior and adjust strategy
"""

from typing import Dict, List
import numpy as np


class BiddingAgent:
    """Strategic bidding with simple opponent modeling"""
    
    def __init__(self, team_id: str, valuation_vector: Dict[str, float], 
                 budget: float, opponent_teams: List[str]):
        self.team_id = team_id
        self.valuation_vector = valuation_vector
        self.budget = budget
        self.initial_budget = budget
        self.opponent_teams = opponent_teams
        self.utility = 0
        self.items_won = []
        self.rounds_completed = 0
        
        # Opponent modeling
        self.observed_prices = []
        self.opponent_wins = {}
    
    def _update_available_budget(self, item_id: str, winning_team: str, price_paid: float):
        if winning_team == self.team_id:
            self.budget -= price_paid
            self.items_won.append(item_id)
    
    def update_after_each_round(self, item_id: str, winning_team: str, price_paid: float):
        self._update_available_budget(item_id, winning_team, price_paid)
        
        if winning_team == self.team_id:
            self.utility += (self.valuation_vector[item_id] - price_paid)
        
        # Track opponent behavior
        if winning_team and price_paid > 0:
            self.observed_prices.append(price_paid)
            self.opponent_wins[winning_team] = self.opponent_wins.get(winning_team, 0) + 1
        
        self.rounds_completed += 1
        return True
    
    def bidding_function(self, item_id: str) -> float:
        """
        Strategic bidding:
        - Estimate market competitiveness from past prices
        - Adjust bids based on item value relative to observed prices
        - Consider budget constraints
        """
        valuation = self.valuation_vector.get(item_id, 0)
        
        if self.budget <= 0:
            return 0
        
        # Calculate average price so far (market estimate)
        if self.observed_prices:
            avg_price = np.mean(self.observed_prices)
            max_price = np.max(self.observed_prices)
        else:
            # No data yet, be conservative
            avg_price = 5.0
            max_price = 10.0
        
        # Rounds remaining
        total_rounds = 15  # Always 15 rounds per game
        rounds_remaining = total_rounds - self.rounds_completed
        
        if rounds_remaining == 0:
            return 0
        
        # Classify item value
        if valuation > max_price:
            # High value item - bid aggressively
            bid_fraction = 0.9
        elif valuation > avg_price:
            # Medium value item - bid moderately
            bid_fraction = 0.7
        else:
            # Low value item - bid conservatively
            bid_fraction = 0.5
        
        # Calculate bid
        bid = valuation * bid_fraction
        
        # Don't exceed budget
        bid = min(bid, self.budget)
        
        # Reserve some budget for future rounds (unless near end)
        if rounds_remaining > 3:
            max_bid_this_round = self.budget * 0.5
            bid = min(bid, max_bid_this_round)
        
        return max(0, bid)
