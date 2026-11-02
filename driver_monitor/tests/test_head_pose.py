"""
Unit Tests for Head Pose Estimation and Nodding Detection.
Validates Euler angle extraction, head-down detection, head-tilt, head-turned, and nodding cycles.
"""

import math
import unittest
import cv2
import numpy as np

from driver_monitor.config import HeadPoseConfig
from driver_monitor.detection.head_pose import HeadPoseEstimator


class TestHeadPose(unittest.TestCase):
    def setUp(self):
        self.config = HeadPoseConfig(
            pitch_down_threshold=16.0,
            pitch_up_threshold=-20.0,
            yaw_turned_threshold=28.0,
            roll_tilted_threshold=22.0,
            head_down_warning_sec=2.2
        )
        self.estimator = HeadPoseEstimator(self.config)

    def _generate_landmarks_with_pose(self, pitch_deg: float, yaw_deg: float, roll_deg: float, w=640, h=480):
        """Projects canonical 3D model points with given pitch, yaw, roll onto 2D image."""
        # Convert Euler to rotation matrix
        # Pitch = rx, Yaw = ry, Roll = rz
        rx = math.radians(pitch_deg)
        ry = math.radians(yaw_deg)
        rz = math.radians(roll_deg)

        Rx = np.array([
            [1, 0, 0],
            [0, math.cos(rx), -math.sin(rx)],
            [0, math.sin(rx), math.cos(rx)]
        ])
        Ry = np.array([
            [math.cos(ry), 0, math.sin(ry)],
            [0, 1, 0],
            [-math.sin(ry), 0, math.cos(ry)]
        ])
        Rz = np.array([
            [math.cos(rz), -math.sin(rz), 0],
            [math.sin(rz), math.cos(rz), 0],
            [0, 0, 1]
        ])
        R = Rz @ Ry @ Rx
        rvec, _ = cv2.Rodrigues(R)
        tvec = np.array([[0.0], [0.0], [1000.0]])

        focal_length = float(w)
        center = (float(w) / 2.0, float(h) / 2.0)
        camera_matrix = np.array([
            [focal_length, 0.0, center[0]],
            [0.0, focal_length, center[1]],
            [0.0, 0.0, 1.0]
        ], dtype=np.float64)
        dist_coeffs = np.zeros((4, 1))

        img_pts, _ = cv2.projectPoints(
            HeadPoseEstimator.MODEL_POINTS_3D, rvec, tvec, camera_matrix, dist_coeffs
        )
        img_pts = img_pts.reshape(-1, 2)

        # Map back to full 468 landmark array
        landmarks = [(0.0, 0.0)] * 468
        for i, idx in enumerate(HeadPoseEstimator.LANDMARK_INDICES):
            landmarks[idx] = (float(img_pts[i][0]), float(img_pts[i][1]))
        return landmarks

    def test_neutral_pose_estimation(self):
        """Test level head facing forward."""
        lms = self._generate_landmarks_with_pose(pitch_deg=0.0, yaw_deg=0.0, roll_deg=0.0)
        metrics = self.estimator.estimate(lms, (480, 640), timestamp=0.0)
        self.assertAlmostEqual(metrics.pitch, 0.0, delta=2.5)
        self.assertAlmostEqual(metrics.yaw, 0.0, delta=2.5)
        self.assertAlmostEqual(metrics.roll, 0.0, delta=2.5)
        self.assertFalse(metrics.is_head_down)
        self.assertFalse(metrics.is_head_turned)
        self.assertFalse(metrics.is_head_tilted)

    def test_head_tilted(self):
        """Scenario 7: Head Tilted."""
        lms = self._generate_landmarks_with_pose(pitch_deg=0.0, yaw_deg=0.0, roll_deg=30.0)
        m1 = self.estimator.estimate(lms, (480, 640), timestamp=0.0)
        self.assertTrue(m1.is_head_tilted)
        self.assertAlmostEqual(m1.roll, 30.0, delta=3.0)

        # Sustained tilt for 2.6s
        m2 = self.estimator.estimate(lms, (480, 640), timestamp=2.6)
        self.assertGreaterEqual(m2.head_tilted_duration_sec, 2.5)

    def test_head_turned(self):
        """Scenario 9: Head Turned Left/Right."""
        lms = self._generate_landmarks_with_pose(pitch_deg=0.0, yaw_deg=35.0, roll_deg=0.0)
        m = self.estimator.estimate(lms, (480, 640), timestamp=0.0)
        self.assertTrue(m.is_head_turned)
        self.assertAlmostEqual(m.yaw, 35.0, delta=3.0)

    def test_head_down(self):
        """Scenario: Sustained Head Down."""
        lms = self._generate_landmarks_with_pose(pitch_deg=25.0, yaw_deg=0.0, roll_deg=0.0)
        m1 = self.estimator.estimate(lms, (480, 640), timestamp=0.0)
        self.assertTrue(m1.is_head_down)
        self.assertAlmostEqual(m1.pitch, 25.0, delta=3.0)

        # Sustained for 2.5s
        m2 = self.estimator.estimate(lms, (480, 640), timestamp=2.5)
        self.assertGreaterEqual(m2.head_down_duration_sec, 2.4)

    def test_head_nodding_detection(self):
        """Scenario 8: Head Nodding."""
        # Frame 1: straight
        lms0 = self._generate_landmarks_with_pose(pitch_deg=0.0, yaw_deg=0.0, roll_deg=0.0)
        self.estimator.estimate(lms0, (480, 640), timestamp=0.0)

        # Frame 2-4: dipping downwards (+25 deg pitch down)
        for t in [0.2, 0.4, 0.6]:
            lms_dip = self._generate_landmarks_with_pose(pitch_deg=25.0, yaw_deg=0.0, roll_deg=0.0)
            self.estimator.estimate(lms_dip, (480, 640), timestamp=t)

        # Frame 5: rebound back up (+2 deg)
        lms_up = self._generate_landmarks_with_pose(pitch_deg=2.0, yaw_deg=0.0, roll_deg=0.0)
        m_nod = self.estimator.estimate(lms_up, (480, 640), timestamp=0.9)
        self.assertGreaterEqual(m_nod.head_nod_count, 1)

    def test_multi_observation_calibration(self):
        """Test multi-observation neutral calibration sequence."""
        self.estimator.start_multi_observation_calibration(num_observations=5)
        self.assertTrue(self.estimator._is_calibrating)

        # Feed 5 frames with steady offset (+4 pitch, +3 yaw, -2 roll)
        lms = self._generate_landmarks_with_pose(pitch_deg=4.0, yaw_deg=3.0, roll_deg=-2.0)
        for t in range(5):
            m = self.estimator.estimate(lms, (480, 640), timestamp=float(t) * 0.1)

        # Calibration completes on 5th frame
        self.assertFalse(self.estimator._is_calibrating)
        self.assertGreaterEqual(m.calibration_confidence, 0.8)

        # Next frame with same physical pose should be zeroed out
        m_cal = self.estimator.estimate(lms, (480, 640), timestamp=1.0)
        self.assertAlmostEqual(m_cal.pitch, 0.0, delta=1.5)
        self.assertAlmostEqual(m_cal.yaw, 0.0, delta=1.5)
        self.assertAlmostEqual(m_cal.roll, 0.0, delta=1.5)


if __name__ == "__main__":
    unittest.main()
