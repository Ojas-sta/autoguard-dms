"""
Main Dashboard Window for Driver Monitoring System.
Automotive-grade cockpit interface integrating live camera, biometric telemetry cards,
performance monitors, real-time strip charts, alert banner, and interactive simulation controls.
"""

import os
import time
from typing import Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon, QFont
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QComboBox, QFileDialog, QSplitter, QCheckBox, QMessageBox
)

from driver_monitor.camera.camera_manager import CameraManager
from driver_monitor.camera.video_source import VideoSource
from driver_monitor.config import AppConfig
from driver_monitor.core.detection_pipeline import DetectionPipeline
from driver_monitor.core.event_manager import global_event_bus
from driver_monitor.core.platform_manager import PlatformManager
from driver_monitor.core.result_models import FrameAnalysisResult
from driver_monitor.dashboard.alert_widget import AlertWidget
from driver_monitor.dashboard.camera_widget import CameraWidget
from driver_monitor.dashboard.debug_panel import DebugPanel
from driver_monitor.dashboard.monitoring_panel import MonitoringPanel
from driver_monitor.dashboard.performance_panel import PerformancePanel
from driver_monitor.hardware.hardware_factory import HardwareFactory
from driver_monitor.logging.event_logger import EventLogger
from driver_monitor.utils.video_generator import generate_all_test_videos


class PipelineWorker(QThread):
    """Background worker thread executing camera capture and detection pipeline."""

    frame_processed = pyqtSignal(FrameAnalysisResult)
    video_progress_updated = pyqtSignal(float, float, float, bool)  # cur_sec, tot_sec, progress, paused
    error_occurred = pyqtSignal(str)

    def __init__(self, camera_mgr: CameraManager, pipeline: DetectionPipeline):
        super().__init__()
        self.camera_mgr = camera_mgr
        self.pipeline = pipeline
        self._running = False

    def run(self) -> None:
        self._running = True
        while self._running:
            ret, frame = self.camera_mgr.read_frame()
            if not ret or frame is None:
                time.sleep(0.03)
                continue

            # Process frame through pipeline
            try:
                res = self.pipeline.process_frame(
                    frame,
                    source_name=self.camera_mgr.get_device_name(),
                    source_type=self.camera_mgr.source_type
                )
                self.frame_processed.emit(res)

                # Emit video progress if playing prerecorded video
                if self.camera_mgr.is_video_source:
                    vid = self.camera_mgr.active_source
                    if isinstance(vid, VideoSource):
                        self.video_progress_updated.emit(
                            vid.current_time_sec,
                            vid.duration_sec,
                            vid.progress_percent,
                            vid.is_paused()
                        )
            except Exception as e:
                self.error_occurred.emit(str(e))
                time.sleep(0.05)

    def stop(self) -> None:
        self._running = False
        self.wait(1000)


