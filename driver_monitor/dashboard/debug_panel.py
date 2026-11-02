"""
Debug and Telemetry Graph Panel for Driver Monitoring System.
Renders real-time rolling strip charts for EAR, MAR, and Head Pose (Pitch, Yaw, Roll)
using lightweight high-performance QPainter graphics, alongside a live state transition log.
"""

from collections import deque
from typing import Deque, List, Optional, Tuple
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QBrush
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QListWidget, QListWidgetItem, QSplitter
)

from driver_monitor.core.result_models import FrameAnalysisResult


class RealtimeGraphWidget(QWidget):
    """Custom high-performance rolling line graph drawn with QPainter."""

    def __init__(
        self,
        title: str,
        series_names: List[str],
        series_colors: List[str],
        y_min: float = 0.0,
        y_max: float = 1.0,
        threshold: Optional[float] = None,
        max_points: int = 120,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self._title = title
        self._series_names = series_names
        self._series_colors = [QColor(c) for c in series_colors]
        self._y_min = y_min
        self._y_max = y_max
        self._threshold = threshold
        self._max_points = max_points

        # Data deques for each series
        self._data: List[Deque[float]] = [deque(maxlen=max_points) for _ in series_names]
        self.setMinimumHeight(80)

    def add_point(self, values: List[float]) -> None:
        for i, val in enumerate(values):
            if i < len(self._data):
                self._data[i].append(val)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Dark graph background
        painter.fillRect(0, 0, w, h, QColor("#0e121a"))

        # Outer border
        painter.setPen(QPen(QColor("#1f2738"), 1))
        painter.drawRect(0, 0, w - 1, h - 1)

        # Title and legend
        painter.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        painter.setPen(QColor("#94a3b8"))
        painter.drawText(8, 14, self._title)

        # Draw series legend labels right-aligned
        lx = w - 10
        for name, color in reversed(list(zip(self._series_names, self._series_colors))):
            painter.setPen(color)
            painter.drawText(lx - 50, 14, name)
            lx -= 55

        # Plot margins
        top = 22
        bot = h - 8
        left = 10
        right = w - 10
        plot_h = bot - top
        plot_w = right - left

        # Grid line: Zero / Center line
        if self._y_min < 0 < self._y_max:
            zero_ratio = (0.0 - self._y_min) / (self._y_max - self._y_min)
            zero_y = bot - zero_ratio * plot_h
            painter.setPen(QPen(QColor("#242d40"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(int(left), int(zero_y), int(right), int(zero_y))

        # Threshold line
        if self._threshold is not None and self._y_min <= self._threshold <= self._y_max:
            thresh_ratio = (self._threshold - self._y_min) / (self._y_max - self._y_min)
            thresh_y = bot - thresh_ratio * plot_h
            painter.setPen(QPen(QColor("#ef4444"), 1, Qt.PenStyle.DotLine))
            painter.drawLine(int(left), int(thresh_y), int(right), int(thresh_y))

        # Draw series lines
        y_range = max(1e-5, self._y_max - self._y_min)

        for s_idx, series in enumerate(self._data):
            if len(series) < 2:
                continue

            pen = QPen(self._series_colors[s_idx], 2)
            painter.setPen(pen)

            step_x = plot_w / float(self._max_points - 1)
            offset_x = left + (self._max_points - len(series)) * step_x

            points = []
            for i, val in enumerate(series):
                clamped_val = max(self._y_min, min(self._y_max, val))
                norm_y = (clamped_val - self._y_min) / y_range
                px = offset_x + i * step_x
                py = bot - norm_y * plot_h
                points.append(QPointF(px, py))

            for i in range(len(points) - 1):
                painter.drawLine(points[i], points[i + 1])

        painter.end()


class DebugPanel(QWidget):
    """Panel hosting live telemetry graphs and recent state transition event log."""

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
            QListWidget {
                background-color: #0b0d13;
                border: 1px solid #1f2533;
                border-radius: 6px;
                color: #cbd5e1;
                font-family: monospace;
                font-size: 10px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # Row 1: Biometric Indicators (EAR and MAR Trends)
        row1 = QHBoxLayout()
        row1.setSpacing(6)

        # 1. EAR Graph (Eye Aspect Ratio)
        grp_ear = QGroupBox("Eye Aspect Ratio (EAR)")
        lay_ear = QVBoxLayout(grp_ear)
        lay_ear.setContentsMargins(6, 6, 6, 6)
        self.graph_ear = RealtimeGraphWidget(
            title="EAR (Thresh: 0.22)",
            series_names=["EAR"],
            series_colors=["#00d2ff"],
            y_min=0.0,
            y_max=0.55,
            threshold=0.22
        )
        lay_ear.addWidget(self.graph_ear)
        row1.addWidget(grp_ear)

        # 2. MAR Graph (Mouth Aspect Ratio)
        grp_mar = QGroupBox("Mouth Aspect Ratio (MAR)")
        lay_mar = QVBoxLayout(grp_mar)
        lay_mar.setContentsMargins(6, 6, 6, 6)
        self.graph_mar = RealtimeGraphWidget(
            title="MAR (Yawn Thresh: 0.55)",
            series_names=["MAR"],
            series_colors=["#f59e0b"],
            y_min=0.0,
            y_max=0.85,
            threshold=0.55
        )
        lay_mar.addWidget(self.graph_mar)
        row1.addWidget(grp_mar)

        layout.addLayout(row1)

        # Row 2: Kinematics & Road Attention Trends
        row2 = QHBoxLayout()
        row2.setSpacing(6)

        # 3. Head Pose (Pitch, Yaw, Roll)
        grp_pose = QGroupBox("Head Orientation Angles (°)")
        lay_pose = QVBoxLayout(grp_pose)
        lay_pose.setContentsMargins(6, 6, 6, 6)
        self.graph_pose = RealtimeGraphWidget(
            title="Pitch / Yaw / Roll",
            series_names=["Pitch", "Yaw", "Roll"],
            series_colors=["#10b981", "#3b82f6", "#a855f7"],
            y_min=-60.0,
            y_max=60.0,
            threshold=None
        )
        lay_pose.addWidget(self.graph_pose)
        row2.addWidget(grp_pose)

        # 4. Road Attention & Off-road Glance Trend
        grp_attn = QGroupBox("Road Attention & Off-Road Glance")
        lay_attn = QVBoxLayout(grp_attn)
        lay_attn.setContentsMargins(6, 6, 6, 6)
        self.graph_attn = RealtimeGraphWidget(
            title="Road Attn % / Glance (s)",
            series_names=["Road %", "Glance(s)"],
            series_colors=["#10b981", "#ef4444"],
            y_min=0.0,
            y_max=100.0,
            threshold=75.0
        )
        lay_attn.addWidget(self.graph_attn)
        row2.addWidget(grp_attn)

        layout.addLayout(row2)

        # 5. State Transitions & Event Log
        grp_log = QGroupBox("Recent State Transitions")
        lay_log = QVBoxLayout(grp_log)
        lay_log.setContentsMargins(6, 6, 6, 6)
        self.log_list = QListWidget()
        self.log_list.setMaximumHeight(85)
        lay_log.addWidget(self.log_list)
        layout.addWidget(grp_log)

    def update_telemetry(self, res: FrameAnalysisResult) -> None:
        """Pushes new frame data to strip charts."""
        self.graph_ear.add_point([res.eyes.avg_ear])
        self.graph_mar.add_point([res.mouth.mar])
        self.graph_pose.add_point([
            res.head_pose.pitch,
            res.head_pose.yaw,
            res.head_pose.roll
        ])
        # Off-road glance duration scaled to match 0-100% chart (e.g., 5.0s = 100%)
        glance_scaled = min(100.0, res.distraction.off_road_glance_duration_sec * 20.0)
        self.graph_attn.add_point([
            res.distraction.road_gaze_percent,
            glance_scaled
        ])

    def add_log_message(self, message: str, level: str = "INFO") -> None:
        """Appends event message to list widget."""
        item = QListWidgetItem(message)
        if level in ("CRITICAL", "RED"):
            item.setForeground(QColor("#ef4444"))
        elif level in ("WARNING", "ORANGE"):
            item.setForeground(QColor("#f97316"))
        elif level in ("ATTENTION", "YELLOW"):
            item.setForeground(QColor("#f59e0b"))
        else:
            item.setForeground(QColor("#10b981"))

        self.log_list.addItem(item)
        if self.log_list.count() > 100:
            self.log_list.takeItem(0)
        self.log_list.scrollToBottom()
