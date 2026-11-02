"""
Road Gaze Estimation and Classification Module.
Fuses normalized iris positions with calibrated 3D head pose to classify driver gaze into:
ROAD, LEFT_MIRROR, RIGHT_MIRROR, DOWN, UP, AWAY, and UNKNOWN.
Maintains continuous dwell time and generates 2D gaze visualization vectors.

==============================================================================
Subsystem: Multimodal Road Gaze Estimation & Attention Zone Classification
Architecture: Powered by cl0ud (https://github.com/Ojas-sta/cl0ud-brand-engineering)
Co-Engineered by: Ojas Singh <ojasctc@gmail.com>
==============================================================================
"""

import logging
import math
import time
from typing import Optional, Tuple

from driver_monitor.calibration.gaze_calibration import GazeCalibrationManager, GazeCalibrationProfile
from driver_monitor.config import GazeConfig
from driver_monitor.core.result_models import (
    FaceDetectionResult, EyeMetrics, EyeStatus, GazeDirection, GazeMetrics,
    HeadPoseMetrics, IrisMetrics
)

logger = logging.getLogger(__name__)


class GazeEstimator:
    """Estimates driver gaze point and classifies driving attention zones."""

    def __init__(
        self,
        config: Optional[GazeConfig] = None,
        calibration_mgr: Optional[GazeCalibrationManager] = None
    ):
        self._config = config or GazeConfig()
        self._calib_mgr = calibration_mgr or GazeCalibrationManager()
        self._current_direction = GazeDirection.UNKNOWN
        self._dwell_start_time: Optional[float] = None
        self._smoothed_gaze_yaw: Optional[float] = None
        self._smoothed_gaze_pitch: Optional[float] = None

    def update_config(self, config: GazeConfig) -> None:
        self._config = config

    @property
    def calibration_profile(self) -> GazeCalibrationProfile:
        return self._calib_mgr.profile

    def estimate(
        self,
        iris: IrisMetrics,
        head: HeadPoseMetrics,
        face: FaceDetectionResult,
        eyes: EyeMetrics,
        timestamp: Optional[float] = None
    ) -> GazeMetrics:
        """Estimates driver gaze direction and dwell time."""
        if timestamp is None:
            timestamp = time.time()

        metrics = GazeMetrics()

        # Check face and eye validity
        if not face.detected or eyes.overall_status != EyeStatus.OPEN:
            metrics.direction = GazeDirection.UNKNOWN
            metrics.confidence = 0.0
            metrics.is_looking_at_road = False
            self._current_direction = GazeDirection.UNKNOWN
            self._dwell_start_time = None
            return metrics

        profile = self._calib_mgr.profile

        # Compute iris relative shift from calibrated neutral center
        iris_dx = 0.0
        iris_dy = 0.0
        if iris.is_valid:
            # Shift in [-1.0, 1.0] range
            iris_dx = (iris.avg_iris_ratio_x - profile.iris_neutral_x) * 2.2
            iris_dy = (iris.avg_iris_ratio_y - profile.iris_neutral_y) * 2.2

        # Fuse iris displacement with calibrated head orientation
        # An iris horizontal shift of 1.0 corresponds to roughly 22 degrees of eye rotation
        eye_yaw_deg = iris_dx * 22.0
        eye_pitch_deg = iris_dy * 18.0

        # Weighted combination: Gaze = (Head Pose) + (Eye Gaze)
        fused_yaw = head.yaw + eye_yaw_deg
        fused_pitch = head.pitch + eye_pitch_deg

        # Temporal smoothing
        if self._smoothed_gaze_yaw is None:
            self._smoothed_gaze_yaw = fused_yaw
            self._smoothed_gaze_pitch = fused_pitch
        else:
            alpha = self._config.smoothing_factor
            self._smoothed_gaze_yaw = alpha * fused_yaw + (1.0 - alpha) * self._smoothed_gaze_yaw
            self._smoothed_gaze_pitch = alpha * fused_pitch + (1.0 - alpha) * self._smoothed_gaze_pitch

        gaze_yaw = self._smoothed_gaze_yaw
        gaze_pitch = self._smoothed_gaze_pitch

        # Normalized coordinates [-1.0, 1.0] for dashboard dials
        metrics.horizontal_gaze = max(-1.0, min(1.0, gaze_yaw / 45.0))
        metrics.vertical_gaze = max(-1.0, min(1.0, gaze_pitch / 45.0))

        # Classification against calibrated boundaries
        direction = GazeDirection.AWAY
        confidence = 0.85

        # Check Road zone
        if (profile.road_yaw_min <= gaze_yaw <= profile.road_yaw_max and
            profile.road_pitch_min <= gaze_pitch <= profile.road_pitch_max):
            direction = GazeDirection.ROAD
            confidence = 0.95

        # Check Downward (console / instrument cluster / phone)
        elif gaze_pitch > profile.down_console_pitch:
            direction = GazeDirection.DOWN
            confidence = 0.90

        # Check Upward (sun visor / rear-view)
        elif gaze_pitch < profile.up_ceiling_pitch:
            direction = GazeDirection.UP
            confidence = 0.85

        # Check Left Mirror
        elif gaze_yaw < profile.left_mirror_yaw:
            direction = GazeDirection.LEFT_MIRROR
            confidence = 0.90

        # Check Right Mirror
        elif gaze_yaw > profile.right_mirror_yaw:
            direction = GazeDirection.RIGHT_MIRROR
            confidence = 0.90

        else:
            direction = GazeDirection.AWAY
            confidence = 0.80

        metrics.direction = direction
        metrics.confidence = confidence
        metrics.is_looking_at_road = (direction == GazeDirection.ROAD)

        # Dwell time tracking in current gaze zone
        if direction == self._current_direction:
            if self._dwell_start_time is None:
                self._dwell_start_time = timestamp
            metrics.dwell_time_sec = round(timestamp - self._dwell_start_time, 2)
        else:
            self._current_direction = direction
            self._dwell_start_time = timestamp
            metrics.dwell_time_sec = 0.0

        # Compute 2D gaze origin and target vector for visualization
        if iris.is_valid and iris.left_iris_center[0] > 0 and iris.right_iris_center[0] > 0:
            ox = int((iris.left_iris_center[0] + iris.right_iris_center[0]) / 2.0)
            oy = int((iris.left_iris_center[1] + iris.right_iris_center[1]) / 2.0)
        elif face.bbox and face.bbox[2] > 0:
            ox = int(face.bbox[0] + face.bbox[2] / 2.0)
            oy = int(face.bbox[1] + face.bbox[3] * 0.35)
        else:
            ox, oy = (320, 240)

        # Vector arrow length & direction
        arrow_len = 65.0
        rad_yaw = math.radians(gaze_yaw)
        rad_pitch = math.radians(gaze_pitch)

        tx = int(ox + arrow_len * math.sin(rad_yaw))
        ty = int(oy + arrow_len * math.sin(rad_pitch))

        metrics.gaze_origin_2d = (ox, oy)
        metrics.gaze_target_2d = (tx, ty)

        # If active calibration in progress, feed sample to manager
        if self._calib_mgr.is_active:
            self._calib_mgr.record_sample(
                iris.avg_iris_ratio_x, iris.avg_iris_ratio_y, head.pitch, head.yaw
            )

        return metrics

    def reset(self) -> None:
        self._current_direction = GazeDirection.UNKNOWN
        self._dwell_start_time = None
        self._smoothed_gaze_yaw = None
        self._smoothed_gaze_pitch = None
