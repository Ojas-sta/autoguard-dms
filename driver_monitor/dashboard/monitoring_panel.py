"""
Driver Monitoring Telemetry Panel for Driver Monitoring System.
Renders real-time biometric indicators, EAR/MAR meters, head pose kinematics,
and physiological fatigue states with automotive aesthetics.
"""

from typing import Optional
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QGroupBox, QGridLayout
)

from driver_monitor.core.result_models import EyeStatus, FrameAnalysisResult, GazeDirection, DistractionState


class MonitoringPanel(QWidget):
    """Cockpit telemetry card display for driver physiological signals."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet("""
            QGroupBox {
                background-color: #121620;
                border: 1px solid #1e2638;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 12px;
                font-weight: bold;
                font-size: 11px;
                color: #00d2ff;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 6px;
                left: 10px;
            }
            QLabel {
                color: #94a3b8;
                font-size: 11px;
            }
            .ValueLabel {
                color: #f8fafc;
                font-weight: bold;
                font-size: 12px;
                font-family: monospace;
            }
            .StatusBadge {
                font-weight: bold;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 10px;
                text-align: center;
            }
            QProgressBar {
                background-color: #1b2130;
                border: 1px solid #283347;
                border-radius: 4px;
                text-align: center;
                color: #ffffff;
                font-size: 10px;
                height: 14px;
            }
            QProgressBar::chunk {
                background-color: #00d2ff;
                border-radius: 3px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        # 1. Driver Face Status Group
        grp_face = QGroupBox("Driver Face & Tracking")
        lay_face = QGridLayout(grp_face)
        lay_face.setContentsMargins(10, 10, 10, 10)

        lay_face.addWidget(QLabel("Face Status:"), 0, 0)
        self.lbl_face_status = QLabel("DETECTED")
        self.lbl_face_status.setStyleSheet("color: #10b981; font-weight: bold;")
        lay_face.addWidget(self.lbl_face_status, 0, 1)

        lay_face.addWidget(QLabel("Confidence:"), 0, 2)
        self.lbl_confidence = QLabel("95%")
        self.lbl_confidence.setProperty("class", "ValueLabel")
        lay_face.addWidget(self.lbl_confidence, 0, 3)

        layout.addWidget(grp_face)

        # 2. Eye Monitoring Group
        grp_eyes = QGroupBox("Eye Status & EAR")
        lay_eyes = QGridLayout(grp_eyes)
        lay_eyes.setContentsMargins(10, 10, 10, 10)
        lay_eyes.setSpacing(6)

        lay_eyes.addWidget(QLabel("Left Eye:"), 0, 0)
        self.lbl_left_eye = QLabel("OPEN")
        self.lbl_left_eye.setStyleSheet("color: #10b981; font-weight: bold;")
        lay_eyes.addWidget(self.lbl_left_eye, 0, 1)

        lay_eyes.addWidget(QLabel("Right Eye:"), 0, 2)
        self.lbl_right_eye = QLabel("OPEN")
        self.lbl_right_eye.setStyleSheet("color: #10b981; font-weight: bold;")
        lay_eyes.addWidget(self.lbl_right_eye, 0, 3)

        lay_eyes.addWidget(QLabel("EAR Value:"), 1, 0)
        self.lbl_ear_val = QLabel("0.35")
        self.lbl_ear_val.setProperty("class", "ValueLabel")
        lay_eyes.addWidget(self.lbl_ear_val, 1, 1)

        self.bar_ear = QProgressBar()
        self.bar_ear.setRange(0, 50)  # 0.00 to 0.50
        self.bar_ear.setValue(35)
        lay_eyes.addWidget(self.bar_ear, 1, 2, 1, 2)

        lay_eyes.addWidget(QLabel("Closure Time:"), 2, 0)
        self.lbl_closure_dur = QLabel("0.0s")
        self.lbl_closure_dur.setProperty("class", "ValueLabel")
        lay_eyes.addWidget(self.lbl_closure_dur, 2, 1)

        lay_eyes.addWidget(QLabel("Blink Rate:"), 2, 2)
        self.lbl_blink_rate = QLabel("16 bpm")
        self.lbl_blink_rate.setProperty("class", "ValueLabel")
        lay_eyes.addWidget(self.lbl_blink_rate, 2, 3)

        layout.addWidget(grp_eyes)

        # 3. Yawning & Mouth Group
        grp_mouth = QGroupBox("Yawning & Mouth (MAR)")
        lay_mouth = QGridLayout(grp_mouth)
        lay_mouth.setContentsMargins(10, 10, 10, 10)
        lay_mouth.setSpacing(6)

        lay_mouth.addWidget(QLabel("Mouth Status:"), 0, 0)
        self.lbl_mouth_status = QLabel("NORMAL")
        self.lbl_mouth_status.setStyleSheet("color: #10b981; font-weight: bold;")
        lay_mouth.addWidget(self.lbl_mouth_status, 0, 1)

        lay_mouth.addWidget(QLabel("MAR Value:"), 0, 2)
        self.lbl_mar_val = QLabel("0.22")
        self.lbl_mar_val.setProperty("class", "ValueLabel")
        lay_mouth.addWidget(self.lbl_mar_val, 0, 3)

        self.bar_mar = QProgressBar()
        self.bar_mar.setRange(0, 100)  # 0.00 to 1.00
        self.bar_mar.setValue(22)
        lay_mouth.addWidget(self.bar_mar, 1, 0, 1, 4)

        lay_mouth.addWidget(QLabel("Yawn Count:"), 2, 0)
        self.lbl_yawn_count = QLabel("0")
        self.lbl_yawn_count.setProperty("class", "ValueLabel")
        lay_mouth.addWidget(self.lbl_yawn_count, 2, 1)

        lay_mouth.addWidget(QLabel("Yawn Duration:"), 2, 2)
        self.lbl_yawn_dur = QLabel("0.0s")
        self.lbl_yawn_dur.setProperty("class", "ValueLabel")
        lay_mouth.addWidget(self.lbl_yawn_dur, 2, 3)

        layout.addWidget(grp_mouth)

        # 4. Head Pose Kinematics Group
        grp_head = QGroupBox("Head Pose & Kinematics")
        lay_head = QGridLayout(grp_head)
        lay_head.setContentsMargins(10, 10, 10, 10)
        lay_head.setSpacing(6)

        lay_head.addWidget(QLabel("Pitch (Up/Down):"), 0, 0)
        self.lbl_pitch = QLabel("0.0°")
        self.lbl_pitch.setProperty("class", "ValueLabel")
        lay_head.addWidget(self.lbl_pitch, 0, 1)

        lay_head.addWidget(QLabel("Yaw (Left/Right):"), 1, 0)
        self.lbl_yaw = QLabel("0.0°")
        self.lbl_yaw.setProperty("class", "ValueLabel")
        lay_head.addWidget(self.lbl_yaw, 1, 1)

        lay_head.addWidget(QLabel("Roll (Tilt):"), 2, 0)
        self.lbl_roll = QLabel("0.0°")
        self.lbl_roll.setProperty("class", "ValueLabel")
        lay_head.addWidget(self.lbl_roll, 2, 1)

        lay_head.addWidget(QLabel("Head Posture:"), 0, 2)
        self.lbl_head_posture = QLabel("LEVEL")
        self.lbl_head_posture.setStyleSheet("color: #10b981; font-weight: bold;")
        lay_head.addWidget(self.lbl_head_posture, 0, 3)

        lay_head.addWidget(QLabel("Nodding Count:"), 1, 2)
        self.lbl_nod_count = QLabel("0")
        self.lbl_nod_count.setProperty("class", "ValueLabel")
        lay_head.addWidget(self.lbl_nod_count, 1, 3)

        layout.addWidget(grp_head)

        # 5. Road Gaze & Iris Tracking Group
        grp_gaze = QGroupBox("Road Gaze & Iris Tracking")
        lay_gaze = QGridLayout(grp_gaze)
        lay_gaze.setContentsMargins(10, 10, 10, 10)
        lay_gaze.setSpacing(6)

        lay_gaze.addWidget(QLabel("Gaze Direction:"), 0, 0)
        self.lbl_gaze_dir = QLabel("ROAD")
        self.lbl_gaze_dir.setStyleSheet("color: #10b981; font-weight: bold; font-size: 12px;")
        lay_gaze.addWidget(self.lbl_gaze_dir, 0, 1)

        lay_gaze.addWidget(QLabel("Confidence:"), 0, 2)
        self.lbl_gaze_conf = QLabel("95%")
        self.lbl_gaze_conf.setProperty("class", "ValueLabel")
        lay_gaze.addWidget(self.lbl_gaze_conf, 0, 3)

        lay_gaze.addWidget(QLabel("Zone Dwell:"), 1, 0)
        self.lbl_gaze_dwell = QLabel("0.0s")
        self.lbl_gaze_dwell.setProperty("class", "ValueLabel")
        lay_gaze.addWidget(self.lbl_gaze_dwell, 1, 1)

        lay_gaze.addWidget(QLabel("Iris Center:"), 1, 2)
        self.lbl_iris_center = QLabel("(0.50, 0.50)")
        self.lbl_iris_center.setProperty("class", "ValueLabel")
        lay_gaze.addWidget(self.lbl_iris_center, 1, 3)

        layout.addWidget(grp_gaze)

        # 6. Driver Distraction & Attention Analytics Group
        grp_dist = QGroupBox("Distraction & Attention Analytics")
        lay_dist = QGridLayout(grp_dist)
        lay_dist.setContentsMargins(10, 10, 10, 10)
        lay_dist.setSpacing(6)

        lay_dist.addWidget(QLabel("Distraction State:"), 0, 0)
        self.lbl_distraction_state = QLabel("NORMAL")
        self.lbl_distraction_state.setStyleSheet("color: #10b981; font-weight: bold;")
        lay_dist.addWidget(self.lbl_distraction_state, 0, 1)

        lay_dist.addWidget(QLabel("Off-Road Glance:"), 0, 2)
        self.lbl_offroad_glance = QLabel("0.0s")
        self.lbl_offroad_glance.setProperty("class", "ValueLabel")
        lay_dist.addWidget(self.lbl_offroad_glance, 0, 3)

        lay_dist.addWidget(QLabel("Road Attention:"), 1, 0)
        self.lbl_road_attn_pct = QLabel("100%")
        self.lbl_road_attn_pct.setProperty("class", "ValueLabel")
        lay_dist.addWidget(self.lbl_road_attn_pct, 1, 1)

        self.bar_road_attn = QProgressBar()
        self.bar_road_attn.setRange(0, 100)
        self.bar_road_attn.setValue(100)
        lay_dist.addWidget(self.bar_road_attn, 1, 2, 1, 2)

        lay_dist.addWidget(QLabel("Glance Counters:"), 2, 0)
        self.lbl_glance_counts = QLabel("Down:0 | L:0 | R:0")
        self.lbl_glance_counts.setStyleSheet("color: #94a3b8; font-family: monospace; font-size: 10px;")
        lay_dist.addWidget(self.lbl_glance_counts, 2, 1, 1, 2)

        self.lbl_dist_events = QLabel("Events: 0")
        self.lbl_dist_events.setProperty("class", "ValueLabel")
        lay_dist.addWidget(self.lbl_dist_events, 2, 3)

        layout.addWidget(grp_dist)

        # 7. High-Level Decision States Group
        grp_state = QGroupBox("System State Machine")
        lay_state = QGridLayout(grp_state)
        lay_state.setContentsMargins(10, 10, 10, 10)
        lay_state.setSpacing(6)

        lay_state.addWidget(QLabel("Drowsiness:"), 0, 0)
        self.lbl_drowsiness_state = QLabel("NORMAL")
        self.lbl_drowsiness_state.setStyleSheet("color: #10b981; font-weight: bold; font-size: 12px;")
        lay_state.addWidget(self.lbl_drowsiness_state, 0, 1)

        lay_state.addWidget(QLabel("Abnormal Motion:"), 1, 0)
        self.lbl_abnormal_state = QLabel("NORMAL")
        self.lbl_abnormal_state.setStyleSheet("color: #10b981; font-weight: bold; font-size: 11px;")
        lay_state.addWidget(self.lbl_abnormal_state, 1, 1)

        layout.addWidget(grp_state)
        layout.addStretch()

    def update_telemetry(self, res: FrameAnalysisResult) -> None:
        """Updates all telemetry fields from analysis result."""
        # 1. Face
        if res.face.detected:
            self.lbl_face_status.setText("DETECTED")
            self.lbl_face_status.setStyleSheet("color: #10b981; font-weight: bold;")
            self.lbl_confidence.setText(f"{res.face.confidence:.0%}")
        else:
            lost_sec = res.face.face_lost_duration_sec
            self.lbl_face_status.setText(f"LOST ({lost_sec:.1f}s)")
            self.lbl_face_status.setStyleSheet("color: #ef4444; font-weight: bold;")
            self.lbl_confidence.setText("0%")

        # 2. Eyes
        self.lbl_left_eye.setText(res.eyes.left_status.value)
        self.lbl_left_eye.setStyleSheet("color: #10b981;" if res.eyes.left_status == EyeStatus.OPEN else "color: #ef4444;")
        self.lbl_right_eye.setText(res.eyes.right_status.value)
        self.lbl_right_eye.setStyleSheet("color: #10b981;" if res.eyes.right_status == EyeStatus.OPEN else "color: #ef4444;")

        self.lbl_ear_val.setText(f"{res.eyes.avg_ear:.2f}")
        self.bar_ear.setValue(int(res.eyes.avg_ear * 100))
        # Color bar based on closure
        if res.eyes.overall_status == EyeStatus.CLOSED:
            self.bar_ear.setStyleSheet("QProgressBar::chunk { background-color: #ef4444; }")
        else:
            self.bar_ear.setStyleSheet("QProgressBar::chunk { background-color: #00d2ff; }")

        self.lbl_closure_dur.setText(f"{res.eyes.closure_duration_sec:.1f}s")
        self.lbl_blink_rate.setText(f"{res.eyes.blink_frequency_bpm:.0f} bpm")

        # 3. Mouth
        if res.mouth.is_yawning:
            self.lbl_mouth_status.setText("YAWNING")
            self.lbl_mouth_status.setStyleSheet("color: #f97316; font-weight: bold;")
        elif res.mouth.is_mouth_open:
            self.lbl_mouth_status.setText("OPEN")
            self.lbl_mouth_status.setStyleSheet("color: #f59e0b; font-weight: bold;")
        else:
            self.lbl_mouth_status.setText("NORMAL")
            self.lbl_mouth_status.setStyleSheet("color: #10b981; font-weight: bold;")

        self.lbl_mar_val.setText(f"{res.mouth.mar:.2f}")
        self.bar_mar.setValue(min(100, int(res.mouth.mar * 100)))
        self.lbl_yawn_count.setText(str(res.mouth.yawn_count))
        self.lbl_yawn_dur.setText(f"{res.mouth.yawn_duration_sec:.1f}s")

        # 4. Head Pose
        self.lbl_pitch.setText(f"{res.head_pose.pitch:+.1f}°")
        self.lbl_yaw.setText(f"{res.head_pose.yaw:+.1f}°")
        self.lbl_roll.setText(f"{res.head_pose.roll:+.1f}°")

        if res.head_pose.is_head_down:
            self.lbl_head_posture.setText("HEAD DOWN")
            self.lbl_head_posture.setStyleSheet("color: #ef4444; font-weight: bold;")
        elif res.head_pose.is_head_turned:
            self.lbl_head_posture.setText("TURNED")
            self.lbl_head_posture.setStyleSheet("color: #f97316; font-weight: bold;")
        elif res.head_pose.is_head_tilted:
            self.lbl_head_posture.setText("TILTED")
            self.lbl_head_posture.setStyleSheet("color: #f59e0b; font-weight: bold;")
        else:
            self.lbl_head_posture.setText("LEVEL")
            self.lbl_head_posture.setStyleSheet("color: #10b981; font-weight: bold;")

        self.lbl_nod_count.setText(str(res.head_pose.head_nod_count))

        # 5. Road Gaze & Iris
        gaze_col = "#10b981" if res.gaze.is_looking_at_road else "#00d2ff"
        if res.gaze.direction in (GazeDirection.DOWN, GazeDirection.AWAY):
            gaze_col = "#f97316"
        self.lbl_gaze_dir.setText(res.gaze.direction.value)
        self.lbl_gaze_dir.setStyleSheet(f"color: {gaze_col}; font-weight: bold; font-size: 12px;")
        self.lbl_gaze_conf.setText(f"{res.gaze.confidence:.0%}")
        self.lbl_gaze_dwell.setText(f"{res.gaze.dwell_time_sec:.1f}s")
        if res.iris.is_valid:
            self.lbl_iris_center.setText(f"({res.iris.avg_iris_ratio_x:.2f}, {res.iris.avg_iris_ratio_y:.2f})")
        else:
            self.lbl_iris_center.setText("N/A")

        # 6. Distraction & Analytics
        dist_colors = {
            DistractionState.NORMAL: "#10b981",
            DistractionState.BRIEF_GLANCE: "#00d2ff",
            DistractionState.ATTENTION_WARNING: "#f59e0b",
            DistractionState.VISUAL_DISTRACTION: "#f97316",
            DistractionState.DOWNWARD_DISTRACTION: "#f97316",
            DistractionState.CRITICAL_DEMO_ALERT: "#ef4444",
            DistractionState.UNKNOWN: "#64748b"
        }
        self.lbl_distraction_state.setText(res.distraction.state.value)
        self.lbl_distraction_state.setStyleSheet(f"color: {dist_colors.get(res.distraction.state, '#ffffff')}; font-weight: bold;")
        self.lbl_offroad_glance.setText(f"{res.distraction.off_road_glance_duration_sec:.1f}s")
        self.lbl_road_attn_pct.setText(f"{res.distraction.road_gaze_percent:.0f}%")
        self.bar_road_attn.setValue(int(res.distraction.road_gaze_percent))
        if res.distraction.road_gaze_percent < 60.0:
            self.bar_road_attn.setStyleSheet("QProgressBar::chunk { background-color: #ef4444; }")
        elif res.distraction.road_gaze_percent < 80.0:
            self.bar_road_attn.setStyleSheet("QProgressBar::chunk { background-color: #f59e0b; }")
        else:
            self.bar_road_attn.setStyleSheet("QProgressBar::chunk { background-color: #10b981; }")

        self.lbl_glance_counts.setText(
            f"Down:{res.distraction.downward_glance_count} | L:{res.distraction.left_glance_count} | R:{res.distraction.right_glance_count}"
        )
        self.lbl_dist_events.setText(f"Events: {res.distraction.distraction_event_count}")

        # 7. States
        drow_colors = {
            "NORMAL": "#10b981",
            "ATTENTION": "#f59e0b",
            "DROWSINESS_WARNING": "#f97316",
            "CRITICAL_DEMO_ALERT": "#ef4444"
        }
        self.lbl_drowsiness_state.setText(res.drowsiness.state.value)
        self.lbl_drowsiness_state.setStyleSheet(f"color: {drow_colors.get(res.drowsiness.state.value, '#ffffff')}; font-weight: bold;")

        abn_text = res.abnormal.alert_title if res.abnormal.is_active else "NORMAL"
        self.lbl_abnormal_state.setText(abn_text)
        self.lbl_abnormal_state.setStyleSheet("color: #f97316; font-weight: bold;" if res.abnormal.is_active else "color: #10b981; font-weight: bold;")
