"""
Drowsiness Decision Engine for Driver Monitoring System.
Combines multiple physiological and behavioral indicators (eye closure duration,
PERCLOS, blink rate, head nodding, head-down posture, and yawning)
into a unified drowsiness classification with hysteresis filtering.
"""

import logging
import time
from typing import List, Optional

from driver_monitor.config import EyeMonitoringConfig, HeadPoseConfig, YawningConfig
from driver_monitor.core.result_models import (
    DrowsinessResult, DrowsinessState, EyeMetrics, HeadPoseMetrics, MouthMetrics
)

logger = logging.getLogger(__name__)


class DrowsinessEngine:
    """Multi-signal decision engine for driver drowsiness and fatigue classification."""

    def __init__(
        self,
        eye_config: Optional[EyeMonitoringConfig] = None,
        head_config: Optional[HeadPoseConfig] = None,
        yawn_config: Optional[YawningConfig] = None
    ):
        self._eye_config = eye_config or EyeMonitoringConfig()
        self._head_config = head_config or HeadPoseConfig()
        self._yawn_config = yawn_config or YawningConfig()

        self._current_state = DrowsinessState.NORMAL
        self._state_enter_time = time.time()
        self._min_state_dwell_sec = 0.5  # Prevents rapid state jitter

    def evaluate(
        self,
        eyes: EyeMetrics,
        head: HeadPoseMetrics,
        mouth: MouthMetrics,
        perclos: float,
        timestamp: Optional[float] = None
    ) -> DrowsinessResult:
        """Evaluates driver metrics and classifies drowsiness state."""
        if timestamp is None:
            timestamp = time.time()

        reasons: List[str] = []
        target_state = DrowsinessState.NORMAL
        fatigue_score = 0.0

        # ---------------------------------------------------------
        # 1. Critical Level Triggers
        # ---------------------------------------------------------
        # Prolonged eye closure >= 2.5s
        if eyes.closure_duration_sec >= self._eye_config.closure_critical_sec:
            target_state = DrowsinessState.CRITICAL_DEMO_ALERT
            reasons.append(f"Severe eye closure: {eyes.closure_duration_sec:.1f}s")
            fatigue_score = max(fatigue_score, 1.0)

        # Prolonged eye closure >= 1.5s combined with head-down or nod
        elif (eyes.closure_duration_sec >= self._eye_config.closure_warning_sec and
              (head.is_head_down or head.head_nod_count > 0)):
            target_state = DrowsinessState.CRITICAL_DEMO_ALERT
            reasons.append(f"Microsleep with head nodding/drooping ({eyes.closure_duration_sec:.1f}s)")
            fatigue_score = max(fatigue_score, 0.95)

        # Very high PERCLOS (> 30%)
        elif perclos >= self._eye_config.perclos_critical_threshold:
            target_state = DrowsinessState.CRITICAL_DEMO_ALERT
            reasons.append(f"Critical PERCLOS: {perclos * 100:.1f}%")
            fatigue_score = max(fatigue_score, 0.90)

        # ---------------------------------------------------------
        # 2. Warning Level Triggers
        # ---------------------------------------------------------
        elif eyes.closure_duration_sec >= self._eye_config.closure_warning_sec:
            target_state = DrowsinessState.DROWSINESS_WARNING
            reasons.append(f"Prolonged eye closure: {eyes.closure_duration_sec:.1f}s")
            fatigue_score = max(fatigue_score, 0.75)

        elif head.head_down_duration_sec >= self._head_config.head_down_warning_sec:
            target_state = DrowsinessState.DROWSINESS_WARNING
            reasons.append(f"Sustained head-down posture: {head.head_down_duration_sec:.1f}s")
            fatigue_score = max(fatigue_score, 0.70)

        elif head.head_nod_count >= self._head_config.nod_count_warning:
            target_state = DrowsinessState.DROWSINESS_WARNING
            reasons.append(f"Repeated head nodding ({head.head_nod_count} nods detected)")
            fatigue_score = max(fatigue_score, 0.65)

        elif perclos >= self._eye_config.perclos_warning_threshold:
            target_state = DrowsinessState.DROWSINESS_WARNING
            reasons.append(f"High cumulative eye closure: {perclos * 100:.1f}%")
            fatigue_score = max(fatigue_score, 0.60)

        # ---------------------------------------------------------
        # 3. Attention Level Triggers
        # ---------------------------------------------------------
        elif eyes.closure_duration_sec >= self._eye_config.closure_attention_sec:
            target_state = DrowsinessState.ATTENTION
            reasons.append(f"Eye closure duration: {eyes.closure_duration_sec:.1f}s")
            fatigue_score = max(fatigue_score, 0.40)

        elif head.head_down_duration_sec >= self._head_config.head_down_attention_sec:
            target_state = DrowsinessState.ATTENTION
            reasons.append(f"Head beginning to droop: {head.head_down_duration_sec:.1f}s")
            fatigue_score = max(fatigue_score, 0.35)

        elif mouth.is_yawning:
            target_state = DrowsinessState.ATTENTION
            reasons.append(f"Yawn in progress: {mouth.yawn_duration_sec:.1f}s (MAR: {mouth.mar:.2f})")
            fatigue_score = max(fatigue_score, 0.35)

        elif mouth.yawn_count >= self._yawn_config.yawn_count_warning:
            target_state = DrowsinessState.ATTENTION
            reasons.append(f"Frequent yawning ({mouth.yawn_count} yawns in window)")
            fatigue_score = max(fatigue_score, 0.30)

        elif eyes.blink_frequency_bpm > 0 and eyes.blink_frequency_bpm < self._eye_config.low_blink_rate_threshold:
            target_state = DrowsinessState.ATTENTION
            reasons.append(f"Abnormally low blink rate: {eyes.blink_frequency_bpm} bpm")
            fatigue_score = max(fatigue_score, 0.25)

        # ---------------------------------------------------------
        # State Transition Hysteresis
        # ---------------------------------------------------------
        # Upgrades (escalation) happen immediately
        # Downgrades (de-escalation) require dwell time to prevent flickering
        if target_state.value != self._current_state.value:
            is_escalation = (
                (target_state == DrowsinessState.CRITICAL_DEMO_ALERT) or
                (target_state == DrowsinessState.DROWSINESS_WARNING and self._current_state != DrowsinessState.CRITICAL_DEMO_ALERT) or
                (target_state == DrowsinessState.ATTENTION and self._current_state == DrowsinessState.NORMAL)
            )
            if is_escalation or (timestamp - self._state_enter_time >= self._min_state_dwell_sec):
                self._current_state = target_state
                self._state_enter_time = timestamp

        result = DrowsinessResult(
            state=self._current_state,
            score=round(fatigue_score, 2),
            reasons=reasons,
            perclos=round(perclos, 3)
        )
        return result

    def reset(self) -> None:
        self._current_state = DrowsinessState.NORMAL
        self._state_enter_time = time.time()
