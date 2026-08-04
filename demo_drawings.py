"""Demo script for testing drawing tools implementation.

Tests the new TradingView-style shape management features:
- TrendLine with angle display and selection handles
- HorizontalLine with selection handles (single-click)
- VerticalLine with selection handles (single-click)
- AngleLine with 45-degree preset angle
- Rectangle with corner handles and fill
- Long/Short position tool with PnL tracking
- Selection and drag operations
- Copy/Paste support (Ctrl+C / Ctrl+V)
- ESC key and Right Click to cancel drawing
- Ghost shape preview during drawing
- Crosshair hidden during drawing
- Live price updates for position PnL
"""
import tkinter as tk
from finchart import ChartWidget, OHLCV
from finchart.drawing.base import DrawingState
from finchart.core.types import Color
import random


def generate_sample_data(n=100):
    """Generate sample OHLCV data for testing."""
    data = []
    price = 100.0
    for i in range(n):
        change = random.uniform(-2, 2)
        open_p = price
        close_p = price + change
        high_p = max(open_p, close_p) + random.uniform(0, 1)
        low_p = min(open_p, close_p) - random.uniform(0, 1)
        volume = random.uniform(1000, 10000)
        data.append(OHLCV(timestamp=i, open=open_p, high=high_p, low=low_p, close=close_p, volume=volume))
        price = close_p
    return data


