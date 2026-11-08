"""Market model: clearing-price statistics and value bookkeeping."""

from __future__ import annotations

from collections import defaultdict
from typing import DefaultDict, Dict, List, Tuple

from agent.mathutils import safe_quantile

# Value thresholds that define the price buckets.
HIGH_THRESHOLD = 13.0
MID_THRESHOLD = 9.0

# How much data a bucket (or the global history) needs before it is trusted.
MIN_BUCKET_SAMPLES = 4
MIN_GLOBAL_SAMPLES = 6

# Conservative priors used before enough prices have been observed.
GLOBAL_MEDIAN_PRIOR = 6.5
BUCKET_PRIORS: Dict[str, Tuple[float, float]] = {
    "high": (9.0, 12.0),
    "mid": (6.5, 9.0),
    "low": (3.5, 6.0),
}


class MarketModel:
    """Observed clearing prices plus value-derived lookups for one game.

    Prices are bucketed by value tier so the agent can estimate what an item
    *like the current one* will cost, rather than relying on a single global
    average. Value rank and percentile are precomputed once since valuations are
    fixed for the game.

    Attributes:
        price_history: All non-zero clearing prices observed so far.
        zero_price_rounds: Count of rounds that cleared at a price of zero.
        bucket_prices: Clearing prices grouped by the agent's own value bucket.
        rank_by_item: Item id to value rank (0 = most valuable).
        values_sorted: The agent's valuations sorted ascending.
    """

    def __init__(self, valuation_vector: Dict[str, float]) -> None:
        """Initialize empty price history and precompute value lookups.

        Args:
            valuation_vector: Mapping of item id to this agent's private value.
        """
        self.price_history: List[float] = []
        self.zero_price_rounds = 0
        self.bucket_prices: DefaultDict[str, List[float]] = defaultdict(list)

        ranked = sorted(
            valuation_vector.items(), key=lambda kv: (-float(kv[1]), str(kv[0]))
        )
        self.rank_by_item: Dict[str, int] = {
            item_id: rank for rank, (item_id, _) in enumerate(ranked)
        }
        self.values_sorted: List[float] = sorted(
            float(v) for v in valuation_vector.values()
        )

    def observe(self, price: float, my_value: float) -> None:
        """Record a round's clearing price.

        Args:
            price: Price paid by the winner (0 means nobody paid anything).
            my_value: This agent's value for the item that was auctioned, used
                to attribute the price to a value bucket.
        """
        if price > 0:
            self.price_history.append(price)
            self.bucket_prices[self.bucket(my_value)].append(price)
        else:
            self.zero_price_rounds += 1

    def bucket(self, value: float) -> str:
        """Classify a private value into a coarse price bucket.

        Args:
            value: A private item value.

        Returns:
            One of ``"high"``, ``"mid"`` or ``"low"``.
        """
        if value >= HIGH_THRESHOLD:
            return "high"
        if value >= MID_THRESHOLD:
            return "mid"
        return "low"

    def value_percentile(self, value: float) -> float:
        """Compute where a value sits within this agent's own valuations.

        Args:
            value: A private item value.

        Returns:
            Fraction of the agent's values that are ``<= value``, in ``[0, 1]``.
        """
        ys = self.values_sorted
        if not ys:
            return 0.0
        lo, hi = 0, len(ys)
        while lo < hi:
            mid = (lo + hi) // 2
            if ys[mid] <= value:
                lo = mid + 1
            else:
                hi = mid
        return lo / len(ys)

    def rank(self, item_id: str) -> int:
        """Look up an item's value rank.

        Args:
            item_id: Item identifier.

        Returns:
            Rank among the agent's values (0 = most valuable); a large sentinel
            for unknown items.
        """
        return int(self.rank_by_item.get(item_id, 999))

    def global_median_prior(self) -> float:
        """Estimate the market median clearing price.

        Returns:
            The observed median once enough prices are available, otherwise a
            conservative prior.
        """
        if len(self.price_history) >= MIN_GLOBAL_SAMPLES:
            median = safe_quantile(
                self.price_history, 0.50, default=GLOBAL_MEDIAN_PRIOR
            )
            return max(0.5, median)
        return GLOBAL_MEDIAN_PRIOR

    def bucket_stats(self, bucket: str) -> Tuple[float, float]:
        """Estimate typical clearing prices for a value bucket.

        Prefers bucket-specific data, falls back to the global price history,
        and finally to hand-tuned priors when little has been observed.

        Args:
            bucket: One of ``"high"``, ``"mid"`` or ``"low"``.

        Returns:
            A ``(median, p75)`` pair of clearing prices.
        """
        xs = self.bucket_prices.get(bucket, [])
        if len(xs) >= MIN_BUCKET_SAMPLES:
            return self._median_p75(xs)
        if len(self.price_history) >= MIN_GLOBAL_SAMPLES:
            return self._median_p75(self.price_history)
        return BUCKET_PRIORS[bucket]

    @staticmethod
    def _median_p75(xs: List[float]) -> Tuple[float, float]:
        """Return the ``(median, p75)`` of a non-empty price sample."""
        med = safe_quantile(xs, 0.50, default=0.0)
        p75 = safe_quantile(xs, 0.75, default=med)
        return max(0.5, med), max(med, p75)

    def zero_price_rate(self, rounds_completed: int) -> float:
        """Compute the share of rounds that cleared at zero.

        Args:
            rounds_completed: Number of rounds observed so far.

        Returns:
            Fraction of completed rounds with a zero clearing price.
        """
        return self.zero_price_rounds / max(1, rounds_completed)
