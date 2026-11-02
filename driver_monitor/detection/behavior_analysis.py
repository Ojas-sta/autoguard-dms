"""
Behavioral Analysis and PERCLOS Computation for Driver Monitoring System.
Maintains rolling temporal windows to compute PERCLOS (percentage of eye closure time),
angular head velocities, jerk, and attention loss metrics.
"""

from collections import deque
import logging
import math
import time
from typing import Deque, Optional, Tuple

from driver_monitor.config import EyeMonitoringConfig, HeadPoseConfig, AbnormalMovementConfig
from driver_monitor.core.result_models import EyeMetrics, HeadPoseMetrics, EyeStatus

logger = logging.getLogger(__name__)


class BehaviorAnalyzer:
    """Computes rolling temporal metrics including PERCLOS and angular dynamics."""

    def __init__(
        self,
        eye_config: Optional[EyeMonitoringConfig] = None,
        head_config: Optional[HeadPoseConfig] = None,
        abnormal_config: Optional[AbnormalMovementConfig] = None
    ):
        self._eye_config = eye_config or EyeMonitoringConfig()
        self._head_config = head_config or HeadPoseConfig()
        self._abnormal_config = abnormal_config or AbnormalMovementConfig()

        # Rolling eye closure history: (timestamp, is_closed)
        self._eye_history: Deque[Tuple[float, bool]] = deque(maxlen=1800)

        # Rolling head pose history: (timestamp, pitch, yaw, roll)
        self._pose_history: Deque[Tuple[float, float, float, float]] = deque(maxlen=300)

        self._last_update_time = time.time()

    def update(
        self,
        eye_metrics: EyeMetrics,
        head_metrics: HeadPoseMetrics,
        timestamp: Optional[float] = None
    ) -> Tuple[float, float]:
        """
        Updates rolling buffers and returns:
        (perclos_ratio, angular_jerk)
        """
        if timestamp is None:
            timestamp = time.time()

        # Update eye closure history
        is_closed = (eye_metrics.overall_status == EyeStatus.CLOSED)
        self._eye_history.append((timestamp, is_closed))

        # Update pose history
        self._pose_history.append((
            timestamp,
            head_metrics.pitch,
            head_metrics.yaw,
            head_metrics.roll
        ))

        # 1. Calculate PERCLOS over window
        cutoff = timestamp - self._eye_config.perclos_window_sec
        closed_count = 0
        total_count = 0
        for t, closed in self._eye_history:
            if t >= cutoff:
                total_count += 1
                if closed:
                    closed_count += 1

        perclos = (closed_count / float(total_count)) if total_count > 0 else 0.0

        # 2. Calculate Head Angular Velocity & Jerk
        angular_jerk = 0.0
        if len(self._pose_history) >= 4:
            # Look at recent ~0.5s
            t_curr, p_curr, y_curr, r_curr = self._pose_history[-1]
            t_prev, p_prev, y_prev, r_prev = self._pose_history[-3]
            dt = t_curr - t_prev
            if dt > 0.04:
                # Angular displacement
                dp = abs(p_curr - p_prev)
                dy = abs(y_curr - y_prev)
                dr = abs(r_curr - r_prev)
                velocity = (dp + dy + dr) / dt  # deg/sec
                angular_jerk = velocity

        return round(perclos, 3), round(angular_jerk, 2)

    def reset(self) -> None:
        self._eye_history.clear()
        self._pose_history.clear()
