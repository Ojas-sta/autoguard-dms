"""
Unit Tests for Drowsiness Decision Engine.
Validates multi-tier state machine transitions (NORMAL, ATTENTION, DROWSINESS_WARNING, CRITICAL_DEMO_ALERT),
PERCLOS scoring, and combination triggers.
"""

import unittest
from driver_monitor.config import EyeMonitoringConfig, HeadPoseConfig, YawningConfig
from driver_monitor.core.result_models import (
    DrowsinessState, EyeMetrics, EyeStatus, HeadPoseMetrics, MouthMetrics
)
from driver_monitor.engine.drowsiness_engine import DrowsinessEngine


class TestDrowsinessEngine(unittest.TestCase):
    def setUp(self):
        self.eye_cfg = EyeMonitoringConfig(
            closure_attention_sec=0.8,
            closure_warning_sec=1.5,
            closure_critical_sec=2.5,
            perclos_warning_threshold=0.15,
            perclos_critical_threshold=0.30
        )
        self.head_cfg = HeadPoseConfig(head_down_warning_sec=2.2)
        self.yawn_cfg = YawningConfig(yawn_count_warning=3)
        self.engine = DrowsinessEngine(self.eye_cfg, self.head_cfg, self.yawn_cfg)

    def test_normal_alert_state(self):
        """Driver alert: eyes open, head level."""
        eyes = EyeMetrics(overall_status=EyeStatus.OPEN, avg_ear=0.35, closure_duration_sec=0.0)
        head = HeadPoseMetrics(pitch=0.0, yaw=0.0, roll=0.0)
        mouth = MouthMetrics(is_yawning=False)

        res = self.engine.evaluate(eyes, head, mouth, perclos=0.02, timestamp=0.0)
        self.assertEqual(res.state, DrowsinessState.NORMAL)
        self.assertLess(res.score, 0.2)

    def test_attention_transition(self):
        """Attention: brief closure ~0.9s or yawning."""
        eyes = EyeMetrics(overall_status=EyeStatus.CLOSED, avg_ear=0.18, closure_duration_sec=0.9)
        head = HeadPoseMetrics()
        mouth = MouthMetrics()

        res = self.engine.evaluate(eyes, head, mouth, perclos=0.05, timestamp=0.9)
        self.assertEqual(res.state, DrowsinessState.ATTENTION)

    def test_warning_transition(self):
        """Warning: prolonged eye closure 1.6s."""
        eyes = EyeMetrics(overall_status=EyeStatus.CLOSED, avg_ear=0.18, closure_duration_sec=1.6)
        head = HeadPoseMetrics()
        mouth = MouthMetrics()

        res = self.engine.evaluate(eyes, head, mouth, perclos=0.10, timestamp=1.6)
        self.assertEqual(res.state, DrowsinessState.DROWSINESS_WARNING)

    def test_critical_severe_closure(self):
        """Critical: severe eye closure 2.6s."""
        eyes = EyeMetrics(overall_status=EyeStatus.CLOSED, avg_ear=0.15, closure_duration_sec=2.6)
        head = HeadPoseMetrics()
        mouth = MouthMetrics()

        res = self.engine.evaluate(eyes, head, mouth, perclos=0.25, timestamp=2.6)
        self.assertEqual(res.state, DrowsinessState.CRITICAL_DEMO_ALERT)
        self.assertGreaterEqual(res.score, 0.95)

    def test_critical_microsleep_nod_combination(self):
        """Critical: closure 1.6s COMBINED with head nodding."""
        eyes = EyeMetrics(overall_status=EyeStatus.CLOSED, avg_ear=0.16, closure_duration_sec=1.6)
        head = HeadPoseMetrics(head_nod_count=1, is_head_down=True)
        mouth = MouthMetrics()

        res = self.engine.evaluate(eyes, head, mouth, perclos=0.12, timestamp=1.6)
        self.assertEqual(res.state, DrowsinessState.CRITICAL_DEMO_ALERT)


if __name__ == "__main__":
    unittest.main()
