"""
Unit Tests for Alert Arbitration and Hardware Actuation Mapping.
Validates multi-tier prioritization, LED outputs, buzzer cadence commands, and manual emergency overrides.
"""

import unittest
from driver_monitor.core.result_models import (
    AlertLevel, DrowsinessResult, DrowsinessState, AbnormalMovementResult,
    AbnormalMovementState
)
from driver_monitor.engine.alert_manager import AlertManager


class TestAlertManager(unittest.TestCase):
    def setUp(self):
        self.manager = AlertManager()

    def test_normal_alert(self):
        drow = DrowsinessResult(state=DrowsinessState.NORMAL)
        abn = AbnormalMovementResult(state=AbnormalMovementState.NORMAL)

        alert = self.manager.update(drow, abn, is_emergency=False)
        self.assertEqual(alert.level, AlertLevel.NORMAL)
        self.assertTrue(alert.led_green)
        self.assertFalse(alert.led_red)
        self.assertFalse(alert.buzzer_active)
        self.assertEqual(alert.buzzer_pattern, "OFF")

    def test_attention_alert(self):
        drow = DrowsinessResult(state=DrowsinessState.ATTENTION, reasons=["Eye closure 0.9s"])
        abn = AbnormalMovementResult(state=AbnormalMovementState.NORMAL)

        alert = self.manager.update(drow, abn, is_emergency=False)
        self.assertEqual(alert.level, AlertLevel.ATTENTION)
        self.assertTrue(alert.led_yellow)
        self.assertTrue(alert.buzzer_active)
        self.assertEqual(alert.buzzer_pattern, "CHIME")

    def test_warning_alert(self):
        drow = DrowsinessResult(state=DrowsinessState.DROWSINESS_WARNING, reasons=["Prolonged eye closure 1.8s"])
        abn = AbnormalMovementResult(state=AbnormalMovementState.NORMAL)

        alert = self.manager.update(drow, abn, is_emergency=False)
        self.assertEqual(alert.level, AlertLevel.WARNING)
        self.assertTrue(alert.led_orange)
        self.assertEqual(alert.buzzer_pattern, "DOUBLE_PULSE")

    def test_critical_drowsiness_alert(self):
        drow = DrowsinessResult(state=DrowsinessState.CRITICAL_DEMO_ALERT, reasons=["Severe eye closure 2.6s"])
        abn = AbnormalMovementResult(state=AbnormalMovementState.NORMAL)

        alert = self.manager.update(drow, abn, is_emergency=False)
        self.assertEqual(alert.level, AlertLevel.CRITICAL)
        self.assertTrue(alert.led_red)
        self.assertEqual(alert.buzzer_pattern, "RAPID_SIREN")

    def test_manual_emergency_override(self):
        """Scenario 12: Manual Emergency Trigger overrides all sub-alerts."""
        drow = DrowsinessResult(state=DrowsinessState.NORMAL)
        abn = AbnormalMovementResult(state=AbnormalMovementState.NORMAL)

        alert = self.manager.update(drow, abn, is_emergency=True)
        self.assertEqual(alert.level, AlertLevel.CRITICAL)
        self.assertTrue(alert.is_emergency)
        self.assertTrue(alert.led_red)
        self.assertEqual(alert.buzzer_pattern, "RAPID_SIREN")

    def test_reset_emergency_alert(self):
        """Scenario 13: Reset Emergency Alert."""
        drow = DrowsinessResult(state=DrowsinessState.NORMAL)
        abn = AbnormalMovementResult(state=AbnormalMovementState.NORMAL)

        # Triggered
        a1 = self.manager.update(drow, abn, is_emergency=True)
        self.assertTrue(a1.is_emergency)

        # Reset back to False
        a2 = self.manager.update(drow, abn, is_emergency=False)
        self.assertEqual(a2.level, AlertLevel.NORMAL)
        self.assertFalse(a2.is_emergency)
        self.assertTrue(a2.led_green)

    def test_sound_mute_toggle(self):
        """Test muting alert sounds."""
        drow = DrowsinessResult(state=DrowsinessState.CRITICAL_DEMO_ALERT)
        abn = AbnormalMovementResult()

        self.manager.set_sound_enabled(False)
        alert = self.manager.update(drow, abn, is_emergency=False)
        self.assertFalse(alert.buzzer_active)

        self.manager.set_sound_enabled(True)
        alert2 = self.manager.update(drow, abn, is_emergency=False)
        self.assertTrue(alert2.buzzer_active)


if __name__ == "__main__":
    unittest.main()
