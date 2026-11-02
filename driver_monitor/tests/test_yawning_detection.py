"""
Unit Tests for Yawning Detection and Speech Filtering.
Validates Mouth Aspect Ratio (MAR) computation, distinguishing short speech from sustained yawns.
"""

import unittest
from driver_monitor.config import YawningConfig
from driver_monitor.detection.yawning_detection import YawningDetector


class TestYawningDetection(unittest.TestCase):
    def setUp(self):
        self.config = YawningConfig(
            mar_open_threshold=0.55,
            yawn_min_duration_sec=1.6,
            yawn_cooldown_sec=2.0
        )
        self.detector = YawningDetector(self.config)

    def _generate_mouth_landmarks(self, mouth_height: float, mouth_width: float = 60.0):
        """Builds dummy landmarks with specific mouth dimensions."""
        landmarks = [(0.0, 0.0)] * 468
        # Corners: 78 (left), 308 (right)
        landmarks[78] = (100.0, 300.0)
        landmarks[308] = (100.0 + mouth_width, 300.0)
        # Vertical pairs: (13, 14), (81, 178), (311, 402)
        landmarks[13] = (130.0, 300.0 - mouth_height / 2.0)
        landmarks[14] = (130.0, 300.0 + mouth_height / 2.0)
        landmarks[81] = (115.0, 300.0 - mouth_height / 2.0)
        landmarks[178] = (115.0, 300.0 + mouth_height / 2.0)
        landmarks[311] = (145.0, 300.0 - mouth_height / 2.0)
        landmarks[402] = (145.0, 300.0 + mouth_height / 2.0)
        return landmarks

    def test_normal_mouth(self):
        """Test closed or resting mouth."""
        lms = self._generate_mouth_landmarks(mouth_height=10.0, mouth_width=60.0)
        m = self.detector.analyze(lms, timestamp=0.0)
        self.assertLess(m.mar, 0.55)
        self.assertFalse(m.is_mouth_open)
        self.assertFalse(m.is_yawning)

    def test_speech_not_triggering_yawn(self):
        """Test that brief mouth opening for speech (<0.6s) is filtered out."""
        lms_open = self._generate_mouth_landmarks(mouth_height=38.0, mouth_width=60.0)
        lms_closed = self._generate_mouth_landmarks(mouth_height=8.0, mouth_width=60.0)

        # Starts speaking at t=0
        self.detector.analyze(lms_open, timestamp=0.0)
        # Speaking syllable at t=0.4s
        m_speak = self.detector.analyze(lms_open, timestamp=0.4)
        self.assertTrue(m_speak.is_mouth_open)
        self.assertFalse(m_speak.is_yawning)  # Not yet a yawn!

        # Mouth closes at t=0.6s
        m_closed = self.detector.analyze(lms_closed, timestamp=0.6)
        self.assertFalse(m_closed.is_yawning)
        self.assertEqual(m_closed.yawn_count, 0)

    def test_sustained_yawn_detection(self):
        """Scenario 10: Yawning."""
        lms_open = self._generate_mouth_landmarks(mouth_height=42.0, mouth_width=60.0)

        # Start of yawn
        self.detector.analyze(lms_open, timestamp=0.0)
        # Sustained at 1.0s (still waiting)
        self.detector.analyze(lms_open, timestamp=1.0)
        # Sustained at 1.8s (> 1.6s threshold)
        m_yawn = self.detector.analyze(lms_open, timestamp=1.8)

        self.assertTrue(m_yawn.is_yawning)
        self.assertEqual(m_yawn.yawn_count, 1)


if __name__ == "__main__":
    unittest.main()
