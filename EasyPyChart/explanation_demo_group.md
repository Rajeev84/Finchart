# Explanation: demo_group.py

## Purpose
This demo is designed to specifically test and demonstrate the **Grouped Shape Management** system in EasyPyChart. It focuses on tools that consist of multiple primitive shapes but act as a single logical unit.

## Key Features Tested

1.  **Multi-Phase Tool Construction**:
    - The `Long Pos` and `Short Pos` tools require 3 distinct user actions (Entry, Stop Loss/Width, and Target).
    - The demo logs how the `InteractionManager` transitions through these phases.

2.  **Prefix-Based Grouping (`PosUnit_{UID}`)**:
    - When a position tool is created, it generates multiple tags:
        - `PosUnit_{UID}_SL`: The Stop Loss rectangle.
        - `PosUnit_{UID}_TGT`: The Target rectangle.
        - `PosUnit_{UID}_Text_...`: Dynamic labels for RR stats.
    - The "List Tags" button in the demo allows you to inspect these generated tags.

3.  **Synchronized Group Interaction**:
    - **Selection**: Clicking any component of the group highlights all related shapes.
    - **Dragging**: Moving one rectangle automatically moves the other rectangle and all labels, preserving the spatial relationship (Risk/Reward levels).
    - **Deletion**: Pressing the `Delete` key on any component removes the entire group from the chart and the `LayoutManager`.

## Usage Instructions
1.  Run `python demo_group.py`.
2.  Click **Long Pos**.
3.  On the chart:
    - **Click 1**: Set the entry point.
    - **Click 2**: Set the stop loss price and the time-width of the boxes.
    - **Click 3**: Set the target price level.
4.  Switch to **Select/Pan** mode.
5.  Drag either the red or green box to see the group move together.
6.  Select a box and press **Delete** to see the group disappear.
7.  Use **List Tags** to see the underlying `PosUnit` naming convention.

---
**Created At**: 2026-04-23
**Module**: EasyPyChart.demo_group
