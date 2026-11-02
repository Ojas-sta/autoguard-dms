"""
Unit tests for ThreadedCamera and asynchronous frame capture.
Verifies that camera frames are decoupled from inference, buffer queue lag is avoided,
and resources are released cleanly.
"""

import time
import unittest
import numpy as np

from driver_monitor.camera.camera_interface import CameraInterface
from driver_monitor.camera.threaded_camera import ThreadedCamera


class MockHardwareCamera(CameraInterface):
    """Simulates a camera hardware device streaming frames at a fixed rate."""

    def __init__(self, width: int = 640, height: int = 480, fps: int = 30):
        self._width = width
        self._height = height
        self._fps = fps
        self._opened = False
        self._frame_count = 0

    def open(self) -> bool:
        self._opened = True
        return True

    def read_frame(self):
        if not self._opened:
            return False, None
        self._frame_count += 1
        # Create a frame with unique counter value in pixel (0,0)
        frame = np.zeros((self._height, self._width, 3), dtype=np.uint8)
        frame[0, 0, 0] = self._frame_count % 255
        time.sleep(0.01)  # Simulate sensor capture delay
        return True, frame

    def release(self) -> None:
        self._opened = False

    def is_opened(self) -> bool:
        return self._opened

    def get_resolution(self):
        return (self._width, self._height)

    def set_resolution(self, width: int, height: int) -> bool:
        self._width, self._height = width, height
        return True

    def get_fps(self) -> float:
        return float(self._fps)

    def set_fps(self, fps: int) -> bool:
        self._fps = fps
        return True

    def get_device_name(self) -> str:
        return "MockHardwareCamera"


class TestThreadedCamera(unittest.TestCase):

    def setUp(self):
        self.mock_cam = MockHardwareCamera(width=320, height=240, fps=30)
        self.threaded_cam = ThreadedCamera(self.mock_cam)

    def tearDown(self):
        self.threaded_cam.release()

    def test_open_and_read_frame(self):
        """ThreadedCamera starts background thread and provides frames instantly."""
        opened = self.threaded_cam.open()
        self.assertTrue(opened)
        self.assertTrue(self.threaded_cam.is_opened())

        # Give background thread a moment to acquire initial frames
        time.sleep(0.05)
        ret, frame = self.threaded_cam.read_frame()
        self.assertTrue(ret)
        self.assertIsNotNone(frame)
        self.assertEqual(frame.shape, (240, 320, 3))

    def test_latest_frame_freshening(self):
        """ThreadedCamera continuously updates with newer frames."""
        self.threaded_cam.open()
        time.sleep(0.04)

        ret1, frame1 = self.threaded_cam.read_frame()
        val1 = frame1[0, 0, 0]

        # Wait a short interval for sensor to produce new frames
        time.sleep(0.06)

        ret2, frame2 = self.threaded_cam.read_frame()
        val2 = frame2[0, 0, 0]

        self.assertTrue(ret1)
        self.assertTrue(ret2)
        # Background worker must have captured more recent frames
        self.assertGreater(val2, val1)

    def test_clean_shutdown(self):
        """ThreadedCamera cleanly stops thread and releases underlying camera."""
        self.threaded_cam.open()
        time.sleep(0.02)
        self.threaded_cam.release()
        self.assertFalse(self.threaded_cam.is_opened())
        self.assertFalse(self.mock_cam.is_opened())

    def test_metadata_forwarding(self):
        """Resolution, FPS, and device name are forwarded transparently."""
        self.assertEqual(self.threaded_cam.get_resolution(), (320, 240))
        self.assertEqual(self.threaded_cam.get_fps(), 30.0)
        self.assertEqual(self.threaded_cam.get_device_name(), "MockHardwareCamera")


if __name__ == "__main__":
    unittest.main()
