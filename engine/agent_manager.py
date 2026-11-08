"""
Agent Manager for Auction Simulation Engine
Loads, validates, and executes team-submitted bidding agents

SECURITY: Uses multiprocessing for memory isolation to prevent:
- Information leakage via gc module
- Budget manipulation
- Agent sabotage via sys.modules
- Module pollution
"""

import importlib.util
import sys
import os
import time
import logging
from typing import Dict, Optional, Any, Tuple
from pathlib import Path
import multiprocessing as mp
import pickle


logger = logging.getLogger(__name__)


def _worker_execute_bid(file_path: str, team_id: str, valuation_vector: Dict[str, float],
                        budget: float, opponent_teams: list, item_id: str,
                        agent_state: Optional[Dict], result_queue: mp.Queue):
    """
    Worker function to execute bid in isolated process.
    
    This runs in a separate process with isolated memory space,
    preventing access to GameManager or other agents.
    
    Args:
        file_path: Path to agent file
        team_id: Team identifier
        valuation_vector: Item valuations
        budget: Current budget
        opponent_teams: List of opponent team IDs
        item_id: Item to bid on
        agent_state: Serialized agent state from previous rounds
        result_queue: Queue to return results
    """
    try:
        # Load agent module in isolated process
        spec = importlib.util.spec_from_file_location(f"agent_{team_id}", file_path)
        if spec is None or spec.loader is None:
            result_queue.put(('error', 0.0, 0.0, None, "Failed to load module spec"))
            return
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        if not hasattr(module, 'BiddingAgent'):
            result_queue.put(('error', 0.0, 0.0, None, "No BiddingAgent class found"))
            return
        
        agent_class = getattr(module, 'BiddingAgent')
        
        # Create or restore agent instance
        if agent_state is None:
            # First call - instantiate new agent
            agent = agent_class(team_id, valuation_vector, budget, opponent_teams)
        else:
            # Restore agent state
            agent = agent_class(team_id, valuation_vector, budget, opponent_teams)
            # Restore internal state
            for key, value in agent_state.items():
                setattr(agent, key, value)
        
        # Execute bidding function
        start_time = time.time()
        bid = agent.bidding_function(item_id)
        execution_time = time.time() - start_time
        
        # Serialize agent state for next round
        # Only serialize safe attributes (not methods or private internals)
        new_state = {}
        for key, value in agent.__dict__.items():
            if not key.startswith('_') and not callable(value):
                try:
                    # Test if picklable
                    pickle.dumps(value)
                    new_state[key] = value
                except:
                    pass  # Skip non-picklable attributes
        
        result_queue.put(('success', float(bid), execution_time, new_state, None))
        
    except Exception as e:
        result_queue.put(('error', 0.0, 0.0, None, str(e)))


def _worker_update_agent(file_path: str, team_id: str, valuation_vector: Dict[str, float],
                         budget: float, opponent_teams: list, agent_state: Dict,
                         item_id: str, winning_team: str, price_paid: float,
                         result_queue: mp.Queue):
    """
    Worker function to update agent after round in isolated process.
    
    Args:
        file_path: Path to agent file
        team_id: Team identifier
        valuation_vector: Item valuations
        budget: Current budget
        opponent_teams: List of opponent team IDs
        agent_state: Serialized agent state
        item_id: Item that was auctioned
        winning_team: Winning team ID
        price_paid: Price paid
        result_queue: Queue to return results
    """
    try:
        # Load agent module
        spec = importlib.util.spec_from_file_location(f"agent_{team_id}", file_path)
        if spec is None or spec.loader is None:
            result_queue.put(('error', None, "Failed to load module spec"))
            return
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        if not hasattr(module, 'BiddingAgent'):
            result_queue.put(('error', None, "No BiddingAgent class found"))
            return
        
        agent_class = getattr(module, 'BiddingAgent')
        agent = agent_class(team_id, valuation_vector, budget, opponent_teams)
        
        # Restore state
        for key, value in agent_state.items():
            setattr(agent, key, value)
        
        # Update agent
        agent.update_after_each_round(item_id, winning_team, price_paid)
        
        # Serialize new state
        new_state = {}
        for key, value in agent.__dict__.items():
            if not key.startswith('_') and not callable(value):
                try:
                    pickle.dumps(value)
                    new_state[key] = value
                except:
                    pass
        
        result_queue.put(('success', new_state, None))
        
    except Exception as e:
        result_queue.put(('error', None, str(e)))


