"""
Abnormal Head Movement and Dizziness Demonstration Engine.
Implements experimental behavioral indicators (sustained tilt, unusual movement patterns,
sustained abnormal orientations, face unavailability, and slumping).
Provides descriptive non-diagnostic alerts for research and demonstration.

==============================================================================
Subsystem: Abnormal Movement Analysis & Slump Emergency Detection
Architecture: Powered by cl0ud (https://github.com/Ojas-sta/cl0ud-brand-engineering)
Co-Engineered by: Ojas Singh <ojasctc@gmail.com>
==============================================================================
"""

import logging
import time
from typing import Optional

from driver_monitor.config import AbnormalMovementConfig, HeadPoseConfig
from driver_monitor.core.result_models import (
    AbnormalMovementResult, AbnormalMovementState, FaceDetectionResult, HeadPoseMetrics
)

logger = logging.getLogger(__name__)


class AbnormalMovementEngine:
    """Evaluates head kinematics and attention patterns for abnormal behaviors."""

    def __init__(
        self,
        abnormal_config: Optional[AbnormalMovementConfig] = None,
        head_config: Optional[HeadPoseConfig] = None
    ):
        self._abnormal_config = abnormal_config or AbnormalMovementConfig()
        self._head_config = head_config or HeadPoseConfig()
        self._current_state = AbnormalMovementState.NORMAL
        self._state_enter_time = time.time()

    def evaluate(
        self,
        head: HeadPoseMetrics,
        face: FaceDetectionResult,
        angular_jerk: float,
        timestamp: Optional[float] = None
    ) -> AbnormalMovementResult:
        """Evaluates behavioral kinematics and generates descriptive alerts."""
        if timestamp is None:
            timestamp = time.time()

        state = AbnormalMovementState.NORMAL
        title = ""
        details = ""
        is_active = False

        # 1. Check for Possible Driver Emergency (Sudden severe slump or prolonged unresponsive posture)
        if head.is_head_down and head.pitch < self._abnormal_config.slump_pitch_threshold and head.head_down_duration_sec >= self._abnormal_config.slump_motionless_sec:
            state = AbnormalMovementState.POSSIBLE_DRIVER_EMERGENCY_DEMO
            title = "Possible Driver Emergency – Demo"
            details = f"Severe head slump detected ({head.pitch:.1f}°) sustained for {head.head_down_duration_sec:.1f}s"
            is_active = True

        # 2. Check Extended Face Unavailability
        elif not face.detected and face.face_lost_duration_sec >= self._abnormal_config.face_lost_warning_sec:
            state = AbnormalMovementState.DRIVER_ATTENTION_LOST
            title = "Driver Attention Lost"
            details = f"Driver face out of camera view for {face.face_lost_duration_sec:.1f}s"
            is_active = True

        # 3. Check Sustained Head Turned Away (Looking at phone or passenger)
        elif head.is_head_turned and head.head_turned_duration_sec >= self._head_config.head_turned_warning_sec:
            state = AbnormalMovementState.DRIVER_ATTENTION_LOST
            title = "Driver Attention Lost"
            direction = "right" if head.yaw > 0 else "left"
            details = f"Driver head turned {direction} ({abs(head.yaw):.1f}°) for {head.head_turned_duration_sec:.1f}s"
            is_active = True

        # 4. Check Sustained Abnormal Tilt (Head falling sideways)
        elif head.is_head_tilted and head.head_tilted_duration_sec >= self._head_config.head_tilted_warning_sec:
            state = AbnormalMovementState.ABNORMAL_HEAD_POSTURE
            title = "Abnormal Head Posture"
            direction = "right" if head.roll > 0 else "left"
            details = f"Sustained head tilt to {direction} ({abs(head.roll):.1f}°) for {head.head_tilted_duration_sec:.1f}s"
            is_active = True

        # 5. Check Unusual Head Movement (Rapid shaking / erratic movement / disorientation)
        elif angular_jerk >= self._abnormal_config.erratic_jerk_threshold:
            state = AbnormalMovementState.UNUSUAL_HEAD_MOVEMENT
            title = "Unusual Head Movement"
            details = f"High angular jerk / erratic movement pattern ({angular_jerk:.1f}°/s)"
            is_active = True

        self._current_state = state
        return AbnormalMovementResult(
            state=state,
            alert_title=title,
            details=details,
            is_active=is_active
        )

    def reset(self) -> None:
        self._current_state = AbnormalMovementState.NORMAL
        self._state_enter_time = time.time()
