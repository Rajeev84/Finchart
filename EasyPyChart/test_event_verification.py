
import unittest
from unittest.mock import MagicMock, call
import sys
import os
import time

# Add workspace to path
# Add workspace to path
# If we are in 'easypychart' directory, we need to add the parent directory to path
if os.path.basename(os.getcwd()) == 'easypychart':
    sys.path.append(os.path.dirname(os.getcwd()))
else:
    sys.path.append(os.getcwd())

try:
    from easypychart.interaction_manager import InteractionManager
except ImportError:
    # If still failing, try explicit path
    parent = os.path.dirname(os.path.abspath(__file__))
    grandparent = os.path.dirname(parent)
    if grandparent not in sys.path:
        sys.path.append(grandparent)
    from easypychart.interaction_manager import InteractionManager

class MockChart:
    def __init__(self):
        self.callback = None
        self.selected_tags = set()
        self.active_color = '#FF0000'
        self.drawings = {}
        self.drag_start = None
        self.data = MagicMock()
        self.layout = MagicMock()
    
    def render(self):
        pass

    def delete_shape(self, tag):
        pass
        
    def create_line(self, *args, **kwargs): return "mock_shape"
    def create_rectangle(self, *args, **kwargs): return "mock_shape"
    def create_hline(self, *args, **kwargs): return "mock_shape"
    def create_vline(self, *args, **kwargs): return "mock_shape"
    def create_aline(self, *args, **kwargs): return "mock_shape"

class TestInteractionEvents(unittest.TestCase):
    def setUp(self):
        self.chart = MockChart()
        self.layout = MagicMock()
        self.chart.layout = self.layout
        
        # Mock the external callback (User App)
        self.user_callback = MagicMock()
        
        # Original logic: InteractionManager hijacks chart.callback
        # We simulate the user setting chart.callback first
        self.chart.callback = self.user_callback
        
        self.im = InteractionManager(self.chart, self.layout)
        
        # Populate some mock drawings
        self.chart.drawings = {
            'rect_1': {'type': 'rect', 'plot': 'candlestick', 'points': []},
            'PosUnit_100_SL': {'type': 'rect', 'plot': 'candlestick', 'points': []}
        }

    def test_shape_select_event(self):
        # Simulate Click on Shape
        event_data = {'button': 'left', 'shape': 'rect_1', 'time': '2023-01-01', 'y': 100}
        self.im.process_event('click', event_data)
        
        # Verify 'click' THEN 'shape-select'
        calls = self.user_callback.mock_calls
        
        # Debug print
        # print("Calls:", calls)

        click_idx = -1
        select_idx = -1
        
        for i, c in enumerate(calls):
            # c is formatted as (name, args, kwargs) or Call object
            args = c[1] if len(c) > 1 else ()
            if len(args) > 0:
                if args[0] == 'click':
                    if click_idx == -1: click_idx = i
                elif args[0] == 'shape-select':
                    if select_idx == -1: select_idx = i
        
        self.assertNotEqual(click_idx, -1, "Click event missing")
        self.assertNotEqual(select_idx, -1, "Shape-select event missing")
        
        self.assertLess(click_idx, select_idx, "Event Order Mismatch: Expected Click BEFORE Shape-Select")

    def test_shape_deselect_event(self):
        # 1. Select first
        self.im.selected_tag = 'rect_1'
        
        # 2. Click on empty space
        event_data = {'button': 'left', 'time': '2023-01-01', 'y': 100}
        self.im.process_event('click', event_data)
        
        # Verify 'shape-deselect'
        self.user_callback.assert_any_call('shape-deselect', {})
        
    def test_shape_delete_event(self):
        # 1. Select shape
        self.im.selected_tag = 'rect_1'
        
        # 2. Press Delete key
        event_data = {'key': 'Delete'}
        self.im.process_event('key', event_data)
        
        # Verify 'shape-delete' called with correct tag
        self.user_callback.assert_any_call('shape-delete', {'shape': 'rect_1'})

    def test_shape_drop_event(self):
        # 1. Start Drag
        self.im.dragging_shape = 'rect_1'
        self.im.drag_start_data = (100, 100)
        
        # 2. Release Mouse
        self.im.process_event('release', {})
        
        # Verify 'shape-drop'
        self.user_callback.assert_any_call('shape-drop', {'shape': 'rect_1'})

    def test_shape_create_event_line(self):
        # 1. Set Tool
        self.im.set_tool('line')
        
        # 2. Mock 'on_complete' triggering
        # We need to access get_click_cords internals or simulate clicks
        # self.im.capture_state['final'] calls the lambda we want to test
        
        final_cb = self.im.capture_state['final']
        mock_pts = [(0,0), (1,1)]
        
        # Execute Callback
        final_cb(mock_pts)
        
        # Verify 'shape-create'
        # We check if it was called. The tag is dynamic, so we check using simple match or partial
        # We expect a call like ('shape-create', {'shape': 'line_...', 'type': 'line'})
        
        calls = self.user_callback.call_args_list
        found = False
        for c in calls:
            if c[0][0] == 'shape-create' and c[0][1].get('type') == 'line':
                found = True
                break
        self.assertTrue(found, "shape-create event for line type not found")

if __name__ == '__main__':
    unittest.main()
