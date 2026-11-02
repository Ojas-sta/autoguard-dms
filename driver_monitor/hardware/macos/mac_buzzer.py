"""
macOS Buzzer Simulation for Driver Monitoring System.
Plays synthesized automotive warning tones using native macOS '/usr/bin/afplay' command.
Operates asynchronously in background threads to avoid blocking video processing or UI rendering.
"""

import logging
import os
import subprocess
import threading
import time
from typing import Optional

from driver_monitor.hardware.interfaces import BuzzerInterface
from driver_monitor.utils.audio_generator import ensure_alert_sounds

logger = logging.getLogger(__name__)


class MacBuzzer(BuzzerInterface):
    """Buzzer simulator using native macOS afplay audio player."""

    def __init__(self, volume: float = 0.8):
        self._volume = volume
        self._enabled = True
        self._current_pattern = "OFF"
        self._is_active = False
        self._playback_process: Optional[subprocess.Popen] = None
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Locate sound files
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        sounds_dir = os.path.join(base_dir, "resources", "sounds")
        self._sound_paths = ensure_alert_sounds(sounds_dir)

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        if not enabled:
            self.stop_alert()

    def is_active(self) -> bool:
        return self._is_active

    def start_alert(self, pattern: str) -> None:
        """Triggers audio playback for given pattern."""
        if not self._enabled or pattern == "OFF":
            self.stop_alert()
            return

        with self._lock:
            if self._current_pattern == pattern and self._is_active:
                return  # Pattern already actively running

            self._stop_alert_locked()
            self._current_pattern = pattern
            self._is_active = True
            self._stop_event.clear()

            self._thread = threading.Thread(
                target=self._run_pattern_loop,
                args=(pattern,),
                daemon=True,
                name=f"MacBuzzer-{pattern}"
            )
            self._thread.start()

    def stop_alert(self) -> None:
        with self._lock:
            self._stop_alert_locked()

    def _stop_alert_locked(self) -> None:
        self._stop_event.set()
        self._is_active = False
        self._current_pattern = "OFF"

        if self._playback_process is not None:
            try:
                self._playback_process.terminate()
            except Exception:
                pass
            self._playback_process = None

    def _play_sound(self, sound_file: str) -> None:
        """Plays sound synchronously within background thread using afplay."""
        if not os.path.exists(sound_file):
            return

        try:
            # afplay -v <volume 0.0 - 1.0>
            cmd = ["/usr/bin/afplay", "-v", str(self._volume), sound_file]
            self._playback_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            self._playback_process.wait()
        except Exception as e:
            logger.debug("afplay execution note: %s", e)
        finally:
            self._playback_process = None

    def _run_pattern_loop(self, pattern: str) -> None:
        """Background thread executing the audio cadence."""
        sound_map = {
            "CHIME": self._sound_paths.get("attention"),
            "DOUBLE_PULSE": self._sound_paths.get("warning"),
            "RAPID_SIREN": self._sound_paths.get("critical"),
            "EMERGENCY": self._sound_paths.get("emergency"),
        }
        sound_file = sound_map.get(pattern)

        if not sound_file or not os.path.exists(sound_file):
            logger.warning("No sound file available for pattern %s", pattern)
            self._is_active = False
            return

        if pattern == "CHIME":
            # Play once then finish
            self._play_sound(sound_file)
            self._is_active = False

        elif pattern == "DOUBLE_PULSE":
            # Repeat with pause until cancelled
            while not self._stop_event.is_set():
                self._play_sound(sound_file)
                # Pause between pulses
                if self._stop_event.wait(timeout=1.2):
                    break

        elif pattern in ("RAPID_SIREN", "EMERGENCY"):
            # Continuous rapid urgent alarm
            while not self._stop_event.is_set():
                self._play_sound(sound_file)
                if self._stop_event.wait(timeout=0.2):
                    break

        self._is_active = False
