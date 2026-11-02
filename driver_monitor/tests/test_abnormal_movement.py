"""
Unit Tests for Abnormal Head Movement and Dizziness Demonstration Engine.
Validates non-diagnostic behavioral indicators: sustained tilt, unusual movement patterns,
face unavailability, head turned away, and severe slump.
"""

import unittest
from driver_monitor.config import AbnormalMovementConfig, HeadPoseConfig
from driver_monitor.core.result_models import (
    AbnormalMovementState, FaceDetectionResult, HeadPoseMetrics
)
from driver_monitor.engine.abnormal_movement_engine import AbnormalMovementEngine


class TestAbnormalMovement(unittest.TestCase):
    def setUp(self):
        self.abnormal_cfg = AbnormalMovementConfig(
            erratic_jerk_threshold=80.0,
            face_lost_warning_sec=4.0,
            slump_pitch_threshold=-28.0,
            slump_motionless_sec=2.5
        )
        self.head_cfg = HeadPoseConfig(
            head_turned_warning_sec=3.0,
            head_tilted_warning_sec=2.5
        )
        self.engine = AbnormalMovementEngine(self.abnormal_cfg, self.head_cfg)

    def test_sustained_tilt(self):
        """Abnormal Head Posture: sustained roll tilt."""
        head = HeadPoseMetrics(
            roll=26.0, is_head_tilted=True, head_tilted_duration_sec=2.7
        )
        face = FaceDetectionResult(detected=True)

        res = self.engine.evaluate(head, face, angular_jerk=10.0, timestamp=2.7)
        self.assertEqual(res.state, AbnormalMovementState.ABNORMAL_HEAD_POSTURE)
        self.assertIn("Abnormal Head Posture", res.alert_title)

    def test_unusual_movement_jerk(self):
        """Unusual Head Movement: high angular jerk."""
        head = HeadPoseMetrics()
        face = FaceDetectionResult(detected=True)

        res = self.engine.evaluate(head, face, angular_jerk=95.0, timestamp=1.0)
        self.assertEqual(res.state, AbnormalMovementState.UNUSUAL_HEAD_MOVEMENT)
        self.assertIn("Unusual Head Movement", res.alert_title)

    def test_head_turned_away(self):
        """Driver Attention Lost: head turned left/right for > 3s."""
        head = HeadPoseMetrics(
            yaw=35.0, is_head_turned=True, head_turned_duration_sec=3.2
        )
        face = FaceDetectionResult(detected=True)

        res = self.engine.evaluate(head, face, angular_jerk=5.0, timestamp=3.2)
        self.assertEqual(res.state, AbnormalMovementState.DRIVER_ATTENTION_LOST)
        self.assertIn("Driver Attention Lost", res.alert_title)

    def test_face_lost_extended(self):
        """Scenario 11: Face Temporarily / Extendedly Unavailable."""
        head = HeadPoseMetrics()
        face = FaceDetectionResult(detected=False, face_lost_duration_sec=4.5)

        res = self.engine.evaluate(head, face, angular_jerk=0.0, timestamp=4.5)
        self.assertEqual(res.state, AbnormalMovementState.DRIVER_ATTENTION_LOST)
        self.assertIn("Driver Attention Lost", res.alert_title)

    def test_driver_slump_emergency_demo(self):
        """Possible Driver Emergency - Demo: head slump."""
        head = HeadPoseMetrics(
            pitch=-32.0, is_head_down=True, head_down_duration_sec=2.8
        )
        face = FaceDetectionResult(detected=True)

        res = self.engine.evaluate(head, face, angular_jerk=2.0, timestamp=2.8)
        self.assertEqual(res.state, AbnormalMovementState.POSSIBLE_DRIVER_EMERGENCY_DEMO)
        self.assertIn("Possible Driver Emergency", res.alert_title)


if __name__ == "__main__":
    unittest.main()
