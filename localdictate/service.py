from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
import logging
from threading import Event, Lock, Thread
import time

import numpy as np

from .audio import MicrophoneRecorder
from .config import Settings


class RecordingController:
    """Serializes recording lifecycle; transcription never blocks the input hook."""

    def __init__(self, settings: Settings, transcriber, injector, logger: logging.Logger,
                 recorder_factory: Callable[..., MicrophoneRecorder] = MicrophoneRecorder,
                 on_recording_started: Callable[[], None] | None = None,
                 on_recording_stopped: Callable[[], None] | None = None,
                 on_live_preview: Callable[[str], None] | None = None) -> None:
        self.settings, self.transcriber, self.injector, self.logger = settings, transcriber, injector, logger
        self._factory, self._recorder, self._lock = recorder_factory, None, Lock()
        self._on_started, self._on_stopped = on_recording_started, on_recording_stopped
        self._on_live_preview = on_live_preview
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="transcription")
        self._transcription_lock = Lock()
        self._live_stop = Event()
        self._live_thread: Thread | None = None

    @property
    def recording(self) -> bool:
        return self._recorder is not None

    def start(self) -> None:
        with self._lock:
            if self._recorder is not None:
                return
            self._recorder = self._factory(self.settings.sample_rate, self.settings.microphone, self.stop,
                                           self.settings.silence_threshold, self.settings.auto_stop_seconds,
                                           self.settings.auto_stop_on_silence)
            try:
                capture_focus = getattr(self.injector, "capture_focus", None)
                if capture_focus:
                    capture_focus()
                self._recorder.start()
                self.logger.info("Recording started")
                if self._on_started:
                    self._on_started()
                if self.settings.live_preview:
                    self._live_stop.clear()
                    self._live_thread = Thread(target=self._preview_loop, daemon=True, name="live-preview")
                    self._live_thread.start()
            except Exception:
                self._recorder = None
                self.logger.exception("Unable to start microphone recording")

    def stop(self) -> None:
        with self._lock:
            if self._recorder is None:
                return
            recorder, self._recorder = self._recorder, None
        self._live_stop.set()
        audio = recorder.stop()
        if self._on_stopped:
            self._on_stopped()
        audio = self._trim(audio)
        if audio.size:
            self._executor.submit(self._transcribe_and_inject, audio)
        else:
            self.logger.info("No audible audio captured")

    def cancel(self) -> None:
        """Discard the in-progress recording without transcribing or injecting it."""
        with self._lock:
            if self._recorder is None:
                return
            recorder, self._recorder = self._recorder, None
        self._live_stop.set()
        recorder.stop()
        if self._on_stopped:
            self._on_stopped()
        self.logger.info("Recording cancelled")

    def _trim(self, audio: np.ndarray) -> np.ndarray:
        indices = np.flatnonzero(np.abs(audio) >= self.settings.silence_threshold)
        if not indices.size:
            return np.empty(0, dtype=np.float32)
        padding = int(self.settings.trim_silence_seconds * self.settings.sample_rate)
        return audio[max(0, indices[0] - padding): min(audio.size, indices[-1] + padding + 1)]

    def _transcribe_and_inject(self, audio: np.ndarray) -> None:
        try:
            with self._transcription_lock:
                text = self.transcriber.transcribe(audio)
            if text:
                self.injector.inject(text)
                self.logger.info("Transcript injected")
        except Exception:
            self.logger.exception("Transcription or text injection failed")

    def _preview_loop(self) -> None:
        """Continuously transcribe a trailing audio window while recording stays active."""
        # Give the microphone enough speech before attempting the first partial.
        while not self._live_stop.wait(self.settings.live_preview_interval_seconds):
            recorder = self._recorder
            if recorder is None:
                return
            audio = recorder.snapshot(self.settings.live_preview_window_seconds)
            if audio.size < self.settings.sample_rate:
                continue
            try:
                with self._transcription_lock:
                    if self._live_stop.is_set():
                        return
                    text = self.transcriber.transcribe_preview(audio)
                if text and self._on_live_preview and not self._live_stop.is_set():
                    self._on_live_preview(text)
            except Exception:
                self.logger.exception("Live transcription preview failed")
            time.sleep(0.01)

    def close(self) -> None:
        self.stop()
        self._executor.shutdown(wait=False, cancel_futures=True)
        close_injector = getattr(self.injector, "close", None)
        if close_injector:
            close_injector()
