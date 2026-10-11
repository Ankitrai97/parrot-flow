from __future__ import annotations

import time

import numpy as np
import sounddevice as sd

from .audio import MicrophoneRecorder
from .config import Settings


def list_input_devices() -> None:
    """Print selectable microphone IDs for the config file."""
    default_input = sd.default.device[0]
    print(f"Windows/default input device ID: {default_input}")
    print("\nAvailable input devices:")
    for index, device in enumerate(sd.query_devices()):
        if device["max_input_channels"] > 0:
            marker = " (default)" if index == default_input else ""
            print(f"  {index}: {device['name']} [{device['max_input_channels']} channel(s)]{marker}")


def test_microphone(settings: Settings, seconds: int = 5) -> None:
    """Capture a short sample and report level without saving voice audio to disk."""
    selected = settings.microphone_name or ("Windows default" if settings.microphone is None else str(settings.microphone))
    print(f"Testing microphone {selected}. Speak normally for {seconds} seconds...")
    recorder = MicrophoneRecorder(settings.sample_rate, settings.microphone,
                                  microphone_name=settings.microphone_name)
    recorder.start()
    try:
        time.sleep(seconds)
    finally:
        samples = recorder.stop()
    peak = float(np.max(np.abs(samples))) if samples.size else 0.0
    rms = float(np.sqrt(np.mean(samples * samples))) if samples.size else 0.0
    print(f"Captured {samples.size} samples. Peak: {peak:.5f}; RMS: {rms:.5f}")
    if peak < 0.002:
        print("No usable voice signal. Select another input device or check Windows microphone privacy/settings.")
    else:
        print("Microphone signal looks usable.")
