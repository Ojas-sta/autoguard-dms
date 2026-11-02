"""
Head Pose Estimation and Kinematics Analysis for Driver Monitoring System.
Uses 3D facial anthropometric model and OpenCV solvePnP to extract Pitch, Yaw, and Roll angles.
Corrects coordinate conventions to eliminate angle wrapping and false emergency triggers.
Includes multi-observation neutral calibration and microsleep nodding detection.

==============================================================================
Subsystem: 3D Head Pose Kinematics & Coordinate Decomposition
Architecture: Powered by cl0ud (https://github.com/Ojas-sta/cl0ud-brand-engineering)
Co-Engineered by: Ojas Singh <ojasctc@gmail.com>
==============================================================================
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
    """Estimates 3D head pose with corrected OpenCV camera coordinate conventions."""

    # Canonical 3D anthropometric face model aligned with OpenCV camera coordinate frame:
    # +X points right (image right / subject's left)
    # +Y points down (towards chin)
    # +Z points out of the face towards camera (closer to camera)
    MODEL_POINTS_3D = np.array([
        (0.0, 0.0, 0.0),             # Nose tip (index 1)
        (0.0, 330.0, -65.0),         # Chin (index 152) -> +Y, -Z
        (-225.0, -170.0, -135.0),    # Left in image (index 33) -> -X, -Y, -Z
        (225.0, -170.0, -135.0),     # Right in image (index 263) -> +X, -Y, -Z
        (-150.0, 150.0, -125.0),     # Left mouth (index 61) -> -X, +Y, -Z
        (150.0, 150.0, -125.0)       # Right mouth (index 291) -> +X, +Y, -Z
    ], dtype=np.float64)

    LANDMARK_INDICES = [1, 152, 33, 263, 61, 291]

    AXIS_POINTS_3D = np.array([
        (0.0, 0.0, 0.0),        # Origin (Nose tip)
        (150.0, 0.0, 0.0),      # X-axis (Right)
        (0.0, 150.0, 0.0),      # Y-axis (Down)
        (0.0, 0.0, 150.0),      # Z-axis (Forward)
    ], dtype=np.float64)

    def __init__(self, config: Optional[HeadPoseConfig] = None):
        self._config = config or HeadPoseConfig()
        self._head_down_start: Optional[float] = None
        self._head_turned_start: Optional[float] = None
        self._head_tilted_start: Optional[float] = None

        # Nodding detection state
        self._pitch_history: Deque[Tuple[float, float]] = deque(maxlen=60)  # (timestamp, pitch)
        self._nod_timestamps: Deque[float] = deque()
        self._is_nod_in_progress = False

        # Neutral calibration baseline offsets
        self._pitch_offset = 0.0
        self._yaw_offset = 0.0
        self._roll_offset = 0.0
        self._calibration_confidence = 1.0

        # Extrinsic warm-start cache for fast solvePnP
        self._last_rvec: Optional[np.ndarray] = None
        self._last_tvec: Optional[np.ndarray] = None

        # Camera intrinsic matrix cache (avoids per-frame numpy reallocations)
        self._cached_cam_shape: Optional[Tuple[int, int]] = None
        self._cached_cam_matrix: Optional[np.ndarray] = None
        self._cached_dist_coeffs = np.zeros((4, 1), dtype=np.float64)

        # Multi-observation calibration buffer
        self._is_calibrating = False
        self._calibration_samples: List[Tuple[float, float, float]] = []
        self._calibration_target_samples = 25

    def update_config(self, config: HeadPoseConfig) -> None:
        self._config = config

    def start_multi_observation_calibration(self, num_samples: int = 25, num_observations: Optional[int] = None) -> None:
        """Initiates a multi-frame neutral head pose calibration."""
        if num_observations is not None:
            num_samples = num_observations
        self._is_calibrating = True
        self._calibration_target_samples = num_samples
        self._calibration_samples.clear()
        logger.info("Started multi-observation head pose calibration (target: %d frames)", num_samples)

    def is_calibrating(self) -> bool:
        return self._is_calibrating

    def get_calibration_progress(self) -> float:
        if not self._is_calibrating or self._calibration_target_samples == 0:
            return 1.0
        return len(self._calibration_samples) / float(self._calibration_target_samples)

    def calibrate(self, pitch: float, yaw: float, roll: float) -> None:
        """Direct instantaneous single-point calibration fallback."""
        self._pitch_offset = pitch
        self._yaw_offset = yaw
        self._roll_offset = roll
        self._calibration_confidence = 0.85
        logger.info("Direct head pose calibrated: pitch=%.1f, yaw=%.1f, roll=%.1f", pitch, yaw, roll)

    def set_calibration_offsets(self, pitch_offset: float, yaw_offset: float, roll_offset: float, confidence: float = 1.0) -> None:
        """Sets calibrated neutral offsets."""
        self._pitch_offset = pitch_offset
        self._yaw_offset = yaw_offset
        self._roll_offset = roll_offset
        self._calibration_confidence = confidence

    def get_calibration_offsets(self) -> Tuple[float, float, float, float]:
        """Returns (pitch_offset, yaw_offset, roll_offset, confidence)."""
        return (self._pitch_offset, self._yaw_offset, self._roll_offset, self._calibration_confidence)

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

        if not landmarks_2d or len(landmarks_2d) < 468 or frame_shape[0] == 0 or frame_shape[1] == 0:
            self._head_down_start = None
            self._head_turned_start = None
            self._head_tilted_start = None
            return metrics

        h, w = frame_shape[:2]

        # Extract 2D image points for solvePnP
        image_points = np.array([
            landmarks_2d[idx] for idx in self.LANDMARK_INDICES
        ], dtype=np.float64)

        # Re-use cached camera intrinsic matrix unless frame dimensions change
        if self._cached_cam_shape != (w, h):
            focal_length = float(w)
            center = (float(w) / 2.0, float(h) / 2.0)
            self._cached_cam_matrix = np.array([
                [focal_length, 0.0, center[0]],
                [0.0, focal_length, center[1]],
                [0.0, 0.0, 1.0]
            ], dtype=np.float64)
            self._cached_cam_shape = (w, h)

        camera_matrix = self._cached_cam_matrix
        dist_coeffs = self._cached_dist_coeffs

        # Solve Perspective-n-Point with warm-start extrinsic guess (3x faster on ARM Cortex-A72)
        use_guess = (self._last_rvec is not None and self._last_tvec is not None)
        if use_guess:
            rvec = self._last_rvec.copy()
            tvec = self._last_tvec.copy()
            success, rvec, tvec = cv2.solvePnP(
                self.MODEL_POINTS_3D,
                image_points,
                camera_matrix,
                dist_coeffs,
                rvec=rvec,
                tvec=tvec,
                useExtrinsicGuess=True,
                flags=cv2.SOLVEPNP_ITERATIVE
            )
        else:
            success, rvec, tvec = cv2.solvePnP(
                self.MODEL_POINTS_3D,
                image_points,
                camera_matrix,
                dist_coeffs,
                flags=cv2.SOLVEPNP_ITERATIVE
            )

        if not success:
            self._last_rvec = None
            self._last_tvec = None
            return metrics

        self._last_rvec = rvec
        self._last_tvec = tvec

        metrics.rotation_vector = rvec
        metrics.translation_vector = tvec

        # Convert rotation vector to rotation matrix
        rmat, _ = cv2.Rodrigues(rvec)

        # Compute Euler angles via RQDecomp3x3
        angles, _, _, _, _, _ = cv2.RQDecomp3x3(rmat)

        # OpenCV RQDecomp angles:
        # pitch (up/down): angles[0] (+ = down, - = up)
        # yaw (left/right): angles[1] (+ = right, - = left)
        # roll (tilt): angles[2] (+ = tilt right, - = tilt left)
        raw_pitch = float(angles[0])
        raw_yaw = float(angles[1])
        raw_roll = float(angles[2])

        # Multi-observation calibration sampling
        if self._is_calibrating:
            self._calibration_samples.append((raw_pitch, raw_yaw, raw_roll))
            if len(self._calibration_samples) >= self._calibration_target_samples:
                # Compute stable mean and standard deviation
                pitches = [s[0] for s in self._calibration_samples]
                yaws = [s[1] for s in self._calibration_samples]
                rolls = [s[2] for s in self._calibration_samples]

                mean_p, std_p = float(np.mean(pitches)), float(np.std(pitches))
                mean_y, std_y = float(np.mean(yaws)), float(np.std(yaws))
                mean_r, std_r = float(np.mean(rolls)), float(np.std(rolls))

                self._pitch_offset = mean_p
                self._yaw_offset = mean_y
                self._roll_offset = mean_r

                # Confidence based on stability (low std = high confidence)
                avg_std = (std_p + std_y + std_r) / 3.0
                confidence = max(0.5, min(1.0, 1.0 - (avg_std / 10.0)))
                self._calibration_confidence = round(confidence, 2)
                self._is_calibrating = False
                logger.info(
                    "Multi-observation calibration complete: P_offset=%.1f (std=%.2f), Y_offset=%.1f (std=%.2f), R_offset=%.1f (std=%.2f), Conf=%.0f%%",
                    mean_p, std_p, mean_y, std_y, mean_r, std_r, self._calibration_confidence * 100
                )

        # Normalize relative to calibrated neutral posture
        norm_pitch = (raw_pitch - self._pitch_offset)
        norm_yaw = (raw_yaw - self._yaw_offset)
        norm_roll = (raw_roll - self._roll_offset)

        # Wrap angles cleanly to [-180, 180]
        norm_pitch = (norm_pitch + 180.0) % 360.0 - 180.0
        norm_yaw = (norm_yaw + 180.0) % 360.0 - 180.0
        norm_roll = (norm_roll + 180.0) % 360.0 - 180.0

        metrics.pitch = round(norm_pitch, 1)
        metrics.yaw = round(norm_yaw, 1)
        metrics.roll = round(norm_roll, 1)
        metrics.calibration_confidence = self._calibration_confidence

        # Check Head-Down posture (+pitch > threshold)
        pitch_thresh = abs(self._config.pitch_down_threshold)
        if metrics.pitch > pitch_thresh:
            metrics.is_head_down = True
            if self._head_down_start is None:
                self._head_down_start = timestamp
            metrics.head_down_duration_sec = round(timestamp - self._head_down_start, 2)
        else:
            metrics.is_head_down = False
            self._head_down_start = None
            metrics.head_down_duration_sec = 0.0

        # Check Head-Turned posture (|yaw| > threshold)
        if abs(metrics.yaw) > self._config.yaw_turned_threshold:
            metrics.is_head_turned = True
            if self._head_turned_start is None:
                self._head_turned_start = timestamp
            metrics.head_turned_duration_sec = round(timestamp - self._head_turned_start, 2)
        else:
            metrics.is_head_turned = False
            self._head_turned_start = None
            metrics.head_turned_duration_sec = 0.0

        # Check Head-Tilted posture (|roll| > threshold)
        if abs(metrics.roll) > self._config.roll_tilted_threshold:
            metrics.is_head_tilted = True
            if self._head_tilted_start is None:
                self._head_tilted_start = timestamp
            metrics.head_tilted_duration_sec = round(timestamp - self._head_tilted_start, 2)
        else:
            metrics.is_head_tilted = False
            self._head_tilted_start = None
            metrics.head_tilted_duration_sec = 0.0

        # Update Nodding analysis
        self._update_nodding(metrics.pitch, timestamp, metrics)

        # 3D coordinate axes projection for visualization
        metrics.projected_axes = self._project_axes(rvec, tvec, camera_matrix, dist_coeffs)

        return metrics

    def _update_nodding(self, current_pitch: float, timestamp: float, metrics: HeadPoseMetrics) -> None:
        """Detects micro-sleep nodding cycles (downward pitch drop followed by upward rebound)."""
        self._pitch_history.append((timestamp, current_pitch))

        if len(self._pitch_history) >= 4:
            past_pitches = [p for t, p in self._pitch_history if timestamp - t <= 2.0]
            if past_pitches:
                min_past = min(past_pitches)
                max_past = max(past_pitches)
                diff = max_past - min_past
                # If there was a downward dip (> nod_pitch_dip) and now rebounding
                if diff >= self._config.nod_pitch_dip:
                    if not self._is_nod_in_progress and current_pitch < max_past - 6.0:
                        self._is_nod_in_progress = True
                        self._nod_timestamps.append(timestamp)
                        metrics.recent_nod_detected = True
                    elif current_pitch <= min_past + 3.0:
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
        img_pts, _ = cv2.projectPoints(self.AXIS_POINTS_3D, rvec, tvec, camera_matrix, dist_coeffs)
        pts = img_pts.reshape(-1, 2)
        return [(int(p[0]), int(p[1])) for p in pts]

    def reset(self) -> None:
        self._head_down_start = None
        self._head_turned_start = None
        self._head_tilted_start = None
        self._pitch_history.clear()
        self._nod_timestamps.clear()
        self._is_nod_in_progress = False
        self._is_calibrating = False
        self._calibration_samples.clear()
        self._last_rvec = None
        self._last_tvec = None
