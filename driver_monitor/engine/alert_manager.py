"""
Alert Decision Manager for Driver Monitoring System.
Arbitrates multi-level alert states from drowsiness, abnormal kinematics, and emergency inputs.
Controls buzzer patterns, LED outputs, and alert acknowledgment.
"""

import logging
import time
from typing import Optional

from driver_monitor.core.result_models import (
    AlertLevel, DrowsinessResult, DrowsinessState, AbnormalMovementResult,
    AbnormalMovementState, SystemAlert
)

logger = logging.getLogger(__name__)


class AlertManager:
    """Consolidates system warnings and commands alert audio and visual actuators."""

    def __init__(self):
        self._last_alert = SystemAlert()
        self._sound_enabled = True
        self._last_buzzer_command_time = 0.0

    def set_sound_enabled(self, enabled: bool) -> None:
        self._sound_enabled = enabled
        logger.info("Alert sound enabled set to %s", enabled)

    @property
    def sound_enabled(self) -> bool:
        return self._sound_enabled

    def update(
        self,
        drowsiness: DrowsinessResult,
        abnormal: AbnormalMovementResult,
        is_emergency: bool = False,
        timestamp: Optional[float] = None
    ) -> SystemAlert:
        """Computes arbitrated alert level, display text, buzzer pattern, and LED states."""
        if timestamp is None:
            timestamp = time.time()

        alert = SystemAlert(timestamp=timestamp)

        # ---------------------------------------------------------
        # Priority 1: Manual Emergency
        # ---------------------------------------------------------
        if is_emergency:
            alert.level = AlertLevel.CRITICAL
            alert.title = "EMERGENCY ALERT TRIGGERED"
            alert.description = "Driver manual emergency assistance signal activated"
            alert.color_code = "#ef4444"  # Red
            alert.buzzer_active = self._sound_enabled
            alert.buzzer_pattern = "RAPID_SIREN"
            alert.led_green = False
            alert.led_yellow = False
            alert.led_orange = False
            alert.led_red = True
            alert.is_emergency = True
            self._last_alert = alert
            return alert

        # ---------------------------------------------------------
        # Priority 2: Critical Drowsiness or Critical Emergency Demo
        # ---------------------------------------------------------
        if (drowsiness.state == DrowsinessState.CRITICAL_DEMO_ALERT or
            abnormal.state == AbnormalMovementState.POSSIBLE_DRIVER_EMERGENCY_DEMO):
            alert.level = AlertLevel.CRITICAL
            if drowsiness.state == DrowsinessState.CRITICAL_DEMO_ALERT:
                alert.title = "CRITICAL DROWSINESS ALERT"
                alert.description = "; ".join(drowsiness.reasons) or "Immediate driver intervention required"
            else:
                alert.title = abnormal.alert_title
                alert.description = abnormal.details

            alert.color_code = "#ef4444"  # Red
            alert.buzzer_active = self._sound_enabled
            alert.buzzer_pattern = "RAPID_SIREN"
            alert.led_green = False
            alert.led_yellow = False
            alert.led_orange = False
            alert.led_red = True
            self._last_alert = alert
            return alert

        # ---------------------------------------------------------
        # Priority 3: Drowsiness Warning or Driver Attention Lost
        # ---------------------------------------------------------
        if (drowsiness.state == DrowsinessState.DROWSINESS_WARNING or
            abnormal.state == AbnormalMovementState.DRIVER_ATTENTION_LOST):
            alert.level = AlertLevel.WARNING
            if drowsiness.state == DrowsinessState.DROWSINESS_WARNING:
                alert.title = "DROWSINESS WARNING"
                alert.description = "; ".join(drowsiness.reasons) or "Driver fatigue detected"
            else:
                alert.title = abnormal.alert_title
                alert.description = abnormal.details

            alert.color_code = "#f97316"  # Orange
            alert.buzzer_active = self._sound_enabled
            alert.buzzer_pattern = "DOUBLE_PULSE"
            alert.led_green = False
            alert.led_yellow = False
            alert.led_orange = True
            alert.led_red = False
            self._last_alert = alert
            return alert

        # ---------------------------------------------------------
        # Priority 4: Attention or Abnormal Head Posture / Movement
        # ---------------------------------------------------------
        if (drowsiness.state == DrowsinessState.ATTENTION or
            abnormal.state in (AbnormalMovementState.ABNORMAL_HEAD_POSTURE, AbnormalMovementState.UNUSUAL_HEAD_MOVEMENT)):
            alert.level = AlertLevel.ATTENTION
            if drowsiness.state == DrowsinessState.ATTENTION:
                alert.title = "DRIVER ATTENTION WARNING"
                alert.description = "; ".join(drowsiness.reasons) or "Maintain attention on road"
            else:
                alert.title = abnormal.alert_title
                alert.description = abnormal.details

            alert.color_code = "#f59e0b"  # Yellow
            alert.buzzer_active = self._sound_enabled
            alert.buzzer_pattern = "CHIME"
            alert.led_green = False
            alert.led_yellow = True
            alert.led_orange = False
            alert.led_red = False
            self._last_alert = alert
            return alert

        # ---------------------------------------------------------
        # Priority 5: Normal
        # ---------------------------------------------------------
        alert.level = AlertLevel.NORMAL
        alert.title = "NORMAL"
        alert.description = "Driver attentive and alert"
        alert.color_code = "#10b981"  # Green
        alert.buzzer_active = False
        alert.buzzer_pattern = "OFF"
        alert.led_green = True
        alert.led_yellow = False
        alert.led_orange = False
        alert.led_red = False
        self._last_alert = alert
        return alert

    @property
    def current_alert(self) -> SystemAlert:
        return self._last_alert
