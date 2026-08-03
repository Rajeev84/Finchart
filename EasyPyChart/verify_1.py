"""
Verification 1: Lifecycle Signals
=================================
Validates that InteractionManager correctly emits tool-start, point-capture, 
and shape-create events.
"""

from unittest.mock import MagicMock
from interaction_manager import InteractionManager
import time

def test_lifecycle():
    # 1. Mock setup
    mock_chart = MagicMock()
    mock_chart._original_callback = None
    mock_layout = MagicMock()
    
    im = InteractionManager(mock_chart, mock_layout)
    
    events_received = []
    def callback(event, data):
        events_received.append((event, data))
    
    im._original_callback = callback
    
    print("Test: Starting Line Tool (2 points)")
    im.set_tool('line')
    
    # Check tool-start
    assert any(e[0] == 'tool-start' for e in events_received), "tool-start signal missing"
    assert events_received[-1][1]['target'] == 2
    
    print("Test: Simulating Point 1")
    # Simulate a click event
    im.process_event('click', {'button': 'left', 'time': pd_now(), 'y': 100})
    
    # Check point-capture
    assert any(e[0] == 'point-capture' for e in events_received), "point-capture signal missing"
    assert events_received[-1][1]['captured'] == 1
    
    print("Test: Simulating Point 2 (Complete)")
    im.process_event('click', {'button': 'left', 'time': pd_now(), 'y': 110})
    
    # Check point-capture (2nd) and shape-create
    assert any(e[1].get('captured') == 2 for e in events_received if e[0] == 'point-capture')
    assert any(e[0] == 'shape-create' for e in events_received), "shape-create signal missing"
    
    print("Test: Simulating Cancellation")
    im.set_tool('rect')
    im.process_event('key', {'key': 'Escape'})
    assert any(e[0] == 'capture-stop' for e in events_received), "capture-stop signal missing"
    
    print("\n--- ALL SIGNALS VERIFIED ---")

def pd_now():
    import pandas as pd
    return pd.Timestamp.now()

if __name__ == "__main__":
    try:
        test_lifecycle()
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()
