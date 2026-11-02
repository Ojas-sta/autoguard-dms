"""
Event Logging Module for Driver Monitoring System.
Records timestamped state transitions, alerts, emergency events, and system metrics
both to structured disk log files and real-time in-memory event ring buffer for UI display.
"""

from collections import deque
from datetime import datetime
import json
import logging
import os
import threading
from typing import Any, Deque, Dict, List, Optional

from driver_monitor.core.event_manager import global_event_bus
from driver_monitor.core.result_models import SystemAlert, FrameAnalysisResult

logger = logging.getLogger(__name__)


class EventLogger:
    """Thread-safe event recorder and in-memory event buffer."""

    def __init__(self, log_dir: Optional[str] = None, max_history: int = 200):
        if log_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            log_dir = os.path.join(base_dir, "logs")

        os.makedirs(log_dir, exist_ok=True)
        self._log_file = os.path.join(log_dir, "dms_events.log")
        self._recent_events: Deque[Dict[str, Any]] = deque(maxlen=max_history)
        self._lock = threading.Lock()
        self._last_alert_level: Optional[str] = None

        # Subscribe to global events
        global_event_bus.subscribe("alert_changed", self._on_alert_changed)

    def log_event(self, event_type: str, message: str, level: str = "INFO", details: Optional[Dict[str, Any]] = None) -> None:
        """Records an event with timestamp and writes to disk log."""
        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        entry = {
            "timestamp": timestamp_str,
            "type": event_type,
            "level": level,
            "message": message,
            "details": details or {}
        }

        with self._lock:
            self._recent_events.append(entry)
            try:
                with open(self._log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry) + "\n")
            except Exception as e:
                logger.error("Failed writing event log: %s", e)

        global_event_bus.publish("new_log_entry", entry)

    def _on_alert_changed(self, alert_data: Any) -> None:
        """Listener triggered when system alert level changes."""
        if isinstance(alert_data, dict):
            level = alert_data.get("level", "UNKNOWN")
            title = alert_data.get("title", "")
            desc = alert_data.get("description", "")
        elif isinstance(alert_data, SystemAlert):
            level = alert_data.level.value
            title = alert_data.title
            desc = alert_data.description
        else:
            return

        if level != self._last_alert_level:
            self._last_alert_level = level
            self.log_event(
                event_type="ALERT_STATE_CHANGE",
                message=f"Alert transitioned to {level}: {title} ({desc})",
                level=level
            )

    def get_recent_events(self, count: int = 50) -> List[Dict[str, Any]]:
        """Returns the most recent events."""
        with self._lock:
            items = list(self._recent_events)
            return items[-count:]
