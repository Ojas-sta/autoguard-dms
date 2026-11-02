"""
Hardware Abstraction Interfaces for Driver Monitoring System.
Enforces decoupling between detection logic and platform physical actuators.
"""

from abc import ABC, abstractmethod
from typing import Callable, Optional


class BuzzerInterface(ABC):
    """Abstract interface for audio alert actuators."""

    @abstractmethod
    def start_alert(self, pattern: str) -> None:
        """Starts buzzer cadence pattern ('CHIME', 'DOUBLE_PULSE', 'RAPID_SIREN')."""
        pass

    @abstractmethod
    def stop_alert(self) -> None:
        """Silences the buzzer."""
        pass

    @abstractmethod
    def is_active(self) -> bool:
        """Checks if the buzzer is actively sounding."""
        pass

    @abstractmethod
    def set_enabled(self, enabled: bool) -> None:
        """Enables or mutes the buzzer."""
        pass


class LEDInterface(ABC):
    """Abstract interface for system status LED indicators."""

    @abstractmethod
    def set_led(self, color: str, state: bool) -> None:
        """Sets state (True=ON, False=OFF) for 'green', 'yellow', 'orange', or 'red'."""
        pass

    @abstractmethod
    def get_led(self, color: str) -> bool:
        """Returns current state of specified LED."""
        pass

    @abstractmethod
    def set_all(self, green: bool, yellow: bool, orange: bool, red: bool) -> None:
        """Sets all LED states simultaneously."""
        pass

    @abstractmethod
    def all_off(self) -> None:
        """Turns off all LEDs."""
        pass


class EmergencyButtonInterface(ABC):
    """Abstract interface for driver emergency assistance button."""

    @abstractmethod
    def register_callback(self, callback: Callable[[], None]) -> None:
        """Registers a function to be invoked when the emergency button is triggered."""
        pass

    @abstractmethod
    def is_pressed(self) -> bool:
        """Returns whether the emergency button is currently held/active."""
        pass
