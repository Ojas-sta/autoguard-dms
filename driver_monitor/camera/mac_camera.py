"""
macOS Camera Implementation for Driver Monitoring System.
Uses OpenCV with AVFoundation backend, supporting built-in FaceTime HD camera and USB cameras.
Handles device enumeration, warmup frames, resolution/FPS configuration, and graceful disconnection.
"""

import logging
import time
from typing import List, Optional, Tuple
import cv2
import numpy as np

from driver_monitor.camera.camera_interface import CameraInterface

logger = logging.getLogger(__name__)


class MacCamera(CameraInterface):
    """OpenCV-based camera capture optimized for macOS."""

    def __init__(
        self,
        device_index: int = 0,
        width: int = 1280,
        height: int = 720,
        fps: int = 30,
        warmup_frames: int = 5
    ):
        self._device_index = device_index
        self._target_width = width
        self._target_height = height
        self._target_fps = fps
        self._warmup_frames = warmup_frames
        self._cap: Optional[cv2.VideoCapture] = None
        self._consecutive_failures = 0
        self._max_failures = 10
        self._device_name = f"macOS Camera #{device_index}"

    def open(self) -> bool:
        """Opens video capture using AVFoundation backend."""
        self.release()
        logger.info(
            "Opening macOS camera index %d (requested %dx%d @ %dfps)...",
            self._device_index, self._target_width, self._target_height, self._target_fps
        )

        try:
            # Prefer AVFOUNDATION on macOS
            self._cap = cv2.VideoCapture(self._device_index, cv2.CAP_AVFOUNDATION)
            if not self._cap or not self._cap.isOpened():
                # Fallback to default backend
                logger.warning("AVFOUNDATION failed, attempting default backend...")
                self._cap = cv2.VideoCapture(self._device_index)

            if not self._cap.isOpened():
                logger.error("Failed to open camera index %d", self._device_index)
                return False

            # Configure properties
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._target_width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._target_height)
            self._cap.set(cv2.CAP_PROP_FPS, self._target_fps)

            # Warmup: pump initial frames because macOS camera sensor needs ~0.5s to adjust exposure/gain
            time.sleep(0.3)
            warmed_up = False
            for i in range(self._warmup_frames + 5):
                ret, frame = self._cap.read()
                if ret and frame is not None and frame.size > 0:
                    warmed_up = True
                    break
                time.sleep(0.08)

            if not warmed_up:
                logger.warning("Camera index %d opened but returned no frames during warmup", self._device_index)

            actual_w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = self._cap.get(cv2.CAP_PROP_FPS)

            self._device_name = f"FaceTime HD / USB Camera [{self._device_index}] ({actual_w}x{actual_h})"
            logger.info("macOS Camera [%d] opened successfully: %dx%d @ %.1ffps", self._device_index, actual_w, actual_h, actual_fps)
            self._consecutive_failures = 0
            return True

        except Exception as e:
            logger.error("Exception opening camera index %d: %s", self._device_index, e, exc_info=True)
            self.release()
            return False

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Reads the next frame. Handles transient read failures and disconnection."""
        if not self.is_opened():
            return False, None

        ret, frame = self._cap.read()
        if not ret or frame is None or frame.size == 0:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self._max_failures:
                logger.warning("Camera index %d disconnected or failing consistently (%d consecutive drops)", self._device_index, self._consecutive_failures)
                self.release()
            return False, None

        self._consecutive_failures = 0
        return True, frame

    def release(self) -> None:
        """Releases the camera."""
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception as e:
                logger.error("Error releasing camera %d: %s", self._device_index, e)
            finally:
                self._cap = None

    def is_opened(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def get_resolution(self) -> Tuple[int, int]:
        if not self.is_opened():
            return (self._target_width, self._target_height)
        w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        return (w, h)

    def set_resolution(self, width: int, height: int) -> bool:
        self._target_width = width
        self._target_height = height
        if self.is_opened():
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            return True
        return False

    def get_fps(self) -> float:
        if not self.is_opened():
            return float(self._target_fps)
        return float(self._cap.get(cv2.CAP_PROP_FPS) or self._target_fps)

    def set_fps(self, fps: int) -> bool:
        self._target_fps = fps
        if self.is_opened():
            return bool(self._cap.set(cv2.CAP_PROP_FPS, fps))
        return True

    def get_device_name(self) -> str:
        return self._device_name

    @staticmethod
    def enumerate_cameras(max_indices: int = 4) -> List[Tuple[int, str]]:
        """Scans video capture indices to detect available connected cameras on macOS."""
        available = []
        for idx in range(max_indices):
            cap = cv2.VideoCapture(idx, cv2.CAP_AVFOUNDATION)
            if cap.isOpened():
                name = "FaceTime HD Camera (Built-in)" if idx == 0 else f"USB Camera {idx}"
                available.append((idx, f"Camera {idx}: {name}"))
                cap.release()
        return available
