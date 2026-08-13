"""
FinChart TradingView Constants module.
Contains design and interaction constants specified by FinChart architecture layers 1.0 - 1.7.
"""

# Horizontal scale constants
DEFAULT_BAR_SPACING = 6.0
MIN_BAR_SPACING = 0.5
MAX_BAR_SPACING = 100.0  # maximum sensible bar spacing to avoid runaway zoom
DEFAULT_RIGHT_OFFSET = 0.0

# Vertical price-scale constants
PRICE_TOP_MARGIN = 0.20
PRICE_BOTTOM_MARGIN = 0.10

# Input & Gesture constants
DEFAULT_DRAG_THRESHOLD_PX = 4.0
WHEEL_ZOOM_FACTOR = 0.10
WHEEL_PAN_FACTOR = 1.5

# Rendering & Scheduler constants
TARGET_FRAME_MS = 16

# Added Features:
# - Initialized baseline architectural constants for FinChart 1.0 - 1.7