class MainWindow(QMainWindow):
    """Cockpit Driver Monitoring System main window."""

    def __init__(self, platform_mgr: PlatformManager, initial_video_path: Optional[str] = None):
        super().__init__()
        self.platform_mgr = platform_mgr
        self.config = platform_mgr.config
        self.logger = EventLogger()

        # Initialize Hardware & Pipeline
        self.buzzer, self.leds, self.emergency_button = HardwareFactory.create_hardware(
            platform_mgr.active_platform, self.config.hardware
        )
        self.pipeline = DetectionPipeline(
            self.config, self.buzzer, self.leds, self.emergency_button, self.logger
        )

        # Initialize Camera Manager
        self.camera_mgr = CameraManager(platform_mgr.active_platform, self.config.camera)

        # Worker thread
        self.worker: Optional[PipelineWorker] = None

        # Build UI
        self._setup_ui()
        self._connect_signals()

        # Generate preset test videos if needed
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.videos_dir = os.path.join(base_dir, "resources", "videos")
        self.test_video_paths = generate_all_test_videos(self.videos_dir)

        # Start default video or camera
        if initial_video_path and os.path.exists(initial_video_path):
            self._load_video_file(initial_video_path)
        else:
            self._start_camera()

    def _setup_ui(self) -> None:
        self.setWindowTitle("AutoGuard DMS — Standalone Driver Monitoring & Drowsiness Detection System")
        self.resize(1360, 880)
        self.setMinimumSize(1024, 680)

        # Modern Automotive Dark Theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0b0d13;
            }
            QWidget {
                color: #e2e8f0;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }
            QComboBox {
                background-color: #1a202c;
                border: 1px solid #2d3748;
                border-radius: 4px;
                padding: 4px 8px;
                color: #e2e8f0;
                font-size: 11px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QPushButton {
                background-color: #1e2638;
                color: #e2e8f0;
                border: 1px solid #2d3748;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2b354d;
                border-color: #00d2ff;
            }
            QPushButton:checked {
                background-color: #0284c7;
                border-color: #38bdf8;
                color: #ffffff;
            }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(10)

        # -------------------------------------------------------------
        # 1. Top Header Bar
        # -------------------------------------------------------------
        header = QWidget()
        header.setStyleSheet("""
            QWidget {
                background-color: #12151e;
                border: 1px solid #1e2536;
                border-radius: 8px;
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 8, 14, 8)

        lbl_logo = QLabel("AUTOGUARD DMS")
        lbl_logo.setStyleSheet("font-size: 16px; font-weight: 900; color: #00d2ff; letter-spacing: 2px;")
        header_layout.addWidget(lbl_logo)

        plat_info = self.platform_mgr.get_info()
        plat_badge_text = f"PLATFORM: {self.platform_mgr.active_platform.upper()} [{plat_info['architecture'].upper()}]"
        lbl_plat = QLabel(plat_badge_text)
        lbl_plat.setStyleSheet("background-color: #1e293b; color: #94a3b8; font-size: 10px; font-weight: bold; padding: 4px 8px; border-radius: 4px;")
        header_layout.addWidget(lbl_plat)

        header_layout.addStretch()

        # Sound toggle button
        self.btn_sound_toggle = QPushButton("🔊 AUDIO ALERTS: ON")
        self.btn_sound_toggle.setCheckable(True)
        self.btn_sound_toggle.setChecked(True)
        self.btn_sound_toggle.clicked.connect(self._toggle_sound)
        header_layout.addWidget(self.btn_sound_toggle)

        # Calibrate Neutral Head Pose button
        self.btn_calibrate = QPushButton("🎯 ZERO HEAD POSE")
        self.btn_calibrate.clicked.connect(self._calibrate_head_pose)
        header_layout.addWidget(self.btn_calibrate)

        # Debug charts toggle
        self.btn_debug_toggle = QPushButton("📈 CHARTS: ON")
        self.btn_debug_toggle.setCheckable(True)
        self.btn_debug_toggle.setChecked(True)
        self.btn_debug_toggle.clicked.connect(self._toggle_debug_panel)
        header_layout.addWidget(self.btn_debug_toggle)

        main_layout.addWidget(header)

        # -------------------------------------------------------------
        # 2. Central Splitter (Left: Video | Right: Telemetry & Performance)
        # -------------------------------------------------------------
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(8)

        # Left Column: Video display + Debug charts below
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        self.camera_widget = CameraWidget()
        left_layout.addWidget(self.camera_widget, stretch=3)

        self.debug_panel = DebugPanel()
        left_layout.addWidget(self.debug_panel, stretch=2)

        splitter.addWidget(left_container)

        # Right Column: Monitoring telemetry + Performance panel
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        self.monitoring_panel = MonitoringPanel()
        right_layout.addWidget(self.monitoring_panel, stretch=3)

        self.performance_panel = PerformancePanel()
        right_layout.addWidget(self.performance_panel, stretch=1)

        splitter.addWidget(right_container)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        main_layout.addWidget(splitter, stretch=1)

        # -------------------------------------------------------------
        # 3. Alert Banner & Hardware LED Cluster
        # -------------------------------------------------------------
        self.alert_widget = AlertWidget()
        main_layout.addWidget(self.alert_widget)

        # -------------------------------------------------------------
        # 4. Bottom Controls Action Bar
        # -------------------------------------------------------------
        controls = QWidget()
        controls.setStyleSheet("""
            QWidget {
                background-color: #12151e;
                border: 1px solid #1e2536;
                border-radius: 8px;
            }
        """)
        ctrl_layout = QHBoxLayout(controls)
        ctrl_layout.setContentsMargins(12, 8, 12, 8)
        ctrl_layout.setSpacing(10)

        # Start / Stop Monitoring
        self.btn_start_stop = QPushButton("STOP MONITORING")
        self.btn_start_stop.setStyleSheet("background-color: #0369a1; border-color: #0284c7; color: white;")
        self.btn_start_stop.clicked.connect(self._toggle_monitoring)
        ctrl_layout.addWidget(self.btn_start_stop)

        # Camera Switcher Dropdown
        ctrl_layout.addWidget(QLabel("Camera:"))
        self.combo_camera = QComboBox()
        self._populate_cameras()
        self.combo_camera.currentIndexChanged.connect(self._on_camera_selected)
        ctrl_layout.addWidget(self.combo_camera)

        # Test Video Selector Dropdown
        ctrl_layout.addWidget(QLabel("Test Video:"))
        self.combo_video = QComboBox()
        self.combo_video.addItem("-- Select Test Video --", None)
        self.combo_video.addItem("1. Normal Driving", "normal")
        self.combo_video.addItem("2. Eyes Closed (Drowsiness)", "eyes_closed")
        self.combo_video.addItem("3. Head Nodding", "head_nodding")
        self.combo_video.addItem("4. Yawning", "yawning")
        self.combo_video.addItem("5. Head Tilted", "head_tilted")
        self.combo_video.addItem("6. Head Turned", "head_turned")
        self.combo_video.addItem("7. Face Lost", "face_lost")
        self.combo_video.currentIndexChanged.connect(self._on_preset_video_selected)
        ctrl_layout.addWidget(self.combo_video)

        self.btn_browse_video = QPushButton("Open File...")
        self.btn_browse_video.clicked.connect(self._browse_custom_video)
        ctrl_layout.addWidget(self.btn_browse_video)

        ctrl_layout.addStretch()

        # Simulation Injection Buttons
        self.btn_sim_drowsy = QPushButton("Simulate Drowsy")
        self.btn_sim_drowsy.setCheckable(True)
        self.btn_sim_drowsy.clicked.connect(self._toggle_sim_drowsy)
        ctrl_layout.addWidget(self.btn_sim_drowsy)

        self.btn_sim_abnormal = QPushButton("Simulate Abnormal Head")
        self.btn_sim_abnormal.setCheckable(True)
        self.btn_sim_abnormal.clicked.connect(self._toggle_sim_abnormal)
        ctrl_layout.addWidget(self.btn_sim_abnormal)

        main_layout.addWidget(controls)

    def _connect_signals(self) -> None:
        """Connects signals between widgets and pipeline."""
        self.alert_widget.emergency_triggered.connect(self._on_emergency_triggered)
        self.alert_widget.reset_clicked.connect(self._on_reset_clicked)

        self.camera_widget.seek_requested.connect(self._on_seek_requested)
        self.camera_widget.play_pause_clicked.connect(self._on_play_pause_clicked)
        self.camera_widget.restart_clicked.connect(self._on_restart_clicked)

        # Global event bus subscriptions
        global_event_bus.subscribe("new_log_entry", self._on_new_log)

    def _populate_cameras(self) -> None:
        """Populates available cameras in combo box."""
        self.combo_camera.clear()
        cams = self.camera_mgr.get_available_cameras()
        if not cams:
            self.combo_camera.addItem("Default Camera (Index 0)", 0)
        else:
            for idx, name in cams:
                self.combo_camera.addItem(name, idx)

    def _start_camera(self) -> None:
        """Starts default camera and background worker."""
        if self.worker is not None and self.worker.isRunning():
            self.worker.stop()

        success = self.camera_mgr.initialize_default_camera()
        if not success:
            self.camera_widget.show_no_camera_message("NO CAMERA DETECTED\nCheck Mac Camera Permissions")
            return

        self.camera_widget.set_video_mode(False)
        self._start_worker()

    def _load_video_file(self, file_path: str) -> None:
        """Loads a video file into the camera manager."""
        if self.worker is not None and self.worker.isRunning():
            self.worker.stop()

        success = self.camera_mgr.load_video_file(file_path, loop=True)
        if success:
            self.camera_widget.set_video_mode(True)
            self._start_worker()
        else:
            QMessageBox.warning(self, "Load Error", f"Could not load video file: {file_path}")

    def _start_worker(self) -> None:
        """Spawns background capture and detection thread."""
        self.worker = PipelineWorker(self.camera_mgr, self.pipeline)
        self.worker.frame_processed.connect(self._on_frame_processed)
        self.worker.video_progress_updated.connect(self.camera_widget.update_video_progress)
        self.worker.error_occurred.connect(self._on_worker_error)
        self.worker.start()
        self.btn_start_stop.setText("STOP MONITORING")
        self.btn_start_stop.setStyleSheet("background-color: #0369a1; border-color: #0284c7; color: white;")

    def _stop_worker(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.worker.stop()
            self.worker = None
        self.camera_widget.show_no_camera_message("MONITORING PAUSED")
        self.btn_start_stop.setText("START MONITORING")
        self.btn_start_stop.setStyleSheet("background-color: #10b981; border-color: #059669; color: white;")

    def _on_frame_processed(self, result: FrameAnalysisResult) -> None:
        """Main update dispatcher invoked by worker thread on each processed frame."""
        # Update camera view with annotated frame
        if result.annotated_frame is not None:
            self.camera_widget.update_frame(result.annotated_frame)

        # Update telemetry cards
        self.monitoring_panel.update_telemetry(result)

        # Update performance diagnostics
        self.performance_panel.update_metrics(result.performance)

        # Update debug charts
        self.debug_panel.update_telemetry(result)

        # Update alert banner and LEDs
        self.alert_widget.update_alert(result.alert)

    def _on_new_log(self, entry: dict) -> None:
        msg = f"[{entry['timestamp'].split()[-1]}] {entry['message']}"
        self.debug_panel.add_log_message(msg, entry.get("level", "INFO"))

    def _on_worker_error(self, err_msg: str) -> None:
        self.logger.log_event("PIPELINE_ERROR", err_msg, level="ERROR")

    def _toggle_monitoring(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            self._stop_worker()
        else:
            if self.camera_mgr.active_source is None:
                self._start_camera()
            else:
                self._start_worker()

    def _on_camera_selected(self, index: int) -> None:
        if index < 0:
            return
        cam_idx = self.combo_camera.currentData()
        if cam_idx is not None:
            if self.worker is not None and self.worker.isRunning():
                self.worker.stop()
            self.camera_mgr.switch_to_camera(cam_idx)
            self.camera_widget.set_video_mode(False)
            self._start_worker()

    def _on_preset_video_selected(self, index: int) -> None:
        scenario_key = self.combo_video.currentData()
        if scenario_key and scenario_key in self.test_video_paths:
            path = self.test_video_paths[scenario_key]
            self._load_video_file(path)

    def _browse_custom_video(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Video File", "", "Video Files (*.mp4 *.mov *.avi)"
        )
        if file_path:
            self._load_video_file(file_path)

    def _toggle_sound(self) -> None:
        is_on = self.btn_sound_toggle.isChecked()
        self.pipeline.alert_manager.set_sound_enabled(is_on)
        self.pipeline.buzzer.set_enabled(is_on)
        self.btn_sound_toggle.setText("🔊 AUDIO ALERTS: ON" if is_on else "🔇 AUDIO ALERTS: OFF")

    def _calibrate_head_pose(self) -> None:
        # Zeroes current head orientation as 0,0,0 forward facing
        curr_pitch = self.monitoring_panel.lbl_pitch.text().replace("°", "")
        curr_yaw = self.monitoring_panel.lbl_yaw.text().replace("°", "")
        curr_roll = self.monitoring_panel.lbl_roll.text().replace("°", "")
        try:
            self.pipeline.head_pose_estimator.calibrate(
                float(curr_pitch), float(curr_yaw), float(curr_roll)
            )
            self.logger.log_event("CALIBRATION", "Head pose calibrated to neutral forward position")
        except Exception:
            pass

    def _toggle_debug_panel(self) -> None:
        is_visible = self.btn_debug_toggle.isChecked()
        self.debug_panel.setVisible(is_visible)
        self.btn_debug_toggle.setText("📈 CHARTS: ON" if is_visible else "📈 CHARTS: OFF")

    def _toggle_sim_drowsy(self) -> None:
        active = self.pipeline.emergency_sim.toggle_simulate_drowsiness()
        self.btn_sim_drowsy.setChecked(active)
        self.btn_sim_drowsy.setText("Drowsy (SIMULATED)" if active else "Simulate Drowsy")

    def _toggle_sim_abnormal(self) -> None:
        active = self.pipeline.emergency_sim.toggle_simulate_abnormal_movement()
        self.btn_sim_abnormal.setChecked(active)
        self.btn_sim_abnormal.setText("Abnormal (SIMULATED)" if active else "Simulate Abnormal Head")

    def _on_emergency_triggered(self) -> None:
        self.pipeline.emergency_sim.trigger_emergency()

    def _on_reset_clicked(self) -> None:
        self.pipeline.reset_all()
        self.btn_sim_drowsy.setChecked(False)
        self.btn_sim_drowsy.setText("Simulate Drowsy")
        self.btn_sim_abnormal.setChecked(False)
        self.btn_sim_abnormal.setText("Simulate Abnormal Head")

    def _on_seek_requested(self, percent: float) -> None:
        if self.camera_mgr.is_video_source:
            vid = self.camera_mgr.active_source
            if isinstance(vid, VideoSource):
                vid.seek_percent(percent)

    def _on_play_pause_clicked(self) -> None:
        if self.camera_mgr.is_video_source:
            vid = self.camera_mgr.active_source
            if isinstance(vid, VideoSource):
                vid.toggle_pause()

    def _on_restart_clicked(self) -> None:
        if self.camera_mgr.is_video_source:
            vid = self.camera_mgr.active_source
            if isinstance(vid, VideoSource):
                vid.restart()

    def closeEvent(self, event) -> None:
        """Gracefully release camera and worker thread on close."""
        self._stop_worker()
        self.camera_mgr.release()
        self.pipeline.buzzer.stop_alert()
        event.accept()
