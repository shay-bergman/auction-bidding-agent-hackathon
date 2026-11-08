"""
Game Manager for Auction Simulation Engine
Orchestrates a single game (15 auction rounds)
"""

import logging
from datetime import datetime
from typing import Dict, List, Tuple
import copy

from engine.config import T_AUCTION_ROUNDS, INITIAL_BUDGET
from engine.valuation_generator import ValuationGenerator
from engine.auction_engine import AuctionEngine
from engine.agent_manager import AgentManager
from engine.utils import GameResult, TeamGameResult, AuctionRoundResult, generate_game_id


logger = logging.getLogger(__name__)


class GameManager:
    """
    Manages a single game consisting of T auction rounds.
    
    Workflow:
    1. Generate valuations for all teams
    2. Select and shuffle auction sequence
    3. Initialize all agents
    4. Execute T sequential auction rounds
    5. Update agents after each round
    6. Calculate final results
    """
    
    def __init__(self, stage: int, arena_id: str, game_number: int,
                 valuation_generator: ValuationGenerator,
                 auction_engine: AuctionEngine,
                 agent_manager: AgentManager,
                 fixed_valuations: Dict = None):
        """
        Initialize game manager.
        
        Args:
            stage: Competition stage (1 or 2)
            arena_id: Arena identifier
            game_number: Game number within stage (1-5)
            valuation_generator: Valuation generator instance
            auction_engine: Auction engine instance
            agent_manager: Agent manager instance
            fixed_valuations: Optional pre-generated valuations to use for all games in arena
        """
        self.stage = stage
        self.arena_id = arena_id
        self.game_number = game_number
        self.game_id = generate_game_id(stage, arena_id, game_number)
        
        self.valuation_generator = valuation_generator
        self.auction_engine = auction_engine
        self.agent_manager = agent_manager
        self.fixed_valuations = fixed_valuations  # Store fixed valuations if provided
        
        self.agents = {}
        self.budgets = {}
        self.valuations = {}
        self.items_won = {}
        self.auction_log = []
        self.auction_sequence = []
    
    def initialize_game(self, team_agents: Dict[str, str]) -> bool:
        """
        Initialize game with teams and their agent files.
        
        Args:
            team_agents: Dictionary mapping team_id to agent_file_path
        
        Returns:
            True if initialization successful, False otherwise
        """
        logger.info(f"Initializing game {self.game_id}")
        logger.info(f"Teams: {list(team_agents.keys())}")
        
        try:
            # Use fixed valuations if provided, otherwise generate new ones
            team_ids = list(team_agents.keys())
            if self.fixed_valuations is not None:
                self.valuations = self.fixed_valuations
                logger.info(f"Using fixed valuations for {len(team_ids)} teams")
            else:
                self.valuations, item_categories = self.valuation_generator.generate_arena_valuations(team_ids)
                logger.info(f"Generated valuations for {len(team_ids)} teams")
                logger.debug(f"Item categories: High={item_categories[0]}, Low={item_categories[1]}, Mixed={item_categories[2]}")
            
            # Generate auction sequence
            self.auction_sequence = self.valuation_generator.get_random_auction_sequence(T_AUCTION_ROUNDS)
            logger.info(f"Auction sequence: {self.auction_sequence}")
            
            # Initialize budgets and items_won tracking
            for team_id in team_ids:
                self.budgets[team_id] = INITIAL_BUDGET
                self.items_won[team_id] = []
            
            # Load and initialize agents
            for team_id, agent_file in team_agents.items():
                # Get list of opponent teams (all teams except current one)
                opponent_teams = [tid for tid in team_ids if tid != team_id]
                
                agent = self.agent_manager.load_agent(
                    file_path=agent_file,
                    team_id=team_id,
                    valuation_vector=self.valuations[team_id],
                    budget=INITIAL_BUDGET,
                    opponent_teams=opponent_teams
                )
                
                if agent is None:
                    logger.error(f"Failed to load agent for team {team_id}")
                    return False
                
                self.agents[team_id] = agent
            
            logger.info(f"Successfully initialized {len(self.agents)} agents")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing game: {e}", exc_info=True)
            return False
    
    def execute_auction_round(self, round_number: int, item_id: str) -> AuctionRoundResult:
        """
        Execute a single auction round.
        
        Args:
            round_number: Sequential round number (1-15)
            item_id: Item being auctioned
        
        Returns:
            AuctionRoundResult with complete round information
        """
        logger.info(f"=== Round {round_number}/{T_AUCTION_ROUNDS}: Item {item_id} ===")
        
        # Collect bids from all agents
        bids = {}
        execution_times = {}
        
        for team_id, agent in self.agents.items():
            bid, exec_time, error = self.agent_manager.execute_bid_with_timeout(agent, item_id)
            bids[team_id] = bid
            execution_times[team_id] = exec_time
            
            if error:
                logger.warning(f"Team {team_id} bid error: {error}")
            
            logger.debug(f"Team {team_id}: Bid={bid:.2f}, Budget={self.budgets[team_id]:.2f}, Time={exec_time:.3f}s")
        
        # Execute auction
        round_result = self.auction_engine.execute_round(
            round_number=round_number,
            item_id=item_id,
            bids=bids,
            budgets=self.budgets,
            execution_times=execution_times
        )
        
        # Update game state
        if round_result.winner_id:
            winner_id = round_result.winner_id
            price = round_result.price_paid
            
            # Update budget
            self.budgets[winner_id] -= price
            
            # Track items won
            self.items_won[winner_id].append(item_id)
            
            logger.info(f"Winner: {winner_id}, Price: {price:.2f}, Remaining budget: {self.budgets[winner_id]:.2f}")
        else:
            logger.info("No winner this round")
        
        # Update all agents with round results
        for team_id, agent in self.agents.items():
            winner = round_result.winner_id if round_result.winner_id else ""
            price = round_result.price_paid
            self.agent_manager.update_agent_after_round(agent, item_id, winner, price)
        
        return round_result
    
    def run_game(self, team_agents: Dict[str, str]) -> GameResult:
        """
        Run a complete game.
        
        Args:
            team_agents: Dictionary mapping team_id to agent_file_path
        
        Returns:
            GameResult with complete game information
        """
        logger.info(f"======== Starting Game {self.game_id} ========")
        start_time = datetime.now()
        
        # Initialize game
        if not self.initialize_game(team_agents):
            logger.error("Game initialization failed")
            raise Exception("Game initialization failed")
        
        # Execute all auction rounds
        for round_number in range(1, T_AUCTION_ROUNDS + 1):
            item_id = self.auction_sequence[round_number - 1]
            round_result = self.execute_auction_round(round_number, item_id)
            self.auction_log.append(round_result)
        
        # Calculate final results
        team_results = self._calculate_final_results()
        
        # Create game result
        game_result = GameResult(
            game_id=self.game_id,
            arena_id=self.arena_id,
            stage=self.stage,
            game_number=self.game_number,
            timestamp=start_time,
            team_results=team_results,
            auction_log=self.auction_log,
            auction_sequence=self.auction_sequence
        )
        
        logger.info(f"======== Game {self.game_id} Complete ========")
        self._log_game_summary(team_results)
        
        return game_result
    
    def _calculate_final_results(self) -> Dict[str, TeamGameResult]:
        """
        Calculate final results for all teams.
        
        Returns:
            Dictionary mapping team_id to TeamGameResult
        """
        team_results = {}
        
        for team_id, agent in self.agents.items():
            # Calculate total valuation of won items
            total_valuation_won = sum(
                self.valuations[team_id][item_id] 
                for item_id in self.items_won[team_id]
            )
            
            # Calculate total spent
            budget_spent = INITIAL_BUDGET - self.budgets[team_id]
            
            # Calculate utility
            utility = total_valuation_won - budget_spent
            
            # Find max single item utility
            max_item_utility = 0.0
            if self.items_won[team_id]:
                max_item_utility = max(
                    self.valuations[team_id][item_id] 
                    for item_id in self.items_won[team_id]
                )
            
            team_result = TeamGameResult(
                team_id=team_id,
                utility=utility,
                budget_spent=budget_spent,
                budget_remaining=self.budgets[team_id],
                items_won=self.items_won[team_id].copy(),
                valuation_vector=self.valuations[team_id].copy(),
                max_single_item_utility=max_item_utility,
                total_valuation_won=total_valuation_won
            )
            
            team_results[team_id] = team_result
        
        return team_results
    
    def _log_game_summary(self, team_results: Dict[str, TeamGameResult]):
        """Log summary of game results"""
        logger.info("=== Game Summary ===")
        
        # Sort teams by utility
        sorted_teams = sorted(team_results.items(), 
                            key=lambda x: x[1].utility, 
                            reverse=True)
        
        for rank, (team_id, result) in enumerate(sorted_teams, 1):
            logger.info(
                f"Rank {rank}: {team_id} | "
                f"Utility: {result.utility:.2f} | "
                f"Items Won: {len(result.items_won)} | "
                f"Spent: {result.budget_spent:.2f} | "
                f"Valuation: {result.total_valuation_won:.2f}"
            )
