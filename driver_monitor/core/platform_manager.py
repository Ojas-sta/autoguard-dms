"""
Platform Manager for Driver Monitoring System.
Detects operating system, hardware architecture, and loads the active platform profile.
"""

import json
import logging
import os
import platform
import sys
from typing import Dict, Any, Optional

from driver_monitor.config import AppConfig

logger = logging.getLogger(__name__)


class PlatformManager:
    """Detects and manages platform-specific runtime configuration."""

    def __init__(self, requested_platform: Optional[str] = None):
        self._os_name = sys.platform
        self._machine = platform.machine().lower()
        self._detected_platform = self._detect_platform()
        self.active_platform = requested_platform.lower() if requested_platform else self._detected_platform
        self.config = self._load_configuration()
        logger.info(
            "PlatformManager initialized: OS=%s, Arch=%s, ActivePlatform=%s",
            self._os_name, self._machine, self.active_platform
        )

    def _detect_platform(self) -> str:
        """Automatically detects whether running on macOS or Raspberry Pi."""
        if self._os_name == "darwin":
            return "macos"

        if self._os_name.startswith("linux"):
            # Check for Raspberry Pi device tree
            try:
                if os.path.exists("/proc/device-tree/model"):
                    with open("/proc/device-tree/model", "r") as f:
                        model = f.read().lower()
                        if "raspberry pi" in model:
                            return "raspberrypi"
            except Exception:
                pass

            # Check for arm architecture with raspberrypi in release
            if "arm" in self._machine or "aarch64" in self._machine:
                try:
                    with open("/etc/os-release", "r") as f:
                        if "raspbian" in f.read().lower():
                            return "raspberrypi"
                except Exception:
                    pass

        # Default fallback
        return "macos" if self._os_name == "darwin" else "raspberrypi"

    def _load_configuration(self) -> AppConfig:
        """Loads configuration from the matching profile JSON file."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        profile_path = os.path.join(base_dir, "profiles", f"{self.active_platform}.json")

        if os.path.exists(profile_path):
            logger.info("Loading profile from %s", profile_path)
            return AppConfig.from_profile(profile_path)
        else:
            logger.warning("Profile %s not found. Using default config for %s", profile_path, self.active_platform)
            cfg = AppConfig()
            cfg.platform = self.active_platform
            return cfg

    @property
    def is_macos(self) -> bool:
        return self.active_platform == "macos"

    @property
    def is_raspberry_pi(self) -> bool:
        return self.active_platform == "raspberrypi"

    @property
    def is_apple_silicon(self) -> bool:
        return self.is_macos and ("arm" in self._machine or "aarch64" in self._machine)

    @property
    def is_simulation(self) -> bool:
        return self.config.hardware.simulation_mode or self.is_macos

    def get_info(self) -> Dict[str, Any]:
        """Returns diagnostic platform metadata for the UI and logs."""
        return {
            "os": self._os_name,
            "architecture": self._machine,
            "active_platform": self.active_platform,
            "is_macos": self.is_macos,
            "is_apple_silicon": self.is_apple_silicon,
            "simulation_mode": self.is_simulation,
            "camera_backend": self.config.camera.backend
        }
