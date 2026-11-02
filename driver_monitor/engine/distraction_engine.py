"""
Driver Distraction Detection and Road Attention Analytics Engine.
Evaluates gaze direction, off-road glance durations, head orientation, and visual dwell time.
Classifies distraction states (NORMAL, BRIEF_GLANCE, ATTENTION_WARNING, VISUAL_DISTRACTION,
DOWNWARD_DISTRACTION, CRITICAL_DEMO_ALERT, UNKNOWN) and maintains rolling attention analytics with CSV export.
"""

from collections import deque
import csv
from datetime import datetime
import logging
import os
import time
from typing import Deque, List, Optional, Tuple

from driver_monitor.config import DistractionConfig
from driver_monitor.core.result_models import (
    DistractionMetrics, DistractionState, FaceDetectionResult, GazeDirection,
    GazeMetrics, HeadPoseMetrics
)

logger = logging.getLogger(__name__)


class DistractionEngine:
    """Multi-metric driver distraction evaluation and continuous road gaze analytics."""

    def __init__(self, config: Optional[DistractionConfig] = None):
        self._config = config or DistractionConfig()
        self._current_state = DistractionState.NORMAL
        self._off_road_start_time: Optional[float] = None
        self._longest_glance_sec: float = 0.0
        self._total_distraction_time_sec: float = 0.0

        # Glance counters
        self._downward_count = 0
        self._left_count = 0
        self._right_count = 0
        self._distraction_event_count = 0

        # Rolling window history for attention analytics: (timestamp, is_road)
        self._attention_history: Deque[Tuple[float, bool]] = deque(maxlen=1800)

        # Distraction events rolling queue for events-per-minute: (timestamp)
        self._event_timestamps: Deque[float] = deque()

        # Recorded observations for CSV export
        self._recorded_samples: List[dict] = []

        self._alerts_enabled = True

    def update_config(self, config: DistractionConfig) -> None:
        self._config = config

    def set_alerts_enabled(self, enabled: bool) -> None:
        self._alerts_enabled = enabled
        logger.info("Distraction alerts enabled set to: %s", enabled)

    @property
    def alerts_enabled(self) -> bool:
        return self._alerts_enabled

    def evaluate(
        self,
        gaze: GazeMetrics,
        head: HeadPoseMetrics,
        face: FaceDetectionResult,
        timestamp: Optional[float] = None
    ) -> DistractionMetrics:
        """Evaluates driver distraction kinematics and updates rolling analytics."""
        if timestamp is None:
            timestamp = time.time()

        metrics = DistractionMetrics()

        # 1. Handle Face Missing or Unknown Gaze
        if not face.detected or gaze.direction == GazeDirection.UNKNOWN:
            metrics.state = DistractionState.UNKNOWN
            metrics.is_distracted = False
            metrics.alert_title = "Tracking Unavailable"
            metrics.details = "Driver face or eye landmarks temporarily not confident"
            self._off_road_start_time = None
            self._update_analytics(metrics, timestamp, is_road_gaze=False, record_point=False)
            return metrics

        # 2. Check Gaze Direction
        is_road = (gaze.direction == GazeDirection.ROAD)
        self._attention_history.append((timestamp, is_road))

        if is_road:
            # Looking at road: Reset off-road timer
            if self._off_road_start_time is not None:
                glance_duration = timestamp - self._off_road_start_time
                if glance_duration > self._longest_glance_sec:
                    self._longest_glance_sec = round(glance_duration, 2)
                self._off_road_start_time = None

            metrics.state = DistractionState.NORMAL
            metrics.is_distracted = False
            metrics.off_road_glance_duration_sec = 0.0
            metrics.alert_title = "Driver Attentive"
            metrics.details = "Looking forward towards road"

        else:
            # Looking away from road
            if self._off_road_start_time is None:
                self._off_road_start_time = timestamp
                # Register glance direction counters
                if gaze.direction == GazeDirection.DOWN:
                    self._downward_count += 1
                elif gaze.direction == GazeDirection.LEFT_MIRROR:
                    self._left_count += 1
                elif gaze.direction == GazeDirection.RIGHT_MIRROR:
                    self._right_count += 1

            glance_dur = timestamp - self._off_road_start_time
            metrics.off_road_glance_duration_sec = round(glance_dur, 2)

            if glance_dur > self._longest_glance_sec:
                self._longest_glance_sec = round(glance_dur, 2)

            # Classify Distraction Severity based on Duration and Context
            if glance_dur < self._config.brief_glance_max_sec:
                # Brief mirror check / peripheral scan (< 1.0s)
                metrics.state = DistractionState.BRIEF_GLANCE
                metrics.is_distracted = False
                metrics.alert_title = "Brief Scan"
                metrics.details = f"Normal peripheral glance to {gaze.direction.value} ({glance_dur:.1f}s)"

            elif glance_dur < self._config.attention_warning_sec:
                # Attention Warning (1.0s - 1.5s)
                metrics.state = DistractionState.ATTENTION_WARNING
                metrics.is_distracted = True
                metrics.alert_title = "Attention Warning"
                metrics.details = f"Off-road glance to {gaze.direction.value} exceeding grace period ({glance_dur:.1f}s)"

            elif gaze.direction == GazeDirection.DOWN and glance_dur >= self._config.downward_distraction_sec:
                # Downward Distraction (Console / Phone)
                metrics.state = DistractionState.DOWNWARD_DISTRACTION
                metrics.is_distracted = True
                metrics.alert_title = "Downward Distraction"
                metrics.details = f"Extended downward gaze towards console/phone ({glance_dur:.1f}s)"
                self._record_distraction_event(timestamp)

            elif glance_dur >= self._config.critical_distraction_sec or (glance_dur >= self._config.prolonged_distraction_sec and head.is_head_turned):
                # Critical Alert (> 3.5s or combined off-road head turn + gaze)
                metrics.state = DistractionState.CRITICAL_DEMO_ALERT
                metrics.is_distracted = True
                metrics.alert_title = "CRITICAL DISTRACTION ALERT"
                metrics.details = f"Dangerous off-road dwell time ({glance_dur:.1f}s) towards {gaze.direction.value}"
                self._record_distraction_event(timestamp)

            else:
                # Visual Distraction (> 2.0s)
                metrics.state = DistractionState.VISUAL_DISTRACTION
                metrics.is_distracted = True
                metrics.alert_title = "Visual Distraction"
                metrics.details = f"Prolonged off-road gaze ({glance_dur:.1f}s) away from forward road"
                self._record_distraction_event(timestamp)

            self._total_distraction_time_sec += 0.033  # Approx nominal frame interval

        # Update cumulative metrics
        metrics.longest_off_road_glance_sec = self._longest_glance_sec
        metrics.total_distraction_duration_sec = round(self._total_distraction_time_sec, 1)
        metrics.downward_glance_count = self._downward_count
        metrics.left_glance_count = self._left_count
        metrics.right_glance_count = self._right_count
        metrics.distraction_event_count = self._distraction_event_count

        self._update_analytics(metrics, timestamp, is_road_gaze=is_road, record_point=True, gaze=gaze, head=head)
        self._current_state = metrics.state

        return metrics

    def _record_distraction_event(self, timestamp: float) -> None:
        """Records distinct distraction incident with rate limiting."""
        if not self._event_timestamps or (timestamp - self._event_timestamps[-1] > 2.5):
            self._event_timestamps.append(timestamp)
            self._distraction_event_count += 1

    def _update_analytics(
        self,
        metrics: DistractionMetrics,
        timestamp: float,
        is_road_gaze: bool,
        record_point: bool,
        gaze: Optional[GazeMetrics] = None,
        head: Optional[HeadPoseMetrics] = None
    ) -> None:
        """Calculates rolling road gaze % and events per minute."""
        cutoff = timestamp - self._config.rolling_window_sec

        # 1. Road vs Off-Road Percentage over rolling window
        road_count = 0
        total_count = 0
        for t, road in self._attention_history:
            if t >= cutoff:
                total_count += 1
                if road:
                    road_count += 1

        if total_count > 0:
            road_pct = (road_count / float(total_count)) * 100.0
            metrics.road_gaze_percent = round(road_pct, 1)
            metrics.off_road_gaze_percent = round(100.0 - road_pct, 1)
        else:
            metrics.road_gaze_percent = 100.0
            metrics.off_road_gaze_percent = 0.0

        # 2. Events per minute
        while self._event_timestamps and self._event_timestamps[0] < cutoff:
            self._event_timestamps.popleft()

        window_min = max(0.1, min(self._config.rolling_window_sec, timestamp - (self._event_timestamps[0] if self._event_timestamps else timestamp)) / 60.0)
        metrics.events_per_minute = round(len(self._event_timestamps) / window_min, 1)

        # 3. Buffer sample for CSV export (sample every ~0.5s to keep file compact)
        if record_point and (not self._recorded_samples or timestamp - float(self._recorded_samples[-1]["timestamp_sec"]) >= 0.5):
            self._recorded_samples.append({
                "timestamp_sec": round(timestamp, 2),
                "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                "gaze_direction": gaze.direction.value if gaze else "UNKNOWN",
                "is_road_gaze": is_road_gaze,
                "distraction_state": metrics.state.value,
                "off_road_glance_duration_sec": metrics.off_road_glance_duration_sec,
                "road_gaze_percent": metrics.road_gaze_percent,
                "head_pitch": head.pitch if head else 0.0,
                "head_yaw": head.yaw if head else 0.0,
                "head_roll": head.roll if head else 0.0
            })

    def export_csv(self, output_dir: Optional[str] = None) -> str:
        """Exports recorded gaze and distraction analytics to CSV."""
        if output_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            output_dir = os.path.join(base_dir, "logs")

        os.makedirs(output_dir, exist_ok=True)
        filename = f"gaze_analytics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        file_path = os.path.join(output_dir, filename)

        fieldnames = [
            "timestamp_sec", "datetime", "gaze_direction", "is_road_gaze",
            "distraction_state", "off_road_glance_duration_sec", "road_gaze_percent",
            "head_pitch", "head_yaw", "head_roll"
        ]

        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in self._recorded_samples:
                writer.writerow(row)

        logger.info("Exported %d gaze analytics records to %s", len(self._recorded_samples), file_path)
        return file_path

    def reset(self) -> None:
        """Alias for reset_statistics to conform with standard pipeline interfaces."""
        self.reset_statistics()

    def reset_statistics(self) -> None:
        """Resets running counters and glance timers."""
        self._off_road_start_time = None
        self._longest_glance_sec = 0.0
        self._total_distraction_time_sec = 0.0
        self._downward_count = 0
        self._left_count = 0
        self._right_count = 0
        self._distraction_event_count = 0
        self._attention_history.clear()
        self._event_timestamps.clear()
        self._recorded_samples.clear()
        self._current_state = DistractionState.NORMAL
        logger.info("Distraction statistics and analytics reset.")