def main():
    root = tk.Tk()
    root.title("FinChart - TradingView-Style Drawing Tools")
    root.geometry("1200x800")
    root.configure(bg="#1e1e1e")

    # Dark theme styling
    style = {
        "bg": "#2d2d2d",
        "fg": "#ffffff",
        "activebackground": "#3d3d3d",
        "activeforeground": "#ffffff",
        "relief": "flat",
        "bd": 0,
        "padx": 8,
        "pady": 4
    }

    # Top toolbar (TradingView-style)
    toolbar = tk.Frame(root, bg="#2d2d2d", height=40)
    toolbar.pack(fill="x", side="top")

    # Create chart widget
    chart = ChartWidget(root, width=1200, height=700)
    chart.pack(fill="both", expand=True, padx=5, pady=5)

    # Load sample data
    data = generate_sample_data(200)
    chart.set_data(data)
    chart.fit_content()

    # Tool buttons in toolbar
    def create_tool_button(parent, text, command, tooltip=""):
        btn = tk.Button(parent, text=text, command=command, **style)
        btn.pack(side="left", padx=2, pady=5)
        return btn

    def activate_trendline():
        chart.set_active_tool("trendline")

    def activate_hline():
        chart.set_active_tool("hline")

    def activate_vline():
        chart.set_active_tool("vline")

    def activate_angleline():
        chart.set_active_tool("angleline")

    def activate_rectangle():
        chart.set_active_tool("rectangle")

    def activate_longshort():
        chart.set_active_tool("longshort")

    def activate_long():
        chart.set_active_tool("longshort", "long")

    def activate_short():
        chart.set_active_tool("longshort", "short")

    def deactivate():
        chart.deactivate_tool()

    # Drawing tools section
    tk.Label(toolbar, text="Draw:", bg="#2d2d2d", fg="#888888").pack(side="left", padx=(10, 5))

    create_tool_button(toolbar, "📈 Trend", activate_trendline)
    create_tool_button(toolbar, "━ H-Line", activate_hline)
    create_tool_button(toolbar, "┃ V-Line", activate_vline)
    create_tool_button(toolbar, "∠ Angle", activate_angleline)
    create_tool_button(toolbar, "▢ Rect", activate_rectangle)
    create_tool_button(toolbar, "� Long", activate_long)
    create_tool_button(toolbar, "📉 Short", activate_short)
    create_tool_button(toolbar, "✕ Cancel", deactivate)

    tk.Frame(toolbar, width=2, bg="#444444").pack(side="left", padx=10, fill="y")

    # Quick actions section
    tk.Label(toolbar, text="Actions:", bg="#2d2d2d", fg="#888888").pack(side="left", padx=5)

    def clear_all():
        chart.clear_drawings()

    def add_sample_trendline():
        state = DrawingState(
            tool_type="trendline",
            points=[(50, 105.0), (100, 95.0)],
            color=Color(255, 165, 0),
            width=2.0,
            style="solid",
            label="Support"
        )
        chart.add_drawing(state)

    def add_sample_hline():
        state = DrawingState(
            tool_type="hline",
            points=[(None, 102.0)],
            color=Color(0, 255, 0),
            width=2.0,
            style="dashed",
            label="Resistance"
        )
        chart.add_drawing(state)

    def add_sample_long():
        state = DrawingState(
            tool_type="longshort",
            points=[(30, 100.0), (60, 95.0), (60, 110.0)],
            color=Color(255, 165, 0),
            width=2.0,
            style="solid",
            label="10.0|long"  # quantity and position type
        )
        chart.add_drawing(state)

    def add_sample_short():
        state = DrawingState(
            tool_type="longshort",
            points=[(100, 100.0), (130, 110.0), (130, 95.0)],
            color=Color(255, 165, 0),
            width=2.0,
            style="solid",
            label="5.0|short"  # quantity and position type
        )
        chart.add_drawing(state)

    create_tool_button(toolbar, "🧹 Clear", clear_all)
    create_tool_button(toolbar, "📏 Add Trend", add_sample_trendline)
    create_tool_button(toolbar, "➖ Add H-Line", add_sample_hline)
    create_tool_button(toolbar, "📈 Add Long", add_sample_long)
    create_tool_button(toolbar, "📉 Add Short", add_sample_short)

    # Status bar
    status_frame = tk.Frame(root, bg="#2d2d2d", height=25)
    status_frame.pack(fill="x", side="bottom")

    status_label = tk.Label(
        status_frame,
        text="Ready - Select a tool to start drawing | Long/Short: 3-click (entry → stop → target) | Ctrl+C/V: Copy/Paste",
        bg="#2d2d2d", fg="#888888", anchor="w"
    )
    status_label.pack(side="left", padx=10, pady=2)

    # Update status based on tool context
    def update_status():
        if chart._tool_context:
            tool = chart._tool_context.tool_type
            state = chart._tool_context.state
            if tool == "longshort":
                if state.name == "PREVIEW":
                    status = "Long/Short: Click to set stop-loss level"
                elif state.name == "PREVIEW_2":
                    status = "Long/Short: Click to set target/profit level"
                else:
                    status = "Long/Short: Click to set entry point"
            elif tool in ["hline", "vline"]:
                status = f"{tool.upper()}: Click to place line"
            else:
                status = f"{tool.upper()}: Click to set first point"
        else:
            status = "Ready - Select a tool to start drawing"
        status_label.config(text=status)

    # Periodically update status
    def check_status():
        update_status()
        root.after(100, check_status)

    check_status()

    # Instructions overlay (minimal)
    instructions = (
        "Drawing Tools: TrendLine (2-click), H-Line/V-Line (1-click), AngleLine (45° preset), Rectangle (2-click), "
        "Long/Short Position (3-click: entry → stop → target). "
        "Copy/Paste: Ctrl+C / Ctrl+V. "
        "Cancel: ESC or Right-Click. "
        "Crosshair: Dashed lines (TradingView-style)."
    )
    
    # Compact info panel
    info_frame = tk.Frame(root, bg="#1e1e1e")
    info_frame.pack(fill="x", padx=5, pady=2)
    
    info_label = tk.Label(
        info_frame, 
        text=instructions, 
        bg="#1e1e1e", fg="#666666", 
        font=("Segoe UI", 8),
        wraplength=1180, justify="left"
    )
    info_label.pack(padx=5)

    root.mainloop()


if __name__ == "__main__":
    main()
