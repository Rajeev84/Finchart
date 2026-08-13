"""
FinChart Command History manager for Undo/Redo operations (Layer 1.11).
"""

from typing import List
from .commands import Command


class CommandHistory:
    """Manages undo and redo stacks with configurable max capacity."""

    def __init__(self, capacity: int = 100):
        self.capacity = capacity
        self.undo_stack: List[Command] = []
        self.redo_stack: List[Command] = []

    def push_and_execute(self, command: Command) -> None:
        """Executes a command and pushes it to the undo stack, clearing the redo stack."""
        command.execute()
        self.undo_stack.append(command)
        # Clear redo stack on new operation
        self.redo_stack.clear()

        # Enforce capacity limit
        if len(self.undo_stack) > self.capacity:
            self.undo_stack.pop(0)

    def undo(self) -> bool:
        """Undoes the most recent command."""
        if not self.can_undo():
            return False
        cmd = self.undo_stack.pop()
        cmd.undo()
        self.redo_stack.append(cmd)
        return True

    def redo(self) -> bool:
        """Redoes the most recently undone command."""
        if not self.can_redo():
            return False
        # Replay redos in the original undo order (FIFO) so sequences of
        # undo/redo across multiple commands restore expected states.
        cmd = self.redo_stack.pop(0)
        cmd.execute()
        self.undo_stack.append(cmd)
        return True

    def can_undo(self) -> bool:
        return len(self.undo_stack) > 0

    def can_redo(self) -> bool:
        return len(self.redo_stack) > 0

    def clear(self) -> None:
        self.undo_stack.clear()
        self.redo_stack.clear()
