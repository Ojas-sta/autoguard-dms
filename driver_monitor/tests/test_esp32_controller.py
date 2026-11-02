"""
Unit tests for ESP32Controller and UART protocol.
"""

import json
import unittest
from driver_monitor.hardware.esp32.esp32_controller import ESP32Controller


class TestESP32Controller(unittest.TestCase):
    def setUp(self):
        self.controller = ESP32Controller(port="AUTO", baud_rate=115200)

    def test_button_callback_trigger(self):
        callback_called = False

        def on_button():
            nonlocal callback_called
            callback_called = True

        self.controller.register_button_callback(on_button)

        # Simulate receiving inbound event JSON line from ESP32-S3
        event_json = json.dumps({"event": "EMERGENCY_BUTTON_PRESSED", "timestamp": 12345})
        self.controller._handle_incoming_line(event_json)

        self.assertTrue(callback_called)

    def test_ack_handling(self):
        ack_json = json.dumps({"status": "ACK", "cmd_id": 42})
        self.controller._handle_incoming_line(ack_json)
        self.assertEqual(self.controller._last_ack_cmd_id, 42)

    def test_heartbeat_response(self):
        pong_json = json.dumps({"status": "PONG", "uptime_ms": 5000})
        self.controller._handle_incoming_line(pong_json)
        self.assertGreater(self.controller._last_heartbeat_time, 0.0)


if __name__ == "__main__":
    unittest.main()
