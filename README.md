# Auction Bidding Agent — Hackathon Project

*A strategic bidding agent for sequential second-price auctions, with a simulator to benchmark it against baseline strategies.*

> Built for an algorithmic game theory hackathon — the agent competed in a live tournament against other autonomous agents under a shared-budget, partial-information setting.

## Overview

Each game is a sequence of 15 single-item auctions. Every competitor starts with
the same budget of 60 and a private valuation for each item, drawn once at the
start of the game:

- 6 items are high-value for everyone (values ~ Uniform[10, 20]),
- 4 items are low-value for everyone (~ Uniform[1, 10]),
- 10 items are mixed and may be worth a lot to one competitor and little to another (~ Uniform[1, 20]).

Items are auctioned one at a time under a sealed-bid, second-price (Vickrey)
rule: the highest bidder wins and pays the second-highest bid (a sole bidder
pays nothing, and ties are broken at random with the winner paying the tied
amount). A round's utility is `value_of_item - price_paid`, and a game score is
the sum of those utilities. After each round only the public outcome is revealed
— which item sold, who won it, and the price paid; individual bids are never
disclosed.

In a one-shot Vickrey auction, bidding your true value is optimal. Two frictions
break that here, and the agent exists to handle them:

- a single budget shared across many rounds, so spending is a sequential
  allocation problem rather than a per-item one, and
- partial information — competition must be inferred from clearing prices alone.

## Strategy

The agent bids below its true value by an amount that adapts to how contested the
current item looks. A bid is decided in three stages (implemented in
`agent/policy.py`):

1. **Competition estimate.** A score in `[0, 1]` blends market "temperature"
   (how high and heavy-tailed recent clearing prices are) with the aggression of
   opponents that can still afford to contest the item.

2. **Adaptive shading.** The competition score picks a base shade factor
   (fraction of value to bid): shade hard when competition is high to preserve
   budget, bid close to value when it is low. The factor is then relaxed as the
   game progresses, loosened further when spending lags a pacing target, and
   nudged up on the agent's own highest-percentile items and in quiet markets.

3. **Floors and caps.** A "need-to-win" floor lifts the bid just above the recent
   75th-percentile price (still below value) on items carrying real surplus, so
   comfortably profitable items are not lost by a hair. A soft pacing cap keyed to
   budget-per-remaining-round prevents early budget exhaustion but opens up in the
   final rounds so leftover budget is spent rather than wasted. The bid is finally
   clamped below both the item's value and the remaining budget.

Two supporting models feed the policy:

- **`agent/estimation.py` (market model).** Clearing prices are bucketed by value
  tier (high / mid / low) so the agent estimates what items *like the current
  one* cost, falling back to the global price history and then to priors when
  data is thin. It also precomputes each item's value rank and percentile.

- **`agent/opponents.py` (opponent model).** Each opponent carries an estimated
  remaining budget (decremented by observed payments) and an aggression score
  that rises after expensive wins and decays after cheap ones. Only opponents
  still solvent enough to contest an item feed into the competition estimate.

## Repository structure

```
auction-bidding-agent/
├── agent/                    # the bidding agent (the focus of this project)
│   ├── bidding_agent.py      # BiddingAgent: engine interface and game state
│   ├── policy.py             # bid-decision policy (shading, floors, pacing cap)
│   ├── estimation.py         # market model: price statistics and value lookups
│   ├── opponents.py          # per-opponent budget and aggression models
│   └── mathutils.py          # numeric helpers (clamp, round, quantile)
├── baselines/                # reference opponents to benchmark against
│   ├── truthful_bidder.py
│   ├── budget_aware_bidder.py
│   ├── strategic_bidder.py
│   └── random_bidder.py
├── engine/                   # auction simulation engine
│   ├── config.py             # game parameters
│   ├── valuation_generator.py
│   ├── auction_engine.py     # second-price mechanism
│   ├── agent_manager.py      # isolated, timed agent execution
│   ├── game_manager.py       # orchestrates one 15-round game
│   └── utils.py
├── run.py                    # entry point: agent vs baselines
├── requirements.txt
└── LICENSE
```

The engine runs each agent in an isolated subprocess with a per-bid timeout and
serializes agent state between rounds, so the agent keeps its market and opponent
models for the whole game.

## Getting started

Requires Python 3.9+ and NumPy.

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Agent vs all four baselines, 20 games
python run.py

# Reproducible longer run
python run.py --num-games 100 --seed 42

# Head-to-head against a single opponent
python run.py --opponent baselines/truthful_bidder.py
```

The simulator prints one line per game (the agent's rank, utility, items won, and
spend), then an aggregate summary and a leaderboard ordered by average utility.

## Results

Across randomized games the agent is consistently competitive with the strongest
baselines and well ahead of the weaker ones, typically finishing at or near the
top of the leaderboard on average utility and win rate. The truthful bidder is a
genuinely hard opponent — second-price auctions reward honesty — so the agent's
edge comes from budget discipline and from picking its fights: shading on crowded
items and spending up on the ones it can win cheaply. Exact standings depend on
the random seed; run 50–100+ games for the averages to stabilize.

## License

Released under the MIT License. See [LICENSE](LICENSE).
