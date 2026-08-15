from __future__ import annotations

from collections.abc import Callable
from threading import Lock
import time

import numpy as np
import sounddevice as sd


class MicrophoneRecorder:
    """Collect mono float32 microphone samples with a lightweight silence callback."""

    def __init__(self, sample_rate: int, device: int | None, on_silence: Callable[[], None] | None = None,
                 silence_threshold: float = 0.008, auto_stop_seconds: float = 4.0,
                 auto_stop_on_silence: bool = False) -> None:
        self.sample_rate, self.device = sample_rate, device
        self.on_silence = on_silence
        self.silence_threshold, self.auto_stop_seconds = silence_threshold, auto_stop_seconds
        self.auto_stop_on_silence = auto_stop_on_silence
        self._chunks: list[np.ndarray] = []
        self._lock = Lock()
        self._stream: sd.InputStream | None = None
        self._started_at = 0.0
        self._last_voice_at = 0.0

    def start(self) -> None:
        if self._stream is not None:
            return
        with self._lock:
            self._chunks.clear()
        self._started_at = self._last_voice_at = time.monotonic()
        self._stream = sd.InputStream(
            samplerate=self.sample_rate, device=self.device, channels=1, dtype="float32", callback=self._capture
        )
        self._stream.start()

    def _capture(self, indata: np.ndarray, _frames: int, _time: object, status: sd.CallbackFlags) -> None:
        if status:
            # Callback context: do not raise. The service logger reports device problems on restart.
            return
        samples = indata[:, 0].copy()
        with self._lock:
            self._chunks.append(samples)
        now = time.monotonic()
        if float(np.sqrt(np.mean(samples * samples))) >= self.silence_threshold:
            self._last_voice_at = now
        elif (self.auto_stop_on_silence and now - self._started_at > 0.8
              and now - self._last_voice_at >= self.auto_stop_seconds and self.on_silence):
            self.on_silence()
            self.on_silence = None

    def stop(self) -> np.ndarray:
        stream, self._stream = self._stream, None
        if stream:
            stream.stop()
            stream.close()
        with self._lock:
            return np.concatenate(self._chunks) if self._chunks else np.empty(0, dtype=np.float32)

    def snapshot(self, seconds: float) -> np.ndarray:
        """Return a recent in-memory slice for live preview; never writes audio to disk."""
        frames = int(seconds * self.sample_rate)
        with self._lock:
            if not self._chunks:
                return np.empty(0, dtype=np.float32)
            return np.concatenate(self._chunks)[-frames:]
