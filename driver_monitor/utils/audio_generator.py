"""
Audio Tone Generator for macOS Hardware Simulation.
Synthesizes professional automotive alert sounds using standard library 'wave' and 'math'.
Generates WAV files compatible with macOS afplay command.
"""

import math
import os
import struct
import wave
import logging

logger = logging.getLogger(__name__)


def generate_tone(
    filename: str,
    frequency_hz: float = 880.0,
    duration_sec: float = 0.25,
    sample_rate: int = 44100,
    volume: float = 0.8,
    fade_sec: float = 0.02
) -> str:
    """Generates a clean sine tone with attack/decay envelope to avoid clicks."""
    num_samples = int(sample_rate * duration_sec)
    fade_samples = int(sample_rate * fade_sec)
    
    os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
    
    with wave.open(filename, "w") as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        
        frames = bytearray()
        for i in range(num_samples):
            t = float(i) / sample_rate
            # Sine wave
            sample_val = math.sin(2.0 * math.pi * frequency_hz * t)
            
            # Envelope (attack / decay)
            envelope = 1.0
            if i < fade_samples:
                envelope = i / fade_samples
            elif i > num_samples - fade_samples:
                envelope = (num_samples - i) / fade_samples
                
            sample_val *= volume * envelope
            int_sample = int(sample_val * 32767.0)
            int_sample = max(-32768, min(32767, int_sample))
            frames.extend(struct.pack("<h", int_sample))
            
        wav_file.writeframes(frames)
    return filename


def generate_multi_pulse(
    filename: str,
    pulses: list[tuple[float, float, float]],  # (freq_hz, duration_sec, pause_sec)
    sample_rate: int = 44100,
    volume: float = 0.85
) -> str:
    """Generates a multi-pulse alert tone (e.g. double beep or warning burst)."""
    os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
    
    with wave.open(filename, "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        
        frames = bytearray()
        fade_samples = int(sample_rate * 0.015)
        
        for freq, dur, pause in pulses:
            num_pulse_samples = int(sample_rate * dur)
            for i in range(num_pulse_samples):
                t = float(i) / sample_rate
                sample_val = math.sin(2.0 * math.pi * freq * t)
                envelope = 1.0
                if i < fade_samples:
                    envelope = i / fade_samples
                elif i > num_pulse_samples - fade_samples:
                    envelope = (num_pulse_samples - i) / fade_samples
                sample_val *= volume * envelope
                int_sample = max(-32768, min(32767, int(sample_val * 32767.0)))
                frames.extend(struct.pack("<h", int_sample))
                
            # Pause between pulses
            num_pause_samples = int(sample_rate * pause)
            frames.extend(struct.pack("<h", 0) * num_pause_samples)
            
        wav_file.writeframes(frames)
    return filename


def ensure_alert_sounds(target_dir: str) -> dict[str, str]:
    """Generates and returns standard sound files for each alert level."""
    os.makedirs(target_dir, exist_ok=True)
    
    sounds = {
        "attention": os.path.join(target_dir, "attention_chime.wav"),
        "warning": os.path.join(target_dir, "warning_pulse.wav"),
        "critical": os.path.join(target_dir, "critical_alarm.wav"),
        "emergency": os.path.join(target_dir, "emergency_siren.wav"),
    }
    
    # 1. Attention: gentle two-tone chime (660Hz -> 880Hz)
    if not os.path.exists(sounds["attention"]):
        generate_multi_pulse(
            sounds["attention"],
            [(659.25, 0.12, 0.04), (880.0, 0.18, 0.0)]
        )
        
    # 2. Warning: dual urgency beep (1046Hz, two pulses)
    if not os.path.exists(sounds["warning"]):
        generate_multi_pulse(
            sounds["warning"],
            [(1046.5, 0.15, 0.08), (1046.5, 0.20, 0.0)]
        )
        
    # 3. Critical: rapid 3-pulse urgent beep (1318Hz)
    if not os.path.exists(sounds["critical"]):
        generate_multi_pulse(
            sounds["critical"],
            [(1318.5, 0.12, 0.05), (1318.5, 0.12, 0.05), (1567.98, 0.25, 0.0)]
        )
        
    # 4. Emergency: sharp high-low siren pulse
    if not os.path.exists(sounds["emergency"]):
        generate_multi_pulse(
            sounds["emergency"],
            [(1760.0, 0.15, 0.04), (1174.6, 0.18, 0.04), (1760.0, 0.22, 0.0)]
        )
        
    return sounds


if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sounds_dir = os.path.join(os.path.dirname(current_dir), "resources", "sounds")
    created = ensure_alert_sounds(sounds_dir)
    print("Created sound files:", created)
