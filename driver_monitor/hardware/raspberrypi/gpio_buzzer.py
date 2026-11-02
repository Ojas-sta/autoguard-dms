"""
Raspberry Pi GPIO Buzzer Implementation.
Controls a physical active/passive piezo buzzer connected to a Raspberry Pi GPIO pin.
Includes safe mock fallback when executed on non-Raspberry Pi environments.
"""

import logging
import threading
import time
from typing import Optional

from driver_monitor.hardware.interfaces import BuzzerInterface

logger = logging.getLogger(__name__)

# Safe optional import of RPi.GPIO
try:
    import RPi.GPIO as GPIO
    HAS_RPI_GPIO = True
except (ImportError, RuntimeError):
    GPIO = None
    HAS_RPI_GPIO = False


class GPIOBuzzer(BuzzerInterface):
    """Controls physical GPIO buzzer on Raspberry Pi."""

    def __init__(self, pin: int = 18):
        self._pin = pin
        self._enabled = True
        self._is_active = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        if HAS_RPI_GPIO:
            try:
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(self._pin, GPIO.OUT, initial=GPIO.LOW)
                logger.info("GPIOBuzzer initialized on BCM pin %d", self._pin)
            except Exception as e:
                logger.error("Failed to setup GPIO pin %d for buzzer: %s", self._pin, e)
        else:
            logger.info("RPi.GPIO not available. GPIOBuzzer running in mock mode.")

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        if not enabled:
            self.stop_alert()

    def is_active(self) -> bool:
        return self._is_active

    def start_alert(self, pattern: str) -> None:
        if not self._enabled or pattern == "OFF":
            self.stop_alert()
            return

        self.stop_alert()
        self._is_active = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_pattern,
            args=(pattern,),
            daemon=True,
            name=f"GPIOBuzzer-{pattern}"
        )
        self._thread.start()

    def stop_alert(self) -> None:
        self._stop_event.set()
        self._is_active = False
        if HAS_RPI_GPIO:
            try:
                GPIO.output(self._pin, GPIO.LOW)
            except Exception:
                pass

    def _run_pattern(self, pattern: str) -> None:
        if not HAS_RPI_GPIO:
            # Mock timing
            time.sleep(0.5)
            self._is_active = False
            return

        try:
            if pattern == "CHIME":
                GPIO.output(self._pin, GPIO.HIGH)
                time.sleep(0.15)
                GPIO.output(self._pin, GPIO.LOW)

            elif pattern == "DOUBLE_PULSE":
                while not self._stop_event.is_set():
                    GPIO.output(self._pin, GPIO.HIGH)
                    time.sleep(0.15)
                    GPIO.output(self._pin, GPIO.LOW)
                    time.sleep(0.08)
                    GPIO.output(self._pin, GPIO.HIGH)
                    time.sleep(0.2)
                    GPIO.output(self._pin, GPIO.LOW)
                    if self._stop_event.wait(timeout=1.2):
                        break

            elif pattern in ("RAPID_SIREN", "EMERGENCY"):
                while not self._stop_event.is_set():
                    GPIO.output(self._pin, GPIO.HIGH)
                    time.sleep(0.1)
                    GPIO.output(self._pin, GPIO.LOW)
                    time.sleep(0.1)
        except Exception as e:
            logger.error("Error toggling GPIO buzzer: %s", e)
        finally:
            if HAS_RPI_GPIO:
                try:
                    GPIO.output(self._pin, GPIO.LOW)
                except Exception:
                    pass
            self._is_active = False
