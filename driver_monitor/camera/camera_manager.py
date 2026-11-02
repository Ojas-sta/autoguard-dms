"""
Camera Manager for Driver Monitoring System.
Coordinates camera selection, device switching, video file testing, and frame distribution.

==============================================================================
Subsystem: Cross-Platform Video Capture & Device Abstraction Manager
Architecture: Powered by cl0ud (https://github.com/Ojas-sta/cl0ud-brand-engineering)
Co-Engineered by: Ojas Singh <ojasctc@gmail.com>
==============================================================================
"""

import logging
from threading import Lock
from typing import List, Optional, Tuple
import numpy as np

from driver_monitor.camera.camera_interface import CameraInterface
from driver_monitor.camera.mac_camera import MacCamera
from driver_monitor.camera.pi_camera import PiCamera
from driver_monitor.camera.threaded_camera import ThreadedCamera
from driver_monitor.camera.video_source import VideoSource
from driver_monitor.config import CameraConfig
from driver_monitor.core.event_manager import global_event_bus

logger = logging.getLogger(__name__)


class CameraManager:
    """Manages video input devices and provides seamless runtime switching."""

    def __init__(self, platform_name: str, config: CameraConfig):
        self._platform_name = platform_name
        self._config = config
        self._active_source: Optional[CameraInterface] = None
        self._source_type: str = "webcam"  # 'webcam' or 'video'
        self._lock = Lock()
        self._available_cameras: List[Tuple[int, str]] = []

    def initialize_default_camera(self) -> bool:
        """Initializes the default platform camera."""
        with self._lock:
            if self._platform_name == "macos":
                raw_cam = MacCamera(
                    device_index=self._config.default_device_index,
                    width=self._config.resolution_width,
                    height=self._config.resolution_height,
                    fps=self._config.target_fps,
                    warmup_frames=self._config.warmup_frames
                )
            else:
                raw_cam = PiCamera(
                    device_index=self._config.default_device_index,
                    width=self._config.resolution_width,
                    height=self._config.resolution_height,
                    fps=self._config.target_fps
                )

            if getattr(self._config, "threaded_capture", True):
                self._active_source = ThreadedCamera(raw_cam)
            else:
                self._active_source = raw_cam

            success = self._active_source.open()
            self._source_type = "webcam"
            global_event_bus.publish("camera_status", {
                "opened": success,
                "name": self._active_source.get_device_name(),
                "type": self._source_type
            })
            return success

    def switch_to_camera(self, device_index: int) -> bool:
        """Switches to another camera device index."""
        with self._lock:
            if self._active_source is not None:
                self._active_source.release()

            if self._platform_name == "macos":
                raw_cam = MacCamera(
                    device_index=device_index,
                    width=self._config.resolution_width,
                    height=self._config.resolution_height,
                    fps=self._config.target_fps
                )
            else:
                raw_cam = PiCamera(
                    device_index=device_index,
                    width=self._config.resolution_width,
                    height=self._config.resolution_height,
                    fps=self._config.target_fps
                )

            if getattr(self._config, "threaded_capture", True):
                self._active_source = ThreadedCamera(raw_cam)
            else:
                self._active_source = raw_cam

            success = self._active_source.open()
            self._source_type = "webcam"
            global_event_bus.publish("camera_status", {
                "opened": success,
                "name": self._active_source.get_device_name(),
                "type": self._source_type
            })
            return success

    def load_video_file(self, video_path: str, loop: bool = True) -> bool:
        """Loads a test video file as the active video source."""
        with self._lock:
            if self._active_source is not None:
                self._active_source.release()

            video_source = VideoSource(video_path, loop=loop)
            success = video_source.open()
            if success:
                self._active_source = video_source
                self._source_type = "video"
                global_event_bus.publish("camera_status", {
                    "opened": True,
                    "name": self._active_source.get_device_name(),
                    "type": self._source_type,
                    "duration": video_source.duration_sec,
                    "frames": video_source.total_frames
                })
                return True
            else:
                logger.error("Failed to load video file: %s", video_path)
                return False

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Reads a frame from the active source."""
        with self._lock:
            if self._active_source is None:
                return False, None
            return self._active_source.read_frame()

    def release(self) -> None:
        """Releases the active video source."""
        with self._lock:
            if self._active_source is not None:
                self._active_source.release()
                self._active_source = None

    def get_available_cameras(self) -> List[Tuple[int, str]]:
        """Enumerates connected cameras."""
        if self._platform_name == "macos":
            return MacCamera.enumerate_cameras()
        return [(0, "Default Pi Camera / V4L2")]

    @property
    def active_source(self) -> Optional[CameraInterface]:
        return self._active_source

    @property
    def source_type(self) -> str:
        return self._source_type

    @property
    def is_video_source(self) -> bool:
        return self._source_type == "video"

    def get_device_name(self) -> str:
        if self._active_source:
            return self._active_source.get_device_name()
        return "None"

    def get_resolution(self) -> Tuple[int, int]:
        if self._active_source:
            return self._active_source.get_resolution()
        return (0, 0)
