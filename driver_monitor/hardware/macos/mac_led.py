"""
macOS Virtual LED Simulator for Driver Monitoring System.
Maintains state of green, yellow, orange, and red alert LEDs and emits events to dashboard.
"""

import logging
from typing import Dict

from driver_monitor.core.event_manager import global_event_bus
from driver_monitor.hardware.interfaces import LEDInterface

logger = logging.getLogger(__name__)


class MacLED(LEDInterface):
    """Simulated dashboard LED cluster for macOS."""

    def __init__(self):
        self._states: Dict[str, bool] = {
            "green": True,
            "yellow": False,
            "orange": False,
            "red": False
        }

    def set_led(self, color: str, state: bool) -> None:
        color = color.lower()
        if color in self._states:
            self._states[color] = state
            global_event_bus.publish("led_update", dict(self._states))

    def get_led(self, color: str) -> bool:
        return self._states.get(color.lower(), False)

    def set_all(self, green: bool, yellow: bool, orange: bool, red: bool) -> None:
        self._states["green"] = green
        self._states["yellow"] = yellow
        self._states["orange"] = orange
        self._states["red"] = red
        global_event_bus.publish("led_update", dict(self._states))

    def all_off(self) -> None:
        for k in self._states:
            self._states[k] = False
        global_event_bus.publish("led_update", dict(self._states))
