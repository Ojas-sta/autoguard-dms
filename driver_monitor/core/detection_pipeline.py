"""
Core Detection Pipeline for Driver Monitoring System.
Orchestrates computer vision models, kinematic estimators, multi-signal decision engines,
hardware actuators, and video frame annotation in real time.
"""

from collections import deque
import logging
import time
from typing import Deque, Optional, Tuple
import cv2
import numpy as np
import psutil

from driver_monitor.config import AppConfig
from driver_monitor.core.event_manager import global_event_bus
from driver_monitor.core.result_models import (
    AlertLevel, DrowsinessState, EyeStatus, FrameAnalysisResult,
    PerformanceMetrics, SystemAlert, FaceDetectionResult
)
from driver_monitor.detection.behavior_analysis import BehaviorAnalyzer
from driver_monitor.detection.eye_detection import EyeDetector
from driver_monitor.detection.face_detection import FaceDetector
from driver_monitor.detection.head_pose import HeadPoseEstimator
from driver_monitor.detection.yawning_detection import YawningDetector
from driver_monitor.engine.abnormal_movement_engine import AbnormalMovementEngine
from driver_monitor.engine.alert_manager import AlertManager
from driver_monitor.engine.drowsiness_engine import DrowsinessEngine
from driver_monitor.engine.emergency_simulation import EmergencySimulationEngine
from driver_monitor.hardware.interfaces import BuzzerInterface, LEDInterface, EmergencyButtonInterface
from driver_monitor.logging.event_logger import EventLogger

logger = logging.getLogger(__name__)


