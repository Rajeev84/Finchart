"""
FinChart TradingView Options module (Layer 1.8).
Defines structured options contracts and theme settings with partial-update capability.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from .constants import (
    DEFAULT_BAR_SPACING, DEFAULT_RIGHT_OFFSET, PRICE_TOP_MARGIN, PRICE_BOTTOM_MARGIN
)


@dataclass
class DimensionsOptions:
    width: float = 800.0
    height: float = 600.0
    auto_size: bool = False


@dataclass
class ThemeOptions:
    background_color: str = "#FFFFFF"
    text_color: str = "#131722"
    grid_color: str = "#E0E3EB"
    bull_color: str = "#26A69A"
    bear_color: str = "#EF5350"


@dataclass
class TimeScaleOptions:
    bar_spacing: float = DEFAULT_BAR_SPACING
    right_offset: float = DEFAULT_RIGHT_OFFSET
    fix_left_edge: bool = False
    fix_right_edge: bool = False


@dataclass
class PriceScaleOptions:
    auto_scale: bool = True
    mode: str = "normal"  # normal, log, percentage, indexed
    top_margin: float = PRICE_TOP_MARGIN
    bottom_margin: float = PRICE_BOTTOM_MARGIN


@dataclass
class CrosshairOptions:
    mode: str = "magnet"  # magnet, normal, hidden, magnet_ohlc


@dataclass
class InteractionOptions:
    enable_zoom: bool = True
    enable_pan: bool = True
    enable_drag: bool = True


@dataclass
class KineticOptions:
    decay: float = 0.85
    steps: int = 12
    frame_ms: int = 16


@dataclass
class ChartOptions:
    dimensions: DimensionsOptions = field(default_factory=DimensionsOptions)
    theme: ThemeOptions = field(default_factory=ThemeOptions)
    time_scale: TimeScaleOptions = field(default_factory=TimeScaleOptions)
    price_scale: PriceScaleOptions = field(default_factory=PriceScaleOptions)
    crosshair: CrosshairOptions = field(default_factory=CrosshairOptions)
    interaction: InteractionOptions = field(default_factory=InteractionOptions)
    kinetic: KineticOptions = field(default_factory=KineticOptions)

    def apply_partial(self, opts: Dict[str, Any]) -> None:
        """Applies partial options dictionary without replacing unspecified option fields."""
        if "dimensions" in opts and isinstance(opts["dimensions"], dict):
            for k, v in opts["dimensions"].items():
                if hasattr(self.dimensions, k):
                    setattr(self.dimensions, k, v)

        if "theme" in opts and isinstance(opts["theme"], dict):
            for k, v in opts["theme"].items():
                if hasattr(self.theme, k):
                    setattr(self.theme, k, v)

        if "time_scale" in opts and isinstance(opts["time_scale"], dict):
            for k, v in opts["time_scale"].items():
                if hasattr(self.time_scale, k):
                    setattr(self.time_scale, k, v)

        if "price_scale" in opts and isinstance(opts["price_scale"], dict):
            for k, v in opts["price_scale"].items():
                if hasattr(self.price_scale, k):
                    setattr(self.price_scale, k, v)

        if "crosshair" in opts and isinstance(opts["crosshair"], dict):
            for k, v in opts["crosshair"].items():
                if hasattr(self.crosshair, k):
                    setattr(self.crosshair, k, v)

        if "interaction" in opts and isinstance(opts["interaction"], dict):
            for k, v in opts["interaction"].items():
                if hasattr(self.interaction, k):
                    setattr(self.interaction, k, v)

        if "kinetic" in opts and isinstance(opts["kinetic"], dict):
            for k, v in opts["kinetic"].items():
                if hasattr(self.kinetic, k):
                    setattr(self.kinetic, k, v)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimensions": {
                "width": self.dimensions.width,
                "height": self.dimensions.height,
                "auto_size": self.dimensions.auto_size
            },
            "theme": {
                "background_color": self.theme.background_color,
                "text_color": self.theme.text_color,
                "grid_color": self.theme.grid_color,
                "bull_color": self.theme.bull_color,
                "bear_color": self.theme.bear_color
            },
            "time_scale": {
                "bar_spacing": self.time_scale.bar_spacing,
                "right_offset": self.time_scale.right_offset,
                "fix_left_edge": self.time_scale.fix_left_edge,
                "fix_right_edge": self.time_scale.fix_right_edge
            },
            "price_scale": {
                "auto_scale": self.price_scale.auto_scale,
                "mode": self.price_scale.mode,
                "top_margin": self.price_scale.top_margin,
                "bottom_margin": self.price_scale.bottom_margin
            },
            "crosshair": {
                "mode": self.crosshair.mode
            },
            "interaction": {
                "enable_zoom": self.interaction.enable_zoom,
                "enable_pan": self.interaction.enable_pan,
                "enable_drag": self.interaction.enable_drag
            }
            ,
            "kinetic": {
                "decay": self.kinetic.decay,
                "steps": self.kinetic.steps,
                "frame_ms": self.kinetic.frame_ms
            }
        }

    def from_dict(self, opts: Dict[str, Any]) -> None:
        self.apply_partial(opts)

# Added Features:
# - Structured ChartOptions contracts with partial dictionary update merging.
# - Serialization support for options persistence.
