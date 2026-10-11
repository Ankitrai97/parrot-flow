from __future__ import annotations

import logging
import time
from collections.abc import Callable
from threading import Lock, Thread

import av
import numpy as np
import sounddevice as sd


def resolve_microphone(device: int | None, name: str | None = None) -> int | None:
    """Resolve a saved name on every recording, even after device IDs change."""
    if not name:
        return device
    devices = sd.query_devices()
    candidates = [(i, item) for i, item in enumerate(devices)
                  if item["max_input_channels"] > 0 and name.casefold() in item["name"].casefold()]
    if not candidates:
        raise RuntimeError(f"Microphone '{name}' is unavailable. Reconnect it or select another mic.")
    apis = sd.query_hostapis()
    candidates.sort(key=lambda item: "WASAPI" not in apis[item[1]["hostapi"]]["name"])
    return candidates[0][0]


class MicrophoneRecorder:
    """Collect mono float32 microphone samples with a lightweight silence callback."""

    def __init__(self, sample_rate: int, device: int | None, on_silence: Callable[[], None] | None = None,
                 silence_threshold: float = 0.008, auto_stop_seconds: float = 4.0,
                 auto_stop_on_silence: bool = False, microphone_name: str | None = None) -> None:
        self.sample_rate, self.device = sample_rate, device
        self.on_silence = on_silence
        self.silence_threshold, self.auto_stop_seconds = silence_threshold, auto_stop_seconds
        self.auto_stop_on_silence = auto_stop_on_silence
        self.microphone_name = microphone_name
        self._capture_rate = sample_rate
        self._logger = logging.getLogger("localdictate")
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
        selected = resolve_microphone(self.device, self.microphone_name)
        info = sd.query_devices(selected, "input")
        self._capture_rate = self.sample_rate
        try:
            sd.check_input_settings(device=selected, channels=1, dtype="float32",
                                    samplerate=self.sample_rate)
        except sd.PortAudioError:
            self._capture_rate = int(info["default_samplerate"])
        self._logger.info("Microphone selected: %s (id=%s, capture=%sHz)", info["name"],
                          selected, self._capture_rate)
        self._stream = sd.InputStream(samplerate=self._capture_rate, device=selected, channels=1,
                                      dtype="float32", callback=self._capture)
        try:
            self._stream.start()
        except Exception:
            self._stream.close()
            self._stream = None
            raise

    def _capture(self, indata: np.ndarray, _frames: int, _time: object, status: sd.CallbackFlags) -> None:
        if status:
            self._logger.warning("Microphone stream status: %s", status)
        samples = indata[:, 0].copy()
        with self._lock:
            self._chunks.append(samples)
        now = time.monotonic()
        if float(np.sqrt(np.mean(samples * samples))) >= self.silence_threshold:
            self._last_voice_at = now
        elif (self.auto_stop_on_silence and now - self._started_at > 0.8
              and now - self._last_voice_at >= self.auto_stop_seconds and self.on_silence):
            callback = self.on_silence
            self.on_silence = None
            # PortAudio callbacks cannot stop/close their own stream.
            Thread(target=callback, name="silence-stop", daemon=True).start()

    def stop(self) -> np.ndarray:
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
            finally:
                stream.close()
        with self._lock:
            audio = np.concatenate(self._chunks) if self._chunks else np.empty(0, dtype=np.float32)
            self._chunks.clear()
        return self._resample(audio)

    def snapshot(self, seconds: float) -> np.ndarray:
        """Return a recent in-memory slice for live preview; never writes audio to disk."""
        frames = int(seconds * self._capture_rate)
        with self._lock:
            if not self._chunks:
                return np.empty(0, dtype=np.float32)
            # Avoid copying the entire recording for each trailing preview.
            chunks, count = [], 0
            for chunk in reversed(self._chunks):
                chunks.append(chunk)
                count += chunk.size
                if count >= frames:
                    break
            audio = np.concatenate(chunks[::-1])[-frames:]
        return self._resample(audio)

    def _resample(self, audio: np.ndarray) -> np.ndarray:
        if not audio.size or self._capture_rate == self.sample_rate:
            return audio
        frame = av.AudioFrame.from_ndarray(audio.reshape(1, -1), format="flt", layout="mono")
        frame.sample_rate = self._capture_rate
        resampler = av.AudioResampler(format="flt", layout="mono", rate=self.sample_rate)
        frames = resampler.resample(frame) + resampler.resample(None)
        return np.concatenate([item.to_ndarray().ravel() for item in frames]).astype(np.float32)
