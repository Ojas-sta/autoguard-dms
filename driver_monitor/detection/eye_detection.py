"""
Eye Monitoring and Blink Analysis for Driver Monitoring System.
Calculates Eye Aspect Ratio (EAR) for left and right eyes using standard MediaPipe landmarks.
Tracks eye closure duration, blink frequency, and prolonged eye closure events.
"""

from collections import deque
import logging
import math
import time
from typing import Deque, List, Optional, Tuple

from driver_monitor.config import EyeMonitoringConfig
from driver_monitor.core.result_models import EyeMetrics, EyeStatus

logger = logging.getLogger(__name__)


class EyeDetector:
    """Monitors driver eye status, closure duration, and blink rates."""

    # 6-point landmark indices for left and right eyes in MediaPipe Face Mesh
    LEFT_EYE_INDICES = [33, 160, 158, 133, 153, 144]
    RIGHT_EYE_INDICES = [362, 385, 387, 263, 373, 380]

    def __init__(self, config: Optional[EyeMonitoringConfig] = None):
        self._config = config or EyeMonitoringConfig()
        self._closure_start_time: Optional[float] = None
        self._last_state: EyeStatus = EyeStatus.OPEN
        self._blink_timestamps: Deque[float] = deque()
        self._total_blinks: int = 0
        self._last_open_time: float = time.time()

    def update_config(self, config: EyeMonitoringConfig) -> None:
        self._config = config

    @staticmethod
    def _calculate_ear(eye_points: List[Tuple[float, float]]) -> float:
        """
        Computes EAR using Soukupová and Čech formula:
        EAR = (|p2 - p6| + |p3 - p5|) / (2 * |p1 - p4|)
        """
        if len(eye_points) < 6:
            return 0.0

        p1, p2, p3, p4, p5, p6 = eye_points[:6]

        # Vertical distances
        v1 = math.hypot(p2[0] - p6[0], p2[1] - p6[1])
        v2 = math.hypot(p3[0] - p5[0], p3[1] - p5[1])

        # Horizontal distance
        h = math.hypot(p1[0] - p4[0], p1[1] - p4[1])

        if h < 1e-6:
            return 0.0

        return (v1 + v2) / (2.0 * h)

    def analyze(
        self,
        landmarks_2d: List[Tuple[float, float]],
        timestamp: Optional[float] = None
    ) -> EyeMetrics:
        """Analyzes 2D facial landmarks and returns EyeMetrics."""
        if timestamp is None:
            timestamp = time.time()

        metrics = EyeMetrics()

        if not landmarks_2d or len(landmarks_2d) < 468:
            metrics.overall_status = EyeStatus.UNKNOWN
            metrics.left_status = EyeStatus.UNKNOWN
            metrics.right_status = EyeStatus.UNKNOWN
            self._closure_start_time = None
            return metrics

        # Extract eye coordinates
        left_pts = [landmarks_2d[idx] for idx in self.LEFT_EYE_INDICES]
        right_pts = [landmarks_2d[idx] for idx in self.RIGHT_EYE_INDICES]

        metrics.raw_left_landmarks = left_pts
        metrics.raw_right_landmarks = right_pts

        left_ear = self._calculate_ear(left_pts)
        right_ear = self._calculate_ear(right_pts)
        avg_ear = (left_ear + right_ear) / 2.0

        metrics.left_ear = round(left_ear, 3)
        metrics.right_ear = round(right_ear, 3)
        metrics.avg_ear = round(avg_ear, 3)

        # Determine individual status
        metrics.left_status = EyeStatus.CLOSED if left_ear < self._config.ear_closed_threshold else EyeStatus.OPEN
        metrics.right_status = EyeStatus.CLOSED if right_ear < self._config.ear_closed_threshold else EyeStatus.OPEN

        # Overall eye status with hysteresis
        if avg_ear < self._config.ear_closed_threshold:
            current_state = EyeStatus.CLOSED
        elif avg_ear > self._config.ear_open_threshold:
            current_state = EyeStatus.OPEN
        else:
            current_state = self._last_state

        metrics.overall_status = current_state

        # Handle state transitions and duration
        if current_state == EyeStatus.CLOSED:
            if self._closure_start_time is None:
                self._closure_start_time = timestamp
            metrics.closure_duration_sec = round(timestamp - self._closure_start_time, 2)
        else:
            if self._closure_start_time is not None:
                duration = timestamp - self._closure_start_time
                # Valid blink detection
                if self._config.blink_min_duration_sec <= duration <= self._config.blink_max_duration_sec:
                    self._total_blinks += 1
                    self._blink_timestamps.append(timestamp)
                self._closure_start_time = None
            metrics.closure_duration_sec = 0.0
            self._last_open_time = timestamp

        self._last_state = current_state

        # Check prolonged closure
        if metrics.closure_duration_sec >= self._config.closure_warning_sec:
            metrics.is_prolonged_closure = True

        # Clean old blinks outside rolling window
        cutoff = timestamp - self._config.blink_rate_window_sec
        while self._blink_timestamps and self._blink_timestamps[0] < cutoff:
            self._blink_timestamps.popleft()

        # Calculate blink frequency (blinks per minute)
        window_duration_min = max(0.1, min(self._config.blink_rate_window_sec, timestamp - (self._blink_timestamps[0] if self._blink_timestamps else timestamp)) / 60.0)
        # Standardized rate scaled to 60s
        metrics.blink_count = self._total_blinks
        metrics.blink_frequency_bpm = round(len(self._blink_timestamps) * (60.0 / self._config.blink_rate_window_sec), 1)

        return metrics

    def reset(self) -> None:
        """Resets tracking history."""
        self._closure_start_time = None
        self._last_state = EyeStatus.OPEN
        self._blink_timestamps.clear()
        self._total_blinks = 0
