"""
Video File Source Implementation for Driver Monitoring System.
Supports MP4, MOV, and AVI video file inputs for algorithm testing and validation.
Provides playback controls: pause, resume, seek, restart, and looping.
"""

import logging
import os
import time
from typing import Optional, Tuple
import cv2
import numpy as np

from driver_monitor.camera.camera_interface import CameraInterface

logger = logging.getLogger(__name__)


class VideoSource(CameraInterface):
    """Plays prerecorded video files through the CameraInterface."""

    def __init__(self, file_path: str, loop: bool = True):
        self._file_path = file_path
        self._loop = loop
        self._cap: Optional[cv2.VideoCapture] = None
        self._is_paused = False
        self._total_frames = 0
        self._current_frame_idx = 0
        self._fps = 30.0
        self._width = 640
        self._height = 480
        self._last_frame: Optional[np.ndarray] = None
        self._last_read_time = 0.0

    def open(self) -> bool:
        self.release()
        if not os.path.exists(self._file_path):
            logger.error("Video file not found: %s", self._file_path)
            return False

        logger.info("Opening test video file: %s", self._file_path)
        self._cap = cv2.VideoCapture(self._file_path)
        if not self._cap.isOpened():
            logger.error("Failed to open video file: %s", self._file_path)
            return False

        self._total_frames = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self._fps = float(self._cap.get(cv2.CAP_PROP_FPS) or 30.0)
        self._width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self._height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self._current_frame_idx = 0
        self._is_paused = False
        self._last_read_time = time.time()
        logger.info(
            "Video opened: %dx%d, %d frames @ %.1ffps (duration: %.1fs)",
            self._width, self._height, self._total_frames, self._fps,
            self._total_frames / self._fps if self._fps > 0 else 0
        )
        return True

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        if not self.is_opened():
            return False, None

        if self._is_paused:
            # Return last cached frame when paused
            if self._last_frame is not None:
                return True, self._last_frame.copy()
            return False, None

        # Rate limiter to match video's native FPS
        target_delta = 1.0 / self._fps if self._fps > 0 else 0.033
        now = time.time()
        elapsed = now - self._last_read_time
        if elapsed < target_delta:
            time.sleep(target_delta - elapsed)
        self._last_read_time = time.time()

        ret, frame = self._cap.read()
        if not ret or frame is None:
            if self._loop and self._total_frames > 0:
                # Loop back to beginning
                self.seek(0)
                ret, frame = self._cap.read()
            else:
                return False, None

        if ret and frame is not None:
            self._current_frame_idx = int(self._cap.get(cv2.CAP_PROP_POS_FRAMES))
            self._last_frame = frame.copy()
            return True, frame

        return False, None

    def pause(self) -> None:
        self._is_paused = True

    def resume(self) -> None:
        self._is_paused = False

    def is_paused(self) -> bool:
        return self._is_paused

    def toggle_pause(self) -> bool:
        self._is_paused = not self._is_paused
        return self._is_paused

    def restart(self) -> None:
        self.seek(0)
        self._is_paused = False

    def seek(self, frame_index: int) -> bool:
        if not self.is_opened():
            return False
        frame_index = max(0, min(self._total_frames - 1, frame_index))
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        self._current_frame_idx = frame_index
        ret, frame = self._cap.read()
        if ret and frame is not None:
            self._last_frame = frame.copy()
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        return True

    def seek_percent(self, percent: float) -> bool:
        """Seek by percentage [0.0 - 1.0]."""
        target_frame = int(percent * self._total_frames)
        return self.seek(target_frame)

    def release(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception as e:
                logger.error("Error releasing video: %s", e)
            finally:
                self._cap = None
        self._last_frame = None

    def is_opened(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def get_resolution(self) -> Tuple[int, int]:
        return (self._width, self._height)

    def set_resolution(self, width: int, height: int) -> bool:
        return False  # Prerecorded video resolution is fixed

    def get_fps(self) -> float:
        return self._fps

    def set_fps(self, fps: int) -> bool:
        self._fps = float(fps)
        return True

    def get_device_name(self) -> str:
        return f"Video: {os.path.basename(self._file_path)}"

    @property
    def current_frame_index(self) -> int:
        return self._current_frame_idx

    @property
    def total_frames(self) -> int:
        return self._total_frames

    @property
    def progress_percent(self) -> float:
        if self._total_frames == 0:
            return 0.0
        return self._current_frame_idx / float(self._total_frames)

    @property
    def current_time_sec(self) -> float:
        if self._fps <= 0:
            return 0.0
        return self._current_frame_idx / self._fps

    @property
    def duration_sec(self) -> float:
        if self._fps <= 0:
            return 0.0
        return self._total_frames / self._fps
