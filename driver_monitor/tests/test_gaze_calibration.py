"""
Unit tests for GazeCalibrationManager module.
"""

import os
import tempfile
import unittest
from driver_monitor.calibration.gaze_calibration import GazeCalibrationManager, GazeCalibrationProfile


class TestGazeCalibrationManager(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.profile_path = os.path.join(self.tmpdir.name, "test_calibration.json")
        self.mgr = GazeCalibrationManager(profile_path=self.profile_path)
        self.mgr._target_samples_per_step = 5  # Reduce sample requirement for fast testing

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_start_and_cancel_calibration(self):
        self.assertFalse(self.mgr.is_active)
        self.mgr.start_calibration()
        self.assertTrue(self.mgr.is_active)
        self.assertEqual(self.mgr.current_step_name, "ROAD")

        self.mgr.cancel_calibration()
        self.assertFalse(self.mgr.is_active)

    def test_record_samples_advances_steps_and_completes(self):
        self.mgr.start_calibration()

        # Step 1: ROAD (5 samples)
        for _ in range(5):
            is_done = self.mgr.record_sample(0.50, 0.50, 0.0, 0.0)
            self.assertFalse(is_done)

        # Step 2: LEFT_MIRROR (5 samples)
        self.assertEqual(self.mgr.current_step_name, "LEFT_MIRROR")
        for _ in range(5):
            is_done = self.mgr.record_sample(0.30, 0.50, 0.0, -22.0)
            self.assertFalse(is_done)

        # Step 3: RIGHT_MIRROR (5 samples)
        self.assertEqual(self.mgr.current_step_name, "RIGHT_MIRROR")
        for _ in range(5):
            is_done = self.mgr.record_sample(0.70, 0.50, 0.0, 22.0)
            self.assertFalse(is_done)

        # Step 4: DOWN (5 samples)
        self.assertEqual(self.mgr.current_step_name, "DOWN")
        for _ in range(5):
            is_done = self.mgr.record_sample(0.50, 0.70, 16.0, 0.0)
            self.assertFalse(is_done)

        # Step 5: UP (5 samples)
        self.assertEqual(self.mgr.current_step_name, "UP")
        for _ in range(5):
            is_done = self.mgr.record_sample(0.50, 0.30, -16.0, 0.0)
            self.assertFalse(is_done)

        # Step 6: AWAY (5 samples)
        self.assertEqual(self.mgr.current_step_name, "AWAY")
        for i in range(5):
            is_done = self.mgr.record_sample(0.85, 0.85, 30.0, 40.0)
            if i == 4:
                self.assertTrue(is_done)
            else:
                self.assertFalse(is_done)

        # Calibration completed and saved
        self.assertFalse(self.mgr.is_active)
        self.assertTrue(os.path.exists(self.profile_path))
        self.assertTrue(self.mgr.profile.is_calibrated)
        self.assertAlmostEqual(self.mgr.profile.iris_neutral_x, 0.50, places=2)
        self.assertAlmostEqual(self.mgr.profile.left_mirror_yaw, -22.0, places=1)


if __name__ == "__main__":
    unittest.main()
