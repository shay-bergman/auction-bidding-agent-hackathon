"""The bid-decision policy that turns a private value into a bid."""

from __future__ import annotations

import math

from agent.estimation import MarketModel
from agent.mathutils import clamp, round2
from agent.opponents import OpponentBook

# Shade factors by competition tier (fraction of value to bid). Lower means more
# shading, which preserves budget when an item looks contested.
SHADE_HIGH_COMP = 0.62
SHADE_MID_COMP = 0.75
SHADE_LOW_COMP = 0.90
COMP_HIGH_THRESHOLD = 0.80
COMP_MID_THRESHOLD = 0.55

# Shade adjustments layered on top of the tier.
LATE_GAME_RELIEF = 0.10  # per unit of game progress: less restraint late
PERCENTILE_PUSH = 0.06  # per unit of own-value percentile: push on our best items
QUIET_MARKET_PUSH = 0.03  # nudge on mid/high items when many rounds clear at zero
QUIET_MARKET_RATE = 0.25
SHADE_MIN = 0.50
SHADE_MAX = 1.02

# Spend pacing: the target fraction of the initial budget to have spent grows
# with game progress; bids are nudged up when actual spend lags that target.
BASE_SPEND_TARGET = 0.30
PROGRESS_SPEND_TARGET = 0.75
MAX_SPEND_TARGET = 0.98
SPEND_BOOST_GAIN = 0.30
SPEND_BOOST_MIN = 0.90
SPEND_BOOST_MAX = 1.18

# "Need-to-win" floor: how much an item's value must exceed the market median
# before the agent lifts its bid above the recent 75th-percentile price.
SURPLUS_FLOOR = 3.0

# Pacing-cap shape parameters.
VALUE_WEIGHT_BASE = 0.95
VALUE_WEIGHT_SLOPE = 2.10
CAP_MULT_BASE = 2.00
CAP_MULT_SLOPE = 1.20


