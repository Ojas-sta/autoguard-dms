"""
ESP32-S3 Peripheral Controller Interface for Driver Monitoring System.
Establishes bidirectional UART / Serial communication between Raspberry Pi / Mac and ESP32-S3.
Transmits alert states, commands LEDs/buzzers, receives physical button interrupts,
and maintains heartbeat health monitoring with graceful reconnection.

==============================================================================
Subsystem: ESP32-S3 Hardware Controller & Real-Time Serial Bridge
Architecture: Powered by cl0ud (https://github.com/Ojas-sta/cl0ud-brand-engineering)
Co-Engineered by: Ojas Singh <ojasctc@gmail.com>
==============================================================================
"""

from dataclasses import dataclass
import json
import logging
import threading
import time
from typing import Callable, Dict, List, Optional

from driver_monitor.config import ESP32Config
from driver_monitor.core.event_manager import global_event_bus
from driver_monitor.core.result_models import SystemAlert

logger = logging.getLogger(__name__)

# Safe optional import of pyserial
try:
    import serial
    import serial.tools.list_ports
    HAS_PYSERIAL = True
except ImportError:
    serial = None
    HAS_PYSERIAL = False


@dataclass
class ESP32Status:
    connected: bool = False
    port: str = "None"
    firmware_version: str = "Unknown"
    button_pressed: bool = False
    sensor_status: str = "UNKNOWN"
    last_heartbeat_time: float = 0.0


