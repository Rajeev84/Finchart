"""
FinChart TradingView Errors module (Layer 1.8).
Defines deterministic, actionable public exception classes for the FinChart API contract.
"""


class FinChartError(Exception):
    """Base class for all FinChart public API exceptions."""
    pass


class ChartRemovedError(FinChartError):
    """Raised when an operation is performed on a removed Chart instance."""
    def __init__(self, message: str = "Cannot execute operation on a removed Chart instance"):
        super().__init__(message)


class EntityNotFoundError(FinChartError):
    """Raised when a requested series, indicator, drawing, or pane ID cannot be found."""
    pass


class InvalidSymbolError(FinChartError):
    """Raised when an invalid symbol string is specified."""
    pass


class InvalidResolutionError(FinChartError):
    """Raised when an unsupported or malformed timeframe resolution is specified."""
    pass


class InvalidChartTypeError(FinChartError):
    """Raised when an unsupported chart type is specified."""
    pass


class InvalidSeriesTypeError(FinChartError):
    """Raised when an invalid or unregistered series type is requested."""
    pass


class InvalidIndicatorError(FinChartError):
    """Raised when an invalid or unregistered indicator name is requested."""
    pass


class InvalidDrawingError(FinChartError):
    """Raised when drawing shape creation parameters are invalid."""
    pass


class InvalidCoordinateError(FinChartError):
    """Raised when market coordinates or screen coordinates are malformed."""
    pass


class InvalidPaneError(FinChartError):
    """Raised when an invalid pane operation is attempted (e.g., deleting main pane)."""
    pass


class UnsupportedOperationError(FinChartError):
    """Raised when an operation is not supported in the current chart configuration."""
    pass

# Added Features:
# - Deterministic public error hierarchy (ChartRemovedError, EntityNotFoundError, InvalidSymbolError, etc.)
