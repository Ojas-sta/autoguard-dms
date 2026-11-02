"""
Integration and End-to-End Scenario Verification for Driver Monitoring System.
Covers camera switching, video-file playback, seeking, pausing, and camera disconnection recovery.
"""

import os
import unittest
import numpy as np

from driver_monitor.camera.camera_manager import CameraManager
from driver_monitor.camera.video_source import VideoSource
from driver_monitor.config import AppConfig, CameraConfig
from driver_monitor.core.detection_pipeline import DetectionPipeline
from driver_monitor.hardware.hardware_factory import HardwareFactory


class TestIntegrationScenarios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cls.video_path = os.path.join(base_dir, "resources", "videos", "test_normal.mp4")

    def setUp(self):
        self.config = AppConfig()
        self.buzzer, self.leds, self.emergency_button = HardwareFactory.create_hardware(
            "macos", self.config.hardware
        )
        self.pipeline = DetectionPipeline(
            self.config, self.buzzer, self.leds, self.emergency_button
        )
        self.camera_mgr = CameraManager("macos", self.config.camera)

    def tearDown(self):
        self.camera_mgr.release()
        self.pipeline.buzzer.stop_alert()

    def test_scenario_15_video_file_playback(self):
        """Scenario 15: Video-File Playback with Pause, Resume, Seek."""
        self.assertTrue(os.path.exists(self.video_path))
        video = VideoSource(self.video_path, loop=True)
        self.assertTrue(video.open())

        # 1. Read normal frames
        ret, frame1 = video.read_frame()
        self.assertTrue(ret)
        self.assertIsNotNone(frame1)

        # 2. Pause
        video.pause()
        self.assertTrue(video.is_paused())
        ret, frame_paused = video.read_frame()
        self.assertTrue(ret)  # Returns cached frame

        # 3. Resume
        video.resume()
        self.assertFalse(video.is_paused())

        # 4. Seek
        self.assertTrue(video.seek(50))
        self.assertEqual(video.current_frame_index, 50)

        # 5. Restart
        video.restart()
        self.assertEqual(video.current_frame_index, 0)
        video.release()

    def test_scenario_16_camera_switching(self):
        """Scenario 16: Switching between cameras and video files."""
        # 1. Start with test video
        success = self.camera_mgr.load_video_file(self.video_path)
        self.assertTrue(success)
        self.assertEqual(self.camera_mgr.source_type, "video")

        ret, frame = self.camera_mgr.read_frame()
        self.assertTrue(ret)

        # 2. Switch to another source (re-load or camera index)
        success_cam = self.camera_mgr.switch_to_camera(0)
        # On macOS with permission, camera 0 opens
        self.assertEqual(self.camera_mgr.source_type, "webcam")

    def test_scenario_14_camera_disconnection_handling(self):
        """Scenario 14: Camera Disconnected Graceful Handling."""
        # When read_frame returns False, None, pipeline handles it safely without crashing
        res = self.pipeline.process_frame(np.zeros((0, 0, 3), dtype=np.uint8), "DeadCamera", "webcam")
        self.assertFalse(res.face.detected)

    def test_scenario_1_and_2_face_detection_lifecycle(self):
        """Scenario 1 & 2: Face Detected Normally vs Face Not Detected."""
        # Read frame with face from normal video
        video = VideoSource(self.video_path, loop=False)
        video.open()
        ret, frame_with_face = video.read_frame()
        video.release()

        # Face present
        res1 = self.pipeline.process_frame(frame_with_face, "Test", "video")
        self.assertTrue(res1.face.detected)
        self.assertGreater(res1.face.confidence, 0.7)

        # Face absent (black frame)
        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        res2 = self.pipeline.process_frame(blank, "Test", "video")
        self.assertFalse(res2.face.detected)


if __name__ == "__main__":
    unittest.main()
