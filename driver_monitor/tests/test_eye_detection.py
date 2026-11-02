"""
Unit Tests for Eye Detection, EAR Computation, and Blink Analysis.
Validates Open/Closed classifications, EAR math, blink counting, and closure durations.
"""

import unittest
from driver_monitor.config import EyeMonitoringConfig
from driver_monitor.core.result_models import EyeStatus
from driver_monitor.detection.eye_detection import EyeDetector


class TestEyeDetection(unittest.TestCase):
    def setUp(self):
        self.config = EyeMonitoringConfig(
            ear_closed_threshold=0.22,
            ear_open_threshold=0.27,
            blink_min_duration_sec=0.08,
            blink_max_duration_sec=0.40,
            closure_warning_sec=1.5
        )
        self.detector = EyeDetector(self.config)

    def _generate_synthetic_landmarks(self, eye_height: float, eye_width: float = 30.0):
        """Builds dummy 468-point landmarks list with specific eye dimension."""
        landmarks = [(0.0, 0.0)] * 468
        # Left eye: [33, 160, 158, 133, 153, 144]
        # p1=33, p4=133 (corners, width)
        landmarks[33] = (100.0, 200.0)
        landmarks[133] = (100.0 + eye_width, 200.0)
        # Vertical pairs: (160, 144), (158, 153)
        landmarks[160] = (110.0, 200.0 - eye_height / 2.0)
        landmarks[144] = (110.0, 200.0 + eye_height / 2.0)
        landmarks[158] = (120.0, 200.0 - eye_height / 2.0)
        landmarks[153] = (120.0, 200.0 + eye_height / 2.0)

        # Right eye: [362, 385, 387, 263, 373, 380]
        landmarks[362] = (200.0, 200.0)
        landmarks[263] = (200.0 + eye_width, 200.0)
        landmarks[385] = (210.0, 200.0 - eye_height / 2.0)
        landmarks[373] = (210.0, 200.0 + eye_height / 2.0)
        landmarks[387] = (220.0, 200.0 - eye_height / 2.0)
        landmarks[380] = (220.0, 200.0 + eye_height / 2.0)
        return landmarks

    def test_eyes_open_status(self):
        """Scenario 3: Eyes Open."""
        # High height -> EAR > 0.30
        lms = self._generate_synthetic_landmarks(eye_height=12.0, eye_width=30.0)
        metrics = self.detector.analyze(lms, timestamp=10.0)
        self.assertEqual(metrics.overall_status, EyeStatus.OPEN)
        self.assertGreater(metrics.avg_ear, 0.27)
        self.assertEqual(metrics.closure_duration_sec, 0.0)

    def test_eyes_closed_status(self):
        """Scenario 4: Eyes Closed."""
        # Very small height -> EAR < 0.20
        lms = self._generate_synthetic_landmarks(eye_height=2.0, eye_width=30.0)
        metrics = self.detector.analyze(lms, timestamp=10.0)
        self.assertEqual(metrics.overall_status, EyeStatus.CLOSED)
        self.assertLess(metrics.avg_ear, 0.22)

    def test_prolonged_eye_closure(self):
        """Scenario 5: Prolonged Eye Closure."""
        lms_closed = self._generate_synthetic_landmarks(eye_height=2.0)
        # Frame at t=0
        self.detector.analyze(lms_closed, timestamp=0.0)
        # Frame at t=1.0 (Attention level)
        m1 = self.detector.analyze(lms_closed, timestamp=1.0)
        self.assertEqual(m1.closure_duration_sec, 1.0)
        self.assertFalse(m1.is_prolonged_closure)

        # Frame at t=1.6 (> 1.5s warning threshold)
        m2 = self.detector.analyze(lms_closed, timestamp=1.6)
        self.assertGreaterEqual(m2.closure_duration_sec, 1.5)
        self.assertTrue(m2.is_prolonged_closure)

    def test_blink_detection(self):
        """Scenario 6: Repeated Blinking."""
        lms_open = self._generate_synthetic_landmarks(eye_height=12.0)
        lms_closed = self._generate_synthetic_landmarks(eye_height=2.0)

        # Initial state: Open
        self.detector.analyze(lms_open, timestamp=0.0)
        # Eyes close for 0.15s (normal blink)
        self.detector.analyze(lms_closed, timestamp=0.1)
        # Eyes open again at t=0.25
        m_after_blink = self.detector.analyze(lms_open, timestamp=0.25)

        self.assertEqual(m_after_blink.blink_count, 1)

    def test_missing_landmarks_unknown(self):
        """Test graceful handling of empty or partial landmarks."""
        metrics = self.detector.analyze([], timestamp=0.0)
        self.assertEqual(metrics.overall_status, EyeStatus.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
