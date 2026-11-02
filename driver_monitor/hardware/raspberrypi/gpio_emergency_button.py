"""
Raspberry Pi GPIO Emergency Button Implementation.
Monitors a physical momentary push button wired to a Raspberry Pi GPIO pin with pull-up.
Includes safe mock fallback when executed on non-Raspberry Pi environments.
"""

import logging
from typing import Callable, List

from driver_monitor.hardware.interfaces import EmergencyButtonInterface

logger = logging.getLogger(__name__)

try:
    import RPi.GPIO as GPIO
    HAS_RPI_GPIO = True
except (ImportError, RuntimeError):
    GPIO = None
    HAS_RPI_GPIO = False


class GPIOEmergencyButton(EmergencyButtonInterface):
    """Monitors physical emergency button via GPIO interrupt on Raspberry Pi."""

    def __init__(self, pin: int = 16):
        self._pin = pin
        self._callbacks: List[Callable[[], None]] = []

        if HAS_RPI_GPIO:
            try:
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(self._pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                GPIO.add_event_detect(
                    self._pin, GPIO.FALLING, callback=self._gpio_callback, bouncetime=300
                )
                logger.info("GPIOEmergencyButton initialized on pin %d (active LOW)", self._pin)
            except Exception as e:
                logger.error("Failed to setup GPIO emergency button pin %d: %s", self._pin, e)
        else:
            logger.info("RPi.GPIO not available. GPIOEmergencyButton running in mock mode.")

    def _gpio_callback(self, channel: int) -> None:
        logger.warning("Hardware emergency button pressed on pin %d!", channel)
        for cb in self._callbacks:
            try:
                cb()
            except Exception as e:
                logger.error("Error in emergency callback: %s", e)

    def register_callback(self, callback: Callable[[], None]) -> None:
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def is_pressed(self) -> bool:
        if HAS_RPI_GPIO:
            try:
                # Active LOW: pressed when LOW (0)
                return GPIO.input(self._pin) == GPIO.LOW
            except Exception:
                return False
        return False
