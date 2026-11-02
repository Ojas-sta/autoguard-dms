"""
Automotive Alert Banner and Simulated LED Cluster Widget.
Renders large illuminated status indicators (Green, Yellow, Orange, Red)
and provides immediate Emergency Trigger and Reset controls.
"""

from typing import Optional
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QBrush, QPen
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
)

from driver_monitor.core.result_models import AlertLevel, SystemAlert


class LEDIndicator(QWidget):
    """Circular simulated hardware LED with realistic glow effect."""

    def __init__(self, color_name: str, label_text: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._color_name = color_name
        self._label_text = label_text
        self._is_on = False
        self.setFixedSize(50, 55)

    def set_state(self, is_on: bool) -> None:
        if self._is_on != is_on:
            self._is_on = is_on
            self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        color_palette = {
            "green": (QColor("#10b981"), QColor("#064e3b")),
            "yellow": (QColor("#f59e0b"), QColor("#78350f")),
            "orange": (QColor("#f97316"), QColor("#7c2d12")),
            "red": (QColor("#ef4444"), QColor("#7f1d1d")),
        }

        lit_color, dim_color = color_palette.get(self._color_name, (QColor("#ffffff"), QColor("#333333")))

        cx, cy, r = 25, 20, 14

        # Bezel / outer ring
        painter.setPen(QPen(QColor("#2d3748"), 2))
        painter.setBrush(QBrush(QColor("#1a202c")))
        painter.drawEllipse(cx - r - 2, cy - r - 2, (r + 2) * 2, (r + 2) * 2)

        # LED core
        if self._is_on:
            painter.setPen(Qt.PenStyle.NoPen)
            # Subtle glow
            painter.setBrush(QBrush(lit_color))
            painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)
            # Specular highlight
            painter.setBrush(QBrush(QColor(255, 255, 255, 180)))
            painter.drawEllipse(cx - 6, cy - 8, 6, 4)
        else:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(dim_color))
            painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        # Text label below
        painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        painter.setPen(lit_color if self._is_on else QColor("#64748b"))
        painter.drawText(0, 48, 50, 12, Qt.AlignmentFlag.AlignCenter, self._label_text)
        painter.end()


class AlertWidget(QWidget):
    """High-visibility automotive alert banner with physical LED simulation."""

    emergency_triggered = pyqtSignal()
    reset_clicked = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._pulse_state = False
        self._is_critical = False
        self._setup_ui()

        # Pulse timer for critical alert flashing
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._on_pulse)
        self._pulse_timer.start(400)

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(16)

        self.setStyleSheet("""
            AlertWidget {
                background-color: #12151e;
                border: 1px solid #1e2536;
                border-radius: 8px;
            }
        """)

        # 1. Simulated LED Cluster
        led_container = QWidget()
        led_layout = QHBoxLayout(led_container)
        led_layout.setContentsMargins(0, 0, 0, 0)
        led_layout.setSpacing(8)

        self.led_green = LEDIndicator("green", "NORM")
        self.led_yellow = LEDIndicator("yellow", "ATTN")
        self.led_orange = LEDIndicator("orange", "WARN")
        self.led_red = LEDIndicator("red", "CRIT")

        self.led_green.set_state(True)

        led_layout.addWidget(self.led_green)
        led_layout.addWidget(self.led_yellow)
        led_layout.addWidget(self.led_orange)
        led_layout.addWidget(self.led_red)
        layout.addWidget(led_container)

        # 2. Main Alert Text Banner
        self.banner_frame = QFrame()
        self.banner_frame.setStyleSheet("""
            QFrame {
                background-color: #18202f;
                border: 2px solid #10b981;
                border-radius: 8px;
                padding: 6px 14px;
            }
        """)
        banner_layout = QVBoxLayout(self.banner_frame)
        banner_layout.setContentsMargins(8, 4, 8, 4)
        banner_layout.setSpacing(2)

        self.lbl_title = QLabel("SYSTEM READY - DRIVER ATTENTIVE")
        self.lbl_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #10b981; letter-spacing: 1px;")
        banner_layout.addWidget(self.lbl_title)

        self.lbl_description = QLabel("All biometric indicators within safe operating parameters")
        self.lbl_description.setStyleSheet("font-size: 11px; color: #94a3b8;")
        banner_layout.addWidget(self.lbl_description)

        layout.addWidget(self.banner_frame, stretch=1)

        # 3. Action Buttons
        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(8)

        self.btn_emergency = QPushButton("TRIGGER\nEMERGENCY")
        self.btn_emergency.setStyleSheet("""
            QPushButton {
                background-color: #991b1b;
                color: #ffffff;
                border: 2px solid #ef4444;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #dc2626;
                border-color: #f87171;
            }
        """)
        self.btn_emergency.clicked.connect(self.emergency_triggered.emit)
        btn_layout.addWidget(self.btn_emergency)

        self.btn_reset = QPushButton("RESET\nALERTS")
        self.btn_reset.setStyleSheet("""
            QPushButton {
                background-color: #1e2638;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #2b354d;
                border-color: #00d2ff;
            }
        """)
        self.btn_reset.clicked.connect(self.reset_clicked.emit)
        btn_layout.addWidget(self.btn_reset)

        layout.addWidget(btn_container)

    def update_alert(self, alert: SystemAlert) -> None:
        """Updates display banner and LEDs to match SystemAlert state."""
        self._is_critical = (alert.level == AlertLevel.CRITICAL)

        self.led_green.set_state(alert.led_green)
        self.led_yellow.set_state(alert.led_yellow)
        self.led_orange.set_state(alert.led_orange)
        self.led_red.set_state(alert.led_red)

        self.lbl_title.setText(alert.title)
        self.lbl_title.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {alert.color_code}; letter-spacing: 1px;")
        self.lbl_description.setText(alert.description)

        self.banner_frame.setStyleSheet(f"""
            QFrame {{
                background-color: #18202f;
                border: 2px solid {alert.color_code};
                border-radius: 8px;
                padding: 6px 14px;
            }}
        """)

    def _on_pulse(self) -> None:
        """Pulses critical alert border."""
        if self._is_critical:
            self._pulse_state = not self._pulse_state
            glow_color = "#ef4444" if self._pulse_state else "#7f1d1d"
            self.banner_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {'#2a1215' if self._pulse_state else '#18202f'};
                    border: 2px solid {glow_color};
                    border-radius: 8px;
                    padding: 6px 14px;
                }}
            """)
