"""
Raspberry Pi GPIO LED Cluster Implementation.
Controls physical status LEDs (Green, Yellow, Orange, Red) connected to Raspberry Pi GPIO.
Includes safe mock fallback when executed on non-Raspberry Pi environments.
"""

import logging
from typing import Dict

from driver_monitor.hardware.interfaces import LEDInterface

logger = logging.getLogger(__name__)

try:
    import RPi.GPIO as GPIO
    HAS_RPI_GPIO = True
except (ImportError, RuntimeError):
    GPIO = None
    HAS_RPI_GPIO = False


class GPIOLED(LEDInterface):
    """Controls physical GPIO alert LEDs on Raspberry Pi."""

    def __init__(
        self,
        green_pin: int = 23,
        yellow_pin: int = 24,
        orange_pin: int = 25,
        red_pin: int = 12
    ):
        self._pins = {
            "green": green_pin,
            "yellow": yellow_pin,
            "orange": orange_pin,
            "red": red_pin
        }
        self._states: Dict[str, bool] = {k: False for k in self._pins}

        if HAS_RPI_GPIO:
            try:
                GPIO.setmode(GPIO.BCM)
                for pin in self._pins.values():
                    GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
                logger.info("GPIOLED initialized on pins: %s", self._pins)
            except Exception as e:
                logger.error("Failed to setup GPIO pins for LEDs: %s", e)
        else:
            logger.info("RPi.GPIO not available. GPIOLED running in mock mode.")

    def set_led(self, color: str, state: bool) -> None:
        color = color.lower()
        if color in self._pins:
            self._states[color] = state
            if HAS_RPI_GPIO:
                try:
                    GPIO.output(self._pins[color], GPIO.HIGH if state else GPIO.LOW)
                except Exception as e:
                    logger.error("Failed to set GPIO pin for %s: %s", color, e)

    def get_led(self, color: str) -> bool:
        return self._states.get(color.lower(), False)

    def set_all(self, green: bool, yellow: bool, orange: bool, red: bool) -> None:
        self.set_led("green", green)
        self.set_led("yellow", yellow)
        self.set_led("orange", orange)
        self.set_led("red", red)

    def all_off(self) -> None:
        self.set_all(False, False, False, False)
