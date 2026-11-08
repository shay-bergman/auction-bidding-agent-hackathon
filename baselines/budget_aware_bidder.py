"""
Example Agent 2: Budget-Aware Bidder
Considers remaining budget and future rounds when bidding
"""

from typing import Dict, List


class BiddingAgent:
    """Budget-aware strategy - scales bids based on remaining budget"""
    
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
        self.total_rounds = 15  # Always 15 rounds per game
    
    def _update_available_budget(self, item_id: str, winning_team: str, price_paid: float):
        if winning_team == self.team_id:
            self.budget -= price_paid
            self.items_won.append(item_id)
    
    def update_after_each_round(self, item_id: str, winning_team: str, price_paid: float):
        self._update_available_budget(item_id, winning_team, price_paid)
        if winning_team == self.team_id:
            self.utility += (self.valuation_vector[item_id] - price_paid)
        self.rounds_completed += 1
        return True
    
    def bidding_function(self, item_id: str) -> float:
        """
        Budget-aware bidding:
        - Scale bid based on budget remaining
        - Be more conservative if many rounds left
        - Be more aggressive near the end
        """
        valuation = self.valuation_vector.get(item_id, 0)
        
        # Calculate rounds remaining
        rounds_remaining = self.total_rounds - self.rounds_completed
        
        if rounds_remaining == 0:
            return 0
        
        # Calculate budget per remaining round
        budget_per_round = self.budget / rounds_remaining
        
        # Bid strategy: bid up to valuation, but be mindful of budget
        # Allow higher bids near the end of the game
        progress = self.rounds_completed / self.total_rounds
        aggressiveness = 0.7 + (0.3 * progress)  # 70% to 100% as game progresses
        
        bid = min(valuation * aggressiveness, self.budget, valuation)
        
        return max(0, bid)
