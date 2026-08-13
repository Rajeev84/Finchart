"""
FinChart TradingView PriceScale module (Layer 1.1 Foundation).
Authoritative coordinate transformation engine for Y-axis (Price <-> Screen Pixel Y).
"""

from typing import Tuple
from typing import List
from .types import OHLCVBar


class PriceScale:
    """Authoritative transform between logical price values and screen Y coordinates for a pane."""
    def __init__(self, pane_height: float = 400.0, price_min: float = 0.0, price_max: float = 100.0):
        self.pane_height = pane_height
        self.price_min = price_min
        self.price_max = price_max

    def price_to_y(self, price: float) -> float:
        """Transforms price to screen Y (0 at top of pane)."""
        price_range = self.price_max - self.price_min
        if price_range <= 0:
            return self.pane_height / 2.0
        normalized = (price - self.price_min) / price_range
        # Screen Y goes downwards, high price at top (Y=0)
        return self.pane_height * (1.0 - normalized)

    def y_to_price(self, y: float) -> float:
        """Transforms screen Y to logical price."""
        if self.pane_height <= 0:
            return self.price_min
        normalized = 1.0 - (y / self.pane_height)
        price_range = self.price_max - self.price_min
        return self.price_min + (normalized * price_range)

    def set_range(self, price_min: float, price_max: float) -> None:
        if price_max > price_min:
            self.price_min = price_min
            self.price_max = price_max

    def set_range_from_bars(self, bars: List[OHLCVBar], padding_factor: float = 0.05) -> None:
        """Set the price_min/price_max from a list of bars with optional padding.

        `padding_factor` adds fractional padding of the computed range (5% by default).
        """
        if not bars:
            return
        lows = [b.low for b in bars]
        highs = [b.high for b in bars]
        pmin = min(lows)
        pmax = max(highs)
        if pmax <= pmin:
            # zero-range, expand slightly
            delta = abs(pmin) * 0.01 if pmin != 0 else 1.0
            pmin -= delta
            pmax += delta
        else:
            pad = (pmax - pmin) * padding_factor
            pmin -= pad
            pmax += pad

        self.set_range(pmin, pmax)

    def normalize_price(self, price: float) -> float:
        """Return normalized price in [0,1] relative to current range."""
        pr = self.price_max - self.price_min
        if pr <= 0:
            return 0.5
        return (price - self.price_min) / pr

# Added Features:
# - Authoritative PriceScale transformation functions price_to_y and y_to_price.
