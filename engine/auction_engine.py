"""
Auction Engine for Auction Simulation Engine
Executes single auction rounds using second-price sealed-bid mechanism
"""

import numpy as np
from typing import Dict, Tuple, List
from datetime import datetime
import logging

from engine.utils import AuctionRoundResult


logger = logging.getLogger(__name__)


class AuctionEngine:
    """
    Executes a single auction round using second-price sealed-bid (Vickrey) mechanism.
    
    Process:
    1. Collect bids from all agents
    2. Determine winner (highest bid)
    3. Calculate price (second-highest bid)
    4. Handle ties randomly
    """
    
    def __init__(self):
        """Initialize auction engine"""
        pass
    
    def validate_bid(self, bid: float, budget: float, team_id: str) -> Tuple[float, bool]:
        """
        Validate and cap bid to available budget.
        
        Args:
            bid: The bid amount
            budget: Available budget
            team_id: Team identifier (for logging)
        
        Returns:
            Tuple of (capped_bid, was_capped)
        """
        if bid is None or not isinstance(bid, (int, float)):
            logger.warning(f"Team {team_id}: Invalid bid type {type(bid)}, treating as 0")
            return 0.0, False
        
        if bid < 0:
            logger.warning(f"Team {team_id}: Negative bid {bid}, treating as 0")
            return 0.0, False
        
        if bid > budget:
            logger.warning(f"Team {team_id}: Bid {bid:.2f} exceeds budget {budget:.2f}, capping to budget")
            return round(budget, 2), True
        
        # Round bid to 2 decimal places
        return round(float(bid), 2), False
    
    def determine_winner(self, bids: Dict[str, float]) -> Tuple[str, float, List[str]]:
        """
        Determine auction winner and price using second-price mechanism.
        
        Args:
            bids: Dictionary mapping team_id to bid amount
        
        Returns:
            Tuple of (winner_id, price_paid, tied_teams)
            - If no valid bids, returns (None, 0.0, [])
            - price_paid is the second-highest bid (or 0 if only one bidder)
        """
        if not bids:
            return None, 0.0, []
        
        # Filter out zero or negative bids
        valid_bids = {team_id: bid for team_id, bid in bids.items() if bid > 0}
        
        if not valid_bids:
            logger.info("No valid bids in this round")
            return None, 0.0, []
        
        # Sort bids in descending order
        sorted_bids = sorted(valid_bids.items(), key=lambda x: x[1], reverse=True)
        
        # Get highest bid(s) - may have ties
        highest_bid = sorted_bids[0][1]
        highest_bidders = [team_id for team_id, bid in sorted_bids if bid == highest_bid]
        
        # Handle ties with random selection
        if len(highest_bidders) > 1:
            winner_id = np.random.choice(highest_bidders)
            logger.info(f"Tie broken randomly among {highest_bidders}, winner: {winner_id}")
        else:
            winner_id = highest_bidders[0]
        
        # Calculate second-price
        if len(sorted_bids) == 1:
            # Only one bidder - pays 0 (or minimum bid if we want to set one)
            price_paid = 0.0
            logger.info(f"Single bidder {winner_id}, pays 0")
        else:
            # Second-highest bid (or highest if tied)
            if len(highest_bidders) > 1:
                # If there's a tie for highest, winner pays the tied amount
                price_paid = highest_bid
            else:
                # Winner pays second-highest bid
                price_paid = sorted_bids[1][1]
        
        return winner_id, price_paid, highest_bidders if len(highest_bidders) > 1 else []
    
    def execute_round(self, round_number: int, item_id: str, 
                     bids: Dict[str, float], budgets: Dict[str, float],
                     execution_times: Dict[str, float]) -> AuctionRoundResult:
        """
        Execute a complete auction round.
        
        Args:
            round_number: Sequential round number (1-15)
            item_id: ID of item being auctioned
            bids: Dictionary mapping team_id to bid amount
            budgets: Dictionary mapping team_id to available budget
            execution_times: Dictionary mapping team_id to bid execution time
        
        Returns:
            AuctionRoundResult with complete round information
        """
        logger.info(f"Round {round_number}: Auctioning {item_id}")
        
        # Validate and cap all bids
        validated_bids = {}
        capped_teams = []
        
        for team_id, bid in bids.items():
            budget = budgets.get(team_id, 0)
            validated_bid, was_capped = self.validate_bid(bid, budget, team_id)
            validated_bids[team_id] = validated_bid
            
            if was_capped:
                capped_teams.append(team_id)
        
        logger.debug(f"Validated bids: {validated_bids}")
        if capped_teams:
            logger.warning(f"Teams with capped bids: {capped_teams}")
        
        # Determine winner and price
        winner_id, price_paid, tied_teams = self.determine_winner(validated_bids)
        
        if winner_id:
            logger.info(f"Winner: {winner_id}, Price: {price_paid:.2f}")
            if tied_teams:
                logger.info(f"Tie broken among: {tied_teams}")
        else:
            logger.info("No winner (no valid bids)")
        
        # Create result object
        result = AuctionRoundResult(
            round_number=round_number,
            item_id=item_id,
            winner_id=winner_id,
            price_paid=price_paid,
            all_bids=validated_bids,
            timestamp=datetime.now(),
            execution_times=execution_times
        )
        
        return result
