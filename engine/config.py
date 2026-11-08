"""Configuration and constants for the auction simulation engine."""

# Game parameters.
K_TOTAL_ITEMS = 20  # size of the item pool valuations are drawn for
T_AUCTION_ROUNDS = 15  # items auctioned per game
INITIAL_BUDGET = 60  # starting budget for every competitor

# Item valuation categories and their value ranges.
HIGH_VALUE_ITEMS = 6
LOW_VALUE_ITEMS = 4
MIXED_VALUE_ITEMS = 10

HIGH_VALUE_RANGE = (10, 20)
LOW_VALUE_RANGE = (1, 10)
MIXED_VALUE_RANGE = (1, 20)

# Execution limits for a single bid.
BID_TIMEOUT_SECONDS = 2.0
BID_DECIMAL_PLACES = 2

# Item id format string, e.g. "item_0".
ITEM_ID_FORMAT = "item_{}"

# Default random seed (None = nondeterministic); overridden per run.
RANDOM_SEED = None
