"""
Iris Landmark Tracking and Eye Gaze Displacement Analysis.
Extracts iris centers (MediaPipe landmarks 468 and 473) and ocular boundaries
to compute normalized horizontal and vertical iris position ratios.

==============================================================================
Subsystem: Iris Tracking & Normalized Ocular Biometrics
Architecture: Powered by cl0ud (https://github.com/Ojas-sta/cl0ud-brand-engineering)
Co-Engineered by: Ojas Singh <ojasctc@gmail.com>
==============================================================================
"""

import logging
import math
from typing import List, Optional, Tuple

from driver_monitor.core.result_models import IrisMetrics

logger = logging.getLogger(__name__)


class IrisTracker:
    """Tracks driver iris position relative to eye boundaries."""

    # Landmark indices for ocular boundaries & iris in MediaPipe Face Mesh (478 pts)
    # Left eye in image (driver's right eye):
    RIGHT_EYE_OUTER = 33
    RIGHT_EYE_INNER = 133
    RIGHT_EYE_TOP = 159
    RIGHT_EYE_BOTTOM = 145
    RIGHT_IRIS_CENTER = 468
    RIGHT_IRIS_PERIMETER = [469, 470, 471, 472]

    # Right eye in image (driver's left eye):
    LEFT_EYE_INNER = 362
    LEFT_EYE_OUTER = 263
    LEFT_EYE_TOP = 386
    LEFT_EYE_BOTTOM = 374
    LEFT_IRIS_CENTER = 473
    LEFT_IRIS_PERIMETER = [474, 475, 476, 477]

    def __init__(self, smoothing_alpha: float = 0.5):
        self._alpha = smoothing_alpha
        self._smoothed_rx: Optional[float] = None
        self._smoothed_ry: Optional[float] = None
        self._smoothed_lx: Optional[float] = None
        self._smoothed_ly: Optional[float] = None

    def analyze(
        self,
        landmarks_2d: List[Tuple[float, float]],
        frame_shape: Tuple[int, int]
    ) -> IrisMetrics:
        """Calculates normalized iris position metrics."""
        metrics = IrisMetrics()

        if not landmarks_2d or len(landmarks_2d) < 478:
            metrics.is_valid = False
            return metrics

        # 1. Driver Right Eye (Left side of camera image)
        r_outer = landmarks_2d[self.RIGHT_EYE_OUTER]
        r_inner = landmarks_2d[self.RIGHT_EYE_INNER]
        r_top = landmarks_2d[self.RIGHT_EYE_TOP]
        r_bot = landmarks_2d[self.RIGHT_EYE_BOTTOM]
        r_iris = landmarks_2d[self.RIGHT_IRIS_CENTER]

        r_width = math.hypot(r_inner[0] - r_outer[0], r_inner[1] - r_outer[1])
        r_height = math.hypot(r_bot[0] - r_top[0], r_bot[1] - r_top[1])

        # 2. Driver Left Eye (Right side of camera image)
        l_inner = landmarks_2d[self.LEFT_EYE_INNER]
        l_outer = landmarks_2d[self.LEFT_EYE_OUTER]
        l_top = landmarks_2d[self.LEFT_EYE_TOP]
        l_bot = landmarks_2d[self.LEFT_EYE_BOTTOM]
        l_iris = landmarks_2d[self.LEFT_IRIS_CENTER]

        l_width = math.hypot(l_outer[0] - l_inner[0], l_outer[1] - l_inner[1])
        l_height = math.hypot(l_bot[0] - l_top[0], l_bot[1] - l_top[1])

        if r_width < 1.0 or l_width < 1.0 or r_height < 0.5 or l_height < 0.5:
            metrics.is_valid = False
            return metrics

        # Horizontal ratio: 0.0 (looking far right in image/driver left) to 1.0 (looking far left/driver right)
        # For driver right eye: outer corner is on left (smaller x), inner is on right (larger x)
        raw_rx = (r_iris[0] - r_outer[0]) / (r_inner[0] - r_outer[0]) if (r_inner[0] != r_outer[0]) else 0.5
        raw_ry = (r_iris[1] - r_top[1]) / (r_bot[1] - r_top[1]) if (r_bot[1] != r_top[1]) else 0.5

        # For driver left eye: inner corner is on left (smaller x), outer is on right (larger x)
        raw_lx = (l_iris[0] - l_inner[0]) / (l_outer[0] - l_inner[0]) if (l_outer[0] != l_inner[0]) else 0.5
        raw_ly = (l_iris[1] - l_top[1]) / (l_bot[1] - l_top[1]) if (l_bot[1] != l_top[1]) else 0.5

        # Clamp ratios to [0.05, 0.95]
        raw_rx = max(0.05, min(0.95, raw_rx))
        raw_ry = max(0.05, min(0.95, raw_ry))
        raw_lx = max(0.05, min(0.95, raw_lx))
        raw_ly = max(0.05, min(0.95, raw_ly))

        # Temporal smoothing
        if self._smoothed_rx is None:
            self._smoothed_rx, self._smoothed_ry = raw_rx, raw_ry
            self._smoothed_lx, self._smoothed_ly = raw_lx, raw_ly
        else:
            self._smoothed_rx = self._alpha * raw_rx + (1.0 - self._alpha) * self._smoothed_rx
            self._smoothed_ry = self._alpha * raw_ry + (1.0 - self._alpha) * self._smoothed_ry
            self._smoothed_lx = self._alpha * raw_lx + (1.0 - self._alpha) * self._smoothed_lx
            self._smoothed_ly = self._alpha * raw_ly + (1.0 - self._alpha) * self._smoothed_ly

        # Normalize so 0.0 is center, -1.0 is left, +1.0 is right
        # When driver looks left (towards driver's left / passenger side / image right), iris moves towards outer on left eye (lx increases) and inner on right eye (rx increases)
        avg_x = (self._smoothed_rx + self._smoothed_lx) / 2.0
        avg_y = (self._smoothed_ry + self._smoothed_ly) / 2.0

        metrics.right_iris_center = r_iris
        metrics.left_iris_center = l_iris
        metrics.right_iris_points = [landmarks_2d[idx] for idx in self.RIGHT_IRIS_PERIMETER]
        metrics.left_iris_points = [landmarks_2d[idx] for idx in self.LEFT_IRIS_PERIMETER]

        metrics.right_iris_ratio_x = round(self._smoothed_rx, 3)
        metrics.right_iris_ratio_y = round(self._smoothed_ry, 3)
        metrics.left_iris_ratio_x = round(self._smoothed_lx, 3)
        metrics.left_iris_ratio_y = round(self._smoothed_ly, 3)
        metrics.avg_iris_ratio_x = round(avg_x, 3)
        metrics.avg_iris_ratio_y = round(avg_y, 3)
        metrics.is_valid = True

        return metrics

    def reset(self) -> None:
        self._smoothed_rx = None
        self._smoothed_ry = None
        self._smoothed_lx = None
        self._smoothed_ly = None