class DetectionPipeline:
    """Central processing pipeline for the Driver Monitoring System."""

    def __init__(
        self,
        config: AppConfig,
        buzzer: BuzzerInterface,
        leds: LEDInterface,
        emergency_button: EmergencyButtonInterface,
        event_logger: Optional[EventLogger] = None
    ):
        self.config = config
        self.buzzer = buzzer
        self.leds = leds
        self.emergency_button = emergency_button
        self.logger = event_logger or EventLogger()

        # Detection modules
        self.face_detector = FaceDetector(min_confidence=0.5)
        self.eye_detector = EyeDetector(config.eye)
        self.head_pose_estimator = HeadPoseEstimator(config.head_pose)
        self.yawning_detector = YawningDetector(config.yawning)
        self.behavior_analyzer = BehaviorAnalyzer(config.eye, config.head_pose, config.abnormal)

        # Decision & simulation engines
        self.drowsiness_engine = DrowsinessEngine(config.eye, config.head_pose, config.yawning)
        self.abnormal_engine = AbnormalMovementEngine(config.abnormal, config.head_pose)
        self.alert_manager = AlertManager()
        self.emergency_sim = EmergencySimulationEngine()

        # Connect hardware emergency button callback
        self.emergency_button.register_callback(self.emergency_sim.trigger_emergency)

        # Performance tracking
        self._frame_count = 0
        self._fps_timestamps: Deque[float] = deque(maxlen=30)
        self._current_fps = 0.0
        self._process = psutil.Process()
        self._cpu_check_time = 0.0
        self._cached_cpu = 0.0
        self._cached_mem = 0.0

    def process_frame(
        self,
        frame_bgr: np.ndarray,
        source_name: str = "Default",
        source_type: str = "webcam"
    ) -> FrameAnalysisResult:
        """Processes a single video frame end-to-end."""
        start_time = time.time()
        self._frame_count += 1

        result = FrameAnalysisResult(
            timestamp=start_time,
            frame_index=self._frame_count
        )

        if frame_bgr is None or frame_bgr.size == 0 or frame_bgr.shape[0] == 0 or frame_bgr.shape[1] == 0:
            result.face = FaceDetectionResult(detected=False)
            result.eyes = self.eye_detector.analyze([], timestamp=start_time)
            result.head_pose = self.head_pose_estimator.estimate([], (0, 0), timestamp=start_time)
            result.mouth = self.yawning_detector.analyze([], timestamp=start_time)
            result.alert = self.alert_manager.update(result.drowsiness, result.abnormal, False, timestamp=start_time)
            result.performance = PerformanceMetrics(fps=self._current_fps, source_type=source_type, source_name=source_name)
            return result

        h, w = frame_bgr.shape[:2]

        # -------------------------------------------------------------
        # 1. Face Detection & Tracking
        # -------------------------------------------------------------
        # If simulated face loss is active, simulate face not found
        if self.emergency_sim.is_face_lost_simulated:
            face_result = self.face_detector.detect(None, timestamp=start_time)
            face_result.face_lost_duration_sec = self.emergency_sim.get_abnormal_sim_duration()
        else:
            face_result = self.face_detector.detect(frame_bgr, timestamp=start_time)

        result.face = face_result

        # -------------------------------------------------------------
        # 2. Extract Facial Metrics (if face present)
        # -------------------------------------------------------------
        if face_result.detected and len(face_result.landmarks_2d) >= 468:
            # Eye Analysis
            eye_metrics = self.eye_detector.analyze(face_result.landmarks_2d, timestamp=start_time)

            # Simulation injection for Drowsiness
            if self.emergency_sim.is_drowsiness_simulated:
                sim_dur = self.emergency_sim.get_drowsiness_sim_duration()
                eye_metrics.avg_ear = 0.15
                eye_metrics.left_ear = 0.15
                eye_metrics.right_ear = 0.15
                eye_metrics.overall_status = EyeStatus.CLOSED
                eye_metrics.closure_duration_sec = round(sim_dur, 2)
                if sim_dur >= self.config.eye.closure_warning_sec:
                    eye_metrics.is_prolonged_closure = True

            result.eyes = eye_metrics

            # Head Pose Estimation
            head_metrics = self.head_pose_estimator.estimate(
                face_result.landmarks_2d, (h, w), timestamp=start_time
            )

            # Simulation injection for Abnormal Head Movement
            if self.emergency_sim.is_abnormal_movement_simulated:
                sim_dur = self.emergency_sim.get_abnormal_sim_duration()
                head_metrics.roll = 35.0  # Sideways tilt
                head_metrics.is_head_tilted = True
                head_metrics.head_tilted_duration_sec = round(sim_dur, 2)

            result.head_pose = head_metrics

            # Yawning Analysis
            mouth_metrics = self.yawning_detector.analyze(face_result.landmarks_2d, timestamp=start_time)
            result.mouth = mouth_metrics

            # Behavioral Aggregation (PERCLOS & Jerk)
            perclos, angular_jerk = self.behavior_analyzer.update(
                eye_metrics, head_metrics, timestamp=start_time
            )
        else:
            # Face not detected
            result.eyes = self.eye_detector.analyze([], timestamp=start_time)
            result.head_pose = self.head_pose_estimator.estimate([], (h, w), timestamp=start_time)
            result.mouth = self.yawning_detector.analyze([], timestamp=start_time)
            perclos, angular_jerk = self.behavior_analyzer.update(
                result.eyes, result.head_pose, timestamp=start_time
            )

        # -------------------------------------------------------------
        # 3. Decision Engines
        # -------------------------------------------------------------
        drowsiness_res = self.drowsiness_engine.evaluate(
            result.eyes, result.head_pose, result.mouth, perclos, timestamp=start_time
        )
        result.drowsiness = drowsiness_res

        abnormal_res = self.abnormal_engine.evaluate(
            result.head_pose, result.face, angular_jerk, timestamp=start_time
        )
        result.abnormal = abnormal_res

        # -------------------------------------------------------------
        # 4. Alert Decision Arbitration
        # -------------------------------------------------------------
        alert = self.alert_manager.update(
            drowsiness_res, abnormal_res, self.emergency_sim.is_emergency_active, timestamp=start_time
        )
        result.alert = alert

        # -------------------------------------------------------------
        # 5. Hardware Actuation
        # -------------------------------------------------------------
        if alert.buzzer_active and alert.buzzer_pattern != "OFF":
            self.buzzer.start_alert(alert.buzzer_pattern)
        else:
            self.buzzer.stop_alert()

        self.leds.set_all(alert.led_green, alert.led_yellow, alert.led_orange, alert.led_red)

        # Notify event bus if alert state transitioned
        global_event_bus.publish("alert_changed", alert)

        # -------------------------------------------------------------
        # 6. Performance Metrics
        # -------------------------------------------------------------
        latency_ms = (time.time() - start_time) * 1000.0

        # Rolling FPS calculation
        self._fps_timestamps.append(start_time)
        if len(self._fps_timestamps) > 1:
            dt = self._fps_timestamps[-1] - self._fps_timestamps[0]
            if dt > 0:
                self._current_fps = round((len(self._fps_timestamps) - 1) / dt, 1)

        # CPU and Memory (sampled every 1s to save cycles)
        if start_time - self._cpu_check_time >= 1.0:
            try:
                self._cached_cpu = psutil.cpu_percent()
                self._cached_mem = psutil.virtual_memory().percent
            except Exception:
                pass
            self._cpu_check_time = start_time

        result.performance = PerformanceMetrics(
            fps=self._current_fps,
            processing_latency_ms=round(latency_ms, 1),
            cpu_percent=self._cached_cpu,
            memory_percent=self._cached_mem,
            resolution=(w, h),
            source_type=source_type,
            source_name=source_name
        )

        # -------------------------------------------------------------
        # 7. Professional Video Annotation
        # -------------------------------------------------------------
        result.annotated_frame = self._annotate_frame(frame_bgr, result)

        return result

    def _annotate_frame(self, frame_bgr: np.ndarray, result: FrameAnalysisResult) -> np.ndarray:
        """Renders automotive detection overlays directly onto the video frame."""
        annotated = frame_bgr.copy()
        h, w = annotated.shape[:2]

        # 1. Alert Banner Color Palette
        alert_colors = {
            AlertLevel.NORMAL: (30, 185, 80),      # Emerald Green (BGR)
            AlertLevel.ATTENTION: (30, 175, 245),   # Yellow / Amber (BGR)
            AlertLevel.WARNING: (25, 120, 245),    # Orange (BGR)
            AlertLevel.CRITICAL: (40, 40, 235),     # Crimson Red (BGR)
        }
        theme_color = alert_colors.get(result.alert.level, (30, 185, 80))

        # 2. Draw Face Bounding Box & HUD
        if result.face.detected and result.face.bbox:
            bx, by, bw, bh = result.face.bbox

            # Sleek corner-accent bounding box
            corner_len = min(25, int(bw * 0.15))
            thickness = 2
            # Bounding rectangle outline (subtle)
            cv2.rectangle(annotated, (bx, by), (bx + bw, by + bh), theme_color, 1)

            # Highlighting corners
            # Top-left
            cv2.line(annotated, (bx, by), (bx + corner_len, by), theme_color, thickness + 1)
            cv2.line(annotated, (bx, by), (bx, by + corner_len), theme_color, thickness + 1)
            # Top-right
            cv2.line(annotated, (bx + bw, by), (bx + bw - corner_len, by), theme_color, thickness + 1)
            cv2.line(annotated, (bx + bw, by), (bx + bw, by + corner_len), theme_color, thickness + 1)
            # Bottom-left
            cv2.line(annotated, (bx, by + bh), (bx + corner_len, by + bh), theme_color, thickness + 1)
            cv2.line(annotated, (bx, by + bh), (bx, by + bh - corner_len), theme_color, thickness + 1)
            # Bottom-right
            cv2.line(annotated, (bx + bw, by + bh), (bx + bw - corner_len, by + bh), theme_color, thickness + 1)
            cv2.line(annotated, (bx + bw, by + bh), (bx + bw, by + bh - corner_len), theme_color, thickness + 1)

            # Driver tag
            tag_text = f"DRIVER [CONF: {result.face.confidence:.0%}]"
            cv2.rectangle(annotated, (bx, by - 22), (bx + 180, by), (18, 21, 28), -1)
            cv2.putText(annotated, tag_text, (bx + 6, by - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, theme_color, 1, cv2.LINE_AA)

            # 3. Draw Eye Landmarks & Eye Badges
            for pt in result.eyes.raw_left_landmarks:
                cv2.circle(annotated, (int(pt[0]), int(pt[1])), 2, (0, 240, 255), -1)
            for pt in result.eyes.raw_right_landmarks:
                cv2.circle(annotated, (int(pt[0]), int(pt[1])), 2, (0, 240, 255), -1)

            # 4. Draw Mouth Landmarks
            for pt in result.mouth.raw_mouth_landmarks:
                cv2.circle(annotated, (int(pt[0]), int(pt[1])), 2, (255, 120, 0), -1)

            # 5. Draw 3D Head Pose Axes
            if result.head_pose.projected_axes and len(result.head_pose.projected_axes) >= 4:
                origin = result.head_pose.projected_axes[0]
                x_axis = result.head_pose.projected_axes[1]
                y_axis = result.head_pose.projected_axes[2]
                z_axis = result.head_pose.projected_axes[3]
                # X = Red (Roll), Y = Green (Pitch), Z = Blue (Yaw / Forward)
                cv2.line(annotated, origin, x_axis, (0, 0, 255), 3, cv2.LINE_AA)     # Red (BGR)
                cv2.line(annotated, origin, y_axis, (0, 255, 0), 3, cv2.LINE_AA)     # Green
                cv2.line(annotated, origin, z_axis, (255, 0, 0), 3, cv2.LINE_AA)     # Blue

        # 6. Top Header HUD Bar
        header_h = 36
        overlay = annotated.copy()
        cv2.rectangle(overlay, (0, 0), (w, header_h), (12, 15, 22), -1)
        cv2.addWeighted(overlay, 0.85, annotated, 0.15, 0, annotated)

        # Status text left
        status_text = f"STATUS: {result.alert.level.value} | {result.alert.title}"
        cv2.putText(annotated, status_text, (14, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.55, theme_color, 2, cv2.LINE_AA)

        # Metrics right
        telemetry_text = f"EAR: {result.eyes.avg_ear:.2f} | MAR: {result.mouth.mar:.2f} | P:{result.head_pose.pitch:+.0f} Y:{result.head_pose.yaw:+.0f} R:{result.head_pose.roll:+.0f} | {result.performance.fps:.0f} FPS"
        (tw, _), _ = cv2.getTextSize(telemetry_text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        cv2.putText(annotated, telemetry_text, (w - tw - 14, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 225, 230), 1, cv2.LINE_AA)

        # 7. Critical Alert Warning Glow Border
        if result.alert.level == AlertLevel.CRITICAL:
            cv2.rectangle(annotated, (0, 0), (w, h), (40, 40, 235), 6)

        return annotated

    def reset_all(self) -> None:
        """Resets all sub-modules and state machines."""
        self.eye_detector.reset()
        self.head_pose_estimator.reset()
        self.yawning_detector.reset()
        self.behavior_analyzer.reset()
        self.drowsiness_engine.reset()
        self.abnormal_engine.reset()
        self.emergency_sim.reset_emergency()
        self.buzzer.stop_alert()
        self.leds.set_all(True, False, False, False)
        logger.info("Detection pipeline reset complete.")
