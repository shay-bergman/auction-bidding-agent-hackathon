"""Strategic bidding agent for sequential second-price auctions.

The package is split by responsibility:

- ``mathutils``  -- small numeric helpers (clamping, rounding, quantiles).
- ``estimation`` -- the market model: price statistics and value bookkeeping.
- ``opponents``  -- per-opponent budget and aggression tracking.
- ``policy``     -- the bid-decision policy (shading, pacing, endgame spend-up).
- ``bidding_agent`` -- the ``BiddingAgent`` class the engine talks to, which
  holds game state and delegates estimation and decisions to the modules above.
"""
