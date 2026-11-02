"""
Yawning Detection and Speech Filtering for Driver Monitoring System.
Calculates Mouth Aspect Ratio (MAR) and uses temporal thresholding
to differentiate genuine prolonged yawns from regular conversational speech.
"""

from collections import deque
import logging
import math
import time
from typing import Deque, List, Optional, Tuple

from driver_monitor.config import YawningConfig
from driver_monitor.core.result_models import MouthMetrics

logger = logging.getLogger(__name__)


class YawningDetector:
    """Calculates MAR and detects yawning while filtering out normal speaking."""

    # Key mouth landmark indices in MediaPipe Face Mesh
    MOUTH_CORNER_LEFT = 78
    MOUTH_CORNER_RIGHT = 308
    LIP_INNER_TOP = 13
    LIP_INNER_BOTTOM = 14
    LIP_MID_LEFT_TOP = 81
    LIP_MID_LEFT_BOTTOM = 178
    LIP_MID_RIGHT_TOP = 311
    LIP_MID_RIGHT_BOTTOM = 402

    ALL_MOUTH_INDICES = [78, 308, 13, 14, 81, 178, 311, 402]

    def __init__(self, config: Optional[YawningConfig] = None):
        self._config = config or YawningConfig()
        self._mouth_open_start: Optional[float] = None
        self._is_yawn_active = False
        self._last_yawn_end_time = -9999.0  # Allow immediate first yawn
        self._yawn_timestamps: Deque[float] = deque()
        self._total_yawns: int = 0

    def update_config(self, config: YawningConfig) -> None:
        self._config = config

    @staticmethod
    def _calculate_mar(landmarks_2d: List[Tuple[float, float]]) -> float:
        """
        Computes Mouth Aspect Ratio (MAR):
        MAR = (|p13 - p14| + |p81 - p178| + |p311 - p402|) / (3 * |p78 - p308|)
        """
        p78 = landmarks_2d[78]
        p308 = landmarks_2d[308]
        p13 = landmarks_2d[13]
        p14 = landmarks_2d[14]
        p81 = landmarks_2d[81]
        p178 = landmarks_2d[178]
        p311 = landmarks_2d[311]
        p402 = landmarks_2d[402]

        width = math.hypot(p78[0] - p308[0], p78[1] - p308[1])
        if width < 1e-6:
            return 0.0

        v1 = math.hypot(p13[0] - p14[0], p13[1] - p14[1])
        v2 = math.hypot(p81[0] - p178[0], p81[1] - p178[1])
        v3 = math.hypot(p311[0] - p402[0], p311[1] - p402[1])

        return (v1 + v2 + v3) / (3.0 * width)

    def analyze(
        self,
        landmarks_2d: List[Tuple[float, float]],
        timestamp: Optional[float] = None
    ) -> MouthMetrics:
        """Calculates MAR and detects sustained yawning events."""
        if timestamp is None:
            timestamp = time.time()

        metrics = MouthMetrics()

        if not landmarks_2d or len(landmarks_2d) < 468:
            self._mouth_open_start = None
            return metrics

        # Extract landmarks for visualization
        metrics.raw_mouth_landmarks = [landmarks_2d[idx] for idx in self.ALL_MOUTH_INDICES]

        mar = self._calculate_mar(landmarks_2d)
        metrics.mar = round(mar, 3)

        # Mouth open condition
        is_open = mar >= self._config.mar_open_threshold
        metrics.is_mouth_open = is_open

        if is_open:
            if self._mouth_open_start is None:
                self._mouth_open_start = timestamp
            duration = timestamp - self._mouth_open_start
            metrics.yawn_duration_sec = round(duration, 2)

            # Check if duration exceeds threshold to distinguish from speech
            # Speech pauses are < 0.8s, yawns are sustained > 1.6s
            if duration >= self._config.yawn_min_duration_sec:
                # Check cooldown to prevent multiple alerts for one yawn
                if timestamp - self._last_yawn_end_time >= self._config.yawn_cooldown_sec:
                    metrics.is_yawning = True
                    if not self._is_yawn_active:
                        self._is_yawn_active = True
                        self._total_yawns += 1
                        self._yawn_timestamps.append(timestamp)
                        metrics.recent_yawn_detected = True
        else:
            if self._mouth_open_start is not None:
                duration = timestamp - self._mouth_open_start
                if self._is_yawn_active:
                    self._last_yawn_end_time = timestamp
                self._mouth_open_start = None
                self._is_yawn_active = False
            metrics.yawn_duration_sec = 0.0

        # Prune old yawn timestamps outside rolling window
        cutoff = timestamp - self._config.yawn_count_warning_window_sec
        while self._yawn_timestamps and self._yawn_timestamps[0] < cutoff:
            self._yawn_timestamps.popleft()

        metrics.yawn_count = self._total_yawns
        return metrics

    def reset(self) -> None:
        self._mouth_open_start = None
        self._is_yawn_active = False
        self._last_yawn_end_time = -9999.0
        self._yawn_timestamps.clear()
        self._total_yawns = 0
