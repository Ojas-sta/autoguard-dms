"""
Camera Interface for Driver Monitoring System.
Defines abstract contract for camera and video capture sources across all platforms.
"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple
import numpy as np


class CameraInterface(ABC):
    """Abstract base class for all video capture devices and streams."""

    @abstractmethod
    def open(self) -> bool:
        """Opens the camera or video stream. Returns True if successful."""
        pass

    @abstractmethod
    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Reads the next frame. Returns (success, frame_bgr)."""
        pass

    @abstractmethod
    def release(self) -> None:
        """Releases the camera device and cleans up resources."""
        pass

    @abstractmethod
    def is_opened(self) -> bool:
        """Checks if the device is currently opened and available."""
        pass

    @abstractmethod
    def get_resolution(self) -> Tuple[int, int]:
        """Returns (width, height) of current video capture."""
        pass

    @abstractmethod
    def set_resolution(self, width: int, height: int) -> bool:
        """Configures capture resolution if supported."""
        pass

    @abstractmethod
    def get_fps(self) -> float:
        """Returns current capture FPS."""
        pass

    @abstractmethod
    def set_fps(self, fps: int) -> bool:
        """Sets target capture FPS if supported."""
        pass

    @abstractmethod
    def get_device_name(self) -> str:
        """Returns descriptive name of the camera or stream."""
        pass