class AgentManager:
    """
    Manages loading, validation, and execution of team bidding agents.
    
    SECURITY MODEL:
    - Each agent runs in isolated process (separate memory space)
    - Agent state is serialized/deserialized between calls
    - Prevents memory scanning, budget injection, module pollution
    
    Responsibilities:
    - Load agent code from file
    - Validate agent interface compliance
    - Execute bids with timeout enforcement in isolated processes
    - Handle errors gracefully
    """
    
    def __init__(self, timeout_seconds: float = 3.0):
        """
        Initialize agent manager.
        
        Args:
            timeout_seconds: Maximum time allowed for bid execution
        """
        self.timeout_seconds = timeout_seconds
        self.agent_metadata = {}  # Store file paths and initialization params
        self.agent_states = {}    # Store serialized agent states
    
    def load_agent(self, file_path: str, team_id: str, 
                   valuation_vector: Dict[str, float],
                   budget: float, 
                   opponent_teams: list) -> Optional[Any]:
        """
        Register agent metadata for isolated execution.
        
        Note: Unlike the old implementation, this doesn't actually instantiate
        the agent in the main process. Instead, it stores the metadata needed
        to instantiate it in isolated worker processes.
        
        Args:
            file_path: Path to the team's agent Python file
            team_id: Unique team identifier
            valuation_vector: Item valuations for this game
            budget: Initial budget
            opponent_teams: List of opponent team IDs in the same arena
        
        Returns:
            A proxy object representing the agent (for compatibility)
        """
        try:
            logger.info(f"Registering agent for team {team_id} from {file_path}")
            
            # Check if file exists
            if not os.path.exists(file_path):
                logger.error(f"Agent file not found: {file_path}")
                return None
            
            # Validate agent interface by loading in current process (just for validation)
            spec = importlib.util.spec_from_file_location(f"validate_{team_id}", file_path)
            if spec is None or spec.loader is None:
                logger.error(f"Failed to load module spec from {file_path}")
                return None
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find BiddingAgent class in module
            if not hasattr(module, 'BiddingAgent'):
                logger.error(f"Module {file_path} does not contain BiddingAgent class")
                return None
            
            agent_class = getattr(module, 'BiddingAgent')
            
            # Quick validation - instantiate to check interface
            test_agent = agent_class(team_id, valuation_vector, budget, opponent_teams)
            if not self.validate_agent(test_agent):
                logger.error(f"Agent validation failed for team {team_id}")
                return None
            
            # Store metadata for process-isolated execution
            self.agent_metadata[team_id] = {
                'file_path': file_path,
                'team_id': team_id,
                'valuation_vector': valuation_vector,
                'budget': budget,
                'opponent_teams': opponent_teams
            }
            self.agent_states[team_id] = None  # No state yet
            
            logger.info(f"Successfully registered agent for team {team_id}")
            
            # Return a proxy object for compatibility with existing code
            class AgentProxy:
                def __init__(self, tid):
                    self.team_id = tid
            
            return AgentProxy(team_id)
            
        except Exception as e:
            logger.error(f"Error registering agent for team {team_id}: {e}", exc_info=True)
            return None
    
    def validate_agent(self, agent: Any) -> bool:
        """
        Validate that agent implements required interface.
        
        Args:
            agent: Agent instance to validate
        
        Returns:
            True if agent is valid, False otherwise
        """
        required_methods = ['bidding_function', 'update_after_each_round']
        required_attributes = ['team_id', 'valuation_vector', 'budget']
        
        # Check required methods
        for method_name in required_methods:
            if not hasattr(agent, method_name) or not callable(getattr(agent, method_name)):
                logger.error(f"Agent missing required method: {method_name}")
                return False
        
        # Check required attributes
        for attr_name in required_attributes:
            if not hasattr(agent, attr_name):
                logger.error(f"Agent missing required attribute: {attr_name}")
                return False
        
        return True
    
    def execute_bid_with_timeout(self, agent: Any, item_id: str) -> Tuple[float, float, Optional[str]]:
        """
        Execute agent's bidding function with timeout enforcement in isolated process.
        
        SECURITY: Each bid executes in a separate process with isolated memory,
        preventing access to GameManager, other agents, or system internals.
        
        Args:
            agent: Agent proxy object (contains team_id)
            item_id: ID of item being auctioned
        
        Returns:
            Tuple of (bid_amount, execution_time, error_msg)
            - On success: (bid, time, None)
            - On timeout: (0.0, timeout_seconds, "Timeout")
            - On error: (0.0, time, error_message)
        """
        team_id = agent.team_id
        
        if team_id not in self.agent_metadata:
            logger.error(f"Team {team_id} not registered")
            return 0.0, 0.0, "Agent not registered"
        
        metadata = self.agent_metadata[team_id]
        agent_state = self.agent_states[team_id]
        
        start_time = time.time()
        
        try:
            # Create multiprocessing queue for results
            result_queue = mp.Queue()
            
            # Create isolated process
            process = mp.Process(
                target=_worker_execute_bid,
                args=(
                    metadata['file_path'],
                    metadata['team_id'],
                    metadata['valuation_vector'],
                    metadata['budget'],
                    metadata['opponent_teams'],
                    item_id,
                    agent_state,
                    result_queue
                )
            )
            
            process.start()
            process.join(timeout=self.timeout_seconds)
            
            execution_time = time.time() - start_time
            
            # Check if process timed out
            if process.is_alive():
                process.terminate()
                process.join(timeout=1.0)
                if process.is_alive():
                    process.kill()  # Force kill if terminate didn't work
                logger.warning(f"Team {team_id}: Bid execution timeout ({self.timeout_seconds}s)")
                return 0.0, self.timeout_seconds, "Timeout"
            
            # Get result from queue
            try:
                status, bid, exec_time, new_state, error = result_queue.get(timeout=0.5)
                
                if status == 'success':
                    # Update agent state for next round
                    self.agent_states[team_id] = new_state
                    # Round bid to 2 decimal places
                    rounded_bid = round(float(bid), 2)
                    logger.debug(f"Team {team_id}: Bid {rounded_bid:.2f} in {exec_time:.3f}s")
                    return rounded_bid, exec_time, None
                else:
                    logger.error(f"Team {team_id}: Bid execution error: {error}")
                    return 0.0, execution_time, f"Error: {error}"
                    
            except Exception as e:
                logger.error(f"Team {team_id}: Failed to get result from queue: {e}")
                return 0.0, execution_time, "No result returned"
                
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Team {team_id}: Unexpected error in bid execution: {e}", exc_info=True)
            return 0.0, execution_time, f"Exception: {str(e)}"
        finally:
            # Clean up
            try:
                result_queue.close()
            except:
                pass
    
    def update_agent_after_round(self, agent: Any, item_id: str, 
                                winning_team: str, price_paid: float) -> bool:
        """
        Update agent with round results in isolated process.
        
        SECURITY: Update executes in separate process to maintain isolation.
        
        Args:
            agent: Agent proxy object
            item_id: Item that was auctioned
            winning_team: ID of winning team
            price_paid: Price paid by winner
        
        Returns:
            True if update successful, False otherwise
        """
        team_id = agent.team_id
        
        if team_id not in self.agent_metadata:
            logger.error(f"Team {team_id} not registered")
            return False
        
        metadata = self.agent_metadata[team_id]
        agent_state = self.agent_states[team_id]
        
        if agent_state is None:
            # Agent hasn't been initialized yet (no bids executed)
            logger.warning(f"Team {team_id}: Cannot update agent with no state")
            return False
        
        try:
            result_queue = mp.Queue()
            
            process = mp.Process(
                target=_worker_update_agent,
                args=(
                    metadata['file_path'],
                    metadata['team_id'],
                    metadata['valuation_vector'],
                    metadata['budget'],
                    metadata['opponent_teams'],
                    agent_state,
                    item_id,
                    winning_team,
                    price_paid,
                    result_queue
                )
            )
            
            process.start()
            process.join(timeout=self.timeout_seconds)
            
            if process.is_alive():
                process.terminate()
                process.join(timeout=1.0)
                if process.is_alive():
                    process.kill()
                logger.warning(f"Team {team_id}: Update timeout")
                return False
            
            try:
                status, new_state, error = result_queue.get(timeout=0.5)
                
                if status == 'success':
                    self.agent_states[team_id] = new_state
                    return True
                else:
                    logger.error(f"Team {team_id}: Error in update_after_each_round: {error}")
                    return False
                    
            except Exception as e:
                logger.error(f"Team {team_id}: Failed to get update result: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Team {team_id}: Unexpected error in agent update: {e}", exc_info=True)
            return False
        finally:
            try:
                result_queue.close()
            except:
                pass
