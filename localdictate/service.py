from __future__ import annotations

import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock, Thread

import numpy as np

from .audio import MicrophoneRecorder
from .config import Settings


class RecordingController:
    """Serializes recording lifecycle; transcription never blocks the input hook."""

    def __init__(self, settings: Settings, transcriber, injector, logger: logging.Logger,
                 recorder_factory: Callable[..., MicrophoneRecorder] = MicrophoneRecorder,
                 on_recording_started: Callable[[], None] | None = None,
                 on_recording_stopped: Callable[[], None] | None = None,
                 on_live_preview: Callable[[str], None] | None = None,
                 on_status: Callable[[str, str], None] | None = None) -> None:
        self.settings, self.transcriber, self.injector, self.logger = settings, transcriber, injector, logger
        self._factory, self._recorder, self._lock = recorder_factory, None, Lock()
        self._on_started, self._on_stopped = on_recording_started, on_recording_stopped
        self._on_live_preview = on_live_preview
        self._on_status = on_status
        self._busy = False
        self.ready = True
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="transcription")
        self._transcription_lock = Lock()
        self._live_stop = Event()
        self._live_thread: Thread | None = None

    @property
    def recording(self) -> bool:
        return self._recorder is not None

    def _status(self, state: str, message: str = "") -> None:
        if self._on_status:
            self._on_status(state, message)

    def start(self) -> bool:
        with self._lock:
            if not self.ready:
                self._status("processing", "Preparing speech model…")
                return False
            if self._busy or self._recorder is not None:
                return self._recorder is not None
            try:
                self._recorder = self._factory(self.settings.sample_rate, self.settings.microphone, self.stop,
                                               self.settings.silence_threshold, self.settings.auto_stop_seconds,
                                               self.settings.auto_stop_on_silence,
                                               self.settings.microphone_name)
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
                return True
            except Exception:
                self._recorder = None
                self.logger.exception("Unable to start microphone recording")
                self._status("error", "Microphone unavailable. Check your selected mic and try again.")
                return False

    def stop(self) -> None:
        with self._lock:
            if self._recorder is None:
                return
            recorder, self._recorder = self._recorder, None
            self._busy = True
        self._live_stop.set()
        try:
            audio = recorder.stop()
        except Exception:
            with self._lock:
                self._busy = False
            self.logger.exception("Unable to stop microphone recording")
            self._status("error", "Microphone disconnected. Reconnect it and try again.")
            return
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        rms = float(np.sqrt(np.mean(audio * audio))) if audio.size else 0.0
        self.logger.info("Captured %.1fs; peak=%.5f, rms=%.5f", audio.size / self.settings.sample_rate,
                         peak, rms)
        audio = self._trim(audio)
        if audio.size:
            self._status("processing", "Transcribing…")
            self._executor.submit(self._transcribe_and_inject, audio)
        else:
            with self._lock:
                self._busy = False
            self.logger.warning("No audible audio captured")
            self._status("error", "No voice detected. Check your microphone or mute switch.")

    def cancel(self) -> None:
        """Discard the in-progress recording without transcribing or injecting it."""
        with self._lock:
            if self._recorder is None:
                return
            recorder, self._recorder = self._recorder, None
            self._busy = True
        self._live_stop.set()
        try:
            recorder.stop()
        except Exception:
            self.logger.exception("Unable to close cancelled microphone recording")
        finally:
            with self._lock:
                self._busy = False
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
                if self._on_stopped:
                    self._on_stopped()
            else:
                self._status("error", "No speech recognized. Try speaking closer to the microphone.")
        except Exception:
            self.logger.exception("Transcription or text injection failed")
            self._status("error", "Dictation failed. Check the log, then try again.")
        finally:
            with self._lock:
                self._busy = False

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
        self.cancel()
        self._executor.shutdown(wait=True, cancel_futures=True)
        close_injector = getattr(self.injector, "close", None)
        if close_injector:
            close_injector()
