"""
Unit tests for DistractionEngine module.
"""

import os
import tempfile
import unittest
from driver_monitor.config import DistractionConfig
from driver_monitor.core.result_models import (
    FaceDetectionResult, GazeDirection, GazeMetrics, HeadPoseMetrics, DistractionState
)
from driver_monitor.engine.distraction_engine import DistractionEngine


class TestDistractionEngine(unittest.TestCase):
    def setUp(self):
        self.config = DistractionConfig(
            brief_glance_max_sec=1.0,
            attention_warning_sec=1.5,
            prolonged_distraction_sec=2.0,
            downward_distraction_sec=1.8,
            critical_distraction_sec=3.5
        )
        self.engine = DistractionEngine(self.config)

    def _face(self, detected=True):
        return FaceDetectionResult(detected=detected)

    def _head(self, pitch=0.0, yaw=0.0, turned=False):
        return HeadPoseMetrics(pitch=pitch, yaw=yaw, is_head_turned=turned)

    def test_road_gaze_is_normal(self):
        gaze = GazeMetrics(direction=GazeDirection.ROAD, is_looking_at_road=True, dwell_time_sec=5.0)
        res = self.engine.evaluate(gaze, self._head(), self._face(), timestamp=0.0)

        self.assertEqual(res.state, DistractionState.NORMAL)
        self.assertFalse(res.is_distracted)
        self.assertEqual(res.off_road_glance_duration_sec, 0.0)
        self.assertEqual(res.road_gaze_percent, 100.0)

    def test_brief_glance_grace_period(self):
        gaze = GazeMetrics(direction=GazeDirection.LEFT_MIRROR, is_looking_at_road=False)
        # t = 0.0s (start glance)
        self.engine.evaluate(gaze, self._head(), self._face(), timestamp=0.0)
        # t = 0.6s (within 1.0s grace period)
        res = self.engine.evaluate(gaze, self._head(), self._face(), timestamp=0.6)

        self.assertEqual(res.state, DistractionState.BRIEF_GLANCE)
        self.assertFalse(res.is_distracted)
        self.assertAlmostEqual(res.off_road_glance_duration_sec, 0.6, places=1)

    def test_attention_warning_threshold(self):
        gaze = GazeMetrics(direction=GazeDirection.RIGHT_MIRROR, is_looking_at_road=False)
        self.engine.evaluate(gaze, self._head(), self._face(), timestamp=0.0)
        res = self.engine.evaluate(gaze, self._head(), self._face(), timestamp=1.2)

        self.assertEqual(res.state, DistractionState.ATTENTION_WARNING)
        self.assertTrue(res.is_distracted)

    def test_downward_distraction(self):
        gaze = GazeMetrics(direction=GazeDirection.DOWN, is_looking_at_road=False)
        self.engine.evaluate(gaze, self._head(), self._face(), timestamp=0.0)
        res = self.engine.evaluate(gaze, self._head(), self._face(), timestamp=2.0)

        self.assertEqual(res.state, DistractionState.DOWNWARD_DISTRACTION)
        self.assertTrue(res.is_distracted)
        self.assertGreaterEqual(res.downward_glance_count, 1)

    def test_critical_distraction_extended_dwell(self):
        gaze = GazeMetrics(direction=GazeDirection.AWAY, is_looking_at_road=False)
        self.engine.evaluate(gaze, self._head(), self._face(), timestamp=0.0)
        res = self.engine.evaluate(gaze, self._head(), self._face(), timestamp=3.8)

        self.assertEqual(res.state, DistractionState.CRITICAL_DEMO_ALERT)
        self.assertTrue(res.is_distracted)

    def test_critical_distraction_combined_head_turn(self):
        # Combined off-road glance >= 2.0s with head turned sideways
        gaze = GazeMetrics(direction=GazeDirection.RIGHT_MIRROR, is_looking_at_road=False)
        head = self._head(yaw=35.0, turned=True)
        self.engine.evaluate(gaze, head, self._face(), timestamp=0.0)
        res = self.engine.evaluate(gaze, head, self._face(), timestamp=2.2)

        self.assertEqual(res.state, DistractionState.CRITICAL_DEMO_ALERT)
        self.assertTrue(res.is_distracted)

    def test_csv_export(self):
        gaze = GazeMetrics(direction=GazeDirection.ROAD, is_looking_at_road=True)
        self.engine.evaluate(gaze, self._head(), self._face(), timestamp=0.0)

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = self.engine.export_csv(output_dir=tmpdir)
            self.assertTrue(os.path.exists(file_path))
            self.assertTrue(file_path.endswith(".csv"))

    def test_reset_statistics(self):
        gaze = GazeMetrics(direction=GazeDirection.DOWN, is_looking_at_road=False)
        self.engine.evaluate(gaze, self._head(), self._face(), timestamp=0.0)
        self.engine.evaluate(gaze, self._head(), self._face(), timestamp=2.0)

        self.engine.reset_statistics()
        self.assertEqual(self.engine._downward_count, 0)
        self.assertEqual(self.engine._distraction_event_count, 0)
        self.assertIsNone(self.engine._off_road_start_time)


if __name__ == "__main__":
    unittest.main()
