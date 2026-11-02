"""
macOS Virtual Emergency Button for Driver Monitoring System.
Allows software-driven emergency activation via UI button or keyboard shortcut.
"""

from typing import Callable, List
from driver_monitor.hardware.interfaces import EmergencyButtonInterface


class MacEmergencyButton(EmergencyButtonInterface):
    """Software emergency button simulation for macOS."""

    def __init__(self):
        self._callbacks: List[Callable[[], None]] = []
        self._is_pressed: bool = False

    def register_callback(self, callback: Callable[[], None]) -> None:
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def press(self) -> None:
        """Triggered when software emergency button is clicked."""
        self._is_pressed = True
        for cb in self._callbacks:
            try:
                cb()
            except Exception:
                pass

    def release(self) -> None:
        self._is_pressed = False

    def is_pressed(self) -> bool:
        return self._is_pressed
