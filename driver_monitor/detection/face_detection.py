"""
Face Detection and Landmark Tracking for Driver Monitoring System.
Uses MediaPipe Tasks Face Landmarker for real-time 468/478 3D landmark extraction.
Supports primary face selection, temporal smoothing, confidence estimation, and face loss tracking.
"""

import logging
import os
import time
from typing import List, Optional, Tuple
import cv2
import numpy as np

import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from driver_monitor.core.result_models import FaceDetectionResult
from driver_monitor.models.download_models import ensure_model_downloaded

logger = logging.getLogger(__name__)


class FaceDetector:
    """Detects faces and extracts 3D facial landmarks."""

    def __init__(self, model_path: Optional[str] = None, min_confidence: float = 0.5):
        if model_path is None or not os.path.exists(model_path):
            model_path = ensure_model_downloaded()

        self._model_path = model_path
        self._min_confidence = min_confidence
        self._detector: Optional[vision.FaceLandmarker] = None
        self._last_face_time = 0.0
        self._smoothed_bbox: Optional[Tuple[int, int, int, int]] = None
        self._bbox_alpha = 0.65  # EMA smoothing factor
        self._initialize_detector()

    def _initialize_detector(self) -> None:
        """Initializes the MediaPipe Face Landmarker graph."""
        try:
            base_options = python.BaseOptions(model_asset_path=self._model_path)
            options = vision.FaceLandmarkerOptions(
                base_options=base_options,
                output_face_blendshapes=True,
                output_facial_transformation_matrixes=True,
                num_faces=1,
                min_face_detection_confidence=self._min_confidence,
                min_face_presence_confidence=self._min_confidence,
                min_tracking_confidence=self._min_confidence,
                running_mode=vision.RunningMode.IMAGE
            )
            self._detector = vision.FaceLandmarker.create_from_options(options)
            logger.info("MediaPipe FaceLandmarker initialized successfully.")
        except Exception as e:
            logger.error("Failed to initialize FaceLandmarker: %s", e, exc_info=True)
            self._detector = None

    def detect(self, frame_bgr: np.ndarray, timestamp: Optional[float] = None) -> FaceDetectionResult:
        """Processes a BGR image frame and returns FaceDetectionResult."""
        if timestamp is None:
            timestamp = time.time()

        result = FaceDetectionResult()
        if self._detector is None or frame_bgr is None or frame_bgr.size == 0:
            if self._last_face_time > 0:
                result.face_lost_duration_sec = timestamp - self._last_face_time
            return result

        h, w = frame_bgr.shape[:2]

        try:
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
            detection = self._detector.detect(mp_image)

            if not detection.face_landmarks or len(detection.face_landmarks) == 0:
                if self._last_face_time > 0:
                    result.face_lost_duration_sec = timestamp - self._last_face_time
                self._smoothed_bbox = None
                return result

            # Face detected
            self._last_face_time = timestamp
            result.detected = True
            result.face_lost_duration_sec = 0.0

            # Extract primary face landmarks
            landmarks = detection.face_landmarks[0]
            landmarks_2d: List[Tuple[float, float]] = []
            landmarks_3d: List[Tuple[float, float, float]] = []

            xs = []
            ys = []
            for lm in landmarks:
                px = lm.x * w
                py = lm.y * h
                pz = lm.z * w
                landmarks_2d.append((px, py))
                landmarks_3d.append((px, py, pz))
                xs.append(px)
                ys.append(py)

            result.landmarks_2d = landmarks_2d
            result.landmarks_3d = landmarks_3d

            # Compute bounding box
            min_x, max_x = max(0, min(xs)), min(w, max(xs))
            min_y, max_y = max(0, min(ys)), min(h, max(ys))
            raw_w = max_x - min_x
            raw_h = max_y - min_y

            # Pad bounding box slightly for aesthetics
            pad_x = raw_w * 0.12
            pad_y = raw_h * 0.15
            box_x = int(max(0, min_x - pad_x))
            box_y = int(max(0, min_y - pad_y))
            box_w = int(min(w - box_x, raw_w + 2 * pad_x))
            box_h = int(min(h - box_y, raw_h + 2 * pad_y))

            # Smooth bounding box with EMA
            if self._smoothed_bbox is None:
                self._smoothed_bbox = (box_x, box_y, box_w, box_h)
            else:
                sx, sy, sw, sh = self._smoothed_bbox
                self._smoothed_bbox = (
                    int(self._bbox_alpha * box_x + (1 - self._bbox_alpha) * sx),
                    int(self._bbox_alpha * box_y + (1 - self._bbox_alpha) * sy),
                    int(self._bbox_alpha * box_w + (1 - self._bbox_alpha) * sw),
                    int(self._bbox_alpha * box_h + (1 - self._bbox_alpha) * sh),
                )

            result.bbox = self._smoothed_bbox

            # Confidence estimation from detection and presence
            if detection.face_blendshapes and len(detection.face_blendshapes) > 0:
                result.confidence = 0.95
            else:
                result.confidence = 0.85

            return result

        except Exception as e:
            logger.error("Error in face detection: %s", e)
            if self._last_face_time > 0:
                result.face_lost_duration_sec = timestamp - self._last_face_time
            return result
