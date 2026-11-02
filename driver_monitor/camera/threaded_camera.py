"""
Threaded Camera Capture Wrapper for Driver Monitoring System.
Decouples camera I/O from computer vision inference to eliminate video buffer lag
and prevent hardware frame queue buildup on resource-constrained devices like Raspberry Pi 4B.
"""

import logging
import threading
import time
from typing import Optional, Tuple
import numpy as np

from driver_monitor.camera.camera_interface import CameraInterface

logger = logging.getLogger(__name__)


class ThreadedCamera(CameraInterface):
    """
    Asynchronous camera capture wrapper.
    A dedicated daemon thread continuously reads frames from the underlying CameraInterface
    and retains only the single most recent frame. When the detection pipeline calls
    read_frame(), it receives the freshest frame immediately without blocking on camera I/O
    and without suffering from stale buffered frames.
    """

    def __init__(self, source: CameraInterface):
        self._source = source
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()
        self._latest_frame: Optional[np.ndarray] = None
        self._latest_ret = False
        self._has_new_frame = False

    def open(self) -> bool:
        """Opens underlying camera and starts background reader thread."""
        success = self._source.open()
        if not success:
            return False

        # Read initial frame synchronously to confirm readiness
        ret, frame = self._source.read_frame()
        with self._lock:
            self._latest_ret = ret
            self._latest_frame = frame
            self._has_new_frame = ret

        self._running = True
        self._thread = threading.Thread(target=self._capture_worker, daemon=True, name="CameraCaptureWorker")
        self._thread.start()
        logger.info("ThreadedCamera started for source: %s", self.get_device_name())
        return True

    def _capture_worker(self) -> None:
        """Background thread continuously pulling latest frames."""
        consecutive_drops = 0
        while self._running:
            if not self._source.is_opened():
                time.sleep(0.05)
                continue

            ret, frame = self._source.read_frame()
            if ret and frame is not None and frame.size > 0:
                with self._lock:
                    self._latest_ret = True
                    self._latest_frame = frame
                    self._has_new_frame = True
                consecutive_drops = 0
            else:
                consecutive_drops += 1
                if consecutive_drops > 25:
                    with self._lock:
                        self._latest_ret = False
                        self._latest_frame = None
                time.sleep(0.005)

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Returns the latest available frame instantly."""
        with self._lock:
            if not self._latest_ret or self._latest_frame is None:
                return False, None
            return True, self._latest_frame

    def release(self) -> None:
        """Stops the reader thread and releases underlying camera."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
            self._thread = None

        with self._lock:
            self._latest_ret = False
            self._latest_frame = None

        self._source.release()
        logger.info("ThreadedCamera released.")

    def is_opened(self) -> bool:
        return self._running and self._source.is_opened()

    def get_resolution(self) -> Tuple[int, int]:
        return self._source.get_resolution()

    def set_resolution(self, width: int, height: int) -> bool:
        return self._source.set_resolution(width, height)

    def get_fps(self) -> float:
        return self._source.get_fps()

    def set_fps(self, fps: int) -> bool:
        return self._source.set_fps(fps)

    def get_device_name(self) -> str:
        return self._source.get_device_name()

    @property
    def underlying_source(self) -> CameraInterface:
        return self._source
