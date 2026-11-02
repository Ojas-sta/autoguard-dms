"""
Raspberry Pi Camera Implementation for Driver Monitoring System.
Supports Picamera2 for official Raspberry Pi cameras (V1/V2/V3/HQ) and V4L2 for USB cameras.
Designed with graceful fallback so it safely imports and runs in simulation on non-Pi systems.
"""

import logging
from typing import Optional, Tuple
import numpy as np

from driver_monitor.camera.camera_interface import CameraInterface

logger = logging.getLogger(__name__)

# Safe optional import of Picamera2
try:
    from picamera2 import Picamera2
    HAS_PICAMERA2 = True
except ImportError:
    Picamera2 = None
    HAS_PICAMERA2 = False

import cv2


class PiCamera(CameraInterface):
    """Raspberry Pi camera adapter supporting Picamera2 or V4L2 OpenCV fallback."""

    def __init__(
        self,
        device_index: int = 0,
        width: int = 640,
        height: int = 480,
        fps: int = 30,
        use_picamera2: bool = True
    ):
        self._device_index = device_index
        self._width = width
        self._height = height
        self._fps = fps
        self._use_picamera2 = use_picamera2 and HAS_PICAMERA2
        self._picam2 = None
        self._cv_cap = None
        self._is_opened = False
        self._device_name = "Raspberry Pi Camera"

    def open(self) -> bool:
        self.release()
        logger.info(
            "Opening Pi Camera (picamera2=%s, %dx%d @ %dfps)...",
            self._use_picamera2, self._width, self._height, self._fps
        )

        if self._use_picamera2:
            try:
                self._picam2 = Picamera2()
                config = self._picam2.create_video_configuration(
                    main={"size": (self._width, self._height), "format": "RGB888"}
                )
                self._picam2.configure(config)
                self._picam2.start()
                self._is_opened = True
                self._device_name = "Raspberry Pi Camera (Picamera2)"
                logger.info("Picamera2 started successfully.")
                return True
            except Exception as e:
                logger.warning("Picamera2 initialization failed: %s. Falling back to OpenCV V4L2...", e)
                self._picam2 = None

        # Fallback to OpenCV V4L2 or standard capture
        try:
            self._cv_cap = cv2.VideoCapture(self._device_index, cv2.CAP_V4L2)
            if not self._cv_cap or not self._cv_cap.isOpened():
                self._cv_cap = cv2.VideoCapture(self._device_index)

            if self._cv_cap.isOpened():
                self._cv_cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
                self._cv_cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
                self._cv_cap.set(cv2.CAP_PROP_FPS, self._fps)
                self._is_opened = True
                self._device_name = f"Raspberry Pi USB/V4L2 Camera #{self._device_index}"
                logger.info("Pi OpenCV V4L2 camera opened successfully.")
                return True
        except Exception as e:
            logger.error("Failed to open Pi camera via OpenCV: %s", e)

        self._is_opened = False
        return False

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        if not self.is_opened():
            return False, None

        if self._picam2 is not None:
            try:
                frame_rgb = self._picam2.capture_array()
                # Convert RGB to BGR for OpenCV standard pipeline
                frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
                return True, frame_bgr
            except Exception as e:
                logger.error("Error reading frame from Picamera2: %s", e)
                return False, None

        if self._cv_cap is not None:
            ret, frame = self._cv_cap.read()
            return ret, frame

        return False, None

    def release(self) -> None:
        if self._picam2 is not None:
            try:
                self._picam2.stop()
                self._picam2.close()
            except Exception as e:
                logger.error("Error stopping Picamera2: %s", e)
            finally:
                self._picam2 = None

        if self._cv_cap is not None:
            try:
                self._cv_cap.release()
            except Exception as e:
                logger.error("Error releasing Pi OpenCV camera: %s", e)
            finally:
                self._cv_cap = None

        self._is_opened = False

    def is_opened(self) -> bool:
        return self._is_opened

    def get_resolution(self) -> Tuple[int, int]:
        return (self._width, self._height)

    def set_resolution(self, width: int, height: int) -> bool:
        self._width = width
        self._height = height
        return True

    def get_fps(self) -> float:
        return float(self._fps)

    def set_fps(self, fps: int) -> bool:
        self._fps = fps
        return True

    def get_device_name(self) -> str:
        return self._device_name
