"""
Hardware Factory for Driver Monitoring System.
Instantiates platform-appropriate hardware adapters based on active platform configuration.
"""

import logging
from typing import Tuple

from driver_monitor.config import HardwareConfig
from driver_monitor.hardware.interfaces import BuzzerInterface, LEDInterface, EmergencyButtonInterface
from driver_monitor.hardware.macos.mac_buzzer import MacBuzzer
from driver_monitor.hardware.macos.mac_led import MacLED
from driver_monitor.hardware.macos.mac_emergency_button import MacEmergencyButton
from driver_monitor.hardware.raspberrypi.gpio_buzzer import GPIOBuzzer
from driver_monitor.hardware.raspberrypi.gpio_led import GPIOLED
from driver_monitor.hardware.raspberrypi.gpio_emergency_button import GPIOEmergencyButton

logger = logging.getLogger(__name__)


class HardwareFactory:
    """Factory creating hardware abstraction components."""

    @staticmethod
    def create_hardware(
        platform_name: str,
        config: HardwareConfig
    ) -> Tuple[BuzzerInterface, LEDInterface, EmergencyButtonInterface]:
        """
        Creates and returns (buzzer, leds, emergency_button) based on platform:
        - If 'macos' or simulation_mode: returns MacBuzzer, MacLED, MacEmergencyButton.
        - If 'raspberrypi' and not simulation_mode: returns GPIOBuzzer, GPIOLED, GPIOEmergencyButton.
        """
        is_simulation = config.simulation_mode or (platform_name == "macos")

        if is_simulation:
            logger.info("Initializing macOS / Simulation hardware layer...")
            buzzer = MacBuzzer(volume=config.buzzer_volume)
            leds = MacLED()
            emergency_button = MacEmergencyButton()
            return buzzer, leds, emergency_button
        else:
            logger.info("Initializing Raspberry Pi physical GPIO hardware layer...")
            buzzer = GPIOBuzzer(pin=config.gpio_buzzer_pin)
            leds = GPIOLED(
                green_pin=config.gpio_led_green_pin,
                yellow_pin=config.gpio_led_yellow_pin,
                orange_pin=config.gpio_led_orange_pin,
                red_pin=config.gpio_led_red_pin
            )
            emergency_button = GPIOEmergencyButton(pin=config.gpio_emergency_button_pin)
            return buzzer, leds, emergency_button