class BidPolicy:
    """Pure decision layer that maps game state to a bid.

    The policy holds no mutable game state; it reads the market model and
    opponent book and applies the tunable constants defined in this module. The
    decision proceeds in three stages: estimate a competition level, convert it
    to a shade factor adjusted for pacing and item rank, then apply a
    need-to-win floor and a soft pacing cap before clamping to value and budget.
    """

    def competition_level(
        self,
        opponents: OpponentBook,
        bucket: str,
        value: float,
        med: float,
        p75: float,
    ) -> float:
        """Estimate how contested the current item is.

        Blends market "temperature" (how high and heavy-tailed recent prices
        are) with the aggression of opponents still able to contest the item.

        Args:
            opponents: Opponent book, queried for contesting aggression.
            bucket: The item's value bucket.
            value: This agent's value for the item.
            med: Estimated median clearing price for the bucket.
            p75: Estimated 75th-percentile clearing price for the bucket.

        Returns:
            A competition level in ``[0, 1]``.
        """
        market_hot = clamp((med - 4.0) / 10.0, 0.0, 1.0)
        market_tail = clamp((p75 - med) / 6.0, 0.0, 1.0)
        opponent_pressure = opponents.contesting_aggression(value)

        # High-value items are more likely to be commonly contested.
        bucket_bias = 0.15 if bucket == "high" else (0.05 if bucket == "mid" else -0.05)

        comp = (
            0.45 * market_hot
            + 0.15 * market_tail
            + 0.40 * opponent_pressure
            + bucket_bias
        )
        return clamp(comp, 0.0, 1.0)

    def spend_boost(
        self,
        initial_budget: float,
        budget: float,
        rounds_completed: int,
        total_rounds: int,
    ) -> float:
        """Compute a multiplier that raises bids when spending lags the target.

        Args:
            initial_budget: Budget at the start of the game.
            budget: Current remaining budget.
            rounds_completed: Number of rounds already played.
            total_rounds: Total rounds in the game.

        Returns:
            A multiplier in ``[SPEND_BOOST_MIN, SPEND_BOOST_MAX]``.
        """
        progress = rounds_completed / total_rounds
        target_spend = clamp(
            BASE_SPEND_TARGET + PROGRESS_SPEND_TARGET * progress,
            BASE_SPEND_TARGET,
            MAX_SPEND_TARGET,
        )
        spent = (initial_budget - budget) / max(initial_budget, 1e-9)
        underspend = target_spend - spent
        return clamp(
            1.0 + SPEND_BOOST_GAIN * underspend, SPEND_BOOST_MIN, SPEND_BOOST_MAX
        )

    def pacing_cap(
        self,
        budget: float,
        value: float,
        rank: int,
        pct: float,
        rounds_remaining: int,
        rounds_completed: int,
        total_rounds: int,
    ) -> float:
        """Compute a soft per-round spending cap.

        Keeps early bids in proportion to budget-per-remaining-round (scaled up
        for high-value and top-ranked items) while loosening late in the game,
        and guarantees willingness to commit most of the budget in the final
        rounds so none is left unspent.

        Args:
            budget: Current remaining budget.
            value: This agent's value for the item.
            rank: The item's value rank (0 = most valuable).
            pct: The item's value percentile in ``[0, 1]``.
            rounds_remaining: Rounds left to play, including this one.
            rounds_completed: Number of rounds already played.
            total_rounds: Total rounds in the game.

        Returns:
            The maximum this agent is willing to bid this round.
        """
        budget_per_round = budget / max(1, rounds_remaining)
        progress = rounds_completed / total_rounds

        value_weight = VALUE_WEIGHT_BASE + VALUE_WEIGHT_SLOPE * pct  # ~0.95 .. 3.05
        if rank <= 2:
            value_weight *= 1.25
        elif rank <= 5:
            value_weight *= 1.10
        elif rank >= 12:
            value_weight *= 0.80

        cap_mult = CAP_MULT_BASE + CAP_MULT_SLOPE * (progress**2)  # rises late
        cap = budget_per_round * value_weight * cap_mult

        # Endgame spend-up: make sure remaining budget can actually be deployed.
        if rounds_remaining <= 5:
            cap = max(cap, 0.45 * budget)
        if rounds_remaining <= 3:
            cap = max(cap, 0.80 * budget)

        # Never cap so hard on a high-value item that winning becomes impossible.
        if value >= 10.0:
            cap = max(cap, min(value, 0.18 * budget))
        return cap

    def decide_bid(
        self,
        *,
        item_id: str,
        value: float,
        budget: float,
        initial_budget: float,
        rounds_completed: int,
        total_rounds: int,
        market: MarketModel,
        opponents: OpponentBook,
    ) -> float:
        """Decide the bid for the current item.

        Args:
            item_id: Item being auctioned.
            value: This agent's private value for the item.
            budget: Current remaining budget.
            initial_budget: Budget at the start of the game.
            rounds_completed: Number of rounds already played.
            total_rounds: Total rounds in the game.
            market: Market model with price statistics and value lookups.
            opponents: Opponent book for the competition estimate.

        Returns:
            A bid in ``[0, budget]``, rounded to two decimals and kept strictly
            below ``value`` to avoid negative-utility wins on ties.
        """
        if budget <= 0.0 or value <= 0.0:
            return 0.0
        rounds_remaining = total_rounds - rounds_completed
        if rounds_remaining <= 0:
            return 0.0

        bucket = market.bucket(value)
        med, p75 = market.bucket_stats(bucket)
        pct = market.value_percentile(value)
        rank = market.rank(item_id)
        progress = rounds_completed / total_rounds
        zero_rate = market.zero_price_rate(rounds_completed)

        comp = self.competition_level(opponents, bucket, value, med, p75)

        # Shade harder when competition is high (to preserve budget), bid closer
        # to value when it is low.
        if comp > COMP_HIGH_THRESHOLD:
            shade = SHADE_HIGH_COMP
        elif comp > COMP_MID_THRESHOLD:
            shade = SHADE_MID_COMP
        else:
            shade = SHADE_LOW_COMP

        shade += LATE_GAME_RELIEF * progress
        shade *= self.spend_boost(
            initial_budget, budget, rounds_completed, total_rounds
        )
        shade += PERCENTILE_PUSH * pct
        if zero_rate > QUIET_MARKET_RATE and bucket != "low":
            shade += QUIET_MARKET_PUSH
        shade = clamp(shade, SHADE_MIN, SHADE_MAX)

        bid = shade * value

        # Need-to-win floor: when our value clears the market median with real
        # surplus, bidding below the recent p75 often never wins against
        # truthful-ish opponents, so lift the bid to just above p75.
        if value - med >= SURPLUS_FLOOR and bucket != "low":
            bid = max(bid, min(value, p75 + 0.10))

        # Soft pacing cap, then hard constraints.
        cap = self.pacing_cap(
            budget, value, rank, pct, rounds_remaining, rounds_completed, total_rounds
        )
        bid = min(bid, cap, value, budget)

        # After rounding, keep the bid strictly below value to avoid tie risk.
        bid_r = round2(bid)
        value_r = round2(value)
        if bid_r >= value_r and value_r >= 0.01:
            bid_r = max(0.0, value_r - 0.01)

        if not math.isfinite(bid_r) or bid_r < 0.0:  # reject NaN / inf / negatives
            return 0.0
        return min(bid_r, round2(budget))
