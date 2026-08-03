  
           
           
 Now I have all the freshly downloaded files. Let me do a deep analysis of what changed and what broke.

---

# 🔴 FinChart Subplot Regression Analysis
## MACD Not Showing + RSI Behaving Unexpectedly

---

## Root Cause: Architectural Schism in Subplot Coordinate Systems

The recent update added **per-pane grid rendering** (`grid.py`) and **per-pane price scaling** (`widget.py`), but **RSI and MACD indicators were never updated to use the PriceScale system**. This creates **two competing coordinate systems** inside every subplot pane:

| System | Used By | Coordinate Method |
|--------|---------|-------------------|
| **PriceScale-based** | Grid lines, Price axis, Volume indicator, Crosshair badges | `price_to_y(val, vp, pane="...")` |
| **Manual pixel math** | RSI indicator, MACD indicator | `vp.bottom - ratio * vp.height` |

**Result: Grid lines and indicator lines are drawn on completely different scales within the same pane.**

---

## 🔴 Critical Bug #1: RSI Grid vs. RSI Line Are Misaligned

### What the recent update did:
In `widget.py` `add_indicator()`:
```python
if indicator.__class__.__name__ == "RSI":
    ps = self._coord_engine.get_pane_price_scale(active_pane)
    ps.fixed_range = True
    self._coord_engine.set_pane_price_scale(active_pane, 0.0, 100.0)
```

`set_pane_price_scale()` adds 8% padding top and bottom:
```python
top_pad = rng * ps.top_padding    # 100 * 0.08 = 8
bot_pad = rng * ps.bottom_padding # 100 * 0.08 = 8
new_min = 0.0 - 8.0 = -8.0
new_max = 100.0 + 8.0 = 108.0
```

**So the RSI PriceScale becomes (-8, 108), not (0, 100).**

### What RSI's render_commands() does:
```python
# indicators/standard.py — RSI
ratio = (val - 0.0) / 100.0
y = vp.bottom - ratio * vp.height
```

**RSI=0 → y = vp.bottom (very bottom edge)**
**RSI=100 → y = vp.top (very top edge)**

### What the grid does:
```python
# grid.py — _render_pane_horizontal_grid()
y = self._coord.price_to_y(curr_price, chart_vp, pane=pane_name)
```

**Price=0 → y ≈ 6.9% from bottom** (because of -8 to 108 range)
**Price=100 → y ≈ 93.1% from top**

### Visual Result:
- Grid line for "0" appears slightly above the bottom of the pane
- RSI line at value 0 appears at the very bottom edge
- Grid line for "100" appears slightly below the top
- RSI line at value 100 appears at the very top edge
- **They don't align.** The RSI line overshoots the grid boundaries by ~7% on each side.

---

## 🔴 Critical Bug #2: MACD Uses Completely Independent Y Scale

### What `_update_price_scale()` does for MACD:
```python
# widget.py — computes range across ALL three MACD series
for key, vals in ind._last_result.values.items():  # "macd", "signal", "histogram"
    for i in range(start_idx, min(end_idx, len(vals))):
        v = vals[i]
        if v is not None:
            p_min = min(p_min, v)
            p_max = max(p_max, v)
self._coord_engine.set_pane_price_scale("macd", p_min, p_max)
```

Grid lines are drawn based on this PriceScale.

### What MACD's render_commands() does:
```python
# indicators/standard.py — MACD
zero_y = vp.center_y  # ← Always geometric center of pane!
max_abs = 0.0
for i in range(start_idx, min(end_idx, len(self._macd_line))):
    v = self._macd_line[i]
    if v is not None:
        max_abs = max(max_abs, abs(v))
if max_abs < 1e-9:
    return []  # ← EARLY EXIT if no visible data

half_h = vp.height * 0.45
def val_to_y(val):
    return zero_y - (val / max_abs) * half_h
```

**MACD's zero line = geometric center of pane (`vp.center_y`)**
**MACD's scale = based on `max_abs` of MACD line ONLY in visible range**

### The PriceScale zero vs. MACD zero are unrelated:
- PriceScale zero: depends on `p_min` and `p_max` (could be anywhere)
- MACD zero: always at `vp.center_y` (geometric center)

### The PriceScale range vs. MACD range are unrelated:
- PriceScale: based on ALL three series (macd + signal + histogram)
- MACD: based on MACD line ONLY

