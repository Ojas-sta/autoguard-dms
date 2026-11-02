"""
Camera and Video Display Widget for Driver Monitoring System.
Renders annotated video frames with high performance in PyQt6,
and provides video playback controls (play/pause, seek slider, restart) when playing prerecorded files.
"""

from typing import Optional
import cv2
import numpy as np

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QPainter, QColor, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QPushButton, QSizePolicy
)

from driver_monitor.camera.video_source import VideoSource


class CameraWidget(QWidget):
    """Displays camera stream and provides video playback controls."""

    seek_requested = pyqtSignal(float)   # Emits progress [0.0 - 1.0]
    play_pause_clicked = pyqtSignal()
    restart_clicked = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._current_pixmap: Optional[QPixmap] = None
        self._is_video_mode = False
        self._is_seeking = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Video Frame Display Area
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet("""
            QLabel {
                background-color: #0b0d13;
                border: 1px solid #1f2533;
                border-radius: 8px;
            }
        """)
        self.video_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.video_label.setMinimumSize(480, 320)
        layout.addWidget(self.video_label)

        # Video Playback Control Bar (hidden by default, shown for video files)
        self.controls_widget = QWidget()
        self.controls_widget.setStyleSheet("""
            QWidget {
                background-color: #141822;
                border-radius: 6px;
                padding: 4px;
            }
            QPushButton {
                background-color: #1f2637;
                color: #e2e8f0;
                border: 1px solid #2d3748;
                border-radius: 4px;
                padding: 5px 12px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #2b354d;
                border-color: #3b82f6;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #232a3b;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #00d2ff;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                width: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }
            QLabel {
                color: #94a3b8;
                font-size: 11px;
                font-family: monospace;
            }
        """)
        controls_layout = QHBoxLayout(self.controls_widget)
        controls_layout.setContentsMargins(8, 4, 8, 4)
        controls_layout.setSpacing(10)

        self.btn_play_pause = QPushButton("PAUSE")
        self.btn_play_pause.clicked.connect(self.play_pause_clicked.emit)
        controls_layout.addWidget(self.btn_play_pause)

        self.btn_restart = QPushButton("RESTART")
        self.btn_restart.clicked.connect(self.restart_clicked.emit)
        controls_layout.addWidget(self.btn_restart)

        self.lbl_time = QLabel("00:00 / 00:00")
        controls_layout.addWidget(self.lbl_time)

        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.setValue(0)
        self.seek_slider.sliderPressed.connect(self._on_slider_pressed)
        self.seek_slider.sliderReleased.connect(self._on_slider_released)
        controls_layout.addWidget(self.seek_slider)

        layout.addWidget(self.controls_widget)
        self.controls_widget.setVisible(False)

    def set_video_mode(self, is_video: bool) -> None:
        """Shows or hides video playback scrub bar."""
        self._is_video_mode = is_video
        self.controls_widget.setVisible(is_video)

    def update_frame(self, frame_bgr: np.ndarray) -> None:
        """Renders an OpenCV BGR frame onto the QLabel."""
        if frame_bgr is None or frame_bgr.size == 0:
            return

        h, w, ch = frame_bgr.shape
        bytes_per_line = ch * w
        # Convert BGR to RGB
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        qimg = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)

        # Scale smoothly while preserving aspect ratio
        scaled = pixmap.scaled(
            self.video_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.video_label.setPixmap(scaled)
        self._current_pixmap = scaled

    def update_video_progress(self, current_sec: float, total_sec: float, progress: float, is_paused: bool) -> None:
        """Updates scrub slider and time indicator for prerecorded video."""
        if not self._is_video_mode or self._is_seeking:
            return

        cur_m, cur_s = divmod(int(current_sec), 60)
        tot_m, tot_s = divmod(int(total_sec), 60)
        self.lbl_time.setText(f"{cur_m:02d}:{cur_s:02d} / {tot_m:02d}:{tot_s:02d}")
        self.seek_slider.setValue(int(progress * 1000))
        self.btn_play_pause.setText("PLAY" if is_paused else "PAUSE")

    def _on_slider_pressed(self) -> None:
        self._is_seeking = True

    def _on_slider_released(self) -> None:
        self._is_seeking = False
        val = self.seek_slider.value() / 1000.0
        self.seek_requested.emit(val)

    def show_no_camera_message(self, message: str = "CAMERA STANDBY") -> None:
        """Displays standby / disconnected state."""
        pixmap = QPixmap(self.video_label.size())
        pixmap.fill(QColor("#0b0d13"))
        painter = QPainter(pixmap)
        painter.setPen(QColor("#64748b"))
        painter.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, message)
        painter.end()
        self.video_label.setPixmap(pixmap)
