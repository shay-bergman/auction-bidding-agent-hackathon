"""
Utility classes and helper functions for Auction Simulation Engine
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional
import json


@dataclass
class Team:
    """Represents a competing team"""
    team_id: str
    team_name: str
    agent_file_path: str
    registration_timestamp: datetime
    members: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "team_id": self.team_id,
            "team_name": self.team_name,
            "agent_file_path": self.agent_file_path,
            "registration_timestamp": self.registration_timestamp.isoformat(),
            "members": self.members
        }


@dataclass
class AuctionRoundResult:
    """Results from a single auction round"""
    round_number: int
    item_id: str
    winner_id: str
    price_paid: float
    all_bids: Dict[str, float]
    timestamp: datetime
    execution_times: Dict[str, float]  # Time taken by each agent to bid
    
    def to_dict(self) -> dict:
        return {
            "round_number": self.round_number,
            "item_id": self.item_id,
            "winner_id": self.winner_id,
            "price_paid": self.price_paid,
            "all_bids": self.all_bids,
            "timestamp": self.timestamp.isoformat(),
            "execution_times": self.execution_times
        }
    
    def to_public_dict(self) -> dict:
        """Public information only (for teams)"""
        return {
            "round_number": self.round_number,
            "item_id": self.item_id,
            "winner_id": self.winner_id,
            "price_paid": self.price_paid
        }


@dataclass
class TeamGameResult:
    """Results for a single team in one game"""
    team_id: str
    utility: float
    budget_spent: float
    budget_remaining: float
    items_won: List[str]
    valuation_vector: Dict[str, float]
    max_single_item_utility: float
    total_valuation_won: float
    
    def to_dict(self) -> dict:
        return {
            "team_id": self.team_id,
            "utility": self.utility,
            "budget_spent": self.budget_spent,
            "budget_remaining": self.budget_remaining,
            "items_won": self.items_won,
            "valuation_vector": self.valuation_vector,
            "max_single_item_utility": self.max_single_item_utility,
            "total_valuation_won": self.total_valuation_won,
            "num_items_won": len(self.items_won)
        }


@dataclass
class GameResult:
    """Complete results from one game"""
    game_id: str
    arena_id: str
    stage: int
    game_number: int
    timestamp: datetime
    team_results: Dict[str, TeamGameResult]
    auction_log: List[AuctionRoundResult]
    auction_sequence: List[str]
    
    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id,
            "arena_id": self.arena_id,
            "stage": self.stage,
            "game_number": self.game_number,
            "timestamp": self.timestamp.isoformat(),
            "team_results": {tid: tr.to_dict() for tid, tr in self.team_results.items()},
            "auction_log": [ar.to_dict() for ar in self.auction_log],
            "auction_sequence": self.auction_sequence
        }


@dataclass
class StageResult:
    """Results from an entire stage"""
    stage: int
    arena_results: Dict[str, List[GameResult]]
    leaderboard: List[Dict]
    timestamp: datetime
    
    def to_dict(self) -> dict:
        return {
            "stage": self.stage,
            "arena_results": {
                arena_id: [game.to_dict() for game in games]
                for arena_id, games in self.arena_results.items()
            },
            "leaderboard": self.leaderboard,
            "timestamp": self.timestamp.isoformat()
        }


def format_currency(amount: float) -> str:
    """Format currency for display"""
    return f"{amount:.2f}"


def format_utility(utility: float) -> str:
    """Format utility for display"""
    return f"{utility:.2f}"


def save_json(data: dict, filepath: str) -> None:
    """Save data to JSON file"""
    import os
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)


def load_json(filepath: str) -> dict:
    """Load data from JSON file"""
    with open(filepath, 'r') as f:
        return json.load(f)


def generate_game_id(stage: int, arena_id: str, game_number: int) -> str:
    """Generate unique game ID"""
    return f"stage{stage}_arena{arena_id}_game{game_number}"


def generate_team_id() -> str:
    """Generate unique team ID (UUID)"""
    import uuid
    return str(uuid.uuid4())