### Visual Result:
- Grid shows one scale (based on combined data range)
- MACD lines use a completely different scale (based on MACD line only, centered)
- **They don't align at all.** MACD could appear stretched, compressed, or offset relative to the grid.
- If `max_abs < 1e-9` in the visible window (e.g., zoomed to a flat region), MACD returns `[]` — **nothing renders**.

---

## 🔴 Critical Bug #3: Crosshair Badges Show Wrong Values for Subplots

The recent update changed `_update_crosshair_badges()` to show badges for ALL panes:
```python
for pane_name in self._layout_engine.panes:
    ...
    if pane_name == "candlestick":
        price_val = self._coord_engine.y_to_price(mouse_y, chart_vp, pane="candlestick")
    else:
        indicator_val = self._coord_engine.y_to_price(mouse_y, pane_vp, pane=pane_name)
        badges.append(PaneBadge(badge_y=mouse_y, ...))
```

**Problem:** `mouse_y` is the global mouse Y position. For panes that the mouse is NOT over, `y_to_price()` computes a value from a Y coordinate outside the pane's viewport, using that pane's PriceScale. This produces **nonsensical values** for all non-active panes.

Example: Mouse is at Y=200 (main chart area). MACD pane is at Y=400-500. The MACD badge computes `y_to_price(200, pane="macd")` → a value far outside the MACD range. The badge then gets clamped to the MACD pane's top edge but displays a garbage number.

---

## 🔴 Critical Bug #4: Drawing Tools Still Ignore Pane Price Scales

**Not fixed in the recent update.** All drawing tools (`TrendLine`, `HorizontalLine`, `Rectangle`, `LongShort`) call:
```python
y = coord_engine.price_to_y(float(price), vp)  # pane defaults to "candlestick"
```

If a user draws a horizontal line at RSI=70 in the RSI pane, it gets Y-transformed using the **candlestick price scale** (e.g., stock price $70), not the RSI 0-100 scale. The line renders at the wrong location or outside the RSI pane entirely.

---

## Summary: Why MACD "Isn't Showing"

| Scenario | Explanation |
|----------|-------------|
| **MACD renders but looks wrong** | Grid and MACD are on different scales. MACD might appear as a tiny squiggle while grid shows widely spaced lines. |
| **MACD literally absent** | If visible range has `max_abs < 1e-9` (all None values before EMA warmup, or zoomed to flat region), `render_commands()` returns `[]`. |
| **RSI looks "unexpected"** | RSI line extends 7% beyond grid boundaries because manual mapping uses 0-100 exactly while PriceScale has -8 to 108 padding. |

---

## Fix Priority

### P0 — Fix Subplot Coordinate Alignment (Causes the visual breakage)

| File | Change |
|------|--------|
| `indicators/standard.py` | **RSI**: Replace manual `y = vp.bottom - ratio * vp.height` with `coord_engine.price_to_y(val, vp, pane="rsi")` |
| `indicators/standard.py` | **MACD**: Replace manual `val_to_y()` with `coord_engine.price_to_y(val, vp, pane="macd")`. Remove `max_abs` computation. |
| `widget.py` | **MACD price scale**: Make symmetric around zero so zero line stays centered: `max_val = max(abs(p_min), abs(p_max)); p_min = -max_val; p_max = max_val` |
| `coordinates/engine.py` | **Fixed range padding**: Skip padding when `fixed_range=True`, OR add `no_padding` flag |

### P1 — Fix Crosshair Badge Accuracy

| File | Change |
|------|--------|
| `widget.py` | In `_update_crosshair_badges()`, for subplots: use `badge_y = clamp(mouse_y, pane_top, pane_bottom)` and compute value from clamped Y, not raw `mouse_y` |

### P2 — Fix Drawing Tools in Subplots (Still broken from before)

| File | Change |
|------|--------|
| `drawing/tools.py` | Pass `pane=self.state.pane_name` to all `price_to_y()` and `y_to_price()` calls |

---

## Bottom Line

The **subplot architecture itself is structurally sound** (shared x-axis, per-pane y-scales, pane viewports, crosshair badges). The **recent update correctly added per-pane grid rendering**. 

But the **RSI and MACD indicators were never migrated to use the PriceScale system**. They still use hardcoded manual pixel math from before subplots existed. This creates a **schism where grid and indicators speak different coordinate languages** within the same pane.

**Fix: Make RSI and MACD use `price_to_y(val, vp, pane=self.pane)` just like Volume already does.**