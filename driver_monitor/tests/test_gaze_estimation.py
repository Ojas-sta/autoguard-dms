"""
Unit tests for GazeEstimator module.
"""

import unittest
from driver_monitor.calibration.gaze_calibration import GazeCalibrationManager
from driver_monitor.config import GazeConfig
from driver_monitor.core.result_models import (
    FaceDetectionResult, EyeMetrics, EyeStatus, GazeDirection, HeadPoseMetrics, IrisMetrics
)
from driver_monitor.detection.gaze_estimation import GazeEstimator


class TestGazeEstimator(unittest.TestCase):
    def setUp(self):
        self.calib_mgr = GazeCalibrationManager()
        self.estimator = GazeEstimator(config=GazeConfig(), calibration_mgr=self.calib_mgr)

    def _create_mock_face(self, detected=True):
        return FaceDetectionResult(detected=detected, confidence=0.9, bbox=(100, 100, 200, 200))

    def _create_mock_eyes(self, status=EyeStatus.OPEN):
        return EyeMetrics(overall_status=status, left_status=status, right_status=status)

    def test_face_not_detected(self):
        iris = IrisMetrics(is_valid=True)
        head = HeadPoseMetrics(pitch=0.0, yaw=0.0, roll=0.0)
        face = self._create_mock_face(detected=False)
        eyes = self._create_mock_eyes(status=EyeStatus.OPEN)

        res = self.estimator.estimate(iris, head, face, eyes, timestamp=10.0)
        self.assertEqual(res.direction, GazeDirection.UNKNOWN)
        self.assertFalse(res.is_looking_at_road)
        self.assertEqual(res.confidence, 0.0)

    def test_eyes_closed(self):
        iris = IrisMetrics(is_valid=True)
        head = HeadPoseMetrics(pitch=0.0, yaw=0.0, roll=0.0)
        face = self._create_mock_face(detected=True)
        eyes = self._create_mock_eyes(status=EyeStatus.CLOSED)

        res = self.estimator.estimate(iris, head, face, eyes, timestamp=10.0)
        self.assertEqual(res.direction, GazeDirection.UNKNOWN)
        self.assertFalse(res.is_looking_at_road)

    def test_forward_road_gaze(self):
        iris = IrisMetrics(
            is_valid=True,
            avg_iris_ratio_x=0.50,
            avg_iris_ratio_y=0.50,
            left_iris_center=(150.0, 120.0),
            right_iris_center=(250.0, 120.0)
        )
        head = HeadPoseMetrics(pitch=0.0, yaw=0.0, roll=0.0)
        face = self._create_mock_face()
        eyes = self._create_mock_eyes()

        res = self.estimator.estimate(iris, head, face, eyes, timestamp=10.0)
        self.assertEqual(res.direction, GazeDirection.ROAD)
        self.assertTrue(res.is_looking_at_road)
        self.assertGreater(res.confidence, 0.7)
        self.assertNotEqual(res.gaze_origin_2d, (0, 0))
        self.assertNotEqual(res.gaze_target_2d, (0, 0))

    def test_left_mirror_gaze(self):
        iris = IrisMetrics(is_valid=True, avg_iris_ratio_x=0.30, avg_iris_ratio_y=0.50)
        head = HeadPoseMetrics(pitch=0.0, yaw=-25.0, roll=0.0)
        face = self._create_mock_face()
        eyes = self._create_mock_eyes()

        res = self.estimator.estimate(iris, head, face, eyes, timestamp=10.0)
        self.assertEqual(res.direction, GazeDirection.LEFT_MIRROR)
        self.assertFalse(res.is_looking_at_road)

    def test_right_mirror_gaze(self):
        iris = IrisMetrics(is_valid=True, avg_iris_ratio_x=0.70, avg_iris_ratio_y=0.50)
        head = HeadPoseMetrics(pitch=0.0, yaw=25.0, roll=0.0)
        face = self._create_mock_face()
        eyes = self._create_mock_eyes()

        res = self.estimator.estimate(iris, head, face, eyes, timestamp=10.0)
        self.assertEqual(res.direction, GazeDirection.RIGHT_MIRROR)
        self.assertFalse(res.is_looking_at_road)

    def test_downward_console_gaze(self):
        iris = IrisMetrics(is_valid=True, avg_iris_ratio_x=0.50, avg_iris_ratio_y=0.75)
        head = HeadPoseMetrics(pitch=18.0, yaw=0.0, roll=0.0)
        face = self._create_mock_face()
        eyes = self._create_mock_eyes()

        res = self.estimator.estimate(iris, head, face, eyes, timestamp=10.0)
        self.assertEqual(res.direction, GazeDirection.DOWN)
        self.assertFalse(res.is_looking_at_road)

    def test_dwell_time_tracking(self):
        iris = IrisMetrics(is_valid=True, avg_iris_ratio_x=0.50, avg_iris_ratio_y=0.50)
        head = HeadPoseMetrics(pitch=0.0, yaw=0.0, roll=0.0)
        face = self._create_mock_face()
        eyes = self._create_mock_eyes()

        # Frame 1 at t=0s
        res1 = self.estimator.estimate(iris, head, face, eyes, timestamp=0.0)
        self.assertEqual(res1.dwell_time_sec, 0.0)

        # Frame 2 at t=1.5s
        res2 = self.estimator.estimate(iris, head, face, eyes, timestamp=1.5)
        self.assertEqual(res2.dwell_time_sec, 1.5)


if __name__ == "__main__":
    unittest.main()
