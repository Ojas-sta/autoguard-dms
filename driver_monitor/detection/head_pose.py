"""
Head Pose Estimation and Nodding Detection for Driver Monitoring System.
Uses 3D facial model and OpenCV solvePnP to extract Pitch, Yaw, and Roll angles.
Detects sustained head-down postures, repeated nodding motions (microsleep indicators),
sustained abnormal orientations, and generates 3D pose projection axes.
"""

from collections import deque
import logging
import math
import time
from typing import Deque, List, Optional, Tuple
import cv2
import numpy as np

from driver_monitor.config import HeadPoseConfig
from driver_monitor.core.result_models import HeadPoseMetrics

logger = logging.getLogger(__name__)


class HeadPoseEstimator:
    """Estimates 3D head pose and monitors abnormal head postures."""

    # 3D generic anthropometric facial points (in arbitrary coordinate scale, mm)
    MODEL_POINTS_3D = np.array([
        (0.0, 0.0, 0.0),             # Nose tip (index 1)
        (0.0, -330.0, -65.0),        # Chin (index 152)
        (-225.0, 170.0, -135.0),     # Left eye outer corner (index 33)
        (225.0, 170.0, -135.0),      # Right eye outer corner (index 263)
        (-150.0, -150.0, -125.0),    # Left mouth corner (index 61)
        (150.0, -150.0, -125.0),     # Right mouth corner (index 291)
    ], dtype=np.float64)

    # Corresponding MediaPipe landmark indices
    LANDMARK_INDICES = [1, 152, 33, 263, 61, 291]

    def __init__(self, config: Optional[HeadPoseConfig] = None):
        self._config = config or HeadPoseConfig()
        self._head_down_start: Optional[float] = None
        self._head_turned_start: Optional[float] = None
        self._head_tilted_start: Optional[float] = None

        # Nodding detection state
        self._pitch_history: Deque[Tuple[float, float]] = deque(maxlen=60)  # (timestamp, pitch)
        self._nod_timestamps: Deque[float] = deque()
        self._is_nod_in_progress = False
        self._nod_baseline_pitch = 0.0

        # Calibration offset
        self._pitch_offset = 0.0
        self._yaw_offset = 0.0
        self._roll_offset = 0.0

    def update_config(self, config: HeadPoseConfig) -> None:
        self._config = config

    def calibrate(self, pitch: float, yaw: float, roll: float) -> None:
        """Zeros the current head pose as the neutral forward-looking position."""
        self._pitch_offset = pitch
        self._yaw_offset = yaw
        self._roll_offset = roll
        logger.info("Head pose calibrated: pitch_offset=%.1f, yaw_offset=%.1f, roll_offset=%.1f", pitch, yaw, roll)

    def estimate(
        self,
        landmarks_2d: List[Tuple[float, float]],
        frame_shape: Tuple[int, int],
        timestamp: Optional[float] = None
    ) -> HeadPoseMetrics:
        """Estimates head pose from 2D landmarks and returns HeadPoseMetrics."""
        if timestamp is None:
            timestamp = time.time()

        metrics = HeadPoseMetrics()

        if not landmarks_2d or len(landmarks_2d) < 468:
            self._head_down_start = None
            self._head_turned_start = None
            self._head_tilted_start = None
            return metrics

        h, w = frame_shape[:2]

        # Extract 2D image points for solvePnP
        image_points = np.array([
            landmarks_2d[idx] for idx in self.LANDMARK_INDICES
        ], dtype=np.float64)

        # Approximate camera intrinsic matrix
        focal_length = float(w)
        center = (float(w) / 2.0, float(h) / 2.0)
        camera_matrix = np.array([
            [focal_length, 0.0, center[0]],
            [0.0, focal_length, center[1]],
            [0.0, 0.0, 1.0]
        ], dtype=np.float64)
        dist_coeffs = np.zeros((4, 1), dtype=np.float64)

        # Solve Perspective-n-Point
        success, rvec, tvec = cv2.solvePnP(
            self.MODEL_POINTS_3D,
            image_points,
            camera_matrix,
            dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE
        )

        if not success:
            return metrics

        metrics.rotation_vector = rvec
        metrics.translation_vector = tvec

        # Convert rotation vector to rotation matrix
        rmat, _ = cv2.Rodrigues(rvec)

        # Compute Euler angles via RQDecomp3x3
        angles, _, _, _, _, _ = cv2.RQDecomp3x3(rmat)

        # OpenCV RQDecomp angles:
        # pitch (up/down): angles[0]
        # yaw (left/right): angles[1]
        # roll (tilt): angles[2]
        raw_pitch = float(angles[0])
        raw_yaw = float(angles[1])
        raw_roll = float(angles[2])

        # Normalize angles to neutral range [-180, 180]
        # On standard face model, pitch ~ 0 when level, positive = up, negative = down
        norm_pitch = (raw_pitch - self._pitch_offset)
        norm_yaw = (raw_yaw - self._yaw_offset)
        norm_roll = (raw_roll - self._roll_offset)

        # Keep in [-180, 180]
        norm_pitch = (norm_pitch + 180) % 360 - 180
        norm_yaw = (norm_yaw + 180) % 360 - 180
        norm_roll = (norm_roll + 180) % 360 - 180

        metrics.pitch = round(norm_pitch, 1)
        metrics.yaw = round(norm_yaw, 1)
        metrics.roll = round(norm_roll, 1)

        # Check Head-Down
        if metrics.pitch < self._config.pitch_down_threshold:
            metrics.is_head_down = True
            if self._head_down_start is None:
                self._head_down_start = timestamp
            metrics.head_down_duration_sec = round(timestamp - self._head_down_start, 2)
        else:
            metrics.is_head_down = False
            self._head_down_start = None
            metrics.head_down_duration_sec = 0.0

        # Check Head-Turned
        if abs(metrics.yaw) > self._config.yaw_turned_threshold:
            metrics.is_head_turned = True
            if self._head_turned_start is None:
                self._head_turned_start = timestamp
            metrics.head_turned_duration_sec = round(timestamp - self._head_turned_start, 2)
        else:
            metrics.is_head_turned = False
            self._head_turned_start = None
            metrics.head_turned_duration_sec = 0.0

        # Check Head-Tilted
        if abs(metrics.roll) > self._config.roll_tilted_threshold:
            metrics.is_head_tilted = True
            if self._head_tilted_start is None:
                self._head_tilted_start = timestamp
            metrics.head_tilted_duration_sec = round(timestamp - self._head_tilted_start, 2)
        else:
            metrics.is_head_tilted = False
            self._head_tilted_start = None
            metrics.head_tilted_duration_sec = 0.0

        # Nodding detection logic
        self._update_nodding(metrics.pitch, timestamp, metrics)

        # 3D coordinate axes projection for visualization
        metrics.projected_axes = self._project_axes(rvec, tvec, camera_matrix, dist_coeffs)

        return metrics

    def _update_nodding(self, current_pitch: float, timestamp: float, metrics: HeadPoseMetrics) -> None:
        """Detects micro-sleep nodding cycles (rapid downward pitch drop followed by rebound)."""
        self._pitch_history.append((timestamp, current_pitch))

        # Check for downward dip then upward return
        if len(self._pitch_history) >= 4:
            past_pitches = [p for t, p in self._pitch_history if timestamp - t <= 2.0]
            if past_pitches:
                min_past = min(past_pitches)
                max_past = max(past_pitches)
                diff = max_past - min_past
                # If there was a dip > nod_pitch_dip and currently recovering
                if diff >= self._config.nod_pitch_dip:
                    if not self._is_nod_in_progress and current_pitch > min_past + 6.0:
                        # Nod rebound completed
                        self._is_nod_in_progress = True
                        self._nod_timestamps.append(timestamp)
                        metrics.recent_nod_detected = True
                    elif current_pitch >= max_past - 3.0:
                        self._is_nod_in_progress = False

        # Clean old nods
        cutoff = timestamp - self._config.nod_time_window_sec
        while self._nod_timestamps and self._nod_timestamps[0] < cutoff:
            self._nod_timestamps.popleft()

        metrics.head_nod_count = len(self._nod_timestamps)

    def _project_axes(
        self,
        rvec: np.ndarray,
        tvec: np.ndarray,
        camera_matrix: np.ndarray,
        dist_coeffs: np.ndarray
    ) -> List[Tuple[int, int]]:
        """Projects 3D Cartesian axes (X, Y, Z) starting from nose tip (0,0,0) onto image."""
        axis_length = 150.0
        axis_points_3d = np.array([
            (0.0, 0.0, 0.0),                    # Origin (Nose tip)
            (axis_length, 0.0, 0.0),            # X-axis (Pitch/Roll right)
            (0.0, -axis_length, 0.0),           # Y-axis (Up)
            (0.0, 0.0, axis_length),            # Z-axis (Forward pointing out of face)
        ], dtype=np.float64)

        img_pts, _ = cv2.projectPoints(axis_points_3d, rvec, tvec, camera_matrix, dist_coeffs)
        pts = img_pts.reshape(-1, 2)
        return [(int(p[0]), int(p[1])) for p in pts]

    def reset(self) -> None:
        self._head_down_start = None
        self._head_turned_start = None
        self._head_tilted_start = None
        self._pitch_history.clear()
        self._nod_timestamps.clear()
        self._is_nod_in_progress = False
