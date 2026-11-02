"""
Event Manager for Driver Monitoring System.
Thread-safe publisher-subscriber message broker for internal system decoupling.
"""

from collections import defaultdict
import logging
from threading import Lock
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)


class EventManager:
    """Thread-safe event dispatcher for DMS."""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[Any], None]]] = defaultdict(list)
        self._lock = Lock()

    def subscribe(self, event_type: str, callback: Callable[[Any], None]) -> None:
        """Registers a callback for a specific event type."""
        with self._lock:
            if callback not in self._subscribers[event_type]:
                self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable[[Any], None]) -> None:
        """Removes a registered callback."""
        with self._lock:
            if callback in self._subscribers[event_type]:
                self._subscribers[event_type].remove(callback)

    def publish(self, event_type: str, data: Any = None) -> None:
        """Dispatches an event to all registered subscribers."""
        with self._lock:
            callbacks = list(self._subscribers[event_type])

        for cb in callbacks:
            try:
                cb(data)
            except Exception as e:
                logger.error("Error in event callback for '%s': %s", event_type, e, exc_info=True)


# Global singleton instance
global_event_bus = EventManager()