class ESP32Controller:
    """Manages serial protocol communication with the companion ESP32-S3 peripheral."""

    PROTOCOL_VERSION = 1

    def __init__(
        self,
        config: Optional[ESP32Config] = None,
        port: Optional[str] = None,
        baud_rate: Optional[int] = None
    ):
        if config is None:
            self._config = ESP32Config()
            if port is not None:
                self._config.port = port
            if baud_rate is not None:
                self._config.baud_rate = baud_rate
        else:
            self._config = config

        self._serial = None
        self._is_running = False
        self._thread: Optional[threading.Thread] = None
        self._status = ESP32Status()
        self._button_callbacks: List[Callable[[], None]] = []
        self._last_ack_cmd_id: Optional[int] = None
        self._last_heartbeat_time: float = 0.0
        self._lock = threading.Lock()

        # Cached last state to transmit
        self._current_alert_payload = {
            "version": self.PROTOCOL_VERSION,
            "command": "ALERT_UPDATE",
            "drowsiness": "NORMAL",
            "distraction": "NORMAL",
            "blindspot_left": False,
            "blindspot_right": False,
            "buzzer": False,
            "led_state": "GREEN"
        }

    @property
    def status(self) -> ESP32Status:
        return self._status

    @property
    def is_connected(self) -> bool:
        return self._status.connected

    def register_button_callback(self, callback: Callable[[], None]) -> None:
        """Registers listener invoked when physical button on ESP32 is pressed."""
        if callback not in self._button_callbacks:
            self._button_callbacks.append(callback)

    def start(self) -> bool:
        """Starts background communication thread."""
        if not self._config.enabled:
            logger.info("ESP32-S3 controller disabled in configuration.")
            return False

        self._is_running = True
        self._thread = threading.Thread(target=self._communication_loop, daemon=True, name="ESP32Controller")
        self._thread.start()
        return True

    def stop(self) -> None:
        """Stops communication and closes serial port."""
        self._is_running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._close_serial()

    def update_alert_state(self, alert: SystemAlert, drowsiness_state: str = "NORMAL", distraction_state: str = "NORMAL") -> None:
        """Updates alert payload transmitted to ESP32."""
        led_color = "GREEN"
        if alert.led_red:
            led_color = "RED"
        elif alert.led_orange:
            led_color = "ORANGE"
        elif alert.led_yellow:
            led_color = "YELLOW"

        with self._lock:
            self._current_alert_payload = {
                "version": self.PROTOCOL_VERSION,
                "command": "ALERT_UPDATE",
                "drowsiness": drowsiness_state,
                "distraction": distraction_state,
                "blindspot_left": False,
                "blindspot_right": False,
                "buzzer": alert.buzzer_active,
                "led_state": led_color,
                "buzzer_pattern": alert.buzzer_pattern
            }

    def _find_port(self) -> Optional[str]:
        """Auto-discovers ESP32-S3 serial port."""
        if not HAS_PYSERIAL:
            return None

        if self._config.port != "AUTO" and os.path.exists(self._config.port):
            return self._config.port

        ports = serial.tools.list_ports.comports()
        for p in ports:
            desc = p.description.lower()
            hwid = p.hwid.lower()
            # Check for common ESP32-S3 USB-JTAG/Serial identifiers (VID 303a)
            if "esp32" in desc or "303a:" in hwid or "usb serial" in desc or "wchusb" in desc or "cp210" in desc:
                return p.device

        # If any ttyUSB or cu.usbmodem port exists
        for p in ports:
            if "usbmodem" in p.device or "ttyusb" in p.device.lower():
                return p.device
        return None

    def _open_serial(self) -> bool:
        if not HAS_PYSERIAL:
            return False

        port = self._find_port()
        if not port:
            return False

        try:
            self._serial = serial.Serial(
                port=port,
                baudrate=self._config.baud_rate,
                timeout=self._config.timeout_sec
            )
            self._status.connected = True
            self._status.port = port
            logger.info("Connected to ESP32-S3 on %s @ %d baud", port, self._config.baud_rate)
            return True
        except Exception as e:
            logger.warning("Could not open serial port %s: %s", port, e)
            self._close_serial()
            return False

    def _close_serial(self) -> None:
        if self._serial:
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None
        self._status.connected = False

    def _communication_loop(self) -> None:
        """Main serial IO thread sending heartbeats/commands and parsing JSON lines."""
        last_tx_time = 0.0

        while self._is_running:
            # Reconnection logic
            if not self._status.connected:
                success = self._open_serial()
                if not success:
                    time.sleep(2.0)
                    continue

            now = time.time()

            # Transmit alert command or periodic heartbeat every 200ms
            if now - last_tx_time >= 0.20:
                with self._lock:
                    payload = dict(self._current_alert_payload)
                try:
                    line = json.dumps(payload) + "\n"
                    self._serial.write(line.encode("utf-8"))
                    last_tx_time = now
                except Exception as e:
                    logger.warning("Failed writing to ESP32: %s", e)
                    self._close_serial()
                    time.sleep(1.0)
                    continue

            # Read incoming lines
            try:
                if self._serial and self._serial.in_waiting > 0:
                    raw_line = self._serial.readline().decode("utf-8", errors="ignore").strip()
                    self._handle_incoming_line(raw_line, now)
            except Exception as e:
                logger.debug("Serial read exception: %s", e)

            # Check communication timeout
            if self._status.last_heartbeat_time > 0 and (now - self._status.last_heartbeat_time > 4.0):
                logger.warning("ESP32-S3 communication timed out (no heartbeat for > 4s)")
                self._status.connected = False
                self._close_serial()

            time.sleep(0.02)

    def _handle_incoming_line(self, raw_line: str, timestamp: Optional[float] = None) -> None:
        """Parses a raw JSON line received from serial."""
        if timestamp is None:
            timestamp = time.time()
        raw_line = raw_line.strip()
        if raw_line.startswith("{") and raw_line.endswith("}"):
            try:
                data = json.loads(raw_line)
                self._handle_incoming_message(data, timestamp)
            except Exception as e:
                logger.debug("Failed parsing JSON line: %s", e)

    def _handle_incoming_message(self, data: dict, timestamp: float) -> None:
        """Processes parsed JSON packet from ESP32."""
        self._status.last_heartbeat_time = timestamp
        self._last_heartbeat_time = timestamp
        self._status.firmware_version = data.get("firmware", self._status.firmware_version)
        self._status.sensor_status = data.get("sensor_status", "OK")

        if "cmd_id" in data:
            self._last_ack_cmd_id = data["cmd_id"]

        is_event_button = data.get("event") == "EMERGENCY_BUTTON_PRESSED"
        button_pressed = data.get("button_pressed", False) or is_event_button

        if button_pressed and (not self._status.button_pressed or is_event_button):
            logger.warning("ESP32-S3 physical button pressed!")
            for cb in self._button_callbacks:
                try:
                    cb()
                except Exception as e:
                    logger.error("Error in button callback: %s", e)

        self._status.button_pressed = button_pressed
