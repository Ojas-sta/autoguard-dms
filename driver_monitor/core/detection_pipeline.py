"""
Core Detection Pipeline for Driver Monitoring System.
Orchestrates computer vision models, kinematic estimators, multi-signal decision engines,
hardware actuators, and video frame annotation in real time.

==============================================================================
Subsystem: Core Computer Vision Pipeline & Frame Orchestration
Architecture: Powered by cl0ud (https://github.com/Ojas-sta/cl0ud-brand-engineering)
Co-Engineered by: Ojas Singh <ojasctc@gmail.com>
==============================================================================
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
    PerformanceMetrics, SystemAlert, FaceDetectionResult,
    GazeDirection, DistractionState, IrisMetrics, GazeMetrics, DistractionMetrics
)
from driver_monitor.calibration.gaze_calibration import GazeCalibrationManager
from driver_monitor.detection.behavior_analysis import BehaviorAnalyzer
from driver_monitor.detection.eye_detection import EyeDetector
from driver_monitor.detection.face_detection import FaceDetector
from driver_monitor.detection.gaze_estimation import GazeEstimator
from driver_monitor.detection.head_pose import HeadPoseEstimator
from driver_monitor.detection.iris_tracking import IrisTracker
from driver_monitor.detection.yawning_detection import YawningDetector
from driver_monitor.engine.abnormal_movement_engine import AbnormalMovementEngine
from driver_monitor.engine.alert_manager import AlertManager
from driver_monitor.engine.distraction_engine import DistractionEngine
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
        downsample_w = getattr(config.power, "inference_downsample_width", 320)
        self.face_detector = FaceDetector(min_confidence=0.5, downsample_width=downsample_w)
        self.eye_detector = EyeDetector(config.eye)
        self.head_pose_estimator = HeadPoseEstimator(config.head_pose)
        self.yawning_detector = YawningDetector(config.yawning)
        self.behavior_analyzer = BehaviorAnalyzer(config.eye, config.head_pose, config.abnormal)
        self.iris_tracker = IrisTracker(config.gaze.iris_smoothing_alpha if hasattr(config, "gaze") else 0.5)
        self.gaze_calibration_manager = GazeCalibrationManager()
        self.gaze_calibration_manager.load_calibration()
        self.gaze_estimator = GazeEstimator(config.gaze if hasattr(config, "gaze") else None, self.gaze_calibration_manager)

        # Decision & simulation engines
        self.drowsiness_engine = DrowsinessEngine(config.eye, config.head_pose, config.yawning)
        self.abnormal_engine = AbnormalMovementEngine(config.abnormal, config.head_pose)
        self.distraction_engine = DistractionEngine(config.distraction if hasattr(config, "distraction") else None)
        self.alert_manager = AlertManager()
        self.emergency_sim = EmergencySimulationEngine()

        # Connect hardware emergency button callback
        self.emergency_button.register_callback(self.emergency_sim.trigger_emergency)

        # Overlays toggle (disabled in LOW_POWER profile to eliminate rendering overhead on RPi 4B)
        self.debug_overlays_enabled = (getattr(config.power, "profile_name", "") != "LOW_POWER")

        # Performance tracking
        self._frame_count = 0
        self._dropped_frames = 0
        self._last_face_result: Optional[FaceDetectionResult] = None
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
            result.iris = self.iris_tracker.analyze([], (0, 0))
            result.gaze = self.gaze_estimator.estimate(result.iris, result.head_pose, result.face, result.eyes, timestamp=start_time)
            result.distraction = self.distraction_engine.evaluate(result.gaze, result.head_pose, result.face, timestamp=start_time)
            result.alert = self.alert_manager.update(result.drowsiness, result.abnormal, result.distraction, False, timestamp=start_time)
            result.performance = PerformanceMetrics(fps=self._current_fps, source_type=source_type, source_name=source_name)
            return result

        h, w = frame_bgr.shape[:2]

        # -------------------------------------------------------------
        # 1. Face Detection & Tracking
        # -------------------------------------------------------------
        interval = getattr(self.config.power, 'face_detection_interval_frames', 1)
        reuse_previous = (
            getattr(self.config.power, 'adaptive_processing', False)
            and interval > 1
            and (self._frame_count % interval != 0)
            and self._last_face_result is not None
            and self._last_face_result.detected
            and not self.emergency_sim.is_face_lost_simulated
        )

        if reuse_previous:
            face_result = self._last_face_result
            self._dropped_frames += 1
        elif self.emergency_sim.is_face_lost_simulated:
            face_result = self.face_detector.detect(None, timestamp=start_time)
            face_result.face_lost_duration_sec = self.emergency_sim.get_abnormal_sim_duration()
            self._last_face_result = face_result
        else:
            face_result = self.face_detector.detect(frame_bgr, timestamp=start_time)
            self._last_face_result = face_result

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

            # Iris Tracking
            iris_metrics = self.iris_tracker.analyze(face_result.landmarks_2d, (h, w))
            result.iris = iris_metrics

            # Road Gaze Estimation
            gaze_metrics = self.gaze_estimator.estimate(
                iris_metrics, head_metrics, face_result, eye_metrics, timestamp=start_time
            )

            # Simulation injection for Road Gaze and Distraction
            if self.emergency_sim.is_road_gaze_simulated:
                gaze_metrics.direction = GazeDirection.ROAD
                gaze_metrics.is_looking_at_road = True
                gaze_metrics.confidence = 0.95
                gaze_metrics.horizontal_ratio = 0.5
                gaze_metrics.vertical_ratio = 0.5
                gaze_metrics.dwell_time_sec = 2.5
            elif self.emergency_sim.is_distraction_simulated:
                sim_dur = self.emergency_sim.get_distraction_sim_duration()
                gaze_metrics.direction = GazeDirection.DOWN
                gaze_metrics.is_looking_at_road = False
                gaze_metrics.confidence = 0.95
                gaze_metrics.dwell_time_sec = sim_dur

            result.gaze = gaze_metrics

            # Distraction Engine Evaluation
            distraction_metrics = self.distraction_engine.evaluate(
                gaze_metrics, head_metrics, face_result, timestamp=start_time
            )
            result.distraction = distraction_metrics

        else:
            # Face not detected
            result.eyes = self.eye_detector.analyze([], timestamp=start_time)
            result.head_pose = self.head_pose_estimator.estimate([], (h, w), timestamp=start_time)
            result.mouth = self.yawning_detector.analyze([], timestamp=start_time)
            perclos, angular_jerk = self.behavior_analyzer.update(
                result.eyes, result.head_pose, timestamp=start_time
            )
            result.iris = self.iris_tracker.analyze([], (h, w))
            result.gaze = self.gaze_estimator.estimate(
                result.iris, result.head_pose, face_result, result.eyes, timestamp=start_time
            )
            result.distraction = self.distraction_engine.evaluate(
                result.gaze, result.head_pose, face_result, timestamp=start_time
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
            drowsiness_res,
            abnormal_res,
            result.distraction,
            self.emergency_sim.is_emergency_active,
            timestamp=start_time
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
            source_name=source_name,
            power_profile=getattr(self.config.power, 'profile_name', 'BALANCED'),
            dropped_frames=self._dropped_frames
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

            # 3. Draw Eye Landmarks & Iris Centers
            if self.debug_overlays_enabled:
                for pt in result.eyes.raw_left_landmarks:
                    cv2.circle(annotated, (int(pt[0]), int(pt[1])), 2, (0, 240, 255), -1)
                for pt in result.eyes.raw_right_landmarks:
                    cv2.circle(annotated, (int(pt[0]), int(pt[1])), 2, (0, 240, 255), -1)

                # Iris Centers (Cyan)
                if result.iris.is_valid:
                    rx, ry = result.iris.right_iris_center
                    lx, ly = result.iris.left_iris_center
                    cv2.circle(annotated, (int(rx), int(ry)), 3, (255, 255, 0), -1)
                    cv2.circle(annotated, (int(lx), int(ly)), 3, (255, 255, 0), -1)

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

                # 6. Draw 2D Gaze Vector Arrow
                if result.gaze.gaze_origin_2d and result.gaze.gaze_target_2d:
                    orig = result.gaze.gaze_origin_2d
                    target = result.gaze.gaze_target_2d
                    if orig != (0, 0) and target != (0, 0):
                        arrow_col = (0, 230, 115) if result.gaze.is_looking_at_road else (0, 165, 255)
                        cv2.arrowedLine(annotated, orig, target, arrow_col, 2, tipLength=0.25)

                # 7. Forward Road Gaze Reference Crosshair
                cx, cy = w // 2, h // 2
                cv2.drawMarker(annotated, (cx, cy), (90, 105, 120), cv2.MARKER_CROSS, 14, 1)

        # 6. Top Header HUD Bar (Zero-copy sub-ROI alpha blending for Pi 4B efficiency)
        header_h = 36
        top_roi = annotated[0:header_h, 0:w]
        top_bg = np.full_like(top_roi, (12, 15, 22))
        cv2.addWeighted(top_bg, 0.85, top_roi, 0.15, 0, top_roi)

        # Status text left
        status_text = f"STATUS: {result.alert.level.value} | {result.alert.title}"
        cv2.putText(annotated, status_text, (14, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.55, theme_color, 2, cv2.LINE_AA)

        # Metrics right
        telemetry_text = f"EAR:{result.eyes.avg_ear:.2f} | MAR:{result.mouth.mar:.2f} | P:{result.head_pose.pitch:+.0f} Y:{result.head_pose.yaw:+.0f} | GAZE:{result.gaze.direction.value} | {result.performance.fps:.0f}FPS"
        (tw, _), _ = cv2.getTextSize(telemetry_text, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
        cv2.putText(annotated, telemetry_text, (w - tw - 14, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (220, 225, 230), 1, cv2.LINE_AA)

        # 7. Gaze & Road Attention HUD Badge (Bottom-left, zero-copy sub-ROI blend)
        badge_w, badge_h = 250, 48
        by0 = h - badge_h - 12
        badge_roi = annotated[by0:by0 + badge_h, 12:12 + badge_w]
        badge_bg = np.full_like(badge_roi, (14, 17, 24))
        cv2.addWeighted(badge_bg, 0.85, badge_roi, 0.15, 0, badge_roi)
        cv2.rectangle(annotated, (12, by0), (12 + badge_w, by0 + badge_h), (45, 52, 65), 1)

        gaze_col = (0, 235, 120) if result.gaze.is_looking_at_road else (0, 165, 255)
        cv2.putText(
            annotated,
            f"GAZE: {result.gaze.direction.value} ({result.gaze.dwell_time_sec:.1f}s)",
            (22, by0 + 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            gaze_col,
            1,
            cv2.LINE_AA
        )
        dist_col = (0, 235, 120) if not result.distraction.is_distracted else (40, 40, 235)
        cv2.putText(
            annotated,
            f"ROAD ATTN: {result.distraction.road_gaze_percent:.0f}% | {result.distraction.state.value}",
            (22, by0 + 38),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.38,
            dist_col,
            1,
            cv2.LINE_AA
        )

        # 8. cl0ud & Ojas Singh System Attribution Watermark (Bottom-right, zero-copy sub-ROI blend)
        if w >= 480:
            pill_w, pill_h = 215, 34
            bx1 = w - pill_w - 12
            by1 = h - pill_h - 12
            if bx1 > 0 and by1 > 0 and (bx1 + pill_w) <= w and (by1 + pill_h) <= h:
                attr_roi = annotated[by1:by1 + pill_h, bx1:bx1 + pill_w]
                attr_bg = np.full_like(attr_roi, (11, 15, 25))
                cv2.addWeighted(attr_bg, 0.88, attr_roi, 0.12, 0, attr_roi)
                cv2.rectangle(annotated, (bx1, by1), (bx1 + pill_w, by1 + pill_h), (255, 229, 0), 1)
                cv2.circle(annotated, (bx1 + 11, by1 + 13), 3, (255, 229, 0), -1)
                cv2.putText(annotated, "Powered by cl0ud", (bx1 + 20, by1 + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 229, 0), 1, cv2.LINE_AA)
                cv2.putText(annotated, "Co-engineered by Ojas Singh", (bx1 + 11, by1 + 28), cv2.FONT_HERSHEY_SIMPLEX, 0.31, (180, 195, 210), 1, cv2.LINE_AA)
        else:
            pill_w, pill_h = 175, 18
            bx1 = w - pill_w - 8
            by1 = h - pill_h - 8
            if bx1 > 0 and by1 > 0 and (bx1 + pill_w) <= w and (by1 + pill_h) <= h:
                attr_roi = annotated[by1:by1 + pill_h, bx1:bx1 + pill_w]
                attr_bg = np.full_like(attr_roi, (11, 15, 25))
                cv2.addWeighted(attr_bg, 0.88, attr_roi, 0.12, 0, attr_roi)
                cv2.rectangle(annotated, (bx1, by1), (bx1 + pill_w, by1 + pill_h), (255, 229, 0), 1)
                cv2.putText(annotated, "cl0ud | Ojas Singh", (bx1 + 8, by1 + 13), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (255, 229, 0), 1, cv2.LINE_AA)

        # 9. Critical Alert Warning Glow Border
        if result.alert.level == AlertLevel.CRITICAL:
            cv2.rectangle(annotated, (0, 0), (w, h), (40, 40, 235), 6)

        return annotated

    def reset_all(self) -> None:
        """Resets all sub-modules and state machines."""
        self.eye_detector.reset()
        self.head_pose_estimator.reset()
        self.yawning_detector.reset()
        self.behavior_analyzer.reset()
        self.iris_tracker.reset()
        self.gaze_estimator.reset()
        self.distraction_engine.reset()
        self.drowsiness_engine.reset()
        self.abnormal_engine.reset()
        self.emergency_sim.reset_emergency()
        self.buzzer.stop_alert()
        self.leds.set_all(True, False, False, False)
        logger.info("Detection pipeline reset complete.")
