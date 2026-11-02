"""
Unit tests for IrisTracker module.
"""

import unittest
from driver_monitor.detection.iris_tracking import IrisTracker


class TestIrisTracker(unittest.TestCase):
    def setUp(self):
        self.tracker = IrisTracker(smoothing_alpha=0.5)

    def test_empty_landmarks(self):
        res = self.tracker.analyze([], (480, 640))
        self.assertFalse(res.is_valid)

    def test_insufficient_landmarks(self):
        # 468 points (standard mesh without irises)
        pts = [(100.0, 100.0)] * 468
        res = self.tracker.analyze(pts, (480, 640))
        self.assertFalse(res.is_valid)

    def test_valid_landmarks_center_iris(self):
        pts = [(0.0, 0.0)] * 478
        # Driver Right Eye (Image left): outer=33, inner=133, top=159, bot=145, iris=468
        pts[33] = (150.0, 200.0)   # outer
        pts[133] = (250.0, 200.0)  # inner (width = 100px)
        pts[159] = (200.0, 180.0)  # top
        pts[145] = (200.0, 220.0)  # bot (height = 40px)
        pts[468] = (200.0, 200.0)  # iris centered (x ratio: (200-150)/100 = 0.5)

        # Driver Left Eye (Image right): inner=362, outer=263, top=386, bot=374, iris=473
        pts[362] = (350.0, 200.0)  # inner
        pts[263] = (450.0, 200.0)  # outer (width = 100px)
        pts[386] = (400.0, 180.0)  # top
        pts[374] = (400.0, 220.0)  # bot (height = 40px)
        pts[473] = (400.0, 200.0)  # iris centered (x ratio: (400-350)/100 = 0.5)

        # Perimeter points
        for i in [469, 470, 471, 472, 474, 475, 476, 477]:
            pts[i] = (200.0, 200.0)

        res = self.tracker.analyze(pts, (480, 640))
        self.assertTrue(res.is_valid)
        self.assertAlmostEqual(res.avg_iris_ratio_x, 0.5, delta=0.05)
        self.assertAlmostEqual(res.avg_iris_ratio_y, 0.5, delta=0.05)

    def test_reset_clears_smoothing(self):
        self.tracker._smoothed_rx = 0.7
        self.tracker.reset()
        self.assertIsNone(self.tracker._smoothed_rx)


if __name__ == "__main__":
    unittest.main()
