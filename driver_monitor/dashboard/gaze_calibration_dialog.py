"""
Guided Gaze Calibration Dialog for AutoGuard DMS.
Displays real-time step guidance, target instructions, and sample collection progress.
"""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton, QGroupBox
)

from driver_monitor.calibration.gaze_calibration import GazeCalibrationManager


class GazeCalibrationDialog(QDialog):
    """Interactive modal dialog guiding driver through multi-target gaze calibration."""

    def __init__(self, calib_mgr: GazeCalibrationManager, parent=None):
        super().__init__(parent)
        self.calib_mgr = calib_mgr
        self.setWindowTitle("AutoGuard DMS — Guided Road Gaze Calibration")
        self.setFixedSize(520, 360)
        self._setup_ui()

        # Update timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_progress)

    def _setup_ui(self) -> None:
        self.setStyleSheet("""
            QDialog {
                background-color: #0f131a;
                color: #e2e8f0;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }
            QLabel {
                color: #cbd5e1;
            }
            QProgressBar {
                background-color: #1a202c;
                border: 1px solid #2d3748;
                border-radius: 6px;
                text-align: center;
                color: #ffffff;
                font-size: 11px;
                font-weight: bold;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #00d2ff;
                border-radius: 5px;
            }
            QPushButton {
                background-color: #1e2638;
                color: #e2e8f0;
                border: 1px solid #2d3748;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2b354d;
                border-color: #00d2ff;
            }
            .PrimaryBtn {
                background-color: #0284c7;
                border-color: #38bdf8;
                color: #ffffff;
            }
            .PrimaryBtn:hover {
                background-color: #0369a1;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header
        lbl_title = QLabel("INDIVIDUAL ROAD GAZE CALIBRATION")
        lbl_title.setStyleSheet("font-size: 14px; font-weight: 900; color: #00d2ff; letter-spacing: 1px;")
        layout.addWidget(lbl_title)

        lbl_desc = QLabel(
            "Please follow the visual prompts and look steadily at the designated target "
            "as observations are recorded. This establishes personalized gaze classification boundaries."
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout.addWidget(lbl_desc)

        # Target card
        grp = QGroupBox()
        grp.setStyleSheet("""
            QGroupBox {
                background-color: #141923;
                border: 1px solid #232b3b;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        grp_layout = QVBoxLayout(grp)
        grp_layout.setSpacing(8)

        self.lbl_target_name = QLabel("TARGET: READY")
        self.lbl_target_name.setStyleSheet("font-size: 18px; font-weight: bold; color: #38bdf8;")
        self.lbl_target_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grp_layout.addWidget(self.lbl_target_name)

        self.lbl_instruction = QLabel("Click 'Start Calibration' to begin.")
        self.lbl_instruction.setStyleSheet("font-size: 13px; color: #f8fafc;")
        self.lbl_instruction.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grp_layout.addWidget(self.lbl_instruction)

        grp_layout.addSpacing(6)

        grp_layout.addWidget(QLabel("Target Step Progress:"))
        self.bar_step = QProgressBar()
        self.bar_step.setRange(0, 100)
        self.bar_step.setValue(0)
        grp_layout.addWidget(self.bar_step)

        grp_layout.addWidget(QLabel("Overall Calibration Progress:"))
        self.bar_total = QProgressBar()
        self.bar_total.setRange(0, 100)
        self.bar_total.setValue(0)
        grp_layout.addWidget(self.bar_total)

        layout.addWidget(grp)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_start = QPushButton("START CALIBRATION")
        self.btn_start.setProperty("class", "PrimaryBtn")
        self.btn_start.clicked.connect(self._start)
        btn_layout.addWidget(self.btn_start)

        self.btn_cancel = QPushButton("CANCEL")
        self.btn_cancel.clicked.connect(self._cancel)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_done = QPushButton("CLOSE")
        self.btn_done.setEnabled(False)
        self.btn_done.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_done)

        layout.addLayout(btn_layout)

    def _start(self) -> None:
        self.btn_start.setEnabled(False)
        self.calib_mgr.start_calibration()
        self._timer.start(100)

    def _cancel(self) -> None:
        self._timer.stop()
        self.calib_mgr.cancel_calibration()
        self.reject()

    def _update_progress(self) -> None:
        if self.calib_mgr.is_active:
            self.lbl_target_name.setText(f"TARGET: {self.calib_mgr.current_step_name}")
            self.lbl_instruction.setText(self.calib_mgr.current_step_instruction)
            self.bar_step.setValue(int(self.calib_mgr.step_progress * 100))
            self.bar_total.setValue(int(self.calib_mgr.total_progress * 100))
        else:
            self._timer.stop()
            self.lbl_target_name.setText("CALIBRATION COMPLETE!")
            self.lbl_target_name.setStyleSheet("font-size: 18px; font-weight: bold; color: #10b981;")
            self.lbl_instruction.setText("Personalized boundaries saved to profiles/gaze_calibration.json")
            self.bar_step.setValue(100)
            self.bar_total.setValue(100)
            self.btn_done.setEnabled(True)
            self.btn_cancel.setEnabled(False)

    def closeEvent(self, event):
        if self.calib_mgr.is_active:
            self.calib_mgr.cancel_calibration()
        super().closeEvent(event)
