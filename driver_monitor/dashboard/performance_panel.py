"""
Performance and System Diagnostics Panel for Driver Monitoring System.
Displays real-time FPS, frame latency, CPU and memory utilization, and camera stream properties.
"""

from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QLabel, QGroupBox, QProgressBar
)

from driver_monitor.core.result_models import PerformanceMetrics


class PerformancePanel(QWidget):
    """System resource, frame rate, and hardware latency diagnostic display."""

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
            QProgressBar {
                background-color: #1b2130;
                border: 1px solid #283347;
                border-radius: 4px;
                text-align: center;
                color: #ffffff;
                font-size: 10px;
                height: 12px;
            }
            QProgressBar::chunk {
                background-color: #10b981;
                border-radius: 3px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        grp_perf = QGroupBox("Engine Performance")
        lay = QGridLayout(grp_perf)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(6)

        lay.addWidget(QLabel("Pipeline FPS:"), 0, 0)
        self.lbl_fps = QLabel("30.0 FPS")
        self.lbl_fps.setStyleSheet("color: #10b981; font-weight: bold; font-size: 13px;")
        lay.addWidget(self.lbl_fps, 0, 1)

        lay.addWidget(QLabel("Latency:"), 0, 2)
        self.lbl_latency = QLabel("15.2 ms")
        self.lbl_latency.setProperty("class", "ValueLabel")
        lay.addWidget(self.lbl_latency, 0, 3)

        lay.addWidget(QLabel("CPU Usage:"), 1, 0)
        self.lbl_cpu = QLabel("12%")
        self.lbl_cpu.setProperty("class", "ValueLabel")
        lay.addWidget(self.lbl_cpu, 1, 1)

        self.bar_cpu = QProgressBar()
        self.bar_cpu.setRange(0, 100)
        self.bar_cpu.setValue(12)
        lay.addWidget(self.bar_cpu, 1, 2, 1, 2)

        lay.addWidget(QLabel("Memory:"), 2, 0)
        self.lbl_mem = QLabel("45%")
        self.lbl_mem.setProperty("class", "ValueLabel")
        lay.addWidget(self.lbl_mem, 2, 1)

        self.bar_mem = QProgressBar()
        self.bar_mem.setRange(0, 100)
        self.bar_mem.setValue(45)
        lay.addWidget(self.bar_mem, 2, 2, 1, 2)

        lay.addWidget(QLabel("Resolution:"), 3, 0)
        self.lbl_res = QLabel("1280 x 720")
        self.lbl_res.setProperty("class", "ValueLabel")
        lay.addWidget(self.lbl_res, 3, 1)

        lay.addWidget(QLabel("Input Source:"), 3, 2)
        self.lbl_source = QLabel("FaceTime HD")
        self.lbl_source.setProperty("class", "ValueLabel")
        lay.addWidget(self.lbl_source, 3, 3)

        layout.addWidget(grp_perf)

    def update_metrics(self, perf: PerformanceMetrics) -> None:
        """Updates performance meters."""
        self.lbl_fps.setText(f"{perf.fps:.1f} FPS")
        # Color FPS
        if perf.fps >= 25.0:
            self.lbl_fps.setStyleSheet("color: #10b981; font-weight: bold; font-size: 13px;")
        elif perf.fps >= 15.0:
            self.lbl_fps.setStyleSheet("color: #f59e0b; font-weight: bold; font-size: 13px;")
        else:
            self.lbl_fps.setStyleSheet("color: #ef4444; font-weight: bold; font-size: 13px;")

        self.lbl_latency.setText(f"{perf.processing_latency_ms:.1f} ms")
        self.lbl_cpu.setText(f"{perf.cpu_percent:.0f}%")
        self.bar_cpu.setValue(int(perf.cpu_percent))

        self.lbl_mem.setText(f"{perf.memory_percent:.0f}%")
        self.bar_mem.setValue(int(perf.memory_percent))

        w, h = perf.resolution
        self.lbl_res.setText(f"{w} x {h}")
        self.lbl_source.setText(perf.source_name[:18])
