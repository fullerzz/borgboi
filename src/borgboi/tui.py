"""Backward compatibility module for old tui.py location.

This module provides backward compatibility for any code that might still
import from the old tui.py location.
"""

# Re-export from new location
from borgboi.tui import BorgBoiApp, run_tui

__all__ = ["BorgBoiApp", "run_tui"]
