"""Theme Engine - Color palettes and theme configurations.

Provides DarkTheme and LightTheme presets for FinChart.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from ..core.types import Color


@dataclass
class Theme:
    """Complete theme color palette definition."""
    name: str = "Dark"
    background: Color = field(default_factory=lambda: Color(19, 23, 34))      # #131722
    grid_lines: Color = field(default_factory=lambda: Color(42, 46, 57))      # #2A2E39
    bullish: Color = field(default_factory=lambda: Color(8, 153, 129))        # #089981
    bearish: Color = field(default_factory=lambda: Color(242, 54, 69))        # #F23645
    wick: Color = field(default_factory=lambda: Color(120, 123, 134))          # #787B86
    crosshair: Color = field(default_factory=lambda: Color(149, 152, 161))    # #9598A1
    axis_text: Color = field(default_factory=lambda: Color(178, 181, 190))    # #B2B5BE
    axis_bg: Color = field(default_factory=lambda: Color(19, 23, 34))         # #131722
    card_bg: Color = field(default_factory=lambda: Color(54, 58, 69))         # #363A45


def DarkTheme() -> Theme:
    """Standard TradingView Dark Theme preset."""
    return Theme(name="Dark")


def LightTheme() -> Theme:
    """Standard TradingView Light Theme preset."""
    return Theme(
        name="Light",
        background=Color(255, 255, 255),
        grid_lines=Color(240, 243, 250),
        bullish=Color(8, 153, 129),
        bearish=Color(242, 54, 69),
        wick=Color(120, 123, 134),
        crosshair=Color(149, 152, 161),
        axis_text=Color(80, 80, 80),
        axis_bg=Color(248, 249, 253),
        card_bg=Color(220, 224, 235)
    )
